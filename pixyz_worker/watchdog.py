#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import threading
import tempfile
import time
import json

from celery import Celery
from celery.result import AsyncResult
import pixyz_worker
from pixyz_worker.share import get_logger, TaskInfos

app = Celery()
app.config_from_object('pixyz_worker.settings')

__all__ = ['WatchdogByFileHandler', 'TasksWatchdog']

logger = get_logger('pixyz_worker.watchdog')


class TasksWatchdog(object):
    count = 0

    @staticmethod
    def is_time_to_shutdown():
        if pixyz_worker.config.max_solo_tasks != 0 and TasksWatchdog.count >= pixyz_worker.config.max_solo_tasks:
            return True
        else:
            TasksWatchdog.count = TasksWatchdog.count + 1
            return False


class CeleryMemoryWatchdog(threading.Thread):
    def __init__(self, pid, job_id, celery, max_memory_mb, delay=1):
        threading.Thread.__init__(self)
        self.pid = pid
        self.max_memory_mb = max_memory_mb
        self.job_id = job_id
        self.celery = celery
        self.delay = delay
        self.stop_event = threading.Event()

    def get_rss(self, pid):
        stat_file_path = f"/proc/{pid}/stat"

        try:
            # Read the content of the stat file
            with open(stat_file_path, 'r') as stat_file:
                # Split the content into fields
                stat_fields = stat_file.read().split()

                # RSS value is the 24th field
                rss_value = int(stat_fields[23])

                # Convert from pages to kilobytes
                rss_kb = rss_value * 4  # Assuming the page size is 4KB

                return int(rss_kb / 1024)
        except FileNotFoundError:
            print(f"Error: Process with PID {pid} not found.")
            return None
        except Exception as e:
            print(f"Error reading RSS for PID {pid}: {str(e)}")
            return None

    def kill(self):
        print(f"Killing process for job_id={self.job_id}")
        self.stop()
        self.celery.update_state(state='FAILURE', task_id=self.job_id, meta={'exc': "Out of memory", 'exc_type': "MemoryError"})
        self.celery.send_event('task-end', task_id=self.job_id)
        #ar = AsyncResult(self.job_id)
        #ar.revoke(terminate=True, signal='SIGKILL')

        os.kill(os.getpid(), 9)

    def stop(self):
        print("Stopping watchdog")
        self.stop_event.set()

    def run(self):
        print("Starting watchdog")
        out_of_memory = False
        while not self.stop_event.is_set():
            rss_value = self.get_rss(self.pid)
            print("rss_value=" + str(rss_value) + " MB")
            if rss_value is not None:
                if rss_value > self.max_memory_mb:
                    self.kill()
                    return True
                    # raise MemoryError(f"Out of memory: you have reach the maximum capacity "
                    #                   f"{rss_value} > {self.max_memory_mb} MB")
            if not self.stop_event.is_set():
                time.sleep(self.delay)
        return False


class WatchdogMemoryManager(object):
    def __init__(self, celery, max_memory_mb):
        print(celery)
        print(celery.request.id)
        self.thread = CeleryMemoryWatchdog(os.getpid(), celery.request.id, celery, max_memory_mb)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.thread.stop()
        self.thread.join()


class WatchdogByFileHandler(object):
    tmp_file = os.path.join(tempfile.gettempdir(), 'latest_task_id')

    @staticmethod
    def get_latest_task_info():
        try:
            with open(WatchdogByFileHandler.tmp_file, 'r') as f:
                task_info = TaskInfos(json.loads(f.read()))
                logger.debug(f"Recovering task: {task_info}")
                return task_info
        except FileNotFoundError:
            logger.warning(f"File {WatchdogByFileHandler.tmp_file} not found")
            return None

    @staticmethod
    def set_latest_task_info(task):
        task_serialization = json.dumps(TaskInfos(task), default=str)
        logger.debug(f"Serializing task for recovery: {task_serialization}")
        with open(WatchdogByFileHandler.tmp_file, 'w') as f:
            f.write(task_serialization)

    @staticmethod
    def clear_latest_task_id(first_time=False):
        try:
            logger.debug(f"Removing file {WatchdogByFileHandler.tmp_file}")
            os.remove(WatchdogByFileHandler.tmp_file)
        except FileNotFoundError:
            if not first_time:
                logger.warning(f"File {WatchdogByFileHandler.tmp_file} not found")
        except Exception as e:
            logger.warning(f"Unrecoverable error in clear_latest_task_id: {str(e)}")


def main():
    try:
        logger.info("Starting watchdog recovery")
        task = WatchdogByFileHandler.get_latest_task_info()
        if task is not None:
            task_id = task['task_id']
            if task_id is None:
                logger.warning("No task info found, nothing to do")
                return
        else:
            logger.warning("No task info found, nothing to do")
            return

        logger.info(f"Mark {task_id} as failed...")

        # Update status from the AsyncResult by connecting directly to the backend
        ar = AsyncResult(task_id, app=app)
        failure_meta_dict = {'exc': str("SystemError: Not enough memory or segfault"), 'exc_type': SystemError.__name__,
                             'exc_message': str("SystemError: Not enough memory or segfault ({task})")}
        app.backend.store_result(task_id, failure_meta_dict, state='FAILURE', meta=failure_meta_dict)

        #app.tasks.send_event('task-failed', task_id=task_id, retry=False)
        #app.backend.mark_as_failure(task_id, "Out of memory or segfault", "MemoryError")
        # if task['queue'] == 'gpu':
        #     result = app.send_task(**task)
        # else:
        ar.revoke()
        logger.info(f"{task_id} marked as failed: done")
    except FileNotFoundError:
        logger.warning("No file task found, nothing to do")


if __name__ == '__main__':
    main()
