#!/usr/bin/env python3
import os
import sys
import time

sys.path.append(os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../')))
from pixyz_worker.script import *

def main(pc: ProgramContext, params: dict):
    print("sleep 0.1 sec")
    time.sleep(0.1)

if __name__ == '__main__':
    LocalPixyzTask.from_commandline(__file__, os.getcwd(), 'main')
