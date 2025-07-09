#!/bin/bash
set -e

# Define the maximum limit of memory usage and disable the core dump
ulimit -a
if [ -z "${MAX_MEMORY_USAGE}" ] || [ $MAX_MEMORY_USAGE -eq 0 ]; then
    echo "MAX_MEMORY_USAGE is 0, so set ulimit -m unlimited"
    ulimit -m unlimited
    ulimit -v unlimited
else
    echo "MAX_MEMORY_USAGE is not 0, so set ulimit -m ${MAX_MEMORY_USAGE}"
    ulimit -m ${MAX_MEMORY_USAGE}
    ulimit -v ${MAX_MEMORY_USAGE}
fi

echo "Disable core dump"
ulimit -c 0


if [ -z "${QUEUE_NAME}" ]; then
    echo "QUEUE_NAME is not set, so set default queue name"
    QUEUE_NAME="gpu,cpu"
fi

echo "Selected target queue: ${QUEUE_NAME}"


if [ -z "${CONCURRENT_TASKS}" ]; then
    echo "CONCURRENT_TASKS is not set, so set default concurrent tasks=1"
    CONCURRENT_TASKS=1
fi

echo "Service started with the following ulimit"
ulimit -a

if [ -z "${REDIS_MASTER_SERVICE_PORT}" ]; then
    echo "REDIS_MASTER_SERVICE_PORT is not set, so set default port to 6379"
fi

if [ -z "${REDIS_MASTER_SERVICE_HOST}" ]; then
    echo "REDIS_MASTER_SERVICE_HOST is not set, so set default port to locahost"
fi

if [ -z "${REDIS_PASSWORD}" ]; then
    echo "REDIS_PASSWORD is not set, no auth for redis planned"
fi

echo " ____  ___  ____   _______"
echo "|  _ \(_) \/ /\ \ / /__  /"
echo "| |_) | |\  /  \ V /  / /"
echo "|  __/| |/  \   | |  / /_"
echo "|_|   |_/_/\_\  |_| /____| ........ will be up and running soon"

cd /app/
python3 worker.py && echo 'success' || python3 watchdog.py
