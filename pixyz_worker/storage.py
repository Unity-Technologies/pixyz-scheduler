#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import uuid
import os
import shutil
from tempfile import TemporaryDirectory
from .share import *
from .progress import *
from .exception import *

__all__ = ['StorageOutputManager', 'FileInputTemporary', 'StorageSharedManager', 'StorageTemporaryManager',
           'ExecuteIfEnabled']


class StorageDirectorySourceInterface(object):
    def __init__(self, directory):
        self.directory = directory
        self.logger = get_logger('pixyz_worker.storage.StorageDirectorySourceInterface')

    def get_full_output_filename(self, basename: str):
        return os.path.join(self.directory, basename)

    def cleanup(self):
        raise NotImplementedError("This method must be implemented")

    def create_directory(self):
        raise NotImplementedError("This method must be implemented")

    def __enter__(self):
        self.logger.debug(f"Entering to {self.__class__.__name__} context {self.directory}")
        self.create_directory()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.logger.debug(f"Exiting from {self.__class__.__name__} context {self.directory}, cleanup planned")
        self.cleanup()


class StorageSharedManager(StorageDirectorySourceInterface):
    """
    Storage on shared directory
    """
    def __init__(self, job_id):
        self.sanity_check_or_raise(job_id)
        super(StorageSharedManager, self).__init__(get_job_output_dir(job_id))

    @staticmethod
    def sanity_check_or_raise(job_id):
        # Checking if job_id is a valid uuid4 is important because it is used to create and delete the directory
        if not StorageSharedManager.is_valid_uuid4(job_id):
            raise ValueError(f"Invalid job_id {job_id}")

    @staticmethod
    def is_valid_uuid4(s):
        try:
            uuid_obj = uuid.UUID(s, version=4)
            return str(uuid_obj) == s
        except ValueError:
            return False

    def create_directory(self):
        os.makedirs(self.directory, exist_ok=True)
        if self.directory is not None:
            cleanup_data_after_timeout(self.directory, is_directory=True)

    def cleanup(self):
        # Here we don't cleanup because customer need to get the outputs and you must scheduler a cleanup when the job is created
        # because in case of failure the job directory will not be deleted
        pass



class StorageTemporaryManager(StorageDirectorySourceInterface):
    """
    Storage on temporary directory
    """
    def __init__(self):
        self.temp_dir = TemporaryDirectory()
        super(StorageTemporaryManager, self).__init__(self.temp_dir.name)

    def create_directory(self):
        pass

    def cleanup(self):
        self.temp_dir.cleanup()


class StorageOutputManager(StorageSharedManager):
    """
    Storage on shared directory
    """
    def __init__(self, job_id):
        self.sanity_check_or_raise(job_id)
        basedir = get_job_share_dir(job_id)
        self.output_dir = os.path.join(basedir, 'outputs')
        super(StorageSharedManager, self).__init__(basedir)

    def create_directory(self):
        # Force parent call that cleanup the directory
        super(StorageOutputManager, self).create_directory()
        os.makedirs(os.path.join(self.directory, 'outputs'), exist_ok=True)



class FileInputTemporary(StorageTemporaryManager):
    def __init__(self, filename_in: str, progress: TaskProgress = None, root_file: str = None):
        self.filename_in = filename_in
        self.root_file = root_file
        self.progress = progress
        self.file = None
        self.sanity_check(root_file)
        super(FileInputTemporary, self).__init__()

    @staticmethod
    def sanity_check(root_file):
        if root_file is not None and '..' in root_file:
            raise PixyzSecurityViolation(f"Your root_file contains invalid characters: {root_file}")

    @staticmethod
    def is_an_archive(filename):
        return filename.endswith(".zip") or filename.endswith(".tar.gz")

    def progress_start(self):
        if self.progress is not None:
            self.progress.start()

    def progress_next(self, info=None, output=None, **kwargs):
        if self.progress is not None:
            self.progress.next(info, output, **kwargs)

    def create(self):
        # Nothing to do if filename_in is None
        if self.filename_in is None:
            return

        if not os.path.exists(self.filename_in):
            raise InternalError(f"File {self.filename_in} not found on the shared storage")

        self.progress_start()
        # Check if filename extension is an archive file
        if self.is_an_archive(self.filename_in):
            # Extract archive file/ Keep create_directory because it can be used outside an with block
            self.create_directory()
            self.logger.debug(f"Extract archive {self.filename_in} to {self.directory}")
            self.progress_next(f"Extracting archive")
            shutil.unpack_archive(self.filename_in, self.directory)

            # Try to solve the root file automatically
            if self.root_file is None:
                self.logger.debug(f"No root file specified, auto-searching ON")
                targeted_file_name = get_first_3D_files_in_directory(self.directory)
            else:
                self.logger.debug(f"root file specified, auto-searching OFF")
                targeted_file_name = os.path.join(self.directory, self.root_file)

            # Last check if file exist
            if not os.path.exists(targeted_file_name):
                raise PixyzFileNotFound(f"The 3D file was NOT found in {self.filename_in}")
            else:
                self.logger.debug(f"Found 3D file {targeted_file_name} in {self.filename_in}")
        else:
            targeted_file_name = self.filename_in

        self.logger.info(f"Using {targeted_file_name} as input file")
        self.file = targeted_file_name

    def __enter__(self):
        self.create()
        super(FileInputTemporary, self).__enter__()
        return self


class ExecuteIfEnabled(object):
    def __init__(self, enter_class, enabled=True):
        self.enter_class = enter_class
        self.enabled = enabled

    def __getattr__(self, item):
        return self.enter_class.__getattr__(item)

    # Never enable setattr itself to avoid infinite loop
    # def __setattr__(self, key, value):
    #     print("setattr")
    #     return self.enter_class.__setattr__(key, value)

    def __call__(self, *args, **kwargs):
        return self.enter_class.__call__(*args, **kwargs)

    def __enter__(self):
        if self.enabled:
            return self.enter_class.__enter__()
        else:
            return self.enter_class

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.enabled:
            self.enter_class.__exit__(exc_type, exc_val, exc_tb)
