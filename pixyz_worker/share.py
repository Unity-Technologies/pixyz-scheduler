#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# TODO dmx: This file should be refactored to another module and shared between pixyz_worker and api.
import os
import sys
import uuid
import ast

import logging
import shutil
import requests
from datetime import datetime, timedelta
from pixyz_worker.exception import PixyzWebError, SharePathInvalidError, SharePathNotFoundError
import pixyz_worker.config
import time
from pixyz_worker.license import License

__all__ = ['get_logger', 'cleanup_data_after_timeout',
           'move_file_as_result_to_shared_storage', 'get_first_3D_files_in_directory',
           'get_filename_from_url', 'download_file', 'each',
           'get_job_output_dir', 'TaskInfos', 'is_a_valid_job_id_directory', 'is_job_in_share', 'is_path_in_share',
           'is_job_in_share', 'get_job_share_dir', 'get_job_share_file_path', 'get_job_input_dir',
           'get_job_output_dir', 'get_job_input_dir_content', 'get_job_output_dir_content', 'get_job_input_file_path',
           'get_job_output_file_path', 'get_job_archive_file_path', 'PiXYZSession'
           ]


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


def get_logger(logger_name='pixyz_worker'):
    # TODO dmx: create a pixyzutils and mutualize function like this to avoid code duplication
    try:
        from celery.app.log import TaskFormatter as Formatter
        from celery.app.log import get_logger as getLogger
        from celery.app.defaults import DEFAULT_TASK_LOG_FMT as log_format
    except ImportError:
        from logging import Formatter
        from logging import getLogger

    logger = getLogger(logger_name)
    logger.setLevel(get_string_to_log_level(os.getenv('LOGLEVEL', 'INFO')))
    return logger


logger = get_logger('pixyz_worker.share')




## Shared storage Utils ##
########################################################################################
##                             SHARED FOLDER                                          ##
########################################################################################


# TODO: check with dmx to use StorageSharedManager

job_input_dirname = 'inputs'
job_output_dirname = 'outputs'
job_archive_directory = 'archives'


def is_valid_jobid(job_id):
    from re import match

    # TODO: circular import when using from api.patterns import uuid_path_pattern
    if match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', job_id) is not None:
        return True
    else:
        return False


def is_path_in_share(full_path):
    """
    Check if a file is in the shared storage
    """
    return os.path.exists(full_path) and os.path.realpath(full_path).startswith(pixyz_worker.config.share_dir)


# check if a folder named after an uuid exists in the shared storage
def is_job_in_share(job_id):
    """
    Check if a job_id is in the shared storage
    """
    if is_valid_jobid(job_id):
        job_share_dir = os.path.realpath( os.path.join(pixyz_worker.config.share_dir, job_id) )
        return os.path.exists(job_share_dir)        
    else:
        raise SharePathInvalidError(f"Invalid job_id {job_id}")


def get_job_share_dir(job_id:str):
    """
    Return the dedicated shared directory for a job_id
    Create the directory if it does not exist
    :param job_id: the job_id
    :return: the shared directory for the job_id
    :raises: SharePathInvalidError if the job_id is invalid
    """

    if is_valid_jobid(job_id):
        job_share_dir = os.path.realpath( os.path.join(pixyz_worker.config.share_dir, job_id) )

        #DMXDMX
        # Create the directory if it does not exist
        #if not os.path.exists(job_share_dir):
        #    os.makedirs(job_share_dir, exist_ok=True)
        
        return str(job_share_dir)
    else:
        raise SharePathInvalidError(f"Invalid job_id {job_id}")



def get_job_share_file_path(job_id, file_name='', directory=None, create_directory=True, check_if_exists=False):
    """
    Return the full path of a file in the shared directory for a job_id
    :param job_id: the job_id
    :param file_name: the file name or sub path
    :param directory: the directory where the file is located (ex: `inputs` or `outputs`)
    :param check_if_exists: if `True`, check that the file exists
    :return: the full path of the file
    :raises: SharePathInvalidError if the job_id is invalid
    :raises: SharePathNotFoundError if the file path is not found
    """

    job_shared_dir = get_job_share_dir(job_id)

    if directory is None:
        display_name = file_name
        base_directory = job_shared_dir
    else:
        base_directory = os.path.realpath( os.path.join(job_shared_dir, directory) )
        display_name = os.path.join(directory, file_name)

        # Check that the base directory is in the share job directory
        if not base_directory.startswith(job_shared_dir):
            raise SharePathInvalidError(f"Invalid directory '{directory}'")
        
        # Create the directory if needed
        if create_directory and not os.path.exists(base_directory):
            os.makedirs(base_directory, exist_ok=True)

    if file_name == '':
        return base_directory
    else:
        file_realpath = os.path.realpath( os.path.join(base_directory, file_name) )

        # check that the file is in the share job directory
        if not file_realpath.startswith(job_shared_dir):
            raise SharePathInvalidError(f"Invalid file path '{display_name}'")
        
        # check that the file exists if requested
        if check_if_exists and not os.path.exists(file_realpath):
            raise SharePathNotFoundError(f"File '{display_name}' not found")

        return file_realpath



