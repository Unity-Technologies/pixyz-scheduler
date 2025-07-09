#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)

sys.path.append(os.path.realpath(os.path.join(os.path.dirname(__name__), '..')))
from celery import Celery

app = Celery(include=['pixyz_worker.tasks'])
app.config_from_object('pixyz_worker.settings')


if __name__ == '__main__':
    logging.info('Stopping worker')
    app.control.shutdown()
