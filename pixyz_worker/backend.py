#!/usr/bin/env python
# -*- coding: utf-8 -*-
from celery.backends.base import KeyValueStoreBackend
from celery.utils.graph import DependencyGraph
import requests
from urllib.parse import urlparse, urljoin
from .share import get_logger
from time import sleep
from celery.app.backends import BACKEND_ALIASES

__all__ = ['PiXYZApiBackend']
BACKEND_ALIASES.update({'http': 'pixyz_worker.backend.PiXYZApiBackend', 'https': 'pixyz_worker.backend.PiXYZApiBackend'})


class PixyzApiBackend(KeyValueStoreBackend):
    def __init__(self, **kwargs):
        super(PixyzApiBackend, self).__init__(**kwargs)
        self.logger = get_logger('pixyz_worker.backend')
        url = kwargs.get('url', None)
        if url is None:
            raise ValueError("url is required")
        parsed_url = urlparse(url)
        # Extract components
        scheme = parsed_url.scheme
        netloc = parsed_url.netloc
        path = parsed_url.path
        if '@' in netloc:
            credentials, netloc = netloc.split('@', 1)
            if ':' in credentials:
                login, password = credentials.split(':', 1)
            else:
                password = None
        else:
            login = None
            password = None
        self.url = f"{scheme}://{netloc}"
        if path:
            self.url = urljoin(self.url, path)
        self.token = password

    @staticmethod
    def get_headers(token=None):
        if token is not None:
            return {'x-api-key': token}
        else:
            return {}

    def get_job_status(self, url, job_id, watch=False, batch=False, token=None):
        headers = self.get_headers(token)
        full_url = f'{url}/backend/get_task_meta/{job_id}'
        res = requests.get(full_url, headers=headers)
        res.raise_for_status()
        res_dict = res.json()
        if res.status_code not in (200, 202):
            self.logger.error(f"Invalid return code from job status API({url}):" + str(res.status_code))
        else:
            # check if status/progress/error has changed
            while res_dict['status'] not in ['SUCCESS', 'FAILURE', 'REVOKED']:
                res = requests.get(full_url, headers=headers)
                res.raise_for_status()
                res_dict = res.json()
                sleep(0.5)

            # # check if error
            # if res_dict['error'] is not None:
            #     self.logger.error(f"{full_url} : {res_dict['error']}")
        return res_dict

    def get(self, key):
        ret = self.get_job_status(self.url, key, token=self.token)
        return ret

    def get_task_meta(self, task_id, cache=True):
        return self.get(task_id)

    def _get_task_meta(self, task_id, cache=True):
        return self.get(task_id)

    def _get_task_meta_for(self, task_id, cache=True):
        return self.get(task_id)

    def get_task_meta_for(self, task_id, cache=True):
        return self.get(task_id)
