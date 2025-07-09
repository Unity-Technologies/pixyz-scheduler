#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import logging
import datetime
import traceback
import time
from logging import Formatter
from logging import getLogger
from typing import Callable
from celery.utils import gen_unique_id
from celery.result import AsyncResult
# Keep this import otherwise we can't unserialise exception from result in job
from billiard.pool import *
from fastapi import Response, status, UploadFile, HTTPException
from fastapi.responses import FileResponse

from pixyz_api.models import *
from pixyz_api.patterns import uuid_path_pattern

from pixyz_worker.exception import PixyzException, PixyzTimeout, PixyzExitFault, TaskNotCompletedError, TaskProcessingStarted, SharePathNotFoundError
from pixyz_worker.share import is_job_in_share
import pixyz_worker


__all__ = ['get_api_logger', 'serialize_binary_data_state_dict', 'default_status_manager', 'get_utc_time',
           'upload_file_to_shared_storage', 'upload_file_to_job_input_shared_storage', 'create_job_id',
           'grab_task_status', 'grab_task_details', 'grab_tasks_list', 'grab_task_outputs_list',
           'grab_task_outputs_archive', 'grab_task_output_file', 'get_scripts_list_in_processes_dir',
           'get_script_path_in_processes_dir', 'raise_api_error', 'get_api_response_desc_from_model',
           'get_api_file_response_desc'
           ]

## LOGGER ##

def get_api_logger(logger_name='pixyz_api'):
    def get_string_to_log_level(log_level_str):
        log_level_str = log_level_str.upper()  # Convert to uppercase to handle case-insensitivity

        log_level_mapping = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        # Use get() method with a default value of logging.INFO for unknown log levels
        return log_level_mapping.get(log_level_str, logging.INFO)

    log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'

    logger = getLogger(logger_name)
    logger.setLevel(get_string_to_log_level(os.getenv('LOGLEVEL', 'DEBUG')))
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(Formatter(log_format))
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


logger = get_api_logger('api.utils')
debug_mode = True

## BINARY UTILS ##

def serialize_binary_data_state_dict(d):
    """
    Serialize bytes data to hex string if required, otherwise return the original dict
    :param d: dictionary to serialize
    :return: a serialized dictionary
    """
    ret = {}
    if d is None:
        return {}
    for k, v in d.items():
        if isinstance(v, bytes):
            v = v.hex()
        elif isinstance(v, dict):
            v = serialize_binary_data_state_dict(v)
        else:
            pass
        ret[k] = v
    return ret


def default_status_manager(async_ret: AsyncResult, response: Response, success: Callable, running: Callable = None,
                           failure: Callable = None):
    try:
        if async_ret.state == 'PENDING':
            response.status_code = status.HTTP_404_NOT_FOUND
            return JobStatus(async_ret.state, {'message': 'Job does not exist'})
        elif async_ret.state == 'SENT':
            response.status_code = status.HTTP_202_ACCEPTED
            return JobStatus(async_ret.state, {'message': 'Job is sent'})
        elif async_ret.state == 'STARTED':
            response.status_code = status.HTTP_202_ACCEPTED
            return JobStatus(async_ret.state, {'message': 'Job is started'})
        elif async_ret.state == 'RUNNING':
            if running is not None:
                return running(async_ret, response)
            else:
                response.status_code = status.HTTP_202_ACCEPTED
                result = pixyz_worker.tasks.app.backend.get_task_meta(async_ret.id)
                return JobStatus(result['status'], serialize_binary_data_state_dict(result['result']))
        elif async_ret.state == 'SUCCESS':
            return success(async_ret, response)
        else:
            if failure is not None:
                return failure(async_ret, response)
            else:
                try:
                    result = pixyz_worker.app.backend.get_task_meta(async_ret.id)
                    return JobStatus(result['status'], {'error': str(result['result'])})
                except Exception as e:
                    return JobStatus('UNKNOWN', {'error': str(e)})
    except Exception as e:
        try:
            result = pixyz_worker.app.backend.get_task_meta(async_ret.id)
            return JobStatus(result['status'], {'error': str(result['result']), 'exception': str(e)})
        except Exception as e:
            return JobStatus('UNKNOWN', {'error': str(e)})

