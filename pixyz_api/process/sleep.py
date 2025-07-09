#!/usr/bin/env python3
from pixyz_worker import *
from pxz import core, scene, polygonal, algo, material, view, io
import time

# params : {"duration": 1}
# - `duration`: Float, the duration in seconds to sleep
#
def main(pc: ProgramContext, params: dict):
    # Set the number of progress steps 
    pc.progress_set_total(1)

    duration = params.get('duration', 0.1)

    pc.progress_next(f"Sleeping for {duration} seconds")

    print(f"Sleeping for {duration} sec")

    time.sleep(duration)

    # save last progress step duration
    pc.progress_stop()

    return {"sleep": duration}