def get_job_input_dir(job_id):
    """
    Return the dedicated input directory for a job_id
    Create the directory if it does not exist
    :param job_id: the job_id
    :return: the input directory for the job_id
    """

    return get_job_share_file_path(job_id, directory=job_input_dirname, create_directory=True)


def get_job_output_dir(job_id):
    """
    Return the dedicated output directory for a job_id
    Create the directory if it does not exist
    :param job_id: the job_id
    :return: the output directory for the job_id
    """

    return get_job_share_file_path(job_id, directory=job_output_dirname, create_directory=True, check_if_exists=True)



def get_job_input_dir_content(job_id):
    """
    Return the content of the input directory for a job_id
    :param job_id: the job_id
    :return: the list of files in the input directory
    """
    job_output_dir = get_job_input_dir(job_id)
    return os.listdir(job_output_dir)



def get_job_output_dir_content(job_id):
    """
    Return the content of the output directory for a job_id
    :param job_id: the job_id
    :return: the list of files in the output directory
    """
    job_output_dir = get_job_output_dir(job_id)
    return os.listdir(job_output_dir)



def get_job_input_file_path(job_id, file_name, check_if_exists=False):
    """
    Return the full path of a file in the input directory for a job_id
    :param job_id: the job_id
    :param file_name: the file name or sub path
    :param check_if_exists: if `True`, check that the file exists
    :return: the full path of the file
    :raises: SharePathInvalidError if the job_id is invalid
    :raises: SharePathNotFoundError if the file path is not found
    """
    return get_job_share_file_path(job_id, file_name, directory=job_input_dirname, check_if_exists=check_if_exists)

def get_job_output_file_path(job_id, file_name, check_if_exists=False):
    """
    Return the full path of a file in the output directory for a job_id
    :param job_id: the job_id
    :param file_name: the file name or sub path
    :param check_if_exists: if `True`, check that the file exists
    :return: the full path of the file
    :raises: SharePathInvalidError if the job_id is invalid
    :raises: SharePathNotFoundError if the file path is not found
    """
    return get_job_share_file_path(job_id, file_name, directory=job_output_dirname, check_if_exists=check_if_exists)



def get_job_archive_file_path(job_id, file_name, check_if_exists=False):
    """
    Return the full path of a file in the archive directory for a job_id
    :param job_id: the job_id
    :param file_name: the file name or sub path
    :param check_if_exists: if `True`, check that the file exists
    :return: the full path of the file
    :raises: SharePathInvalidError if the job_id is invalid
    :raises: SharePathNotFoundError if the file path is not found
    """
    return get_job_share_file_path(job_id, file_name, directory=job_archive_directory, check_if_exists=check_if_exists)



# TODO: deprecated



def get_share_glb_file(job_id):
    return get_share_file_for_job(job_id, suffix='.glb')


def get_share_upload_file(file_name):
    uuid_str = str(uuid.uuid4())
    return get_share_file_for_job(file_name, prefix=f"upload_{uuid_str}_")


def get_extract_path(job_id):
    return get_share_file_for_job(job_id, prefix=f"extract_")


def is_a_valid_input_directory(directory_path):
    from re import match
    real_path_directory = os.path.realpath(directory_path)
    return (os.path.exists(real_path_directory) and os.path.isdir(real_path_directory) and
            match(r'.*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/inputs$',
                  real_path_directory) is not None)


def is_a_valid_output_directory(directory_path):
    from re import match
    real_path_directory = os.path.realpath(directory_path)
    return (os.path.exists(real_path_directory) and os.path.isdir(real_path_directory) and
            match(r'.*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/outputs$',
                  real_path_directory) is not None)


def is_a_valid_job_id_directory(directory_path):
    from re import match
    real_path_directory = os.path.realpath(directory_path)
    return (os.path.exists(real_path_directory) and os.path.isdir(real_path_directory) and
            match(r'.*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
                  real_path_directory) is not None)

