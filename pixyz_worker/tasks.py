#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# If acks_late=True and WorkerLostError is raised, the task will be retried infinitely


from __future__ import absolute_import, unicode_literals
import importlib.util
import os
import traceback
import time
import shutil
import platform
import sys


from billiard.exceptions import WorkerLostError, SoftTimeLimitExceeded
from celery import Celery

from tempfile import NamedTemporaryFile, TemporaryDirectory

import pixyz_worker.config
from pixyz_worker.exception import *
from pixyz_worker.signals import *
from pixyz_worker.share import *
from pixyz_worker.extcode import *
from pixyz_worker.progress import TaskProgress
from pixyz_worker.storage import *
from pixyz_worker.utils import *
from pixyz_worker.pc import *
from pixyz_worker.license import *
from celery import states
from celery.exceptions import Retry, Ignore
from multiprocessing import current_process

logger = get_logger('pixyz_worker.tasks')
license_ = License.from_config()

try:
    import pxz
    import pxz.core
    from pxz import io, algo, scene, view, material, core
except ImportError:
    logger.warning("Pixyz not installed, some tasks will not be available")

app = Celery()
app.config_from_object('pixyz_worker.settings')

__all__ = [
            'sleep', 
            'pixyz_execute',
            'cleanup_share_file',
            'app',
            'package'
        ]



# Task definition for pixyz workload
# Retry kwargs seems to be ignored by celery if auto_retry on exception disabled
# Keep track_started = True otherwise the task will be marked as PENDING

# DMX note: retry_kwargs are parameters for retrying task with the autoretry_for feature, and
# max_retries/default_retry_delay out of retry_kwargs are for not autoretry_for options
# https://docs.celeryq.dev/en/latest/userguide/configuration.html#task-reject-on-worker-lost
# Even if task_acks_late is enabled, the worker will acknowledge tasks when the worker process executing them
# abruptly exits or is signaled (e.g., KILL/INT, etc).

### GROUP TEST1
# ******* Segfault from python code and pixyz task with:
#  import ctypes
#  ctypes.string_at(0)
# or pixyz without initialize

# Mode PREFORK=1
# TEST Python segfault & pixyz segfault
# acks_late=False & task_reject_on_worker_lost=False + segfault = WorkerLostError without retry or anything else X
# acks_late=True & task_reject_on_worker_lost=True + segfault = Infinite loop same task X
# acks_late=True & task_reject_on_worker_lost=False + segfault = Infinite loop same task
# acks_late=False & task_reject_on_worker_lost=True + segfault = WorkerLostError without retry or anything else

# Mode SOLO=1
# acks_late=False & task_reject_on_worker_lost=False + segfault = WorkerLostError without retry or anything else
# acks_late=True & task_reject_on_worker_lost=True + segfault = Infinite loop same task
# acks_late=True & task_reject_on_worker_lost=False + segfault = Infinite loop same task
# acks_late=False & task_reject_on_worker_lost=True + segfault = WorkerLostError without retry or anything else

# Global task parameter
pixyz_task_params = {'bind': True, 'track_started': True,
                     'acks_late': False, 'task_reject_on_worker_lost': True,

                      # Auto-retry only
                     'retry_kwargs': {'countdown': 0, 'max_retries': 1, 'queue': 'gpuhigh'},
                     'autoretry_for': (PixyzExecutionFault, WorkerLostError),

                     # Regular retry
                     'retry_backoff': False,
                     'countdown': 0, 'max_retries': 1, 'default_retry_delay': 0,
                     'time_limit': pixyz_worker.config.time_limit
                     }

mgmt_task_params = {'bind': True, 'track_started': True, 'retry_backoff': True, 'task_reject_on_worker_lost': True,
                    'retry_kwargs': {'countdown': 60, 'max_retries': 3}}


retrievable_exceptions = (PixyzExecutionFault, WorkerLostError, SoftTimeLimitExceeded, PixyzTimeout, MemoryError)


def get_task_params(task):
    ret = {}

    # internal from celery get the actual request otherwise, we pick the default
    try:
        if task.request.timelimit is not None:
            ret['time_limit'] = task.request.timelimit[0]
    except (ValueError, AttributeError) as e:
        logger.debug("get_task_params failed to get time_limit params, get default")
        ret['time_limit'] = task.time_limit

    return ret


