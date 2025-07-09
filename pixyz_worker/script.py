#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pixyz_worker.pc import *
from pixyz_worker.share import pixyz_schedule, PiXYZSession
from pixyz_worker.tasks import pixyz_execute
from celery import chain, group, chord, chunks
from pixyz_worker.license import License
from pixyz_worker.local import LocalPixyzTask
import sys
import os


def subtask_async(pc, entrypoint, params=None, **kwargs):
    """
    Run asynchronously the entrypoint function using celery
    """
    sub_pc = pc.clone(entrypoint=entrypoint, params=params)
    return sub_pc.execute(params, **kwargs)
