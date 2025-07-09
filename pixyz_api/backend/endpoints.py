#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from . import *
from pixyz_api.patterns import uuid_path_pattern
from pixyz_api.auth import verify_token
from fastapi.security.api_key import APIKey
from fastapi import UploadFile, File, Form, Depends
from fastapi.responses import FileResponse

from pixyz_worker.exception import SharePathInvalidError, SharePathNotFoundError, TaskNotCompletedError, TaskProcessingStarted

logger = get_api_logger('backend')
router = APIRouter()


# Gets celery task detailled info
@router.get("/get_task_meta/{job_uuid}", **get_api_response_desc_from_model(TaskMeta))
async def get_task_meta(job_uuid: uuid_path_pattern, api_key: APIKey = Depends(verify_token)):

    """
    Get the details of a job
    :param job_uuid: the job ID
    :return: the job details
    """
    #
    try:
        task = AsyncResult(job_uuid, app=pixyz_worker.tasks.app)
        task_meta = task.backend.get_task_meta(job_uuid)
        return TaskMeta(**task_meta)
    except Exception as e:
        raise_api_error(ApiError500, e)

