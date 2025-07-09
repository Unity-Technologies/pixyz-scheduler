#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import os
from celery import Celery
from typing import List
from datetime import datetime, timezone
from .share import get_logger
from kombu.utils.json import register_type

app = Celery()
app.config_from_object('pixyz_worker.settings')

logger = get_logger('pixyz_worker.progress')

__all__ = ['TaskProgress', 'ProgressCallBack']


class ProgressCallBack(object):
    def start(self):
        raise NotImplementedError()

    def next(self, info=None, **kwargs):
        raise NotImplementedError()

    def current(self, pct, **kwargs):
        raise NotImplementedError()


class CeleryAppSerializer(object):
    @staticmethod
    def app_from_celery_conf(conf):
        app = Celery()
        app.conf = conf
        return app


class TaskProgress(ProgressCallBack):
    def __init__(self, celery_self, task_id, step_total=1, time_request=None):
        self.celery_self = celery_self
        self.retry_count = 0  # number of retries

        self.task_id = task_id
        self.step_total = step_total

        self.step_infos = []

        self.time_request = self.get_default_datetime(time_request)
        self.time_started = datetime.now(timezone.utc)
        self.time_stopped = None
        self.step_start_time = None
        self.start()
    
    @property
    def step_total(self):
        return self._step_total

    @step_total.setter
    def step_total(self, value):
        self._step_total = value if value > 0 else 1

    @property
    def step_current(self):
        return len(self.step_infos)

    @property
    def percent(self):
        step_ended = self.step_current - 1 if self.step_current > 0 else 0
        return int(step_ended / self.step_total * 100.0)

    @property
    def timing_info(self):
        return self.get_time_info()

    def serialize(self):
        return {
            'celery_self': None,
            'retry_count': self.retry_count,
            'task_id': self.task_id,
            'step_total': self.step_total,
            'step_infos': self.step_infos,
            'step_start_time': self.step_start_time,
            'time_request': self.time_request,
            'time_started': self.time_started,
            'time_stopped': self.time_stopped
        }

    def update(self, progress):
        self.retry_count = progress.retry_count
        self.step_total = progress.step_total
        self.step_infos = progress.step_infos
        self.step_start_time = progress.step_start_time
        self.time_request = progress.time_request
        self.time_started = progress.time_started
        self.time_stopped = progress.time_stopped

    # Create TaskProgress Object
    @staticmethod
    def builder(d):
        if 'celery_self' not in d:
            d['celery_self'] = None
        tp = TaskProgress(d['celery_self'], d['task_id'], d['step_total'], d['time_request'])
        tp.retry_count = d['retry_count']
        tp.step_total = d['step_total']
        tp.step_infos = d['step_infos']
        tp.step_start_time = d['step_start_time']
        tp.time_started = d['time_started']
        tp.time_stopped = d['time_stopped']
        return tp

    def set_total(self, total):
        self.step_total = total

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    @staticmethod
    def get_default_datetime(time_request):
        if time_request is None:
            logger.warning("time_request is None, inaccurate pickup of the job")
            return datetime(1, 1, 1, 0, 0, 0)
        else:
            if isinstance(time_request, str):
                return datetime.fromtimestamp(time_request, timezone.utc)
            else:
                return time_request

    def _add_step_info(self, step_info):
        current_time = time.perf_counter()

        if len(self.step_infos) > 0:
            # Compute the duration of the previous step
            self.step_infos[-1]['duration'] = current_time - self.step_start_time

        if step_info != 'end':
            self.step_start_time = current_time
            self.step_infos.append({'duration': -1, 'info': step_info})

        # save task state
        self.store(progress=self.percent, steps=self.step_infos)

    def start(self):
        self.time_started = datetime.now(timezone.utc)
        self.store(time_info=self.get_time_info())

    @staticmethod
    def get_max_memory_usage():
        pid = os.getpid()
        try:
            with open(f'/proc/{pid}/status') as status_file:
                for line in status_file:
                    if line.startswith('VmPeak:'):
                        return int(line.split()[1]) / 1024.0
        except FileNotFoundError:
            print(f"Process with PID {pid} not found.")
        return None
    
    def get_time_info(self):
        return {
            'request': self.time_request.isoformat() if self.time_request else None,
            'started': self.time_started.isoformat() if self.time_started else None,
            'stopped': self.time_stopped.isoformat() if self.time_stopped else None,
            #'memory': self.get_max_memory_usage()
        }
    
    def _get_task_meta(self):
        if self.celery_self is not None:
            state_meta = self.celery_self.backend.get_task_meta(self.task_id, cache=False)

            if 'result' in state_meta and state_meta['result'] is not None:
                # remove 'pid' & 'hostname'
                if 'pid' in state_meta['result']:
                    del state_meta['result']['pid']
                if 'hostname' in state_meta['result']:
                    del state_meta['result']['hostname']
                return state_meta['result']
        return {}

    def output(self, output: None):
        return self.store(result=output)

    # grab the task state meta and update it with the new values (formerly `update_task_state_meta`)
    def store(self, **kwargs):
        meta = self._get_task_meta()

        if meta is not None:
            if len(kwargs) > 0:
                meta.update(**kwargs)
                ##DEBUG## logger.info(f"NEW TASK META: {meta}")
                if self.celery_self is not None:
                    self.celery_self.update_state(task_id=self.task_id, state='RUNNING', meta=meta)
            return meta
        return {}

    def retry(self, retry_count=None):
        self.retry_count = retry_count if retry_count is not None else self.retry_count + 1
        self.store(retry=self.retry_count)

    # Compute progress and add kwargs to meta
    def next(self, step_info=None, output=None, **kwargs):
        if step_info is None:
            step_info = f"step {self.step_current}"

        # Store steps
        self._add_step_info(step_info)
        logger.info(f"[task step {self.step_current}/{self.step_total}] {step_info}") # log after record

        # Update meta with extra data
        extra_data = {}
        if output is not None:
            extra_data['output'] = output

        if len(kwargs) > 0:
            extra_data.update(**kwargs)

        if len(extra_data) > 0:
            self.store(**extra_data)

    # @staticmethod
    # def serialize_steps(step_infos):
    #     return {index: value for index, value in enumerate(step_infos)}
    #
    # @staticmethod
    # def build_steps(steps: dict):
    #     return [value for key, value in sorted(steps.items())]

    # Must be called from ProgramContext `pc.progress_stop()``
    def stop(self, **kwargs):
        import time
        # Task state here is still running: self.celery_self.backend.get_status(self.celery_self.request.id)

        # save last step timing and time_stopped
        self._add_step_info("end")
        self.time_stopped = datetime.now(timezone.utc)
        self.store(time_info=self.get_time_info(), progress=100, **kwargs) # TODO: les 2 passent; le progress reste, pas le time_info # TRISTESSE
        
        
## To use inception inside inception, you must serialize celery conf and the Settings class itself

register_type(TaskProgress, 'TaskProgress', lambda a: a.serialize(), lambda a: TaskProgress.builder(a))


### Test
def _test():
    tp = TaskProgress(None, 3, datetime.now(timezone.utc))
    tp.next("step 0")
    time.sleep(1)
    tp.next("step 1")
    time.sleep(2)
    tp.next("step 3")
    time.sleep(3)
    tp.stop()
    print(tp.get_time_info())
    print("finished")


def test_serialization():
    pass


if __name__ == '__main__':
    test_serialization()
