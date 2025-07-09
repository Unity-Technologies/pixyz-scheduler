#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from time import sleep
from datetime import datetime
from pixyz_worker.script import *
from celery import chord, group
from celery.result import allow_join_result
import zlib
from functools import reduce
from random import randint
from logging import getLogger

logger = getLogger('pixyz_worker.snippet.test_import_code')
#
# API --> pixyz_worker.pixyz_execute --> pixyz_worker.extcode.ExternalPythonCode(main) --> 4 * ExternalPythonCode(subtask) -\
#                                        compile the result by summing                 <-----------------------------------_/
#
def checksum_data(input_string):
    zlib.crc32(input_string.encode())


def subtask(pc: ProgramContext, params: dict):
    # Emulate workload
    sleep(randint(1, 5))
    print('pixyz_worker.snippet.test_import_code')
    logger.debug("subtask: " + str(pc))
    with open(pc.get_input_file(), 'rb') as f:
        data = f.read()
        crc32 = zlib.crc32(data)
        logger.info(f"crc32 of {pc.get_input_file()} is {crc32}")
        return {'crc': crc32}


def merge_result(pc: ProgramContext, params):
    # Call this program with the result of the 4 subtask
    pc.progress_next(f"Merging {len(params)}")
    # Emulate workload
    sleep(randint(1, 5))
    return {'crc32': reduce(lambda x, y: x + y, [x['result']['crc'] for x in params])}

@pixyz_schedule(queue="control")
def main(pc: ProgramContext, params: dict):

    ret = {}
    print("ProgramContext: " + str(pc))
    print("Params: " + str(params))

    # 5 step, one for initialization, 4 for checksum
    pc.progress_set_total(1 + 4)
    pc.progress_next("splitting file")
    ## We will do a pseudo distributed checksum
    # Split file from the temporary data dir into 4 parts
    # and create a new task for each part stored in the shared storage
    #

    # Split the file in 4 parts and store it in the shared storage
    with open(pc.get_input_file(), 'rb') as f:
        data = f.read()
        for i in range(0, 4):
            with open(pc.get_output_dir(f'crc_part{i}'), 'wb') as f:
                f.write(data[i * len(data) // 4:(i + 1) * len(data) // 4])

    pc.progress_next("chord")
    # Create a group of task with 4 parts
    # use chord for merging the result and ensure all tasks have been run
    task_group = chord(
        [pixyz_execute.s({}, pc=ProgramContext(script=pc['script'], data=pc.get_output_dir(f'crc_part{i}'),
                                               time_request=datetime.utcnow(),
                                               root_file=pc['root_file'],
                                               entrypoint='subtask')) for i in range(0, 4)])(
        pixyz_execute.s(pc=ProgramContext(script=pc['script'], root_file=pc['root_file'], data=None,
                                          time_request=datetime.utcnow(), entrypoint='merge_result')))

    # Not recommended to call get in a task
    logger.debug("Waiting for task group to finish")
    return task_group.as_tuple()

