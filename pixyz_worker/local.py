#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__all__ = ['LocalPixyzTask', 'AsyncResultLocal', 'allow_join_result']
import logging
import datetime

try:
    import pxz
    from pxz import core, scene, polygonal, algo, material, view
except ModuleNotFoundError:
    pass


class LocalPixyzTask(object):
    """
    Replace the return of subtask_async function
    Run synchronously, in a new pixyz session, the entrypoint function with the given params
    and store the result of the operation
    """
    def _init_pixyz(self):
        try:
            # I must reimport here to avoid error (weird)
            import pxz
            self.calling_session = pxz.get_current_session()
            self.logger.info("Initialize pixyz session")
            self.new_session = pxz.initialize()
        except (ModuleNotFoundError, AttributeError, NameError, SystemError) as e:
            self.logger.error("Pixyz not found, please initialize it before execute local tasks")

    def _release_pixyz(self):
        try:
            # I must reimport here to avoid error (weird)
            import pxz
            pxz.release(self.new_session)
            pxz.set_current_session(self.calling_session)
        except (ModuleNotFoundError, AttributeError, NameError, SystemError):
            self.logger.error("Pixyz not found, please release it before execute local tasks")

    def __init__(self, entrypoint, pc, params=None):
        from pixyz_worker.extcode import ExternalPythonCode
        if params is None:
            params = {}
        pc_task = pc.clone(entrypoint=entrypoint, params=params)
        func = ExternalPythonCode(pc_task['script'])
        self.logger = logging.getLogger('pixyz_worker.local.LocalPixyzTask')
        self._init_pixyz()
        self.ret = func.execute(pc_task)
        self._release_pixyz()

        self.task_id = self
        self.state = "READY"

    @staticmethod
    def from_commandline(script, output_path, entrypoint, params=None, input_file=None):
        from pixyz_worker.share import PiXYZSession
        from pixyz_worker.pc import ProgramContext
        from pixyz_worker.progress import TaskProgress
        PiXYZSession.initialize()
        pc = ProgramContext.from_local(script, input_file, output_path)
        pc['entrypoint'] = entrypoint
        pc['progress'] = TaskProgress(None, "00000000-0000-0000-0000-000000000000",0,
                                      datetime.datetime.now(datetime.timezone.utc))
        lpt=LocalPixyzTask(entrypoint, pc, params)
        return lpt.ret

    def get(self):
        return self.ret

    def ready(self):
        return True


class AsyncResultLocal:
    """
    Replace the AsyncResult class from celery that is constructed from the task_id
    It only stores the task to retrieve its return
    """

    def __init__(self, id, backend=None,
                 task_name=None,            # deprecated
                 app=None, parent=None):
        self.task = id
        self.task_id = id
        self.state = "READY"

    def get(self):
        return self.task.ret

    def ready(self):
        return self.task.ready


class allow_join_result(object):
    """
    Replace allow_join_result() from celery that is used to allow the use of .get() on tasks
    """

    def __enter__(self):
        return True

    def __exit__(self, exc_type, exc_val, exc_tb):
        return
