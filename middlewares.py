import asyncio
import time

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds=10):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds

    async def dispatch(self, request: Request, call_next):
        try:
            start_time = time.time()

            response_task = asyncio.create_task(call_next(request))  # type:ignore

            response = await asyncio.wait_for(
                response_task, timeout=self.timeout_seconds
            )

            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except asyncio.TimeoutError:
            return JSONResponse(
                status_code=200,
                content={
                    "detail": f"Request timed out after {self.timeout_seconds} seconds"
                },
            )