def cleanup_data_after_timeout(file_name, is_directory=False):
    """
    Delete a file after a timeout
    :param file_name: file to delete
    :param is_directory: True if the file is a directory, False otherwise
    :return: None
    """
    if not pixyz_worker.config.cleanup_enabled:
        return
    from pixyz_worker.tasks import cleanup_share_file
    eta = datetime.utcnow() + timedelta(seconds=pixyz_worker.config.cleanup_delay)

    inode_type = "directory" if is_directory else "file"

    logger.info(f"Scheduling a cleanup task for {inode_type} %s at %s", file_name, eta)
    return cleanup_share_file.apply_async(args=[file_name], kwargs={'is_directory': is_directory}, eta=eta)


def move_file_as_result_to_shared_storage(job_id, tmp_glb_file):
    # Move temp file to share storage
    dst_file = get_share_glb_file(job_id)
    shutil.copy2(tmp_glb_file, dst_file)
    os.chmod(dst_file, 0o644)
    os.remove(tmp_glb_file)


def get_first_3D_files_in_directory(directory_path):
    file_extensions = """PXZ 3DS ACIS SAT SAB DWG DXF WIRE FBX IPT IAM NWD NWC RVT RFA RCP RCS VPB CATPART
                      CATPRODUCT CATSHAPE CGR 3DXML ASM NEU PRT XAS XPR PVS PVZ CSB GLTF GLB GDS IFC IGS
                      IGES JT OBJ PRT X_B X_T P_T P_B XMT XMT_TXT XMT_BIN PDF PLMXML E57 PTS PTX PRC 3DM
                      RVM SKP ASM PAR PWD PSM SLDASM SLDPRT STP STEP STPZ STEPZ STPX STPXZ STL U3D USD USD
                      USDZ USDA USDC VDA WRL VRML""".split()
    for root, dirs, files in os.walk(directory_path):
        for file_name in files:
            if file_name.upper().endswith(tuple(file_extensions)):
                return os.path.join(root, file_name)
    return None


def get_filename_from_url(url):
    from urllib.parse import urlparse, parse_qs
    # Split the URL to extract the path
    parsed_url = urlparse(url)
    path = parsed_url.path
    filename = path.split("/")[-1]
    return filename


def download_file(url, destination):
    response = requests.get(url)
    if response.status_code == 200:
        with open(destination, 'wb') as file:
            file.write(response.content)
        logger.info(f"Downloaded {url} to {destination}")
    else:
        logger.error(f"Failed to download {url}. Status code: {response.status_code}")
        raise PixyzWebError(response.status_code, url, response.text)


def each(fn, items):
    for item in items:
        fn(item)


class PiXYZSession(object):
    """
    PiXYZ session class
    """

    def __init__(self, license:License):
        self.license = license

    def __enter__(self):
        self.initialize_at_start_if_needed(self.license)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_at_shutdown_if_needed(self.license)

    @staticmethod
    def initialize_at_start_if_needed(license:License):
        if license.is_acquire_at_start():
            # License is already acquire at start-up
            pass
        else:
            if not license.disable_pixyz:
                PiXYZSession.initialize(True)


    @staticmethod
    def release_at_shutdown_if_needed(license:License):
        if license.disable_pixyz:
            return
        if license.is_acquire_at_start():
            PiXYZSession.reset()
        else:
            PiXYZSession.release()

    @staticmethod
    def initialize_import():
        logger.info("Initialize pixyz session")
        import pxz
        pxz.initialize()
        from pxz import io, algo, scene, view, material, core, polygonal


    @staticmethod
    def initialize(mandatory=False):
        try:
            if os.getenv('PIXYZ_PYTHON_PATH', None) is not None:
                if not os.path.exists(os.getenv('PIXYZ_PYTHON_PATH')):
                    logger.fatal("PIXYZ_PYTHON_PATH environment variable is set but does not exist")
                    sys.exit(1)
                else:
                    sys.path.append(os.getenv('PIXYZ_PYTHON_PATH'))
            else:
                sys.path.append("/opt/pixyz")

            PiXYZSession.initialize_import()

        except ImportError as e:
            if mandatory:
                logger.fatal("PiXYZ module not found, cannot continue")
                raise e
            else:
                logger.warning("Pixyz module not found - Pixyz dataset optimization has been skipped...")

    @staticmethod
    def release():
        """
        Release the pixyz license
        """
        try:
            import pxz
            # usefull?
            pxz.get_current_session()
            pxz.release()
            logger.info("Pixyz session released")
        except:
            logger.warning("Unable to release pixyz, probably unexpected license allocation")

    @staticmethod
    def reset():
        """
        Reset the pixyz license
        """
        try:
            import pxz
            #usefull?
            pxz.get_current_session()
            pxz.core.resetSession()
            logger.info("Pixyz session reset")
        except:
            logger.warning("Unable to reset pixyz")


