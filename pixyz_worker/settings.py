#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging.config
from kombu import Queue, Exchange
from os import environ
from .share import get_logger
from .config import debug
import os
logger = get_logger('pixyz_worker.settings')

################################################################
## BACKEND CONFIGURATION FROM ENVIRONMENT VARIABLES
################################################################
redis_master_port = environ.get('REDIS_MASTER_SERVICE_PORT', '6379')
redis_master_service_host = environ.get('REDIS_MASTER_SERVICE_HOST', 'localhost')
redis_password = environ.get('REDIS_PASSWORD')
redis_database = environ.get('REDIS_DATABASE', '0')

if redis_password:
    redis_password = ':' + redis_password + '@'
else:
    logger.warning("no REDIS_PASSWORD environment variable found, using empty password?")
    redis_password = ''

if redis_database == '0':
    logger.warning("REDIS_DATABASE is set to 0, you are running in PRODUCTION MODE, "
                   "otherwise please change this value to a non-zero value")

redis_url = 'redis://' + redis_password + redis_master_service_host + ':' + redis_master_port + '/' + redis_database

################################################################
## CELERY INITIALIZATION
################################################################
broker_url = environ.get('CELERY_BROKER_URL', redis_url)
result_backend = environ.get('CELERY_RESULT_BACKEND', redis_url+'0')
broker_batch_name = environ.get('CELERY_BATCH_NAME', 'pixyzbatch')


# DMX: When the workerlost exception is raised, the task retry in loop
CHORD_UNLOCK_MAX_RETRIES = 1
result_chord_join_timeout = 60 * 60 * 8  # 4 hours
import celery.utils.log
################################################################
## CELERY ROOT LOGGER
################################################################
# By default CELERYD_HIJACK_ROOT_LOGGER = True
# Is important variable that allows Celery to overlap other custom logging handlers
worker_hijack_root_logger = False


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "()": "celery.app.log.TaskFormatter",
            "format": "[%(asctime)s: %(levelname)s/%(processName)s] %(task_name)s[%(task_id)s]: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose"
        },
    },
    'loggers': {
        "": {
            "level": "INFO",
            "handlers": ["console", ],
            "propagate": False,
        },
    }
}
logging.config.dictConfig(LOGGING)
################################################################
## WORKER CONFIGURATION
################################################################
worker_concurrency = 1

# reconnect on failure
broker_connection_retry_on_startup = 5
broker_connection_max_retries = 5

################################################################
## TASK CONFIGURATION
################################################################
task_queues = (
    Queue('gpu', Exchange('gpu'), routing_key='gpu'),
    Queue('cpu', Exchange('cpu'), routing_key='cpu'),
)

# default queue
task_default_queue = 'cpu'
task_default_exchange = 'cpu'
task_default_routing_key = 'cpu'

# Take only one job at time
worker_prefetch_multiplier = 1

# Reject if worker is lost
# acknowledge at the end of the task
task_reject_on_worker_lost = True
task_acks_late = True
# This settings does not work because for pixyz, because it does not check current running process!
#worker_max_memory_per_child = 4 * 1024 * 1024  # 4GB


task_routes = {
    # -- GPU/HIGH COST OPERATION QUEUE -- #
    'pixyz_worker.tasks.sleep_gpu': {'queue': 'gpu'},
    # -- CPU/LOW COST OPERATION QUEUE -- #
    'pixyz_worker.tasks.sleep_cpu': {'queue': 'cpu'},
}

# Keep result only if you really need them: CELERY_IGNORE_RESULT = False
# In all other cases it is better to have place somewhere in db
#CELERY_IGNORE_RESULT = True

task_expire = 60 * 60 * 24 * 3  # 3 days

# Without this task stay always in PENDING state
task_track_started = False

task_remote_tracebacks = True
################################################################
## TIMEZONE
################################################################
enable_utc = True
#timezone = 'Europe/Paris'

################################################################
# if you want to debug celery worker, you can use this command:
if debug:
    logger.info("Celery entered in debug mode, all tasks will be executed locally and synchronously (debugger allowed)")
if os.getenv('CELERY_ALWAYS_EAGER', 'false').lower() == 'true':
    logger.info("Celery is in always eager mode, all tasks will be executed locally and synchronously")
    task_always_eager = True