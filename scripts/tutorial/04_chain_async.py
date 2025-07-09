#!/usr/bin/env python3
# python3 ./client.py --url http://localhost:8001 exec -s scripts/tutorial/001_workflow_engine.py -d ~/windows/cadfile/panda.fbx -e main -t XXXX -q gpu
from pixyz_worker.script import *
from pixyz_worker.tasks import pixyz_execute
import time
import logging
import os
try:
    from pxz import core, scene, polygonal, algo, material, view, io
except ImportError:
    logging.error("pixyz not installed, please install it with 'pip install pxz'")
from celery import chain


def my_sleep(pc: ProgramContext, params: dict):
    pc.progress_next("inception inside should not working"+str(params))
    print("task params: ", params)
    time.sleep(params['time'])
    params['time'] = params['time'] / 10
    return params


def main(pc: ProgramContext, params: dict):
    c = chain(pixyz_execute.s({'time': 2, 'id': 2}, pc.clone().update(entrypoint='my_sleep', raw=True)),
        pixyz_execute.s(pc=pc.clone().update(entrypoint='my_sleep', raw=True))).apply_async()
    #c.parent.save()
    print("chain return" + str(c) + str(type(c)))
    print(c.children)
    return c.as_tuple()

