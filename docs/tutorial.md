# PiXYZ Scheduler: Tutorial Overview
<!-- TOC -->
* [PiXYZ Scheduler: Tutorial Overview](#pixyz-scheduler-tutorial-overview)
  * [Introduction](#introduction)
    * [Key Features](#key-features)
    * [Limitations](#limitations)
  * [Setting Up and Running PiXYZ Scheduler](#setting-up-and-running-pixyz-scheduler)
    * [Running a Basic Script Locally](#running-a-basic-script-locally)
      * [Example Python Script: 00_sleep.py](#example-python-script-00_sleeppy)
      * [Execution](#execution)
    * [Using the Scheduler: Local Job Execution](#using-the-scheduler-local-job-execution)
      * [Execution Command](#execution-command)
  * [Adding Input Parameters](#adding-input-parameters)
    * [Example: Adding an Input Parameter](#example-adding-an-input-parameter)
      * [Execution](#execution-1)
  * [4. Progress Tracking](#4-progress-tracking)
    * [Example: Progress Tracking in 00_progress.py](#example-progress-tracking-in-00_progresspy)
      * [Execution](#execution-2)
  * [Writing Advanced Scripts: File Conversion](#writing-advanced-scripts-file-conversion)
    * [Example: 00_convert_a_file.py](#example-00_convert_a_filepy)
      * [Execution Command](#execution-command-1)
    * [Downloading Output Files](#downloading-output-files)
* [Download specific file](#download-specific-file)
* [Download all files in a zip](#download-all-files-in-a-zip)
  * [Handling Errors](#handling-errors)
    * [Example: Error Output](#example-error-output)
  * [Using Pre-Built Process Scripts](#using-pre-built-process-scripts)
    * [Example: Listing Pre-Built Scripts](#example-listing-pre-built-scripts)
    * [Execute a Pre-Built Script](#execute-a-pre-built-script)
  * [Create script with Directed-Acyclic Graph (DAG)](#create-script-with-directed-acyclic-graph-dag)
  * [Conclusion](#conclusion)
<!-- TOC -->
This guide provides a step-by-step explanation of how to use the PiXYZ Scheduler, covering everything from basic usage to advanced scripting and task management. It discusses running scripts locally, using the scheduler for job execution, creating scripts with input parameters, tracking progress, handling errors, and using pre-built scripts.

---

## Introduction

PiXYZ Scheduler is a lightweight but powerful scheduling framework designed for efficiently managing computational jobs written in Python. It enables running scripts both locally and in the cloud, providing seamless progression from prototyping to production environments.

---

### Key Features
- Low Latency: Jobs are scheduled with fast processing times (~20ms).
- Light Infrastructure: No Kubernetes is required. Deployment works locally, on-premise, or in cloud environments.
- Ease of Use: Simple setup with pre-built processes for common tasks.
- Dynamic Task Structure: Support for Directed Acyclic Graphs (DAGs) for complex workflows.

### Limitations
- Only supports Python scripts (optimized for PiXYZ SDK).
- Limited isolation and security features—requires external orchestration for privacy and authentication (e.g., Kubernetes or Argo Workflows).
  
> ⚠ Note: Advanced scenarios requiring rigorous security or running other types of jobs (non-Python workloads) should integrate external tools.

---

## Setting Up and Running PiXYZ Scheduler

The PiXYZ Scheduler allows you to execute Python scripts locally or through the scheduler. Here’s how you can execute basic scripts and progressively add features to your workflows.
If you want to create a local script you need to install the `pixyz_worker` package.

### Running a Basic Script Locally

Start by creating a minimal script and running it directly on your workstation:

#### Example Python Script: 00_sleep.py
```python
#!/usr/bin/env python3
import time
from pixyz_worker.script import *

def main(pc: ProgramContext, params: dict):
    print("sleep 0.1 sec")
    time.sleep(0.1)

if name == "main":
    main(ProgramContext.fromlocal(file_), {})
```

#### Execution
```bash
Run the script locally:
python scripts/tutorial/00_sleep.py


Output:
sleep 0.1 sec
```

---

### Using the Scheduler: Local Job Execution

You can run the same script on the PiXYZ Scheduler using the client API. This demonstrates how jobs are uploaded to the scheduler and executed.

#### Execution Command
```bash
python ./client.py -u SERVERURL -k SERVERTOKEN exec -s scripts/tutorial/00_sleep.py -rw


Expected Output:
-------- New PixyzScheduler Job ---------
- script file:  'scripts/tutorial/00_sleep.py'
- script params: "{}"
- worker config: {"entrypoint": "main", "queue": "cpu", "time_limit": 3600}
- watch status: True
-----------------------------------------
Uploading...
Job [UUID] started
Job [UUID] progress: 100, status: SUCCESS [⏳]


You can check job details by using:
python ./client.py -u SERVERURL -k SECRETTOKEN details -j {JOB_UUID}
```

---

## Adding Input Parameters

Scripts can be configured to accept input parameters dynamically, which helps make them reusable for different tasks.

### Example: Adding an Input Parameter
```python
Modify the original script to include a time (t) parameter:
#!/usr/bin/env python3
import time
from pixyz_worker.script import *

def main(pc: ProgramContext, params: dict):
    t = params.get("t", 0.1)
    print(f"sleep {t} sec")
    time.sleep(t)
    return t

if name == "main":
    main(ProgramContext.fromlocal(file_), {"t": float(sys.argv[1])})
```

#### Execution
Run the script with a specified sleep time:
```bash
Pass the parameter:
python scripts/tutorial/00_sleep.py 0.02

Output:
sleep 0.02 sec
```

---

## 4. Progress Tracking

To improve monitoring during task execution, the PiXYZ Scheduler provides functionality to track progress through predefined steps.

### Example: Progress Tracking in 00_progress.py
```python
#!/usr/bin/env python3
import time
from pixyz_worker.script import *

def main(pc: ProgramContext, params: dict):
    pc.progresssettotal(2)  # Define 2 steps
    pc.progress_next("Step 1: Doing something")
    time.sleep(0.1)
    pc.progress_next("Step 2: Doing something else")
    time.sleep(0.2)

if name == "main":
    main(ProgramContext.fromlocal(file_), {})
```

#### Execution
Run the script via the scheduler:
```bash
python ./client.py -u SERVERURL -k SECRETTOKEN exec -s scripts/tutorial/00progress.py -rw


Expected Output:
Job [UUID] progress: 50, status: RUNNING  [Step 1]
Job [UUID] progress: 100, status: SUCCESS [Step 2]
```

You can query for detailed runtime information and step durations.

---

## Writing Advanced Scripts: File Conversion

Create scripts with advanced features like file imports and exports. Below is an example of a script that converts files to a specified output format.

### Example: 00_convert_a_file.py
```python
#!/usr/bin/env python3
import time
from pixyz_worker import io
from pixyz_worker.script import *

def main(pc: ProgramContext, params: dict):
    pc.progresssettotal(3)
    extension = params.get('extension', 'pxz').lower()

    # Import File
    importfilename = pc.get_input_file()
    pc.progressnext(f"Importing file: {importfile_name}")

    # Convert the file
    root = io.importScene(importfilename)
    pc.progress_next(f"Exporting file as output.{extension}")
    io.exportScene(pc.get_output_dir(f'output.{extension}'), root)

    pc.progress_next("Conversion complete")
    return {"output": f"output.{extension}"}

if name == "main":
    main(ProgramContext.fromlocal(file_), {})
```

#### Execution Command
Upload and process a file:
```bash
python ./client.py -u SERVERURL -k SECRETTOKEN exec -s scripts/tutorial/00convertafile.py -i /path/to/input_file -rw
```

### Downloading Output Files
Once the job completes successfully, you can retrieve output files:
# Download specific file
```bash
python ./client.py -u SERVERURL -k SECRETTOKEN download -j {JOBUUID} -f output.pxz -o output.pxz
```

# Download all files in a zip
```bash
python ./client.py -u SERVERURL -k SECRETTOKEN downloadall -j {JOBUUID} -o outputfiles.zip
```

---

## Handling Errors

The PiXYZ Scheduler provides detailed tracebacks when a script fails, which makes it easier to debug issues in the code or input parameters.

### Example: Error Output
```bash
python ./client.py -u SERVERURL -k SECRETTOKEN exec -s scripts/tutorial/00convertafile.py -p '{"extension": 123}' -w


Error Details:
Job [UUID] progress: 0, status: FAILURE  [⌛]
Traceback (most recent call last):
File "00converta_file.py", line 10, in main
    extension = params.get('extension', 'pxz').lower()
AttributeError: 'int' object has no attribute 'lower'
```

Errors are stored in the error field of the API response.

---

## Using Pre-Built Process Scripts

PiXYZ Scheduler includes pre-built scripts for common tasks. These scripts can be queried, executed, and documented programmatically.

### Example: Listing Pre-Built Scripts
```bash
python ./client.py -u SERVER_URL list


Output:
{
    "processes": [
        "api_test",
        "convert_file",
        "generate_metadata",
        "generate_thumbnails",
        "sleep"
    ]
}
```

### Execute a Pre-Built Script
```bash
python ./client.py -u SERVERURL -k SECRETTOKEN process -n convertfile -p '{"extension": "fbx"}' -w
```

---

## Create script with Directed-Acyclic Graph (DAG)

You can use the `pixyz_worker` package to create a Directed-Acyclic Graph (DAG) of tasks. This allows you to define complex workflows with dependencies between tasks.
This example creates a simple DAG:
 * a chain of two tasks: the first task sleeps for a specified time, and the second task sleeps get the result of the first task as parameter.

```python
from pixyz_worker.script import *
from pixyz_worker.tasks import pixyz_execute
import time
from celery import chain

def my_sleep(pc: ProgramContext, params: dict):
    pc.progress_next("inception inside should not working"+str(params))
    print("task params: ", params)
    time.sleep(params['time'])
    params['time'] = params['time'] / 10
    return params


def main(pc: ProgramContext, params: dict):
    c = chain(pixyz_execute.s({'time': 2, 'id': 2}, pc.clone().update(entrypoint='my_sleep', raw=True)),
        pixyz_execute.s(pc=pc.clone().update(entrypoint='my_sleep', raw=True))).apply_async()
    #c.parent.save()
    print("chain return" + str(c) + str(type(c)))
    print(c.children)
    return c.as_tuple()
```
1. Use the `chain` function to create a sequence of tasks. This is a feature of celery framework.
2. The first `pixyz_execute.s` task/function to execute a script with parameters:
   1. parameters for pixyz_execute function
   2. A `ProgramContext`. In this example, we clone the existing `ProgramContext` object, but we change the entrypoint and enable raw parameters (specific to celery framework, we don't want that pixyz scheduler changes the output).
3. The second `pixyz_execute.s` task/function to execute a script with parameters:
   1. We don't set any parameters because the chain function will pass the result of the first task as parameters.
   2. We define the `ProgramContext` through the `pc` parameter. In this example, we clone the existing `ProgramContext` object, but we change the entrypoint and enable raw parameters (specific to celery framework, we don't want that pixyz scheduler changes the output).

Finally, we call the chain function in asynchronous mode, and we return the chain as a tuple.

If you want more example, please check the `pixyz_worker.script` content (dag, group, chain, etc...) or the `pixyz_worker.process.thumbnail_chained` for a more complex example.
 

---

## Conclusion

PiXYZ Scheduler is a versatile framework that supports a wide range of Python-based workloads. With its simple API and customization options, individuals and teams can efficiently process data, convert files, or execute workflows in distributed environments.

For further resources, consult the PiXYZ API documentation or join the discussion in #devs-pixyz.