class TaskInfos(dict):
    def __init__(self, task):
        if isinstance(task, dict):
            super(TaskInfos, self).__init__(task)
        else:
            super(TaskInfos, self).__init__()
            self['task_id'] = task.request.id
            self['name'] = task.name
            self['args'] = task.request.args
            self['kwargs'] = task.request.kwargs
            self['queue'] = task.request.delivery_info['routing_key']
            self['max_retries'] = task.max_retries
            self['retries'] = task.request.retries

    @staticmethod
    def from_dict(d):
        return TaskInfos(d)


def pixyz_schedule(**kwargs_):
    """
    Decorator to select the queue to use for the function. This decorator does nothing, it is just a placeholder for
    api indication
    Args:
        queue_name: The name to the queue to use

    Returns:
        The function with given parameters
    """

    def decorator(f):
        def wrapper(*args, **kwargs):
            ready_job = []

            def process_job_list(pc_, r_):
                for job_id in r_.as_list():
                    if job_id in ready_job:
                        continue
                    task = AsyncResult(job_id)
                    if isinstance(task, AsyncResult):
                        if task.state in ('STARTED', 'RUNNING') or task.ready():
                            #logger.debug(f"Task {task.id} finished in state {task.state}, result=" + str(task.result))
                            pc_.progress_next(f"{task.id}", {'id': task.id, 'state': task.state, task.id: task.result})
                            ready_job.append(job_id)
                    else:
                        logger.error(f"Task {task.id} not return a asyncresult")
                time.sleep(0.1)
            from celery.result import AsyncResult
            if 'wait' in kwargs_ and kwargs_['wait']:
                timeout = kwargs_['timeout'] if 'timeout' in kwargs_ else None
                r = f(*args, **kwargs)
                if isinstance(r, AsyncResult):
                    pc = args[0]
                    pc.progress_set_total(len(r.as_list()))
                    while not r.ready():
                        process_job_list(pc, r)
                    process_job_list(pc, r)
                    with pc.allow_join_result():
                        return r.get(timeout=timeout)
                else:
                    logger.warning("The wait feature is enabled, but the function does not return an "
                                   "AsyncResult, cannot wait for the result")
            else:
                return f(*args, **kwargs)
        return wrapper

    return decorator


class SourceInspector(object):
    def __init__(self, source_file):
        self.tree = SourceInspector.load_tree(source_file)

    @staticmethod
    def load_tree(file):
        """
        Load the AST tree of a file
        Args:
            file: The file to load the AST tree from
        """
        with open(file, 'r') as f:
            return ast.parse(f.read())

    def is_function_exist(self, func_name):
        """
        Check if a function exist in the source
        Args:
            func_name: The name of the function to check
        Returns:
            True if the function exist, False otherwise
        """
        return any(isinstance(node, ast.FunctionDef) and node.name == func_name for node in self.tree.body)

    def get_pixyz_all_decorators_for_a_function(self, function_name, decorator_filter='pixyz_schedule'):
        """
        Get all the decorators for a function
        Args:
            function_name: The name of the function to get the decorators for
        Returns:
            The decorators for the function
        """
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return list(filter(lambda a: a.func.id == decorator_filter, node.decorator_list))
        return []

    def get_pixyz_decorator_for_a_function(self, function_name, decorator_filter='pixyz_schedule'):
        """
        Get the decorator for a function
        Args:
            function_name: The name of the function to get the decorator for
        Returns:
            The decorator for the function
        """
        l = self.get_pixyz_all_decorators_for_a_function(function_name, decorator_filter)
        if l:
            return l[-1]
        else:
            return None

    @staticmethod
    def get_decorator_kwargs(decorator: ast.Call):
        """
        Get the kwargs of a decorator
        Args:
            decorator: The decorator to get the kwargs from
        Returns:
            The kwargs of the decorator
        """
        ret = {}
        for keyword in decorator.keywords:
            if (isinstance(keyword.value, ast.Constant) or isinstance(keyword.value, ast.Str) or
                    isinstance(keyword.value, ast.Num)):
                ret[keyword.arg] = keyword.value.value
            else:
                logger.warning(f"Unsupported keyword value type {type(keyword.value)} for pixyz_schedule decorator detection")
        # The wait process will stay on control queue
        if 'wait' in ret and ret['wait'] and 'queue' not in ret:
            ret['queue'] = 'control'
        return ret

    def get_pixyz_decorator_kwargs_for_a_function(self, function_name, decorator_filter='pixyz_schedule'):
        """
        Get the kwargs of the decorator for a function
        Args:
            function_name: The name of the function to get the decorator for
        Returns:
            The kwargs of the decorator for the function
        """
        decorator = self.get_pixyz_decorator_for_a_function(function_name, decorator_filter)
        if decorator:
            return self.get_decorator_kwargs(decorator)
        else:
            return {}

