#!/usr/bin/env python3
# python3 ./client.py --url http://localhost:8001 exec -s scripts/tutorial/001_workflow_engine.py -d ~/windows/cadfile/panda.fbx -e main -t XXXX -q gpu
from pixyz_worker import *
from pixyz_worker.script import *
from datetime import datetime
import logging
import pxz
import math
import os
import json
from pxz import core, scene, polygonal, algo, material, view, io

# Expected parameters {'width': 512, 'height': 512}

logger = logging.getLogger(__name__)

def diff_time_microseconds(start_time):
    diff = datetime.now() - start_time
    nb_sec = diff.days * 24 * 60 * 60 + diff.seconds
    return (nb_sec * 1000000 + diff.microseconds) / 1000000.0


def generate_thumbnail_icon_all_in_one(filepath, output_dir, progress, params={'width': 512, 'height': 512}):
    def take_screenshot(viewer, camera, angle, name):
        target_file = os.path.join(output_dir, f"{name}.png")
        logger.info(f"take screenshot angle {angle} to {target_file}")

        pxz.view.fitCamera(camera, pxz.view.CameraType.Perspective, angle, viewer=viewer)
        pxz.view.takeScreenshot(target_file, viewer)

        # return file name
        return os.path.basename(target_file)

    logger.info("starting")

    # Set the image size
    img_size_x, img_size_y = 512, 512
    if params is not None and isinstance(params, dict):
        if 'width' in params:
            img_size_x = params['width']
        if 'height' in params:
            img_size_y = params['height']
    logger.info(f"Image size: {img_size_x}x{img_size_y}")

    # Tessellate to convert BRep data to polygons (count as 1 step in the progress)
    tessellationPresets = [
        # MaxSag, SagRatio
        [0.01, 0.0001],  # Very High
        [0.1, 0.0002],  # High
        [0.2, 0.0003],  # Medium
        [1, 0.001],  # Low
    ]
    quality = 0

    output = {}
    # get the start time
    start_time = datetime.now()

    # Import the files in a scene
    pxz.core.resetSession()
    progress.next('Importing file')
    pxz.io.importFiles([filepath])

    # Repair the BRep with a tolerance based on the model size (count as 1 step in the progress)
    aabb = pxz.scene.getAABB([pxz.scene.getRoot()])
    tolerance = 0.1
    ratio = 0.0002
    diagLength = math.sqrt(
        ((aabb.high.x - aabb.low.x) * (aabb.high.x - aabb.low.x))
        + ((aabb.high.y - aabb.low.y) * (aabb.high.y - aabb.low.y))
        + ((aabb.high.z - aabb.low.z) * (aabb.high.z - aabb.low.z))
    )
    ratioCompute = diagLength * ratio
    tolerance = min(ratioCompute, tolerance)
    progress.next('Repairing CAD')
    pxz.algo.repairCAD([pxz.scene.getRoot()], tolerance, False)


    # Repair the Meshes with a tolerance based on the model size (count as 1 step in the progress)
    aabb = pxz.scene.getAABB([pxz.scene.getRoot()])
    tolerance = 0.1
    ratio = 0.0002
    diagLength = math.sqrt(
        ((aabb.high.x - aabb.low.x) * (aabb.high.x - aabb.low.x))
        + ((aabb.high.y - aabb.low.y) * (aabb.high.y - aabb.low.y))
        + ((aabb.high.z - aabb.low.z) * (aabb.high.z - aabb.low.z))
    )
    ratioCompute = diagLength * ratio
    tolerance = min(ratioCompute, tolerance)
    progress.next('Repairing Mesh')
    pxz.algo.repairMesh([pxz.scene.getRoot()], tolerance, False, False)

    progress.next('tessellateRelativelyToAABB')
    pxz.algo.tessellateRelativelyToAABB(
        [pxz.scene.getRoot()],
        tessellationPresets[quality][0],
        tessellationPresets[quality][1],
        -1,
        -1,
        True,
        0,
        1,
        0.000000000000,
        True,
        False,
        False,
        False,
    )

    # Create viewer (count as 1 step in the progress)
    progress.next('Creating viewer')
    #viewer=None
    viewer = pxz.view.createViewer(img_size_x, img_size_y)

    progress.next('Creating GPUScene')
    # Add GPU Scene (count as 1 step in the progress)
    gpuScene = pxz.view.createGPUScene([pxz.scene.getRoot()])
    pxz.view.addGPUScene(gpuScene, viewer)

    # Specify to not show background
    pxz.view.setViewerProperty("ShowBackground", "False", viewer)

    progress.next('Screenshotting')
    output['thumbs'] = {}
    output['thumbs']['iso'] = take_screenshot(viewer, pxz.geom.Point3(-0.5, -0.5, -1), 70, 'iso')
    output['thumbs']['x'] = take_screenshot(viewer, pxz.geom.Point3(0, 0, -1), 90, 'x')
    output['thumbs']['y'] = take_screenshot(viewer, pxz.geom.Point3(-1, 0, 0), 90, 'y')
    output['thumbs']['z'] = take_screenshot(viewer, pxz.geom.Point3(0, -1, 0), 90, 'z')

    # Release the viewer to avoid memory leak
    pxz.view.destroyViewer(viewer)

    progress.next('Combine Material', output)
    pxz.scene.mergeImages([])
    pxz.scene.mergeMaterials([], False)
    pxz.scene.mergePartOccurrencesByMaterials([], mergeHiddenPartsMode=0, combineMeshes=True)
    pxz.core.setModuleProperty("Material", "ExportTextureFormat", "KTX2")

    progress.next('DecimateTarget', output)
    pxz.algo.decimateTarget([], ["triangleCount", 500000], 0, False, 1500000, False)

    glb_preview_filename = "preview.glb"

    progress.next(f"Exporting model preview to {glb_preview_filename}", output)
    glb_file = os.path.join(output_dir, glb_preview_filename)
    pxz.io.exportScene(glb_file)

    preview = {}
    preview['file'] = glb_preview_filename
    preview['size'] = f"{img_size_x}x{img_size_y}"
    output['preview'] = preview

    progress.next('Generating metadata', output)
    brep_infos = pxz.scene.getBRepInfos()
    mesh_infos = pxz.scene.getTessellationInfos()
    pmiComps = pxz.scene.listComponent(pxz.scene.ComponentType.PMI)
    metadataComps = pxz.scene.listComponent(pxz.scene.ComponentType.Metadata)
    annotationGroupCount = 0
    annotationCount = 0
    metadataPropertyCount = 0

    for pmiId in pmiComps:
        groups = pxz.scene.getAnnotationGroups(pmiId)
        annotationGroupCount += len(groups)

        for groupId in groups:
            annotationCount += len(pxz.scene.getAnnotations(groupId))


    for metadataId in metadataComps:
        metadataPropertyCount += len(pxz.core.listProperties(metadataId))
    occurrences = [pxz.scene.getRoot()]

    meta = {}
    meta["aabb"] = str(diagLength)
    meta["part_count"] = len(pxz.scene.getPartOccurrences())
    meta["material_count"] = len(pxz.material.getAllMaterials())
    meta["brep_boundary"] = brep_infos["boundaryCount"]
    meta["brep_body_count"] = brep_infos["bodyCount"]
    meta["mesh_boundary"] = mesh_infos["boundaryCount"]
    meta["mesh_edge_count"] = mesh_infos["edgeCount"]
    meta["mesh_vertex_count"] = mesh_infos["vertexCount"]
    meta["polygon_count"] = pxz.scene.getPolygonCount(occurrences)
    meta["animation_count"] = len(pxz.scene.listAnimations())
    meta["variant_count"] = len(pxz.scene.listVariants())
    meta["pmi_component_count"] = len(pmiComps)
    meta["annotation_group_count"] = annotationGroupCount
    meta["annotation_count"] = annotationCount
    meta["metadata_component_count"] = len(metadataComps)
    meta["metadata_property_count"] = metadataPropertyCount
    output['metadata'] = meta

    # get the execution time
    output["process_duration"] = diff_time_microseconds(start_time)

    progress.next("Export 'metadata.json'", output)
    json_file = os.path.join(output_dir, 'metadata.json')
    with open(json_file, 'w') as f:
        f.write(json.dumps(meta, indent=4))

    progress.stop()
    return output


@pixyz_schedule(queue='gpu')
def main(pc: ProgramContext, params: dict):
    """
    Generate png thumbnails [iso,x,y,z], preview.glb and metadata.json for the given file

    Parameters
    {
    'width': 1920, [optional] output images width (default: 512)
    'height': 1080, [optional] output images height (default: 512)
    } 
    """
    pc.progress_set_total(12)
    ret = generate_thumbnail_icon_all_in_one(pc.get_input_file(), pc.get_output_dir(), pc['progress'], params)
    return ret
