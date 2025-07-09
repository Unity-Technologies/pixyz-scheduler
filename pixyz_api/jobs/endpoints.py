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
from pixyz_worker.share import SourceInspector
from kombu.exceptions import OperationalError

logger = get_api_logger('api')
router = APIRouter()

# /!\ DO NOT ADD / in the path of the router
# FAT WARNING: DON'T ADD / in GET or POST
# Because of temporary redirect in FastAPI, it will cause a 308 redirect to the same URL with a trailing slash

# Gets list of all registered jobs
@router.get("", **get_api_response_desc_from_model(JobList))
async def list_all_jobs_status(api_key: APIKey = Depends(verify_token)):
    try:
        return {'jobs': grab_tasks_list()}
    except Exception as e:
        raise_api_error(ApiError500, e)

# Creates a new job
@router.post("", **get_api_response_desc_from_model(JobState))
async def create_new_job(
        api_key: APIKey = Depends(verify_token),
        process: str = Form("custom"), # process name
        file: UploadFile | str = File(None, example=None), # input file
        script: UploadFile | str = File(None), # custom process script
        params: str = Form(None, example=None), # process parameters (JSON string)
        name: str = Form(None, example=None), # job custom name
        config: str = Form(None, example=None), # worker configuration (JSON string)
    ):
    def remove_immutable_keys(user_config_: dict):
        for key in ('script', 'data', 'shadow', 'uuid'):
            if key in user_config_:
                warnings[key] = f"The '{key}' config key is not mutable"
                del user_config_[key]

    def delete_key_with_none(user_config_: dict):
        for key in list(user_config_.keys()):
            if user_config_[key] is None:
                del user_config_[key]

    def update_dict_on_none(dst, src):
        for k, v in src.items():
            if (k in dst and dst[k] is None) or (k not in dst):
                dst[k] = src[k]

    # Create a new job uuid
    uuid = create_job_id()

    # Upload files to shared storage
    input_file_path = upload_file_to_job_input_shared_storage(uuid, file) if file else None
    input_script_path = upload_file_to_job_input_shared_storage(uuid, script) if script else None

    # Parse params from JSON string
    if params:
        try:
            params = json.loads(params)
        except Exception as e:
            raise_api_error(ApiError400, f"Invalid JSON string for 'params': {e}")
    else:
        # Always initialize params as a dict to prevent NoneType errors in the worker
        params = {}

    # Launch the appropriate process
    process_file_path = None
    
    if process == 'custom':
        if not script:
            raise_api_error(ApiError400, "'custom' process requires a 'script' file")
        
        process_file_path = input_script_path       
    else:
        # check if process matches a valid process file
        if(process not in get_scripts_list_in_processes_dir()):
            raise_api_error(ApiError400, f"Invalid process '{process}'")
        
        process_file_path = get_script_path_in_processes_dir(process)

    # create a pixyz worker task with uuid and name to execute the process
    logger.info(f"Creating a new '{process}' task with uuid '{uuid}'")

    # default worker config
    # TODO: expose documentation
    worker_config = {
        'task_id': uuid, # task id
        'script': process_file_path, # script path
        'data': input_file_path, # input file path
        'root_file': None, # Name of the root file if input is an archive # TODO archive + root file
        'time_request': get_utc_time(), # request time in UTC 
        'time_limit': 3600, # job timeout in seconds
        # Queue must be specified at the end of the process because the queue can be selected by the script
        'entrypoint': 'main', # script entrypoint
        'compute_only': False,
        'shadow': name,
    }

    # Log task configuration 
    user_config = {}

    # parse config from JSON string
    warnings = {}

    if config:
        try:
            user_config = json.loads(config)
        except Exception as e:
            raise_api_error(ApiError400, f"Invalid JSON string for 'config': {e}")
    else:
        user_config = {}

    # If a user config contains a null, the next steps will overwrite the default values
    # To prevent it, we remove all keys with None values
    delete_key_with_none(user_config)

    # remove unmutable keys
    remove_immutable_keys(user_config)

    if len(warnings) > 0:
        logger.warning(f"User config warnings: {warnings}")
    
    # Update worker config with user config
    worker_config.update(user_config)

    # Check if the source file contains the entrypoint function otherwise raise an error
    si = SourceInspector(process_file_path)
    if not si.is_function_exist(worker_config['entrypoint']):
        raise_api_error(ApiError400, f"The script file does not have the function {worker_config['entrypoint']}")

    function_default_parameters = si.get_pixyz_decorator_kwargs_for_a_function(worker_config['entrypoint'])
    remove_immutable_keys(function_default_parameters)
    # Reapply config from function to user config priority
    worker_config.update(function_default_parameters)
    worker_config.update(user_config)

    # Define a queue if nobody has defined it
    worker_config['queue'] = worker_config.get('queue', 'cpu')

    # create the task's program context
    pc = pixyz_worker.extcode.ProgramContext(**worker_config)

    task = None

    try:
        task = pixyz_worker.tasks.pixyz_execute.apply_async(args=(params, pc), **worker_config)
    except OperationalError as e:
        # This error is raised when the worker is not running or the queue is not available
        raise HTTPException(status_code=503, detail=f"Service not available: Backend is not ready, please check your redis: {e}")
    except Exception as e:
        # TODO: handle PixyzTimeout ??
        raise_api_error(ApiError500, e)
    finally:
        if file is not None and isinstance(file, UploadFile):
            file.file.close()
        if script is not None and isinstance(script, UploadFile):
            script.file.close()

    return JobState(uuid, name, status='SENT')

