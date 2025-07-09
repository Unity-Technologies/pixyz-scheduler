#!/usr/bin/env python3
import time
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../'))
from pixyz_worker.script import *


def main(pc: ProgramContext, params: dict):
   pc.progress_set_total(3)
   pc.progress_next(f"Do something 1")
   time.sleep(0.1)
   pc.progress_next(f"Do something 2")
   time.sleep(0.2)
   return 1


if __name__ == '__main__':
   LocalPixyzTask.from_commandline(__file__, os.getcwd(), 'main')