# TODO: deprecated, must use timezone
def get_utc_time():
    return datetime.datetime.utcnow()

########################################################################################
##                                 STORAGE UTILS                                      ##
########################################################################################

def upload_file_to_shared_storage(file: UploadFile, shared_file_name: str):
    with open(shared_file_name, 'wb') as f:
        while content := file.file.read(10 * 1024 * 1024):  # Lisez le fichier en mode streaming
            f.write(content)
    os.chmod(shared_file_name, 0o777)


# TODO: deprecated
def download_and_load_to_shared_if_available(data: UploadFile = None):
    if data is None:
        return None
    data_filename = os.path.basename(data.filename)
    shared_data_path = pixyz_worker.share.get_share_upload_file(data_filename)
    logger.info(f"Uploading file {data_filename} to shared storage: {shared_data_path}")
    upload_file_to_shared_storage(data, shared_data_path)
    logger.info(f"File {data_filename} uploaded to {shared_data_path}")
    return shared_data_path


def upload_file_to_job_input_shared_storage(job_id: str, file: UploadFile):
    if file is None:
        return None
    filename = os.path.basename(file.filename)
    shared_file_path = pixyz_worker.share.get_job_input_file_path(job_id, filename)
    logger.info(f"Uploading file {filename} to shared storage: {shared_file_path}")
    upload_file_to_shared_storage(file, shared_file_path)
    logger.info(f"File {filename} uploaded to {shared_file_path}")
    return shared_file_path

########################################################################################
##                                   TASKS UTILS                                      ##
########################################################################################



def create_job_id():
    """
    Create a shared job unique ID with celery
    returns the job ID
    """
    return gen_unique_id()


# TODO: improve handling for instances of PixyzExitFault, PixyzTimeout with get_message
def get_error_from_task_meta(task_meta: dict):
    """
    Get the error message from a task metadata
    """
    if 'traceback' in task_meta and task_meta['traceback'] is not None:
        # task_meta result contains the error (if exists)
        # use custom error if exists or task.info (in task_meta['result'] if traceback)

        # TODO: get custom exceptions messages
        if isinstance(task_meta['result'], PixyzTimeout):
            return "Task process timeout"
        elif isinstance(task_meta['result'], PixyzExitFault):
            return "Task process exited with error"
        elif isinstance(task_meta['result'], PixyzException):
            return "Pixyz Internal error"
        else:
            # TODO: what to display when task_meta['result'] contains the full traceback
            task_error = task_meta['result']['error'] if isinstance(task_meta['result'], dict) and 'error' in task_meta['result'] else 'Internal error'

            if isinstance(task_error, str):
                return task_error
            else: 
                return str(task_error)

    return None

def grab_task_status(job_id: uuid_path_pattern):
    """
    Get the status of a given job ID
    """

    job_status = JobState(job_id)

    task = None
    try:
        task = AsyncResult(job_id, app=pixyz_worker.tasks.app)
        
        job_status.name = task.name
        job_status.status = str(task.state)
    except Exception as e:
        if debug_mode:
            logger.error(e)
        job_status.status = 'UNKNOWN'
        job_status.error = 'Unable to get job status'
        return job_status
        
    # Retrieve tasks metadata
    task_meta = task.backend.get_task_meta(job_id)

    job_status.error = get_error_from_task_meta(task_meta)

    if 'result' in task_meta and isinstance(task_meta['result'], dict):
        job_status.update_from_task_result(task_meta['result'])

    return job_status


