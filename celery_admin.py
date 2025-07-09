#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import json
from celery.app.control import Inspect


from pixyz_worker import *
import argparse

logger = get_logger('pixyz_worker.celery_admin')


def safe_json_dump(obj):
    try:
        return json.dumps(obj, indent=4, default=str)
    except Exception as e:
        logger.error(f"Error while dumping json: {e}")
        return "n/a"


def list_tasks(queue_tasks):
    if queue_tasks.active:
        print("Active tasks:")
        print(safe_json_dump(Inspect(app=app).active()))
    if queue_tasks.scheduled:
        print("Scheduled tasks:")
        print(safe_json_dump(Inspect(app=app).scheduled()))
    if queue_tasks.reserved:
        print("Reserved tasks:")
        print(safe_json_dump(Inspect(app=app).reserved()))


def list_stats():
    print(json.dumps(Inspect(app=app).stats(), indent=4))


def list_queues():
    for queues in list(app.control.inspect().active_queues().values()):
        for queue in queues:
            print(queue['name'])


def main():
    arg_parser = argparse.ArgumentParser(description='Celery admin tool')
    subparsers = arg_parser.add_subparsers(title='subcommands', dest='command', help='Available commands')

    queue_tasks = subparsers.add_parser('tasks', help='Tasks management')
    queue_tasks.add_argument('-a', '--active', action='store_true', help='active tasks')
    queue_tasks.add_argument('-s', '--scheduled', action='store_true', help='scheduled tasks (clean tasks)')
    queue_tasks.add_argument('-r', '--reserved', action='store_true', help='reserved tasks (pre-fetch tasks)')
    subparsers.add_parser('stats', help='Stats tasks management')
    queue = subparsers.add_parser('queue', help='Purge tasks management')
    queue.add_argument('-p', '--purge', action='store_true', help='purge all queues')
    queue.add_argument('-l', '--list', action='store_true', help='list queue')

    args = arg_parser.parse_args()

    if args.command == 'tasks':
        list_tasks(args)
    elif args.command == 'stats':
        list_stats()
    elif args.command == 'queue':
        if args.list:
            list_queues()
        elif args.purge:
            print(f"We have purged {app.control.purge()} tasks")
        else:
            arg_parser.print_help()
    else:
        arg_parser.print_help()


if __name__ == '__main__':
    main()