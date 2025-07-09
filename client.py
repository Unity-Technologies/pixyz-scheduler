#!/usr/bin/env python3
import os
import sys
import requests
import argparse
import json
import ast
from time import sleep
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

__version__ = '0.0.8'

debug = os.getenv('DEBUG', 'false').lower() == 'true'
default_url = 'http://127.0.0.1:8001'
verify_ssl = True
# Set up logging
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

############################ utils ############################
    
def format_filesize(num, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def get_stream(batch=False):
    if batch:
        return sys.stderr
    else:
        return sys.stdout

# return the content of a print_followed line base on the status_dict content
try:
    spinner = ['⌛', '⏳', '⌛', '⏳'] if 'utf' in getattr(sys.stdout, 'encoding', None).lower() else ['|', '/', '-', '\\']
except:
    spinner = ['|', '/', '-', '\\']
spinpos = 0

def print_followed_status(status_dict, stream):
    global spinner, spinpos

    # return to start of line
    stream.write('\r')
    stream.write('\033[K')
    if status_dict['progress'] is None:
        status_dict['progress'] = 0

    last_step = ""
    try:
        if 'steps' in status_dict and status_dict['steps'] is not None:
            last_step = f"({status_dict['steps'][-2]['info']})" if len(status_dict['steps']) > 1 else ""
    except (KeyError, IndexError):
        last_step = ""
    stream.write( f"Job [ {status_dict['uuid']} ] progress: {format(status_dict['progress'], '03d')}, status: {status_dict['status']} {last_step} [{spinner[spinpos]}]" )
    stream.flush()

    # increment spinpos and reset to 0 if it's 4
    spinpos = (spinpos + 1) % 4

def truncate_dict_for_display(d, size=5000):
    ret = {}
    if d is None:
        return {}
    for k, v in d.items():
        if isinstance(v, str):
            if len(v) > size:
                v = v[:size] + '...'
            else:
                pass
        elif isinstance(v, dict):
            v = truncate_dict_for_display(v)
        else:
            pass
        ret[k] = v
    return ret


def get_headers(token=None):
    if token is not None:
        return {'x-api-key': token}
    else:
        return {}

############################ API utils ############################

# Simple API call
def api_call(url, token=None):
    res = requests.get(url, headers=get_headers(token), verify=verify_ssl)
    res.raise_for_status()
    res_dict = res.json()
    
    if res.status_code not in (200, 202):
        print("Error: ", res.status_code)
        
    return res_dict


# Returns a list of available processes
def get_processes(url, token=None):
    return api_call(f'{url}/processes', token)


# Returns a list of all jobs status
def get_jobs(url, token=None):
    return api_call(f'{url}/jobs', token)


def get_job_status(url, job_id, watch=False, batch=False, token=None, max_retry=None):
    headers = get_headers(token)
    res = requests.get(f'{url}/jobs/{job_id}/details', headers=headers, verify=verify_ssl)
    res.raise_for_status()
    res_dict = res.json()
    stream = get_stream(batch)
    if res.status_code not in (200, 202):
        print("Error: ", res.status_code, file=stream)
        if batch:
            sys.exit(1)
    else:        
        if watch:
            print_followed_status(res_dict, stream)

            # check if status/progress/error has changed
            retry=0
            while (res_dict['status'] not in ['SUCCESS', 'FAILURE', 'REVOKED'] and
                   (max_retry is None or retry < max_retry)):
                res = requests.get(f'{url}/jobs/{job_id}/details', headers=headers, verify=verify_ssl)
                res.raise_for_status()
                res_dict = res.json()
                print_followed_status(res_dict, stream)
                sleep(1)
                retry+=1

            if max_retry is not None and retry > max_retry:
                raise RuntimeError(f"We reached the maximum retry({max_retry}) for getting the status")

            # print the final status
            print_followed_status(res_dict, stream)
            print("", file=stream)

            # check if error
            if res_dict['error'] is not None:
                print(f"Error: {res_dict['error']}", file=stream)
    
    return res_dict


def get_job_details(url, job_id, token=None):
    return api_call(f'{url}/jobs/{job_id}/details', token)


def get_job_outputs(url, job_id, token=None):
    return api_call(f'{url}/jobs/{job_id}/outputs', token)


def download_job_output(url, job_id, filepath, destination, token=None):
    headers = get_headers(token)
    res = requests.get(f'{url}/jobs/{job_id}/outputs/{filepath}', headers=headers, verify=verify_ssl)
    res.raise_for_status()

    if res.status_code == 200:
        total_size = int(res.headers.get('content-length', 0))
        file_size = 0
        bar_length = 30
        with open(destination, 'wb') as f:
            for chunk in res.iter_content(chunk_size=1048576):
                if chunk:
                    f.write(chunk)
                    file_size += len(chunk)
                    progress = 100 * file_size / total_size
                    filled_length = int(bar_length * file_size // total_size)
                    bar = '█' * filled_length + '-' * (bar_length - filled_length)
                    sys.stdout.write(f'\rDownloading: [{bar}] {progress:.1f}% ')
                    sys.stdout.flush()

            print(f"Job [ {job_id} ] output '{filepath}' downloaded to '{destination}' ({format_filesize(file_size)})")
        return True
    else:
        print("Error: ", res.status_code)
        print(res.text)
        return False


def download_job_archive(url, job_id, destination, token=None):
    headers = get_headers(token)
    retry = 0
    print("Requesting job output file download...", end="", flush=True)
    res = requests.get(f'{url}/jobs/{job_id}/outputs/archive', headers=headers, verify=verify_ssl)
    while retry < 30:
        res = requests.get(f'{url}/jobs/{job_id}/outputs/archive', headers=headers, verify=verify_ssl)
        if res.status_code == 425:
            retry+=1
            print(".", flush=True, end="")
            sleep(1)
            continue
        elif res.status_code == 200:
            print(" ready.", flush=True)
            break
        else:
            res.raise_for_status()

    # create destination folder if it does not exist
    if not os.path.exists(os.path.realpath(os.path.dirname(destination))):
        os.makedirs(os.path.dirname(destination))
    total_size = int(res.headers.get('content-length', 0))
    if res.status_code == 200:
        file_size = 0
        bar_length = 30
        with open(destination, 'wb') as f:
            for chunk in res.iter_content(chunk_size=1048576):
                if chunk:
                    f.write(chunk)
                    progress = 100 * file_size / total_size
                    filled_length = int(bar_length * file_size // total_size)
                    bar = '█' * filled_length + '-' * (bar_length - filled_length)
                    sys.stdout.write(f'\rDownloading: [{bar}] {progress:.1f}% ')
                    sys.stdout.flush()
                    file_size += len(chunk)
            progress = 100
            bar = '█' * bar_length
            sys.stdout.write(f'\rDownloading: [{bar}] {progress:.1f}% ')
            print(f"\nJob [ {job_id} ] outputs downloaded to '{destination}' ({format_filesize(file_size)})")
        return res
    elif res.status_code == 425:
        print("The outputs packaging task job is running")
        return res
    else:
        print("Error: ", res.status_code)
        print(res.text)
        return res

# Note: script_file and input_file are file objects
def post_job(args, process='custom'):
    # Track upload progress with callback function
    def progress_callback(monitor):
        # Calculate percentage
        progress = 100 * monitor.bytes_read / monitor.len

        # Print progress bar
        bar_length = 30
        filled_length = int(bar_length * monitor.bytes_read // monitor.len)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)

        # Print and update in-place with carriage return
        sys.stdout.write(f'\rUploading: [{bar}] {progress:.1f}% ')
        sys.stdout.flush()
    # merge default args values into Namespace
    default_args = {
        'url': default_url,
        'entrypoint': 'main',
        'queue': None,
        'limit': 3600,
        'input': None,
        'script': None,
        'params': {},
        'watch': False,
        'batch': False,
        'result': False,
        'token': None,
        'alias': None,
        'max_retry': None
    }

    default_args.update(**vars(args))
    args = argparse.Namespace(**default_args)

    # create worker configuration from parameters
    config = {
        'entrypoint': args.entrypoint,
        'queue': args.queue,
        'time_limit': int(args.limit)
    }

    # create API form files
    form_files = {
        'file': (os.path.basename(args.input.name), args.input, 'application/octet-stream') if args.input is not None else None,
        'script': (os.path.basename(args.script.name), args.script, 'text/plain') if process == 'custom' and args.script is not None else None
    }

    if isinstance(args.params, str):
        raise ValueError("Invalid JSON string for 'params'")

    # create API form data
    form_data = {
        'process': process,
        'params': json.dumps(args.params),
        'config': json.dumps(config),
        'name': args.alias
    }
    fields = {**form_data, **form_files}
    monitor = MultipartEncoderMonitor.from_fields(fields=fields, callback=progress_callback)

    if not args.batch:
        print("")
        print("-------- New PixyzScheduler Job ---------")
        if process == 'custom' and args.script is not None:
            print(f"- script file:  '{args.script.name}'")
        else:
            print(f"- process:  '{process}'")
        if args.input is not None:
            print(f"-  input file:  '{args.input.name}'")
        if form_data['params'] is not None:
            print("- script params: ", form_data['params'])
        print("- worker config: ", form_data['config'])
        if args.watch:
            print("-  watch status: ", args.watch)
        print("-----------------------------------------")
        print("")

    logging.info(f"Sending POST request to '/jobs'")
    if args.token is not None:
        if not args.batch:
            pass
            #print(f"Using 'x-api-key' authentication with provided token")
        headers = {'x-api-key': args.token}
    else:
        headers = {}

    headers['Content-Type'] = monitor.content_type
    if not args.batch and (args.script is not None or args.input is not None):
        print("Uploading...", end="")
    res = requests.post(f'{args.url}/jobs', data=monitor, headers=headers, verify=verify_ssl,
                        stream=True, allow_redirects=True)
    print("\n")
    res.raise_for_status()
    json_res = res.json()
    job_uuid = json_res['uuid'] if 'uuid' in json_res else None

    if res.status_code == 200:
        # Get the JSON data as a Python dictionary
        if not args.batch:
            print(f"Job [ {job_uuid} ] started")
        else:
            if not args.watch:
                print(job_uuid)
        if args.watch:
            res = get_job_status(args.url, job_uuid, True, token=args.token, max_retry=args.max_retry)
            if args.batch:
                status_to_exit = {
                    'SUCCESS': 0,
                    'FAILURE': 10,
                    'REVOKED': 11,
                    'RETRY': 12,
                    'PENDING': 13,
                    'STARTED': 14,
                    'RECEIVED': 15,
                    'REJECTED': 16,
                    'UNKNOWN': 17
                }
                if res['status'] in status_to_exit:
                    sys.exit(status_to_exit[res['status']])
                else:
                    sys.exit(status_to_exit['UNKNOWN'])
            else:
                if args.result:
                    print(json.dumps(get_job_details(args.url, job_uuid,token=args.token), indent=4))
    else:
        print("Error: ", res.status_code)
        print(json_res)

    # Return the job id
    return job_uuid


def main():
    """
    PixyzScheduler client command-line interface

    Example:

        List available processes:
        =========================

            COMMAND: python3 ./client.py list
            
            OUTPUT: {
                "processes": [
                    "api_test",
                    "convert_file",
                    "generate_metadata",
                    "generate_thumbnails",
                    "sleep"
                ]
            }
        
        List all jobs status:
        =====================

            COMMAND: python3 ./client.py jobs

            OUTPUT: {
                "jobs": [
                    {
                        "uuid": "23d0ce51-ec6b-46cd-849a-99c72908ca9c",
                        "name": null,
                        "status": "SUCCESS",
                        "progress": 100,
                        "error": null
                    },
                    { ... }
                ]
            }

        Get the status of a job:
        =========================

            COMMAND: python3 ./client.py status -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c

            OUTPUT: {
                "uuid": "23d0ce51-ec6b-46cd-849a-99c72908ca9c",
                "name": null,
                "status": "SUCCESS",
                "progress": 100,
                "error": null
            }

        Get the details of a job:
        =========================

            COMMAND: python3 ./client.py details -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c

            OUTPUT: {
                "uuid": "23d0ce51-ec6b-46cd-849a-99c72908ca9c",
                "name": null,
                "status": "SUCCESS",
                "progress": 100,
                "error": null,
                "time_info": {
                    "request": "2024-02-22T18:28:41.337127",
                    "started": "2024-02-22T18:28:41.403575+00:00",
                    "stopped": "2024-02-22T18:28:53.033697+00:00"
                },
                "steps": [
                    {
                        "duration": 11.586801195982844,
                        "info": "Importing file"
                    },
                    {
                        "duration": 0.012804429978132248,
                        "info": "Exporting file to 'buggy.pxz'"
                    }
                ],
                "retry": 0,
                "output": {
                    "file": "buggy.pxz"
                }
            }

        Get the list of all available outputs of a job:
        ==============================================

            COMMAND: python3 ./client.py outputs -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c

            OUTPUT: {
                "outputs": [
                    "buggy.pxz",
                    "..."
                ]
            }

        Download a job output file:
        ===========================

            COMMAND: python3 ./client.py download -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c -f buggy.pxz -o ./output.pxz

            OUTPUT: Job [23d0ce51-ec6b-46cd-849a-99c72908ca9c] output 'buggy.pxz' downloaded to './output.pxz' (3.8MiB)

        Execute a local script:
        =======================

            COMMAND: python3 client.py exec -s ./my_custom_script.py -i ./input_file.ext -p '{"myparam": "myvalue"}' -l 3600 -w

            TIPS: Use the -w option to follow the status of the job and wait for the process completion        
        
        
        Convert a file to another format:
        =================================

            COMMAND: python3 ./client.py convert -i ~/work/CADFile/bunny.usdz -p '{"filename": "bunny", "extension": "glb"}' -o ./bunny.glb

        Generate thumbnails and a preview glb from a file:
        =================================================

            COMMAND: python3 ./client.py thumbnails -i ~/work/CADFile/bunny.usdz -p '{"width": 1024, "height": 768}' -o ./output_folder

        Generate metadata from a file:
        ==============================

            COMMAND: python3 ./client.py metadata -i ~/work/CADFile/bunny.usdz -o local_metadata.json

    """
    parser = argparse.ArgumentParser()

    parser.add_argument('-u', '--url', help='URL of the API', default=default_url)

    # Arguments naming convention:
    # c = chut (no verbose mode and designed for batch)
    # i = input (string file path)
    # o = output (string file path)
    # f = file (string file path)
    # s = script (string file path)
    # j = jobid (string uuid)
    # p = params (string json)
    # n = name (string)
    # q = queue (string)
    # r = result (string)
    # l = limit (int seconds)
    # w = watch (Boolean)
    # t = token (string)
    # a = alias (string) Custom job name

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(title='subcommands', dest='command', help='Available commands')

    # Command Print version:
    ## TEST CMD: ## python3 client.py version
    parser_version = subparsers.add_parser('version', help='List available embedded processes')

    # Command list processes:
    ## TEST CMD: ## python3 client.py list
    parser_processes = subparsers.add_parser('list', help='List available embedded processes')

    # Command doc process:
    ## TEST CMD: ## python3 client.py doc -n convert_file
    parser_doc = subparsers.add_parser('doc', help='Get the process documentation')
    parser_doc.add_argument('-n', '--name', type=str, help='The process name', required=True)
    
    # Command list jobs:
    ## TEST CMD: ## python3 client.py jobs
    parser_jobs = subparsers.add_parser('jobs', help='List all jobs status')
    parser_jobs.add_argument('-t', '--token', type=str, help='API bearer token', default=None, required=True)

    # Command Job status:
    ## TEST CMD: ## python3 client.py status -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c -w
    parser_status = subparsers.add_parser('status', help='Get or watch job status')
    parser_status.add_argument('-j', '--jobid', type=str, help='The job unique id', required=True)
    parser_status.add_argument('-w', '--watch', action='store_true', help='Follow the job status evolution',
                               default=False)
    parser_status.add_argument('-t', '--token', type=str, help='API bearer token', default=None, required=True)

    # Command Job details:
    ## TEST CMD: ## python3 client.py details -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c
    parser_details = subparsers.add_parser('details', help='Get job details')
    parser_details.add_argument('-j', '--jobid', type=str, help='The job unique id', required=True)
    parser_details.add_argument('-t', '--token', type=str, help='API bearer token', required=True)

    # Command Job outputs:
    ## TEST CMD: ## python3 client.py outputs -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c
    parser_outputs = subparsers.add_parser('outputs', help='Get job outputs list')
    parser_outputs.add_argument('-j', '--jobid', type=str, help='The job unique id', required=True)
    parser_outputs.add_argument('-t', '--token', type=str, help='API bearer token', required=True)

    # Command Download output:
    ## TEST CMD: ## python3 client.py download -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c -f buggy.pxz -o ./output.pxz
    parser_download = subparsers.add_parser('download', help='Download a job output file')
    parser_download.add_argument('-j', '--jobid', type=str, help='The job unique id', required=True)
    parser_download.add_argument('-f', '--file', type=str, help='The job output file path')
    parser_download.add_argument('-o', '--output', type=str, help='Filename where to store the result file')
    parser_download.add_argument('-t', '--token', type=str, help='API bearer token', required=True)

    # Command Download outputs archive:
    ## TEST CMD: ## python3 client.py download_all -j 23d0ce51-ec6b-46cd-849a-99c72908ca9c -o ./output_folder/archive.zip
    parser_download_archive = subparsers.add_parser('download_all', help='Download all job outputs as an archive')
    parser_download_archive.add_argument('-j', '--jobid', type=str, help='The job unique id', required=True)
    parser_download_archive.add_argument('-o', '--output', type=str, help='Filename where to store the result archive')
    parser_download_archive.add_argument('-t', '--token', type=str, help='API bearer token', required=True)

    # Command exec:
    ### TEST CMD: ## python3 client.py exec -s ~/projects/lab/pixyz-scheduler/scripts/process/convert_file.py -i ~/projects/lab/pixyz-webapi/data_engine/data/cad/buggy.3dxml -p '{"hello": "world"}' -l 3600 -w
    parser_exec = subparsers.add_parser('exec',  help='Execute pixyz script in the cloud')
    parser_exec.add_argument('-s', '--script', type=argparse.FileType('rb'), help='The local script file path', default=None, required=True)
    parser_exec.add_argument('-i', '--input', type=argparse.FileType('rb'), help='The local input file path if any', default=None)
    parser_exec.add_argument('-p', '--params', type=str, help='The parameters', default="{}")
    parser_exec.add_argument('-e', '--entrypoint', help='The function name to execute in the script', default='main')
    parser_exec.add_argument('-q', '--queue', type=str, help='Scheduler queue name', default=None)
    parser_exec.add_argument('-l', '--limit', type=int, help='timeout limit in seconds', default=3600)
    parser_exec.add_argument('-w', '--watch', action='store_true', help='Follow the job status evolution', default=False)
    parser_exec.add_argument('-a', '--alias', type=str, help='Custom job name alias', default=None)
    parser_exec.add_argument('-r', '--result', action='store_true', help='Display the result when job done, require -w or --watch', default=False)
    parser_exec.add_argument('-t', '--token', type=str, help='API bearer token', required=True) # TODO: only for admin routes ????
    parser_exec.add_argument('-b', '--batch', action='store_true', help='Return only the ID not without verbose mode', default=False)


    # Command process:
    ### TEST CMD: ## python3 client.py process -n generate_thumbnails -i ~/projects/lab/pixyz-webapi/data_engine/data/cad/buggy.3dxml -p '{"width": 1920, "width": 1080}' -l 3600 -w
    parser_process = subparsers.add_parser('process',  help='Execute an embedded process in the cloud. Use the "list" command et the list of available processes')
    parser_process.add_argument('-n', '--name', type=str, help='The process name', required=True)
    parser_process.add_argument('-i', '--input', type=argparse.FileType('rb'), help='The local input file path', default=None)
    parser_process.add_argument('-p', '--params', type=str, help='The parameters', default="{}")
    parser_process.add_argument('-e', '--entrypoint', help='The function name to execute in the script', default='main')
    parser_process.add_argument('-q', '--queue', type=str, help='Scheduler queue name', default=None)
    parser_process.add_argument('-l', '--limit', type=int, help='timeout limit in seconds', default=3600)
    parser_process.add_argument('-w', '--watch', action='store_true', help='Follow the job status evolution', default=False)
    parser_process.add_argument('-r', '--result', action='store_true',
                             help='Display the result when job done, require -w or --watch', default=False)
    parser_process.add_argument('-a', '--alias', type=str, help='Custom job name alias', default=None)
    parser_process.add_argument('-t', '--token', type=str, help='API bearer token', required=True) # TODO: only for admin routes ????


    # Command convert:
    ## TEST CMD: ## python3 client.py convert -i ~/projects/lab/pixyz-webapi/data_engine/data/cad/buggy.3dxml -p '{"filename": "my_output", "extension": "glb"}' -o ./coucou.glb -l 3600
    parser_convert = subparsers.add_parser('convert', help='Convert a file to another format. Default filename is the input file name and extension is "pxz"')
    parser_convert.add_argument('-i', '--input', type=argparse.FileType('rb'), help='The local input file path', default=None, required=True)
    parser_convert.add_argument('-p', '--params', type=str, help='{"filename": "my_output", "extension": "glb"}', default="{}")
    parser_convert.add_argument('-o', '--output', type=str, help='Local output file path', default=None)
    parser_convert.add_argument('-q', '--queue', type=str, help='Scheduler queue name', default=None)
    parser_convert.add_argument('-l', '--limit', type=int, help='timeout limit in seconds', default=3600)
    parser_convert.add_argument('-a', '--alias', type=str, help='Custom job name alias', default=None)
    parser_convert.add_argument('-t', '--token', type=str, help='API bearer token', required=True) # TODO: only for admin routes ????

    # Command thumbnails:
    ## TEST CMD: ## python3 client.py thumbnails -i ~/projects/lab/pixyz-webapi/data_engine/data/cad/buggy.3dxml -p '{"width": 1024, "height": 768}' -o ./output_folder -l 3600
    parser_thumbnails = subparsers.add_parser('thumbnails', help='Generate thumbnails and a preview glb from a file')
    parser_thumbnails.add_argument('-i', '--input', type=argparse.FileType('rb'), help='The local input file path', default=None, required=True)
    parser_thumbnails.add_argument('-p', '--params', type=str, help='{"width": 1024, "height": 768}', default="{}")
    parser_thumbnails.add_argument('-o', '--output', type=str, help='Local output folder path', default=None)
    parser_thumbnails.add_argument('-q', '--queue', type=str, help='Scheduler queue name', default=None)
    parser_thumbnails.add_argument('-l', '--limit', type=int, help='timeout limit in seconds', default=3600)
    parser_thumbnails.add_argument('-a', '--alias', type=str, help='Custom job name alias', default=None)
    parser_thumbnails.add_argument('-t', '--token', type=str, help='API bearer token', required=True) # TODO: only for admin routes ????

    # Command metadata:
    ## TEST CMD: ## python3 client.py metadata -i ~/projects/lab/pixyz-webapi/data_engine/data/cad/buggy.3dxml -o local_metadata.json -l 3600
    parser_metadata = subparsers.add_parser('metadata', help='Generate metadata from a file')
    parser_metadata.add_argument('-i', '--input', type=argparse.FileType('rb'), help='The local input file path', default=None, required=True)
    parser_metadata.add_argument('-o', '--output', type=str, help='Write metadata.json', default=None)
    parser_metadata.add_argument('-q', '--queue', type=str, help='Scheduler queue name', default=None)
    parser_metadata.add_argument('-l', '--limit', type=int, help='timeout limit in seconds', default=3600)
    parser_metadata.add_argument('-a', '--alias', type=str, help='Custom job name alias', default=None)
    parser_metadata.add_argument('-t', '--token', type=str, help='API bearer token', required=True) # TODO: only for admin routes ????

    # Parse the command-line arguments
    args = parser.parse_args()

    # Based on the selected subcommand, perform the appropriate action
    
    if args.command == 'version':

        print(f"pixyz-scheduler-client v{__version__}")
    
    elif args.command == 'list':

        res = get_processes(args.url)
        print(json.dumps(res, indent=4))

    elif args.command == 'doc':

        # create a process file path from the process name
        processes_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts', 'process')
        script_file_path = os.path.join(processes_path, f'{args.name}.py')

        # check if the process exists
        if not os.path.isfile(script_file_path):
            print(f"Error: '{args.name}' process not found")
            return

        # grab the script file __doc__ content
        doc_content = None

        with open(script_file_path, 'r') as f:           
            tree = ast.parse(f.read())
            function_definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]

            for f in function_definitions:
                if f.name == 'main':
                    doc_content = ast.get_docstring(f)

        if doc_content is not None:
            print(f"Process '{args.name}' documentation:")
            print("")
            print(doc_content)
        else:
            print(f"'{args.name}' process documentation not found")
    
    elif args.command == 'jobs':
        res = get_jobs(args.url, args.token)
        print(json.dumps(res, indent=4))
    
    elif args.command == 'status':

        res = get_job_status(args.url, args.jobid, args.watch, token=args.token)
        print(json.dumps(res, indent=4))
    
    elif args.command == 'details':

        res = get_job_details(args.url, args.jobid, args.token)
        print(json.dumps(res, indent=4))
    
    elif args.command == 'outputs':

        res = get_job_outputs(args.url, args.jobid, args.token)
        print(json.dumps(res, indent=4))
    
    elif args.command == 'download':

        download_job_output(args.url, args.jobid, args.file, args.output, args.token)
    
    elif args.command == 'download_all':

        download_job_archive(args.url, args.jobid, args.output, args.token)

    elif args.command == 'exec':

        # convert the params string to a dictionary
        args.params = json.loads(args.params)
        post_job(args)

    elif args.command == 'process':

        # convert the params string to a dictionary
        args.params = json.loads(args.params)

        # # create a process file path from the process name
        # script_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts', 'process', f'{args.name}.py')
        #
        # # check if the process exists
        # if not os.path.isfile(script_file_path):
        #     print(f"Error: '{args.name}' process not found")
        #     return
        #
        # open local process script file and launch the process
        #script_file = open(script_file_path, 'rb')
        # Launch the process
        print(f"start {args.name} process")
        jobid = post_job(args, process=args.name)

        # close local process script file
        #script_file.close()

        # If watch is true print jobid details else print jobid status
        if args.watch:
            print(f"Job [ {jobid} ] completed")
            res = get_job_details(args.url, jobid, token=args.token)
            print(json.dumps(res, indent=4))
        else:
            print(f"Job [ {jobid} ] submitted")
    
    elif args.command == 'convert':

        # convert the params string to a dictionary
        args.params = json.loads(args.params)

        # grab the convert_file.py script
        script_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts', 'process', 'convert_file.py')

        # check if the file exists
        if not os.path.isfile(script_file_path):
            print(f"Error: '{script_file_path}' process not found")
            return

        # open local process script file and launch conversion process
        #
        script_file = open(script_file_path, 'rb')
        args.script = script_file

        # Launch the convert process and watch the status to wait for process completion
        args.watch = True
        jobid = post_job(args, 'convert_file')

        # close local process script file
        script_file.close()

        details = get_job_details(args.url, jobid)

        print(f"Job [ {jobid} ] completed")

        if args.output is not None:
            # grab the convert process output file name in the job details
            job_output_file = details['output']['file']

            download_job_output(args.url, jobid, job_output_file, args.output)
        else:
            print(json.dumps(details, indent=4))

    elif args.command == 'thumbnails':

        # convert the params string to a dictionary
        args.params = json.loads(args.params)

        # grab the generate_thumbnails.py script
        script_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts', 'process', 'generate_thumbnails.py')

        # check if the file exists
        if not os.path.isfile(script_file_path):
            print(f"Error: '{script_file_path}' process not found")
            return
        
        # open local process script file and launch thumbnails process
        script_file = open(script_file_path, 'rb')
        # Launch the thumbnails process and watch the status to wait for process completion
        args.watch = True
        jobid = post_job(args)

        # close local process script file
        script_file.close()

        details = get_job_details(args.url, jobid)

        print(f"Job [ {jobid} ] completed")

        # grab the list of job output files 
        output_files = get_job_outputs(args.url, jobid)['outputs']

        if args.output is not None:
            # create the output folder if it doesn't exist
            if not os.path.exists(args.output):
                os.makedirs(args.output)

            # download each output file to the output folder
            for output_file in output_files:
                download_job_output(args.url, jobid, output_file, os.path.join(args.output, output_file))
        else:
            print(json.dumps(output_files, indent=4))

    elif args.command == 'metadata':

        # convert the params string to a dictionary
        args.params = json.loads(args.params)

        # grab the generate_metadata.py script
        script_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'scripts', 'process', 'generate_metadata.py')

        # check if the file exists
        if not os.path.isfile(script_file_path):
            print(f"Error: '{script_file_path}' process not found")
            return
        
        # open local process script file and launch metadata process
        script_file = open(script_file_path, 'rb')
        # Launch the metadata process and watch the status to wait for process completion
        args.watch = True
        jobid = post_job(args)

        # close local process script file
        script_file.close()

        details = get_job_details(args.url, jobid)

        print(f"Job [ {jobid} ] completed")

        # grab the metadata in the job details output
        metadata = details['output']['metadata']

        if args.output is not None:
            # write the metadata to the output file
            with open(args.output, 'w') as f:
                f.write(json.dumps(metadata, indent=4))
                print(f"Job [ {jobid} ] metadata written to '{args.output}'")
        else:
            print(json.dumps(metadata, indent=4))
    
    else:
        print('No valid command specified')


if __name__ == "__main__":
    main()
