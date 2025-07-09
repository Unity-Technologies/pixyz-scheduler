#!/usr/bin/env python3
# python3 ./client.py --url http://localhost:8001 exec -s scripts/tutorial/001_workflow_engine.py -d ~/windows/cadfile/panda.fbx -e main -t XXXX -q gpu
from pixyz_worker.script import *
import time

from celery import group

def my_sleep(pc: ProgramContext, params: dict):
    pc.progress_next("inception inside should not working")
    print("task params: ", params)
    time.sleep(params['time'])
    return params['time']


def main(pc: ProgramContext, params: dict):
    c = group(
        group(
        pixyz_execute.s({'time': 2, 'id': 2}, pc.clone().update(entrypoint='my_sleep')),
        pixyz_execute.s({'time': 3, 'id': 3}, pc.clone().update(entrypoint='my_sleep'))),
        group(pixyz_execute.s({'time': 4, 'id': 4}, pc.clone().update(entrypoint='my_sleep')),
        pixyz_execute.s({'time': 50, 'id': 50}, pc.clone().update(entrypoint='my_sleep')))
    )()
    print("group return" + str(c) + str(type(c)))
    print(c.children)
    return c.as_tuple()