def grab_task_details(job_id: uuid_path_pattern):
    """
    Get the info of a given job ID
    """

    job_details = JobDetails(job_id)

    task = None
    try:
        task = AsyncResult(job_id, app=pixyz_worker.tasks.app)

        job_details.name = task.name
        job_details.status = str(task.state)
    except Exception as e:
        job_details.status = 'UNKNOWN'
        job_details.error = 'Unable to get job info'
        return job_details
        
    # Retrieve full tasks metadata, task.get() only returns the result
    task_meta = task.backend.get_task_meta(job_id)

    # task_meta: {
    # 'status': 'SUCCESS', 
    # 'result': {
    #   'pid': 1, 'hostname': 'worker@pixyz-glados', 
    #   'time_info': {'request': '2024-02-19T20:10:19.057121', 'started': '2024-02-19T20:10:19.078839+00:00', 'stopped': None}, 
    #   'progress': 100, 
    #   'steps': [{'duration': 11.703209294006228, 'info': 'Importing file'}, {'duration': 0.11408253596164286, 'info': 'Exporting file to PanDaDance.pxz'}],
    #   'output': '/share/ab6d6726-f630-4467-9e44-c57df60107c3/output/PanDaDance.pxz'
    #   }, 
    # 'traceback': None, 'children': [], 
    # 'date_done': '2024-02-19T20:10:30.952138', 
    # 'task_id': 'ab6d6726-f630-4467-9e44-c57df60107c3'}

    if debug_mode:
        logger.warning("----------------------------------------------------")
        logger.info(task_meta)
        logger.warning("----------------------------------------------------")

    job_details.error = get_error_from_task_meta(task_meta)

    if 'result' in task_meta and isinstance(task_meta['result'], dict):
        # time.ended hack if not present
        if ('date_done' in task_meta and 'time_info' in task_meta['result'] and
                'stopped' in task_meta['result']['time_info'] and
                task_meta['result']['time_info']['stopped'] is None):
            task_meta['result']['time_info']['stopped'] = task_meta['date_done']

        job_details.update_from_task_result(task_meta['result'])
    else:
        # In case of unpickable exception, we can get an exception in result, so try to convert it
        try:

            job_details.result = str(task_meta['result'])
            # Update with the done date if available
            if 'date_done' in task_meta:
                job_details.time_info =  {"request": None, "started": None, "stopped": task_meta['date_done']}
        except Exception as e:
            pass

    if 'traceback' in task_meta and task_meta['traceback'] is not None:
        job_details.error = task_meta['traceback']

    return job_details



def grab_tasks_list():
    """
    Get a list of all task IDs in the result backend (Redis)
    """
    jobs_list = []
    cel_tasks = []

    cel_tasks = pixyz_worker.tasks.app.backend.client.keys('celery-task-meta-*')
    
    for task_id in cel_tasks:
        task_id = task_id.decode('utf-8').replace('celery-task-meta-', '')

        job_status = grab_task_status(task_id)
        jobs_list.append(job_status)

    return jobs_list


def grab_task_outputs_list(job_id: uuid_path_pattern):
    """
    Get the list of all available outputs for a given job ID
    """
    return pixyz_worker.share.get_job_output_dir_content(job_id)


def grab_task_outputs_archive(job_id: uuid_path_pattern, package_type: str = 'zip', repack: bool = False):
    """
    Create an archive of all outputs for a given job ID and return the path
    :param job_id: the job ID
    :param package_type: the package type (zip, tar, tar.gz)
    :param repack: if True, force the creation of a new archive
    :return: the path of the archive
    :raises TaskNotCompletedError: if the job is not finished yet
    """

    # check if the job exists. There is no proper way to check if a job exists in the backend, we'll check if the shared directory exists
    if not is_job_in_share(job_id):
        raise SharePathNotFoundError(f"Job '{job_id}' does not exist")

    # check if the task is finished
    task = AsyncResult(job_id, app=pixyz_worker.tasks.app)
    if str(task.state) not in ['SUCCESS', 'FAILURE']:
        raise TaskNotCompletedError(f"Job '{job_id}' is not finished yet")

    # check if the archive exists
    archive_name = f"{job_id}.{package_type}"
    archive_path = pixyz_worker.share.get_job_share_file_path(job_id, directory="archives", file_name=archive_name)

    if not repack and os.path.exists(archive_path) and os.path.isfile(archive_path):
        return archive_path
    
    # Check if an archive task is not already running
    if pixyz_worker.utils.DiskAsyncState.is_registered(job_id, package_type):
        raise TaskNotCompletedError(f"Archive task for job '{job_id}' is already running")

    # Create a celery package task and waits for completion
    task = pixyz_worker.tasks.package.apply_async(args=(job_id, package_type))

    print(f"Archive Task {task.id} created for job '{job_id}' outputs")

    # Do not wait for the task to complete and send a signal to the client
    raise TaskProcessingStarted(f"Archive Task '{task.id}' created for job '{job_id}' outputs")