# Gets job status
@router.get("/{job_uuid}", **get_api_response_desc_from_model(JobState))
async def get_job_status(job_uuid: uuid_path_pattern, api_key: APIKey = Depends(verify_token)):
    """
    Get the status of a job
    :param job_uuid: the job ID
    :param api_key: the API key
    :return: the job status
    """
    #
    try:
        return grab_task_status(job_uuid)
    except Exception as e:
        raise_api_error(ApiError500, e)

# Gets job detailled info
@router.get("/{job_uuid}/details", **get_api_response_desc_from_model(JobDetails))
async def get_job_details(job_uuid: uuid_path_pattern, api_key: APIKey = Depends(verify_token)):

    """
    Get the details of a job
    :param job_uuid: the job ID
    :return: the job details
    """
    #
    try:
        return grab_task_details(job_uuid)
    except Exception as e:
        raise_api_error(ApiError500, e)


# Gets list of all available outputs (files in the {job_uuid}/output)
@router.get("/{job_uuid}/outputs", **get_api_response_desc_from_model(JobOutputsList))
async def get_outputs(job_uuid: uuid_path_pattern, api_key: APIKey = Depends(verify_token)):

    """
    Get the list of all available outputs for a given job ID
    :param job_uuid: the job ID
    :return: a list of strings with the name of the outputs
    """
    #
    try:
        outputs = grab_task_outputs_list(job_uuid)
        return JobOutputsList(outputs)
    except Exception as e:
        raise_api_error(ApiError500, e)

# Outputs an archive of all outputs
@router.get("/{job_uuid}/outputs/archive", **get_api_file_response_desc())
async def get_all_outputs_as_archive(job_uuid: uuid_path_pattern, api_key: APIKey = Depends(verify_token),
                                     response: Response = None):

    """
    Get the list of all available outputs for a given job ID
    :param job_uuid: the job ID
    :param api_key: the API key
    :param response: the response object
    :return: a list of strings with the name of the outputs
    """

    try:
        archive_path = grab_task_outputs_archive(job_uuid)
    except (TaskProcessingStarted, TaskNotCompletedError) as e:
        raise_api_error(ApiError425, e)
    except (SharePathInvalidError, SharePathNotFoundError) as e:
        raise_api_error(ApiError404, e)
    except Exception as e:
        raise_api_error(ApiError500, e)

    try:
        return FileResponse(archive_path, media_type='application/octet-stream', filename=os.path.basename(archive_path))
    except Exception as e:
        logger.error(f"Error while sending job '{job_uuid}' output archive: '{e}'")
        raise_api_error(ApiError500, f"Failed to retrieve archive")


# Gets list of all available outputs (files in the {job_uuid}/outputs)
@router.get("/{job_uuid}/outputs/{file_path:path}", **get_api_file_response_desc())
async def get_output_file(job_uuid: uuid_path_pattern, file_path: str, api_key: APIKey = Depends(verify_token)):

    """
    Get the list of all available outputs for a given job ID
    :param job_uuid: the job ID
    :param file_path: the file path
    :param api_key: the API key
    :return: a list of strings with the name of the outputs
    """

    try:
        file_fullpath = grab_task_output_file(job_uuid, file_path)
    except SharePathInvalidError as e:
        raise_api_error(ApiError400, e)
    except SharePathNotFoundError as e:
        raise_api_error(ApiError404, e)
    except Exception as e:
        raise_api_error(ApiError500, e)

    try:
        return FileResponse(file_fullpath, media_type='application/octet-stream', filename=os.path.basename(file_fullpath))
    except Exception as e:
        logger.error(f"Error while sending job '{job_uuid}' output file: '{e}'")
        raise_api_error(ApiError500, f"Failed to retrieve file '{file_path}'")
