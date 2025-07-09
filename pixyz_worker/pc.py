#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__all__ = ['ProgramContext']

import logging
from datetime import datetime
from pixyz_worker.exception import *
import os
from kombu.utils.json import register_type


class ProgramContext(dict):
    def __init__(self, **kwargs):
        self.logger = logging.getLogger('pixyz_worker.pc.ProgramContext')
        self.logger.debug(f"Creating FunctionParameters with {kwargs}")
        super(ProgramContext, self).__init__(**kwargs)
        self.set_mandatory_parameters()

    def __str__(self):
        safe_params = {k: v for k, v in self.items() if k not in ['task', 'progress']}
        return f"ProgramContext<{safe_params}>"

    def set_mandatory_parameters(self):
        mandatory_parameters = {'compute_only': False,    # Don't create a shared space, just compute
                                'data': None,             # No data file as input
                                'tmp': True,              # Create a temporary directory if needed
                                'root_file': None,        # No root file
                                'is_local': False,        # By default, the task is not local
                                'entrypoint': 'main',     # Default entrypoint
                                'time_request': datetime.utcnow(),  # Request time
                                'raw': False,             # No raw data useful for single task, raw data is used for chain
                                }
        for key, value in mandatory_parameters.items():
            if key not in self:
                self[key] = value


    def progress_set_total(self, total: int):
        if 'progress' in self:
            self['progress'].set_total(total)
        else:
            pass

    def progress_next(self, info: str = None, output = None):
        if 'progress' in self:
            self['progress'].next(info)
        else:
            print(info)

    def progress_stop(self):
        if 'progress' in self:
            self['progress'].stop()
        else:
            pass

    def progress_output(self, ret):
        if 'progress' in self and self['raw'] is False:
            return self['progress'].output(ret)
        else:
            return ret

    def clone(self, **kwargs):
        pc = ProgramContext(**self)
        if 'time_request' not in kwargs:
            kwargs['time_request'] = datetime.utcnow()

        pc.update(**kwargs)

        # task is not json serializable and it must be removed
        if 'task' in pc:
            del pc['task']

        return pc

    def serialize(self):
        return dict(self)

    @staticmethod
    def builder(d):
        return ProgramContext(**d)

    def update(self, **kwargs):
        """
        Update the current object with the given parameters, ensure that is done by reference
        Args:
            **kwargs:

        Returns:
            self
        """
        for key, value in kwargs.items():
            if key in self and hasattr(value, 'update'):
                self[key].update(value)
            else:
                self[key] = value
        return self

    def get_output_dir(self, filename: str = None):
        if 'output_dir' in self:
            if os.path.isdir(self['output_dir']):
                if filename is not None:
                    return os.path.join(self['output_dir'], filename)
                else:
                    return self['output_dir']
            else:
                raise PixyzSharedDirectoryNotFound(f"output_dir {self['output_dir']} is not found, please "
                                                   f"check backend purge configuration or shared storage")
        else:
            raise PixyzSharedDirectoryNotFound(f"No shared_file_path {self['output_dir']} provided by the caller")

    def _get_dict_value(self, key: str, default=None):
        if key in self:
            return self[key]
        else:
            return default

    def get_input_dir(self, filename: str = None):
        if 'input_dir' in self:
            if os.path.isdir(self['input_dir']):
                if filename is not None:
                    return os.path.join(self['input_dir'], filename)
                else:
                    return self['input_dir']
            else:
                raise PixyzSharedDirectoryNotFound(f"input_dir {self['input_dir']} is not found, please "
                                                   f"check backend purge configuration or shared storage")
        else:
            raise PixyzSharedDirectoryNotFound(f"No shared_file_path {self['input_dir']} provided by the caller")

    def get_input_file(self):
        try:
            return self['input_file']
        except KeyError:
            raise ValueError("No input_file in ProgramContext")

    def is_compute_only(self):
        return self._get_dict_value('compute_only', False)

    def is_need_a_tmp(self):
        return self._get_dict_value('tmp', True)

    def is_local(self):
        return self._get_dict_value('is_local', False)

    @staticmethod
    def from_local(script, input_path=None, output_dir=None):

        return ProgramContext(script=script, input_file=input_path, output_dir=output_dir,
                              is_local=True)

    def AsyncResult(self, id, backend=None,
                 task_name=None,            # deprecated
                 app=None, parent=None):
        if self.is_local():
            from pixyz_worker.local import AsyncResultLocal
            return AsyncResultLocal(id, backend, task_name, app, parent)
        else:
            from celery.result import AsyncResult
            return AsyncResult(id, backend, task_name, app, parent)

    def allow_join_result(self):
        if self.is_local():
            from pixyz_worker.local import allow_join_result
            return allow_join_result()
        else:
            from celery.result import allow_join_result
            return allow_join_result()

    def execute(self, params=None, **kwargs):
        if self.is_local():
            self.logger.debug("Creating a LOCAL task")
            from pixyz_worker.local import LocalPixyzTask
            return LocalPixyzTask(self['entrypoint'], self, params)
        else:
            self.logger.debug("Creating a REMOTE task")
            from pixyz_worker.tasks import pixyz_execute
            pc = self.clone()
            return pixyz_execute.apply_async(args=(params, pc), **kwargs)


register_type(ProgramContext, 'ProgramContext', lambda a: a.serialize(), lambda b: ProgramContext.builder(b))