def retry_on_pixyz_fault_with_raise(task, exc, **kwargs):
    # params = {'exc': exc, 'countdown': 0, 'max_retries': 1, 'throw': True,
    #           'correlation_id': task.request.correlation_id or task.request.id}
    params = {'countdown': 0, 'max_retries': 1}

    logger.debug("Retrying...")

    if task.request.delivery_info.get('routing_key') in ('gpu', 'cpu'):
        logger.debug("Retrying in queue gpuhigh")
        params.update(queue='gpuhigh', time_limit=pixyz_worker.config.retry_time_limit)
    else:
        logger.debug("Retrying in queue default queue")
    params.update(kwargs)
    logger.exception(f"PixyzExecutionFault: Retrying({str(params)}) {exc}")
    raise task.retry(**params)


def task_params(base, **kwargs):
    return {**base, **kwargs}


def update_state_with_exception(self, exc, **kwargs):
    logger.exception(exc)
    try:
        failure_meta_dict = {'exc_traceback': traceback.format_exc().split('\n'),
                             'exc_type': type(exc).__name__,
                             'exc_module': exc.__class__.__module__,
                             'exc_message': str(exc)
                             }
        logger.error("task failed, change STATE to FAILURE with: %s", failure_meta_dict)
    except Exception:
        failure_meta_dict = {'exc_type': type(exc).__name__,
                             'exc_message': str(exc)}
    failure_meta_dict.update(kwargs)
    logger.debug("updating state to FAILURE with: %s", failure_meta_dict)
    self.update_state(state=states.FAILURE, meta=failure_meta_dict)
    self.send_event('task-failed', exception=repr(exc))
    logger.error(f"UPDATED state to FAILURE")
    #raise Ignore()

# You must retry a delete for avoiding an OS file system cache error
    
@app.task(**task_params(mgmt_task_params, name="cleanup_share_file", queue="clean"))
def cleanup_share_file(self, file_path, is_directory=False):
    inode_type = "DIRECTORY" if is_directory else "file"
    logger.info(f"Cleanup share {inode_type} {file_path}")
    try:
        if not is_directory:
            logger.info(f"Removing {inode_type} {file_path}")
            os.remove(file_path)
        else:
            # Ultimate sanity check before removing a directory
            if is_path_in_share(file_path) and is_a_valid_job_id_directory(file_path):
                logger.info(f"Removing {inode_type} {file_path}")
                shutil.rmtree(file_path)
            else:
                logger.warning(f"Sanity check failed before removing {inode_type} >{file_path}<")
    except FileNotFoundError as e:
        logger.warning(f"File not found {file_path}({str(e)})")
    except Exception as exc:
        logger.fatal(f"cleanup exception {str(exc)}")
        update_state_and_raise_a_failure(self, exc, http_code=500)


# All fields must be serializable!
def update_state_and_raise_a_failure(self, exc, **kwargs):
    update_state_with_exception(self, exc, **kwargs)
    raise exc


@app.task(**task_params(pixyz_task_params, name="sleep", queue="gpu"))
def sleep(self, t):
    try:
        #logger.info(f"Sleeping for {t} seconds on queue {self.request.delivery_info.get('routing_key')}")
        # if self.request.retries == 0:
        #     SignalSafeExecution.run(a_fault)
        time.sleep(t)
        return t
    except WorkerLostError as exc:
        logger.exception(exc)
        self.retry(exc=exc, countdown=0, max_retries=3, correlation_id=self.request.correlation_id or self.request.id)
    except AttributeError as exc:
        logger.exception(exc)
        self.retry(exc=exc, countdown=0, max_retries=3, correlation_id=self.request.correlation_id or self.request.id)
    # except Exception as exc:
    #     logger.exception(exc)
    #     self.retry(exc=exc, countdown=0, max_retries=3, correlation_id=self.request.correlation_id or self.request.id)


