#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import types
from pydantic import BaseModel, HttpUrl, field_validator, validator
from fastapi import File, UploadFile, Form
from typing import Any, Dict, List, Literal

from pixyz_api.patterns import uuid_path_pattern

########################################################################################
#                                 API MODELS
#   
#   API models for FastAPI. 
#   - Define the models used in the API.
#   - Define the error responses.
#   - Use model.__doc__ to provide a description.
#   
########################################################################################

# class ValidatedFile(BaseModel):
#     value: str
#
#     @field_validator('value')
#     def check_no_double_dots(cls, value):
#         if '..' in value:
#             raise ValueError("String cannot contain '..'")
#         return value


class UrlInfos(BaseModel):
    source_url: HttpUrl
    callback_url: HttpUrl


class UrlWithFileInfos(BaseModel):
    source_urls: dict[str, HttpUrl]
    callback_url: HttpUrl


class AzureStorage3DModelInfo(BaseModel):
    storage_account_name: str
    container_name: str
    blob_name: str
    storage_account_key: str
    upload_to_bucket: bool = False


class UploadStorage3DModelInfo(BaseModel):
    file: UploadFile


class JobInfo(BaseModel):
    """
    Return the job ID when a job is submitted
    """
    id: str

class JobStatus(BaseModel):
    """
    A job status is composed of a status and a result.
    The status can be one of the following:
    SUCCESS: the job is done and the result is available
    RUNNING: the job is running (but information are available)
    FAILURE: the job failed
    PENDING: the job does not exist
    RECEIVED: the job is received by a worker
    STARTED: the job is started by a worker
    RETRY: the job is retrying
    REVOKED: the job is revoked (by the task itself), in case of error for example (segfault or memory error)
    UNKNOWN: the job is in an unknown state

    The result is a dictionary depends on the job type.
    RUNNING: the result is a dictionary with the following keys:
        - "progress": a number between 0 and 100
        - "info": a string with the current status

    """
    status: str
    result: dict

    def __init__(self, status_: Literal['SUCCESS', 'FAILURE', 'PENDING', 'RECEIVED', 'STARTED', 'RETRY', 'REVOKED',
                 'UNKNOWN'], result=None):
        super(JobStatus, self).__init__(status=status_, result=result)

########################################################################################
    
## Error Models ##

# Default error message
class ApiError(BaseModel):
    """
    Return an error message
    """
    code: int = 0
    message: str = "API Error"
    details: str | None = None

class ApiError400(ApiError):
    """
    Request parameters are invalid
    """
    code: int = 400
    message: str = "Bad Request"

class ApiError401(ApiError):
    """
    Authentication is required
    """
    code: int = 401
    message: str = "Unauthorized"

class ApiError403(ApiError):
    """
    Access to resource is forbidden
    """
    code: int = 403
    message: str = "Forbidden"

class ApiError404(ApiError):
    """
    The requested resource was not found
    """
    code: int = 404
    message: str = "Not Found"

class ApiError425(ApiError):
    """
    Process is ongoing and not completed
    """
    code: int = 425
    message: str = "Too early"

class ApiError500(ApiError):
    """
    An error occured server side and the request could not be completed
    """
    code: int = 500
    message: str = "Internal Server Error"

class ApiError501(ApiError):
    """
    The request method is not supported by the server
    """
    code: int = 501
    message: str = "Not Implemented"




########################################################################################
##                                    JOBS MODELS                                     ##
########################################################################################

class ApiModel(BaseModel):
    """
    Base model for all API models
    """
    
    def dict(self):
        return self.model_dump()

### https://stackoverflow.com/questions/60127234/how-to-use-a-pydantic-model-with-form-data-in-fastapi
### https://github.com/tiangolo/fastapi/issues/5588#issuecomment-1303157267
    

class JobRequest(ApiModel):
    """
    A job request is a dictionary with the following keys
        - "process": pre-defined process name (hlod, convert, thumbnail, custom)
        - "file": input file (optional)
        - "script": custom script file (required if process is "custom")
        - "params": JSON stringified process parameters (optional)
        - "name": the user given name of the job (optional)
    """
    process: str = Form(...)
    file: UploadFile|None = File(None)
    script: UploadFile|None = File(None)
    params: str|None = Form(None) # TODO: Parse JSON
    name: str|None = Form(None)


