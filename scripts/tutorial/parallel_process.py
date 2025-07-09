import sys
import os
from datetime import datetime
from celery import chord, group
from celery.result import allow_join_result
from pixyz_worker.tests.data.valid_script import sleep

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../'))
from pixyz_worker.script import *
import zipfile
from pathlib import Path
import pxz

@pixyz_schedule(queue="cpu")
def subtask(pc: ProgramContext, params: dict):
    pxz.io.importScene(pc.get_input_file())
    pxz.algo.repairCAD([pxz.scene.getRoot()], 0.1, False)
    pxz.algo.tessellate([pxz.scene.getRoot()], 0.1, -1, -1)
    file_name = os.path.basename(pc.get_input_file()) + ".pxz"
    pxz.core.save(pc.get_output_dir() + "/" + file_name)
    return {"file" : pc.get_output_dir() + "/" + file_name}

@pixyz_schedule(queue="cpu")
def merge_result(pc: ProgramContext, params: dict):
    files = [x["result"]["file"] for x in params]
    pxz.io.importFiles(files)
    output = pc['output'] + "/output.glb"
    pxz.io.exportScene(output)
    return {"output": output}

@pixyz_schedule(queue="control")
def main(pc: ProgramContext, params: dict):
    pc.progress_set_total(2)

    data_dir = pc.get_output_dir()
    pc.progress_next(f"Unzip the data files")
    with zipfile.ZipFile(pc.get_input_file(), 'r') as zip_ref:
        zip_ref.extractall(data_dir)

    files = [pc.get_output_dir() + "/" + file for file in os.listdir(data_dir) if file.endswith(".CATPart")]

    pc.progress_set_total(2 + len(files) + 1)

    task_group = chord(
        [pixyz_execute.s({}, pc=pc.clone(data=f, entrypoint='subtask', queue="cpu")) for f in files])(
        pixyz_execute.s(pc=pc.clone(output=data_dir, entrypoint='merge_result', queue="cpu")))

    with allow_join_result():
        return task_group.get(on_message=lambda x: pc.progress_next("next"), propagate=False)