def grab_task_output_file(job_id: uuid_path_pattern, file_path: str):
    """
    Return the path of a file in the job output directory
    Ensure the path is valid
    Ensure the file exists
    """
    return pixyz_worker.share.get_job_output_file_path(job_id, file_path, check_if_exists=True)  

########################################################################################
##                             PROCESSES UTILS                                        ##
########################################################################################


# TODO DMX: move to storage module ?

def get_scripts_list_in_processes_dir():
    # list all python files in the process folder and return them without extension
    return [f.replace('.py', '') for f in os.listdir(pixyz_worker.config.process_path) if f.endswith('.py')]


def get_script_path_in_processes_dir(script_name: str):
    return os.path.join(pixyz_worker.config.process_path, f"{script_name}.py")


########################################################################################
##                                   API UTILS                                        ##
########################################################################################

# Error helper
# TODO: auto add traceback here if error is Exception not string
def raise_api_error(error_model: ApiError, error: Exception | str | None = None):
    """
    Raise an API error with a detailled error message and default code and message
    Automatically 
        - raise an HTTPException with the error code and message
        - log if the error is an exception
        - traceback if debug_mode is True
    """

    # check if error is an exception
    if isinstance(error, Exception):
        detailled_error_message = f"{error.__class__.__name__}: {str(error)}"        
    elif isinstance(error, str):
        detailled_error_message = error
    else:
        detailled_error_message = None

    logger.error(detailled_error_message)
    if debug_mode:
        logger.error(traceback.format_exc())

    err = error_model(details=detailled_error_message)
    raise HTTPException(status_code=err.code, detail=err.dict())



# responses dict to be used in the FastAPI default responses
api_error_responses = {
    400: {"model": ApiError400, "description": ApiError400.__doc__ or ApiError400.__name__},
    401: {"model": ApiError401, "description": ApiError401.__doc__ or ApiError401.__name__},
    #403: {"model": ApiError403, "description": ApiError403.__doc__ or ApiError403.__name__},
    404: {"model": ApiError404, "description": ApiError404.__doc__ or ApiError404.__name__},
    425: {"model": ApiError425, "description": ApiError425.__doc__ or ApiError425.__name__},
    500: {"model": ApiError500, "description": ApiError500.__doc__ or ApiError500.__name__},
    #501: {"model": ApiError501, "description": ApiError501.__doc__ or ApiError501.__name__},
}

def get_api_response_desc_from_model(model):
    """
    Get the description of a route from a model class
    """

    if not model:
        logger.warning(f"Model {model} does not exist")
        return {}
    
    # use model name as description if no docstring
    description = model.__doc__ or model.__name__
    
    return {
        'description': description,
        'response_model': model,
        'responses': {
            **api_error_responses,
            status.HTTP_200_OK: {
                'model': model,
                'description': 'Successful request',
            }
        }
    }



def get_api_file_response_desc():
    """
    Get the description of a route that returns a FileResponse
    """

    return {
        'description': 'Download a file',
        'response_class': FileResponse,
        'responses': {
            **api_error_responses
        }
    }


