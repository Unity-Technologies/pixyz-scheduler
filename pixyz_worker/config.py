#!/usr/bin/env python3
import os
import sys
import dotenv

__all__ = ['share_dir', 'version', 'debug', 'log_level', 'cleanup_delay', 'supported_archive']


def load_configuration_file():
    # check if a local configuration exists
    local_file = os.path.join(os.getcwd(), "pixyz-scheduler.conf")
    configuration_file = None
    if os.path.exists(local_file):
        configuration_file = local_file
    else:
        if sys.platform == 'win32':
            user_config_file = os.path.join(os.environ["APPDATA"], "PixyzSDK", "pixyz-scheduler.conf")
            system_config_path = os.path.join(os.environ["ProgramData"], "PixyzSDK", "pixyz-scheduler.conf")
            if os.path.exists(user_config_file):
                configuration_file = user_config_file
            elif os.path.exists(system_config_path):
                configuration_file = system_config_path
            else:
                print(f"WARNING: Neither Local({user_config_file} or {system_config_path}), loading default configuration with environment variable", file=sys.stderr)
        else:
            system_config_path = "/etc/pixyz-scheduler.conf"
            if os.path.exists(system_config_path):
                configuration_file = system_config_path
            else:
                print(f"WARNING: Neither Local({system_config_path} or {configuration_file}), loading default configuration with environment variable", file=sys.stderr)
    print(f"Loading configuration file {configuration_file}", file=sys.stderr)
    dotenv.load_dotenv(configuration_file)

load_configuration_file()

version = '2025.2.0.1'
debug = os.getenv('DEBUG', 'false').lower() == 'true'
concurrency = os.getenv('CONCURRENT_TASKS', 5 if debug else 1)
pool_type = os.getenv('POOL_TYPE', 'solo')
log_level = os.getenv('LOG_LEVEL', 'INFO')
queue_name = os.getenv('QUEUE_NAME', 'cpu,gpu,zip,clean,control')
supported_archive = {'zip': 'zip', 'tar': 'tar', 'gztar': 'tar.gz'}
max_solo_tasks = int(os.getenv('MAX_TASKS_BEFORE_SHUTDOWN', 0))
disable_pixyz = os.getenv('DISABLE_PIXYZ', 'false').lower() == 'true'
api_port = int(os.getenv('API_PORT', 8001))

# This time limit is used for pixyz task in the internal process manager (not the default celery manager that not works)
time_limit = int(os.getenv('PIXYZ_TIME_LIMIT', 60*40))  # on little worker, you can't wait more time
retry_time_limit = int(os.getenv('PIXYZ_RETRY_TIME_LIMIT', 60*60))  # on gpuhigh queue,you can wait more time

# License information
license_host = os.getenv('LICENSE_HOST', None)
license_port = int(os.getenv('LICENSE_PORT', 35000))
license_acquire_at_start = os.getenv('LICENSE_ACQUIRE_AT_START', 'true').lower() == 'true'
license_flexlm = os.getenv('LICENSE_FLEXLM', 'false').lower() == 'true'

# number of second to wait before deleting a share file (upload or extract)
cleanup_enabled = os.getenv('CLEANUP_ENABLED', 'false').lower() == 'true'
if not cleanup_enabled:
    pass
    # # No logger here, because circular import of logger
    # print('WARNING: Cleanup is disabled, please set environment variable to CLEANUP_ENABLED to true to enable it and '
    #       'CLEANUP_DELAY to set the delay before deleting a file')

# 1H by default
cleanup_delay = int(os.getenv('CLEANUP_DELAY', '3600'))


default_share_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'share'))
share_dir = os.getenv('SHARE_PATH', default_share_dir)

try:
    default_process_dir = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'pixyz_api', 'process'))
except ImportError:
    # In the docker worker case
    default_process_dir = '/process'

process_path = os.getenv('PROCESS_PATH', default_process_dir)


def print_pixyz_scheduler_configuration(variables):
    import sys
    print("PiXYZ Scheduler configuration", file=sys.stderr)
    print("=============================", file=sys.stderr)
    variables = sorted(list(filter(lambda x: not x.startswith("__") and \
                                             isinstance(eval(x), (str, int, float, bool, dict, list)), variables)))
    max_key_len = max([len(variable) for variable in variables])
    for variable in variables:
        if isinstance(eval(variable), (str, int, float, bool, dict, list)):
            print(f"{variable:{max_key_len}}: {eval(variable)}", file=sys.stderr)
    print("=============================", file=sys.stderr)

if debug:
    print_pixyz_scheduler_configuration(dir())
