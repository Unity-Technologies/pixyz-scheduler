#!/usr/bin/env python3
import json
from celery.result import AsyncResult
from celery.exceptions import TaskRevokedError
from billiard.exceptions import WorkerLostError
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import Response, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

import pixyz_worker.share
from pixyz_worker.tasks import app
from . import *
from pixyz_api.admin.endpoints import router as admin_router
from pixyz_api.jobs.endpoints import router as jobs_router
from pixyz_api.processes.endpoints import router as processes_router
from pixyz_api.backend.endpoints import router as backend_router

__all__ = ['api_app']

logger = get_api_logger('api.routes')
api_app = FastAPI(**config.fastapi)

api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@api_app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):    
    raise_api_error(ApiError400, str(exc))
    return PlainTextResponse(str(exc), status_code=400)

## Admin endpoints
# api_app.include_router(admin_router, prefix="/admin", tags=["admin"])

@api_app.get("/")
async def root():
    return Response(status_code=status.HTTP_200_OK, content=f"Welcome to PiXYZ API v{version}!",
                    media_type="text/plain")

# WIP new endpoints
api_app.include_router(processes_router, prefix="/processes", tags=["processes"])
api_app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_app.include_router(backend_router, prefix="/backend", tags=["backend"])

@api_app.post("/dev/callback", status_code=status.HTTP_200_OK, tags=["dev"])
async def callback_info(infos: dict):
    """
    A helper endpoint to test callbacks (development only)

    Parameters:
    - `infos` (dict): Any items to be printed in the console

    Returns:
    - always 200

    """
    logger.info("CALLBACK TEST POST REQUEST:" + str(infos))
    print("CALLBACK POST:" + json.dumps(infos, indent=2))

Instrumentator().instrument(api_app).expose(api_app, include_in_schema=True, should_gzip=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:api", host="0.0.0.0", port=8002, log_level="info", reload=True, workers=1)