#!/usr/bin/env python3
from pixyz_worker.script import *

def main(pc: ProgramContext, params: dict):
    """
    Test the PixyzScheduler API by returning a simple string
    """

    pc.progress_set_total(1)
    pc.progress_next("API tested successfully!")

    return {'output': 'Hello World!', 'params': params}

if __name__ == '__main__':
   main(ProgramContext.from_local(__file__), {})
