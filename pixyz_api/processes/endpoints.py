#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import ast

from . import *
from pixyz_api.patterns import uuid_path_pattern
from fastapi import UploadFile, File, Form

router = APIRouter()

# Gets list of all available scheduler processes (files in the {job_uuid}/output)
@router.get("", **get_api_response_desc_from_model(ProcessList))
async def get_processes_list():
    """
    Get a list of all available scheduler processes to trigger jobs
    :return: a list of strings with the name of the process
    """
    #
    try:
        processes = get_scripts_list_in_processes_dir()
        return ProcessList(processes)
    except Exception as e:
        raise_api_error(ApiError500, e)
    
# Get the Doc of a process
@router.get("/{process_name}")
async def get_process_doc(process_name: str):
    """
    Get the documentation of a process
    :param process_name: the name of the process
    :return: the documentation of the process
    """
    
    # check if process matches a valid process file
    if(process_name not in get_scripts_list_in_processes_dir()):
        raise_api_error(ApiError400, f"Invalid process '{process_name}'")
    
    process_file_path = get_script_path_in_processes_dir(process_name)
    
    doc_content = None
    try:
        # grab the script file __doc__ content
        with open(process_file_path, 'r') as f:           
            tree = ast.parse(f.read())
            function_definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

            for f in function_definitions:
                if f.name == 'main':
                    doc_content = f"Process '{process_name}' documentation:\n\n{ast.get_docstring(f)}"

        if doc_content is not None:
            return {'doc': doc_content}
        else:
            raise_api_error(ApiError404, f"No documentation found for '{process_name}' process")
    except Exception as e:
        raise_api_error(ApiError500, e)