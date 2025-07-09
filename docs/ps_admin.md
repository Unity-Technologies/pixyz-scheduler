# Pixyz Scheduler Administrator Guide
Pixyz Scheduler is a tool designed to manage and schedule tasks within the Celery framework. It provides a command-line interface to inspect, list, and purge tasks and queues. Below is the documentation to help you understand its functionality and usage.


## Statistics
You can get the statistics of the queues by using the `stats` command line tool:

```bash
python celery_admin.py stats
Loading configuration file /home/dmx/work/pixyz-scheduler/pixyz-scheduler.conf
{
    "worker@bear": {
        "total": {
            "pixyz_execute": 25,
            "cleanup_share_file": 23
        },
        "pid": 225477,
        "clock": "15992",
        "uptime": 74212,
        "pool": {
            "implementation": "celery.concurrency.solo:TaskPool",
            "max-concurrency": 1,
            "processes": [
                225477
            ],
...
```

## Tasks management

Pixyz Scheduler is executed as a CLI tool. Below are the available commands and options:

### Command: `tasks`
Manage tasks in the Celery environment.

#### Options:
- `-a, --active`  
  Display active tasks.
  
- `-s, --scheduled`  
  Display scheduled tasks (tasks that are queued for execution).
  
- `-r, --reserved`  
  Display reserved tasks (tasks pre-fetched by workers but not yet executed).

#### Example:
```bash
python pixyz_scheduler.py tasks --active
python pixyz_scheduler.py tasks --scheduled
python pixyz_scheduler.py tasks --reserved
```