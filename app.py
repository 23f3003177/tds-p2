# main.py
import asyncio
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from tempfile import TemporaryDirectory
from typing import Annotated, Any, Dict, List

import aiofiles
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.datastructures import UploadFile, FormData

from config import settings
from logging_config import setup_logging
from services import LLMClient, UVCodeInterpreter

setup_logging()
log = logging.getLogger(__name__)

app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Application startup: Initializing LLMClient...")
    app_state["llm_client"] = LLMClient(settings.gemini_api_key)
    yield
    log.info("Application shutdown: Cleaning up resources.")
    app_state.clear()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def get_llm_client() -> LLMClient:
    return app_state["llm_client"]


async def save_files_to_temp_dir(form_data: FormData, temp_dir: str):
    """
    Saves all uploaded files from a form to a temporary directory.
    Uses the form field's key as the filename.
    """
    async def save_file(key: str, file: UploadFile):
        # Use the key from the form field as the filename
        file_path = os.path.join(temp_dir, key)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(await file.read())

    # Create a list of tasks to run concurrently
    tasks = []
    for key, value in form_data.items():
        if isinstance(value, UploadFile):
            tasks.append(save_file(key, value))
    
    await asyncio.gather(*tasks)


def read_question_from_file(temp_dir: str, filename: str = "questions.txt") -> str:
    question_path = os.path.join(temp_dir, filename)
    if not os.path.exists(question_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Required file '{filename}' not found in upload.",
        )
    with open(question_path, "r") as f:
        return f.read()


@app.post("/api/v1/query")
async def process_query(
    req: Request, llm_client: Annotated[LLMClient, Depends(get_llm_client)]
) -> Any:
    if not req.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported media type. Please use multipart/form-data.",
        )

    form = await req.form()

    uploaded_files = [v for v in form.values() if isinstance(v, UploadFile)]

    if not uploaded_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files were uploaded."
        )

    with TemporaryDirectory() as temp_dir:
        try:
            await save_files_to_temp_dir(form, temp_dir)
            question = read_question_from_file(
                temp_dir
            )

            log.info(f"Processing query from questions.txt")

            response = llm_client.generate_code(question)
            if not response or not response.code:
                raise HTTPException(
                    status_code=503, detail="LLM failed to generate initial code."
                )

            with UVCodeInterpreter(
                temp_dir=temp_dir, timeout=settings.code_exec_timeout
            ) as sbx:
                for i in range(settings.max_error_iterations):
                    log.info(f"Code execution attempt #{i + 1}")
                    stdout, stderr, result = sbx.run(response.code, response.libraries)

                    if not stderr and response.is_final_answer:
                        log.info("Code execution successful with final answer.")
                        return json.loads(result)

                    log.warning(
                        f"Iteration #{i + 1} failed or requires refinement. Error: {stderr[:500]}"
                    )
                    feedback = stderr if stderr else stdout
                    response = llm_client.generate_code(feedback)

                    if not response or not response.code:
                        raise HTTPException(
                            status_code=503, detail="LLM failed to refine code."
                        )

            log.error("Failed to get a valid result after max iterations.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not produce a valid result after maximum error iterations.",
            )

        except json.JSONDecodeError:
            log.error("Failed to decode the final result from the code interpreter.")
            raise HTTPException(
                status_code=500, detail="Final result was not valid JSON."
            )
        except HTTPException as e:
            raise e
        except Exception as e:
            log.exception(f"An unexpected error occurred: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An internal server error occurred.",
            )
