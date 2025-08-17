import logging
import os
import pickle
import re
import subprocess
import sys
import uuid
from tempfile import TemporaryDirectory
from typing import Any, List, Literal, Optional, Tuple

from google import genai
from google.genai import types
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from prompts import optimized_prompt
from schemas import GeneratedCode

log = logging.getLogger(__name__)


class UVCodeInterpreter:
    def __init__(self, temp_dir: str, timeout: int = 300):
        self.timeout = timeout
        self.temp_dir = temp_dir
        self.venv_path = os.path.join(self.temp_dir, ".venv")
        self.python_executable = os.path.join(self.venv_path, "bin", "python")
        self.stdlib_names = sys.stdlib_module_names
        self._initialize_venv()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Cleanup is now handled by the TemporaryDirectory context manager in main.py
        # This method is here to support the 'with' statement syntax.
        pass

    def _initialize_venv(self):
        if not os.path.exists(self.python_executable):
            try:
                # Using cwd ensures uv commands are run from a predictable location
                subprocess.run(
                    ["uv", "venv", self.venv_path],
                    check=True,
                    capture_output=True,
                    text=True,
                    cwd=self.temp_dir,
                )
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                log.error(
                    f"Failed to create uv environment. Is 'uv' installed? Error: {e}"
                )
                raise RuntimeError(
                    f"Failed to create uv environment. Is 'uv' in requirements.txt? Error: {e}"
                )

    def run(
        self, code: str, packages: Optional[List[str]] = None
    ) -> Tuple[str, str, Any]:
        packages = packages or []
        installable_packages = [
            pkg
            for pkg in packages
            if re.split(r"[=<>]+", pkg)[0] not in self.stdlib_names
        ]

        if installable_packages:
            env = os.environ.copy()
            env["VIRTUAL_ENV"] = self.venv_path
            try:
                command = ["uv", "pip", "install", "--quiet"] + installable_packages
                subprocess.run(
                    command, check=True, capture_output=True, text=True, env=env
                )
            except subprocess.CalledProcessError as e:
                return ("", f"--- UV INSTALLATION ERROR ---\n{e.stderr}", None)

        result_path = os.path.join(self.temp_dir, f"{uuid.uuid4()}.pkl")
        injection_code = f"""
import pickle
if 'result' in locals():
    with open('{result_path}', 'wb') as f:
        pickle.dump(result, f)
"""
        full_code = code + "\n" + injection_code

        stdout, stderr, result = "", "", None

        try:
            exec_env = os.environ.copy()
            exec_env["MPLBACKEND"] = "Agg"
            exec_env["TQDM_DISABLE"] = "1"
            exec_env["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"

            proc = subprocess.run(
                [self.python_executable, "-c", full_code],
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=exec_env,
                cwd=self.temp_dir,  # CRITICAL: This makes the code run in the correct directory
            )
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.CalledProcessError as e:
            stdout = e.stdout
            stderr = f"--- EXECUTION ERROR ---\n{e.stderr}"
        except subprocess.TimeoutExpired:
            stderr = f"--- EXECUTION ERROR ---\nCode execution timed out after {self.timeout} seconds."
        finally:
            if os.path.exists(result_path):
                try:
                    with open(result_path, "rb") as f:
                        result = pickle.load(f)
                except Exception as load_error:
                    result = {
                        "error": "Failed to deserialize result variable",
                        "details": str(load_error),
                    }
        return (stdout, stderr, result)


class LLMClient:
    def __init__(
        self,
        api_key: str,
        digital_ocean_model_access_key: str,
        digital_ocean_model_access_base_url: str,
        provider: Literal["gemini", "openai"] = "gemini",
    ) -> None:
        print(f"Using {provider} as provider")
        self.chat_history = [{"role": "system", "content": optimized_prompt}]
        self.provider = provider
        if provider == "openai":
            self.client = OpenAI(
                base_url=digital_ocean_model_access_base_url,
                api_key=digital_ocean_model_access_key,
            )
        else:
            self.client = genai.Client(api_key=api_key)
            self.chat = self.client.chats.create(
                model="gemini-2.5-flash",
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=4096,
                    system_instruction=optimized_prompt,
                    response_mime_type="application/json",
                    response_schema=GeneratedCode,
                    temperature=0,
                ),
            )

    def generate_code(self, prompt: str) -> GeneratedCode:
        if self.provider == "openai":
            client: OpenAI = self.client  # type: ignore
            self.chat_history.append({"content": prompt, "role": "user"})
            response = client.chat.completions.parse(
                model="openai-gpt-5",
                messages=self.chat_history,  # type: ignore
                max_tokens=4096,
                response_format=GeneratedCode,
                reasoning_effort="low",
            )
            message = response.choices[0].message
            parsed_response = GeneratedCode.model_validate(message.parsed)
            self.chat_history.append(
                {"role": "assistant", "content": str(message.content)}
            )
            return parsed_response
        else:
            response = self.chat.send_message(prompt)
            print(response.text)
            parsed_response = GeneratedCode.model_validate(response.parsed)
            return parsed_response
