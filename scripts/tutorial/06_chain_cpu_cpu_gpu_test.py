#!/usr/bin/env python3
# python3 ./client.py --url http://localhost:8001 exec -s scripts/tutorial/001_workflow_engine.py -d ~/windows/cadfile/panda.fbx -e main -t XXXX -q gpu
from pixyz_worker.script import *
from pixyz_worker.tasks import pixyz_execute
import time
import logging
import os
from datetime import datetime
import math
try:
    import pxz
    from pxz import core, scene, polygonal, algo, material, view, io
except ImportError:
    logging.error("pixyz not installed, please install it with 'pip install pxz'")

from celery import chain
import json
logger = logging.getLogger(__name__)

@pixyz_schedule(queue='cpu')
def sleep_cpu(pc: ProgramContext, params: dict):
    from time import sleep
    sleep(0.1)
    return {'sleep_cpu': True}

@pixyz_schedule(queue='gpu')
def sleep_gpu(pc: ProgramContext, params: dict):
    from time import sleep
    sleep(0.1)
    return {'sleep_gpu': True}

@pixyz_schedule(queue='zip')
def sleep_zip(pc: ProgramContext, params: dict):
    from time import sleep
    sleep(0.1)
    return {'sleep_zip': True}

@pixyz_schedule(queue='control')
def sleep_control(pc: ProgramContext, params: dict):
    from time import sleep
    sleep(0.1)
    return {'sleep_control': True}

@pixyz_schedule(wait=True)
def main_wait(pc: ProgramContext, params: dict):
    return chain(pixyz_execute.s(params,
                                 pc.clone().update(entrypoint='sleep_zip',
                                                   raw=True)).set(queue='cpu'),
                 pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_gpu',
                                                      raw=True)).set(queue='gpu'),
                 pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_cpu',
                                                      raw=True)).set(queue='cpu'),
                 pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_zip',
                                                      raw=True)).set(queue='zip'),
                 pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_control',
                                                      raw=True)).set(queue='control')
                 )()


@pixyz_schedule(wait=False)
def main(pc: ProgramContext, params: dict):
    chain(pixyz_execute.s(params,
                          pc.clone().update(entrypoint='sleep_zip',
                                            raw=True)).set(queue='cpu'),
          pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_gpu',
                                               raw=True)).set(queue='gpu'),
          pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_cpu',
                                               raw=True)).set(queue='cpu'),
          pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_zip',
                                               raw=True)).set(queue='zip'),
          pixyz_execute.s(pc=pc.clone().update(entrypoint='sleep_control',
                                               raw=True)).set(queue='control')
          ).apply_async()
    return {'status': 'ok'}
