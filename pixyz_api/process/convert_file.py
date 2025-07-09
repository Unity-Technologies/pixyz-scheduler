#!/usr/bin/env python3
# python3 ./client.py --url http://localhost:8001 process -n generate_metadata -i ~/windows/cadfile/panda.fbx
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../'))
from pixyz_worker.script import *


def main(pc: ProgramContext, params: dict):
    from pxz import core, scene, polygonal, algo, material, view, io

    # (optional) Define the number of task, this class will be used to update the task progress
    pc.progress_set_total(3)
    if isinstance(params, dict):
        extension = params.get('extension', 'pxz').lower()
    else:
        extension = 'pxz'

    # Get the name of the file to import
    import_file_name = pc.get_input_file()

    pc.progress_next(f"Importing file {import_file_name}")
    root = io.importScene(import_file_name)

    # Save the scene to a new file in the current share output directory
    pc.progress_next(f"Exporting file to {pc.get_output_dir(f'output.{extension}')}")
    io.exportScene(pc.get_output_dir(f'output.{extension}'), root)

    pc.progress_next("done")
    # If you return (any) dictionary , the pixyz_execute will add the timing info
    return {'output': f'output.{extension}'}


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3):
        print("Usage: python 00_convert_a_file.py <input_file> [format]")
        print("format: pxz, glb, gltf, fbx, ... (default: pxz)")
        sys.exit(1)

    if len(sys.argv) == 3:
        params = {'extension': sys.argv[2].lower()}
    else:
        # Default extension
        params = {'extension': 'pxz'}

    LocalPixyzTask.from_commandline(__file__, os.getcwd(), 'main', params=params, input_file=sys.argv[1])
