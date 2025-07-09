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

physical_gpu = False


def diff_time_microseconds(start_time):
    diff = datetime.now() - start_time
    nb_sec = diff.days * 24 * 60 * 60 + diff.seconds
    return (nb_sec * 1000000 + diff.microseconds) / 1000000.0


def screenshot(pc: ProgramContext, params: dict):
    start = datetime.now()
    output_dir = params['output_dir']
    pc.progress_next("[screenshot] loading pxz file")
    pxz.io.importFiles([params['pxz']])

    def take_screenshot(viewer, camera, angle, name):
        target_file = os.path.join(output_dir, f"{name}.png")
        logger.info(f"take screenshot angle {angle} to {target_file}")

        pxz.view.fitCamera(camera, pxz.view.CameraType.Perspective, angle, viewer=viewer)
        pxz.view.takeScreenshot(target_file, viewer)

        # return file name
        return os.path.basename(target_file)

    if physical_gpu:
        # Create viewer (count as 1 step in the progress)
        pc.progress_next('Creating viewer')
        #viewer=None
        viewer = pxz.view.createViewer(params['width'], params['height'])


        pc.progress_next('Creating GPUScene')
        # Add GPU Scene (count as 1 step in the progress)
        gpuScene = pxz.view.createGPUScene([pxz.scene.getRoot()])
        pxz.view.addGPUScene(gpuScene, viewer)

        # Specify to not show background
        pxz.view.setViewerProperty("ShowBackground", "False", viewer)

        pc.progress_next('Screenshotting')
        params['thumbs'] = {}
        params['thumbs']['iso'] = take_screenshot(viewer, pxz.geom.Point3(-0.5, -0.5, -1), 70, 'iso')
        params['thumbs']['x'] = take_screenshot(viewer, pxz.geom.Point3(0, 0, -1), 90, 'x')
        params['thumbs']['y'] = take_screenshot(viewer, pxz.geom.Point3(-1, 0, 0), 90, 'y')
        params['thumbs']['z'] = take_screenshot(viewer, pxz.geom.Point3(0, -1, 0), 90, 'z')

        # Release the viewer to avoid memory leak
        pxz.view.destroyViewer(viewer)
    else:
        pc.progress_next(f"[screenshot] emulate screenshot on queue {pc['queue']}")
        params['thumbs'] = {}
        params['thumbs']['iso'] = os.path.join(output_dir, 'iso.png')
        params['thumbs']['x'] = os.path.join(output_dir, 'x.png')
        params['thumbs']['y'] = os.path.join(output_dir, 'y.png')
        params['thumbs']['z'] = os.path.join(output_dir, 'z.png')
        params['thumbs']['time'] = diff_time_microseconds(start)
    return params


def import_and_prepare(pc: ProgramContext, params: dict):
    logger.info("starting")

    filepath, output_dir, progress = params['filepath'], params['output_dir'], pc['progress']
    img_params = {'width': 512, 'height': 512}

    # Set the image size
    img_size_x, img_size_y = 512, 512
    if img_params is not None and isinstance(img_params, dict):
        if 'width' in img_params:
            img_size_x = img_params['width']
        if 'height' in img_params:
            img_size_y = img_params['height']
    logger.info(f"Image size: {img_size_x}x{img_size_y}")

    output = {}

    # get the start time
    start_time = datetime.now()

    # Import the files in a scene
    progress.next(f"Importing file {filepath} into {pc['queue']}")
    pxz.io.importFiles([filepath])

    progress.next('Repairing BRep model')
    pxz.algo.repairCAD([pxz.scene.getRoot()], 0.1, False)

    progress.next('Repairing Mesh')
    pxz.algo.repairMesh([pxz.scene.getRoot()], 0.1, False, False)

    progress.next('Tessellate')
    pxz.algo.tessellate([pxz.scene.getRoot()], 0.1, -1, -1)

    # get the execution time
    output["process_duration"] = diff_time_microseconds(start_time)

    progress.stop()

    # Export to pxz
    pxz_file = os.path.join(output_dir, 'export.pxz')
    pxz.io.exportScene(pxz_file)

    # Prepare for screenshot
    output['pxz'] = pxz_file
    return output


@pixyz_schedule(wait=True, timeout=3600)
def main(pc: ProgramContext, params: dict):
    """

    Generate png thumbnails [iso,x,y,z] for the given file: DAG version -> CPU task (load, repair, tessellate) -> GPU task (screenshot)

    Parameters
    {
    'width': 1920, [optional] output images width (default: 512)
    'height': 1080, [optional] output images height (default: 512)
    }
    """
    pc.progress_set_total(12)
    params['filepath'] = pc.get_input_file()
    params['output_dir'] = pc.get_output_dir()
    params['width'] = 512
    params['height'] = 512

    return chain(pixyz_execute.s(params,
                                 pc.clone().update(entrypoint='import_and_prepare',
                                                   raw=True)).set(queue='cpu'),
                 pixyz_execute.s(pc=pc.clone().update(entrypoint='screenshot',
                                                      raw=True, compute_only=True)).set(queue='gpu'))()
