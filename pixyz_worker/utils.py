#!/usr/bin/env python
# -*- coding: utf-8 -*-
# insert function to check if task is already running or not
from pixyz_worker import tasks
from celery.states import UNREADY_STATES, SUCCESS
from celery.utils.graph import DependencyGraph, GraphFormatter
from collections import deque
from celery.result import AsyncResult, GroupResult, result_from_tuple
from datetime import datetime
import os
from pixyz_worker.share import get_job_share_file_path
from pixyz_worker.exception import DiskStateAlreadyExists

__all__ = ['TasksUtils', 'CeleryBackendResult', 'DiskAsyncState']


class DiskAsyncState(object):
    def __init__(self, task_id, state_name, ttl=3600):
        self.task_id = task_id
        self.state_name = state_name
        self.ttl = ttl
        self.registration_file = DiskAsyncState.get_state_file(task_id, state_name)

    @staticmethod
    def get_state_file(task_id, state_name):
        return get_job_share_file_path(task_id, file_name=f".{state_name}.state", directory="states", create_directory=True)

    @staticmethod
    def is_registered(task_id, state_name):
        return os.path.exists(DiskAsyncState.get_state_file(task_id, state_name))

    def get_date_in_state_file(self):
        try:
            with open(self.registration_file, 'r') as f:
                date = f.read()
                return datetime.fromisoformat(date)
        except ValueError:
            return None

    def set_date_in_state_file(self):
        with open(self.registration_file, 'w') as f:
            f.write(datetime.utcnow().isoformat())
            f.flush()
            os.fsync(f.fileno())
    def is_expired(self):
        date = self.get_date_in_state_file()
        if date is None:
            return True
        else:
            return (datetime.utcnow() - date).total_seconds() > self.ttl

    def register(self):
        if os.path.exists(self.registration_file) and not self.is_expired():
            raise DiskStateAlreadyExists(f"State {self.state_name} already exists for task {self.task_id}"
                                         f"(ttl={self.ttl})")
        else:
            self.set_date_in_state_file()

    def unregistered(self):
        if os.path.exists(self.registration_file):
            os.remove(self.registration_file)

    def __enter__(self):
        self.register()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unregistered()


class CeleryBackendResult(object):
    def __init__(self, meta, task_id=None):
        #self.meta = meta
        self.id = meta.get('task_id', None)
        self.status = meta['status']
        self.is_parent = False if 'parent_id' in meta else False
        self.parent = meta.get('parent_id', None)
        if self.parent is not None:
            self.parent = CeleryBackendResult.from_backend(self.parent)
        self.children = meta.get('children', [])
        if self.children:
            self.children = [result_from_tuple(group, app=tasks.app) for group in self.children]
        self.is_in_group = True if 'group_id' in meta else False
        self.group = meta.get('group_id', None)



    @staticmethod
    def from_backend(task_id):
        meta = tasks.app.backend.get_task_meta(task_id)
        # GroupResult
        if isinstance(meta, list):
            return [result_from_tuple(group, app=tasks.app) for group in meta]
        else:
            return CeleryBackendResult(meta, task_id)

    @staticmethod
    def create_dag(task, prev=None, depth=0):
        dep = []
        if prev is None:
            prev = []

        if isinstance(task, GroupResult):
            for subtask in task:
                dep.append(CeleryBackendResult.create_dag(subtask, prev, depth))
        else:
            pass

        return DependencyGraph(it=CeleryBackendResult.from_backend(task_id))

    def __hash__(self):
        """`hash(self) -> hash(self.id)`."""
        return hash(self.id)

    def __repr__(self):
        return f'<CeleryBackendResult({self.id})[{self.status}] [<{self.parent}] :{self.children}]>'



class TasksUtils(object):
    @staticmethod
    def get_all_tasks_status(task_id):
        task = CeleryBackendResult.from_backend(task_id)

        tasks_status = [task.status]
        if not task.is_parent:
            tasks_status.append(CeleryBackendResult.from_backend(task.parent).status)
        if task.children:
            tasks_status = tasks_status + [child.status for child in task.children]
        return tasks_status

    @staticmethod
    def get_root_task(task_id):
        task = CeleryBackendResult.from_backend(task_id)
        if task.is_parent:
            return task
        else:
            return TasksUtils.get_root_task(task.parent)

    @staticmethod
    def get_task_dag(task_id, formatter=None):
        def iterdeps(task):
            stack = deque([(task.parent, task)])
            while stack:
                parent, node = stack.popleft()
                yield parent, node
                stack.extend((node, child) for child in node.children or [])

        # DMX: Code from result.py in celery but patched for partial result
        task = CeleryBackendResult.from_backend(task_id)
        graph = DependencyGraph(
            formatter=formatter or GraphFormatter(root=task, shape='oval'),
        )
        for parent, node in iterdeps(task):
            graph.add_arc(node)
            if parent:
                graph.add_edge(parent, node)
        return graph

    @staticmethod
    def is_tasks_running(task_id):
        return any(task_state in UNREADY_STATES for task_state in TasksUtils.get_all_tasks_status(task_id))

    @staticmethod
    def is_tasks_success(task_id):
        return all(task_state == SUCCESS for task_state in TasksUtils.get_all_tasks_status(task_id))