@app.task(**task_params(pixyz_task_params, name="pixyz_execute", queue="gpu"))
def pixyz_execute(self, params: dict, pc: ProgramContext = None):
    """
    Import "params" must be always the latest argument otherwise the task with chord will fail
    """
    # Store the shadow name in the task meta
    try:
        self.update_state(task_id=self.request.id, state='RUNNING', meta={'shadow_name': self.request.shadow})
    except:
        pass
    # Run the task
    try:
        with PiXYZSession(license_):
            with TaskProgress(self, self.request.id, 1, time_request=pc['time_request']) as progress:
                with FileInputTemporary(pc['data'], progress=progress, root_file=pc['root_file']) as tmp:
                    with ExecuteIfEnabled(StorageOutputManager(self.request.id), not pc['compute_only']) as shared:
                        if pc is None:
                            pc = ProgramContext()
                        elif isinstance(pc, dict):
                            pc = ProgramContext(**pc)
                        # Prepare the next launch
                        pc.update(input_dir=tmp.directory,
                                  input_file=tmp.file,
                                  output_dir=shared.output_dir,
                                  progress=progress,
                                  params=params,
                                  task=self,
                                  queue=self.request.delivery_info.get('routing_key'),
                                  retry=self.request.retries)

                        # Update the number of retry in the task state
                        if self.request.retries > 0:
                            progress.retry(self.request.retries)
                        try:
                            try:
                                current_queue = self.request.delivery_info.get('routing_key')
                            except Exception as exc:
                                # If the task is not a Celery task, we set the queue to "eee"
                                # This is useful for testing purposes
                                current_queue = "unknown"
                            logger.info(f">>>> Starting PiXYZ execution entrypoint:{str(pc['entrypoint'])} queue:{current_queue} context:{str(pc)}")
                            if current_process().name == 'MainProcess' and platform.system() != 'Windows':
                                # enable segfault protection
                                ret = SignalSafeExecution.run(ExternalPythonCode(pc['script']).execute, pc,
                                                              **get_task_params(self))
                            else:
                                ret = ExternalPythonCode(pc['script']).execute(pc)
                            logger.info(f"<<<< PiXYZ execution finished OK")
                        except retrievable_exceptions as exc:
                            logger.info(f"!!!! PiXYZ execution finished with retrievable exception: {exc}, retrying...")
                            logger.error(traceback.format_exc())
                            try:
                                retry_on_pixyz_fault_with_raise(self, exc)
                            except Retry as exc:
                                # Keep the progress_output json serializable
                                pc.progress_output(str(exc))
                                raise exc

            # If return is a dict, so add the benchmark info
            return pc.progress_output(ret)
    except Retry as exc:
        # Re-raise for retrying
        logger.info(f"EEEE PiXYZ execution finished with retry exception: {exc}")
        raise exc
    except Exception as exc:
        logger.info(f"EEEEE PiXYZ execution finished with exception: {exc}")
        logger.exception(exc)
        logger.fatal(traceback.format_exc())
        update_state_and_raise_a_failure(self, exc)



@app.task(**task_params(mgmt_task_params, name="package_outputs", queue="zip"))
def package(self, job_id, package_type='zip'):
    try:
        if package_type not in pixyz_worker.config.supported_archive.keys():
            raise InvalidBackendParameter(f'Unsupported archive type {package_type}')

        with (DiskAsyncState(job_id, package_type)):
            # Check if a job has been already ran for security reason and other reason
            source_directory = get_job_output_dir(job_id)
            if not os.path.isdir(source_directory):
                raise PixyzFileNotFound(f"Directory {source_directory} not found")

            # remove "all" kinds of archive if already exists
            for package_possible in pixyz_worker.config.supported_archive.values():
                archive_path = get_job_archive_file_path(job_id, file_name=f"{job_id}.{package_possible}")
                if os.path.exists(archive_path) and os.path.isfile(archive_path):
                    logger.info(f"Cleaning up existing archive {archive_path}")
                    os.unlink(archive_path)

            compression_extension = pixyz_worker.config.supported_archive[package_type]
            archive_path = get_job_archive_file_path(job_id, file_name=f"{job_id}.{compression_extension}")

            # Don't archive in the same directory otherwise the archive will be included in the archive
            tmp_file = None

            with NamedTemporaryFile(delete=False) as tmp:
                tmp.close()
                tmp_file = tmp.name
                logger.info(f"Packaging {source_directory} to {tmp_file}...")
                shutil.make_archive(tmp_file, package_type, source_directory)
                logger.info(f"Packaging done.")
            if tmp_file is not None:
                logger.info(f"Move archive from {tmp_file} to output directory {archive_path}")
                # the make_archive function add the file extension to the archive name
                # Don't move because you must keep on the same filesystem
                shutil.copy(f"{tmp_file}.{compression_extension}", archive_path)
                os.unlink(tmp_file)
            else:
                raise PixyzFileNotFound(f"Temporary file {tmp_file} not found")

            # Todo: Update meta with created archive_name ?

    except DiskStateAlreadyExists as exc:
        logger.warning(f"new {package_type} requested, but skipped because a state file already exists")
    except Exception as e:
        update_state_and_raise_a_failure(self, e)