class JobState(ApiModel):
    """
    Short status of a job:
        - uuid: the unique identifier of the job
        - name: the user given name of the job
        - status: a string with the current status
        - progress: a number between 0 and 100
        - error: a string with the blocking error message if the job failed

    The status can be one of the following:
        - SENT: the job has been recieved by the scheduler
        - PENDING: the job is waiting to be processed
        - RUNNING: the job is running and information are available
        - SUCCESS: the job is done and the outputs are available
        - FAILURE: the job failed and the error message is available
        - UNKNOWN: the job failed and the error message is available
    """
    uuid: uuid_path_pattern|None = None # Unique identifier
    name: str|None = None  # User given name
    status: str|None = "UNKNOWN" # SENT, PENDING, RUNNING, SUCCESS, FAILURE, UNKNOWN
    progress: int|None = None # 0-100
    error: str|None = None # Blocking error

    def __init__(self, uuid: uuid_path_pattern, name: str | None = None, **kwargs):
        super().__init__(uuid=uuid, name=name, **kwargs)

    def update_from_task_result(self, result: dict):
        self.progress = result.get("progress", None)
        self.name = result.get("shadow_name", self.name)
    

class JobDetails(JobState):
    """
    Detailled job information:
        - uuid: the unique identifier of the job
        - name: the user given name of the job
        - status: a string with the current status
        - progress: a number between 0 and 100
        - error: a string with the blocking error message if the job failed
        - time: UTC date and time (request, started, ended)
        - steps: list of steps with their duration & info
        - retry: number of retries
        - output: the job output
    """
    time_info: Dict[str, str|None] = {"request": None, "started": None, "stopped": None}
    steps: List[Dict[str, Any]] | None = None
    retry: int = 0
    result: str | None = None

    def __init__(self, uuid: str, name: str | None = None, **kwargs):
        super().__init__(uuid=uuid, name=name, **kwargs)

    def update_from_task_result(self, result: dict):
        # TODO update with errors from traceback or custom error
        self.progress = result.get("progress", None)
        self.name = result.get("shadow_name", self.name)
        self.time_info = result.get("time_info", {"request": None, "started": None, "stopped": None})
        self.steps = result.get("steps", [])
        self.retry = result.get("retry", 0)
        self.result = result.get("result", {})


class TaskMeta(ApiModel):
    """
       ## Come from celery task metadata (useful for integration with PiXYZAPi backend)
        - result: the job result
        - traceback: contains celery error
        - children: list of children if dag in action
        - parent_id: for dag
        - task_id: same as uuid but in celery format
    """
    status: str | None = "PENDING"
    result: Any | None = None
    traceback: str | None = None
    # TODO: DMX change for children
    children: List [Any] = []
    parent_id: str | None = None
    task_id: str | None = None
    date_done: str | None = None

    def __init__(self, **kwargs):
        super(TaskMeta, self).__init__(**kwargs)
        self.update_from_task_result(kwargs)

    def update_from_task_result(self, result: dict):
        self.status = result.get("status", "PENDING")
        self.result = result.get("result", {})
        self.traceback = result.get("traceback", None)
        self.children = result.get("children", [])
        self.parent_id = result.get("parent_id", None)
        self.task_id = result.get("task_id", None)
        self.date_done = result.get("date_done", None)


class JobList(ApiModel):
    """
    List of all registered jobs status
    """
    jobs: List[JobState|None] = []

########################################################################################
##                               PROCESSES MODELS                                     ##
########################################################################################

class ProcessList(ApiModel):
    """
    List of all available scheduler processes to trigger jobs
    """
    processes: List[str|None] = []

    @field_validator("processes")
    def set_processes(cls, processes):
        return processes or []
    
    def __init__(self, processes: List[str|None], **kwargs):
        super().__init__(processes=processes, **kwargs)


########################################################################################
##                                  OUTPUT MODELS                                     ##
########################################################################################

class JobOutputsList(ApiModel):
    """
    List of all output files generated by a job
    """
    outputs: List[str|None] = []

    @field_validator("outputs")
    def set_outputs(cls, outputs):
        return outputs or []

    def __init__(self, outputs: List[str|None], **kwargs):
        super().__init__(outputs=outputs, **kwargs)
        


########################################################################################
##                                    EXPORTS                                         ##
########################################################################################

# Generate __all__ dynamically (all classes, ignores `_[whatever]`)
__all__ = [
    name for name, value in globals().items()
    if not name.startswith('_') 
        and hasattr(value, '__module__') 
        and value.__module__ == globals().get('__name__', '__main__')
        and isinstance(value, type)
        and not isinstance(value, types.ModuleType)
]
