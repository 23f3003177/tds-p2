import sys
import subprocess
import os
import re
import uuid
import pickle
import shutil
from typing import List, Optional, Tuple, Any
from google import genai
from google.genai import types
from prompts import optimized_prompt
from schemas import GeneratedCode

client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))

class UVCodeInterpreter:
    """
    A robust code interpreter for Vercel using 'uv'.
    - Supports 'with' statement and optional full cleanup on exit.
    """
    def __init__(self, timeout: int = 300, cleanup_venv_on_exit: bool = False):
        self.timeout = timeout
        self.cleanup_venv_on_exit = cleanup_venv_on_exit
        self.venv_path = "/tmp/uv_env"
        self.python_executable = os.path.join(self.venv_path, 'bin', 'python')
        self.stdlib_names = sys.stdlib_module_names
        self._initialize_venv()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Cleans up the virtual environment if the option was enabled.
        """
        if self.cleanup_venv_on_exit and os.path.exists(self.venv_path):
            try:
                shutil.rmtree(self.venv_path)
            except Exception as e:
                # In a serverless function, we might want to log this error,
                # but we don't want to crash the whole execution for a cleanup failure.
                print(f"Warning: Failed to cleanup venv at {self.venv_path}. Error: {e}", file=sys.stderr)

    def _initialize_venv(self):
        if not os.path.exists(self.python_executable):
            try:
                subprocess.run(['uv', 'venv', self.venv_path], check=True, capture_output=True, text=True)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                raise RuntimeError(f"Failed to create uv environment. Is 'uv' in requirements.txt? Error: {e}")

    def run(self, code: str, packages: Optional[List[str]] = None) -> Tuple[str, str, Any]:
        packages = packages or []
        installable_packages = [pkg for pkg in packages if re.split(r'[=<>]+', pkg)[0] not in self.stdlib_names]
        
        if installable_packages:
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = self.venv_path
            try:
                command = ['uv', 'pip', 'install', '--quiet'] + installable_packages
                subprocess.run(command, check=True, capture_output=True, text=True, env=env)
            except subprocess.CalledProcessError as e:
                return ("", f"--- UV INSTALLATION ERROR ---\n{e.stderr}", None)
        
        result_path = f"/tmp/{uuid.uuid4()}.pkl"
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
            exec_env['MPLBACKEND'] = 'Agg'
            exec_env['TQDM_DISABLE'] = '1'
            exec_env['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
            
            proc = subprocess.run(
                [self.python_executable, "-c", full_code],
                check=True, capture_output=True, text=True, timeout=self.timeout, env=exec_env
            )
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.CalledProcessError as e:
            stdout = e.stdout
            stderr = f"--- EXECUTION ERROR ---\n{e.stderr}"
        except subprocess.TimeoutExpired:
            stderr = f"--- EXECUTION ERROR ---\nCode execution timed out after {self.timeout} seconds."
        finally:
            # The result file is always cleaned up immediately, which is the safest pattern.
            if os.path.exists(result_path):
                try:
                    with open(result_path, 'rb') as f:
                        result = pickle.load(f)
                except Exception as load_error:
                    result = {"error": "Failed to deserialize result variable", "details": str(load_error)}
                finally:
                    os.remove(result_path)
        
        return (stdout, stderr, result)

class LLMClient:
    def __init__(self) -> None:
        self.chat = client.chats.create(model="gemini-2.5-flash",
                            config=types.GenerateContentConfig(
                                thinking_config=types.ThinkingConfig(thinking_budget=0),
                system_instruction=optimized_prompt,
                response_mime_type="application/json",
                response_schema=GeneratedCode,
                temperature=0)
        )

    def generate_code(self, prompt: str) -> GeneratedCode:
        response = self.chat.send_message(prompt)
        parsed_response = GeneratedCode.model_validate(response.parsed)
        return parsed_response