#!/usr/bin/env python3
# python3 ./client.py --url http://localhost:8001 exec -s scripts/tutorial/001_workflow_engine.py -d ~/windows/cadfile/panda.fbx -e main -t XXXX -q gpu
from pixyz_worker import *
import logging
import pxz
import math
import os
import json
from pxz import core, scene, polygonal, algo, material, view, io

logger = logging.getLogger(__name__)

def export_model_metadata(filepath, output_dir, progress):

    logger.info("starting metadata generation")
    output = {}   

    # Import the file
    pxz.core.resetSession()
    progress.next(f"Importing file '{os.path.basename(filepath)}'", output)
    pxz.io.importFiles([filepath])

    aabb = pxz.scene.getAABB([pxz.scene.getRoot()])
    ratio = 0.0002
    diagLength = math.sqrt(
        ((aabb.high.x - aabb.low.x) * (aabb.high.x - aabb.low.x))
        + ((aabb.high.y - aabb.low.y) * (aabb.high.y - aabb.low.y))
        + ((aabb.high.z - aabb.low.z) * (aabb.high.z - aabb.low.z))
    )

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

    progress.next("Export 'metadata.json'", output)
    json_file = os.path.join(output_dir, 'metadata.json')
    with open(json_file, 'w') as f:
        f.write(json.dumps(meta, indent=4))

    progress.stop()
    return output


def main(pc: ProgramContext, params: dict):
    """
    Generate metadata for a model.

    Outputs a metadata.json file in the output directory and returns the metadata as a dictionary.
    """
    pc.progress_set_total(3)
    ret = export_model_metadata(pc.get_input_file(), pc.get_output_dir(), pc['progress'])
    return ret
