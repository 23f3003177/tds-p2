from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from pydantic import BaseModel
from services import LLMClient, UVCodeInterpreter
# from e2b_code_interpreter import Sandbox
import shutil


app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/api/v1/query")
async def main(file: list[UploadFile]):
    res = {}
    temp_store_path = 'temp_store/'
    question_file_name = 'questions.txt'
    os.makedirs(temp_store_path, exist_ok=True)
    llm_client = LLMClient()
    for f in file:
        with open(temp_store_path + f.filename, 'wb') as w:
            w.write(await f.read())
    with open(temp_store_path + question_file_name, 'r') as r:
        questions = r.read()
        # print(questions)
        response = llm_client.generate_code(questions)
        if response is not None:
            with UVCodeInterpreter(timeout=600) as sbx:
                stdout, stderr, result = sbx.run(response.code, response.libraries)
                # print(stdout, stderr, result)
                i = 1
                while stderr or not response.is_final_answer:
                    # print(f'{i}: Iterating through the error')
                    response = llm_client.generate_code(stderr if stderr else stdout)
                    # print(response)
                    stdout, stderr, result = sbx.run(response.code)
                    print(stdout, stderr, result)
                    if i >= 5:
                        break
                    i += 1
                res = result

    shutil.rmtree(temp_store_path)
    return JSONResponse(res)
