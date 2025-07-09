<!-- TOC -->
* [General information](#general-information)
  * [Repository structure](#repository-structure)
  * [Share storage structure](#share-storage-structure)
* [Developer Guide](#developer-guide)
  * [Create your first script](#create-your-first-script)
    * [Import the SDK](#import-the-sdk)
    * [The ProgramContext](#the-programcontext)

  * [The `pixyz_execute` task](#the-pixyz_execute-task)
  * [The pixyz_schedule decorator](#the-pixyz_schedule-decorator)
  * [Security Considerations](#security-considerations)
* [API Reference](#api-reference)
  * [ProgramContext](#programcontext)
    * [init](#init)
      * [Parameters](#parameters)
        * [Example](#example)
        * [Default parameters](#default-parameters)
    * [update](#update)
      * [Parameters](#parameters-1)
        * [Examples](#examples)
      * [Returns](#returns)
    * [progress _function_](#progress-_function_)
      * [Examples](#examples-1)
    * [clone](#clone)
      * [Parameters](#parameters-2)
      * [Returns](#returns-1)
    * [get_shared_file_path](#get_shared_file_path)
      * [Parameters](#parameters-3)
      * [Returns](#returns-2)
      * [Examples](#examples-2)
    * [get_input_file](#get_input_file)
      * [Examples](#examples-3)
      * [Exceptions](#exceptions)
    * [is_compute_only](#is_compute_only)
      * [Returns](#returns-3)
      * [Examples](#examples-4)
    * [is_local](#is_local)
      * [Returns](#returns-4)
    * [from_local](#from_local)
      * [Parameters](#parameters-4)
      * [Returns](#returns-5)
      * [Examples](#examples-5)
    * [AsyncResult](#asyncresult)
      * [Parameters](#parameters-5)
    * [allow_join_result](#allow_join_result)
      * [Returns](#returns-6)
    * [execute](#execute)
      * [Parameters](#parameters-6)
      * [Returns](#returns-7)
  * [Exceptions](#exceptions-1)
<!-- TOC -->
# General information
## Repository structure
```
.
├── pixyz_api         # Fast API server and endpoints
│   ├── process       # Embedded predifined process exposed by the API
│   ├── admin         # Admin endpoints for managing tasks
│   ├── backend       # API endpoints for celery bindings and task management
│   ├── jobs          # Trigger jobs & monitor status
│   ├── processes     # List and manage preconfigures jobs type 
│   └── tests         # tests and snippet for local usage (*outdated*)
├── pixyz_worker      # the worker for running Pixyz tasks (the PiXYZ Scheduler)
├── scripts           # Prebuilt scripts for Pixyz tasks
│   └── tutorial      # Developer oriented scripts for testing and learning
└── share             # Workers shared directory for local development
```
## Share storage structure
The Pixyz Scheduler uses a shared storage directory to store job input and output files. This directory is created by the scheduler and is unique for each task.
An archive directory will also be created to store a zip archive of all job outputs when requested. 
```
.
├── {UUID}            # Job unique id
│   ├── inputs        # job input file(s) and script
│   ├── outputs       # job output files
│   └── archives      # zip archive of all job outputs
├── {...}
│
```

# Developer Guide
The Pixyz Scheduler is a powerful toolkit designed for orchestrating and executing decentralized tasks across a network of specialized workers.

We are using a dedicated SDK which allows you to create your own local scripts (you can execute the script without a Pixyz scheduler infrastructure) or execute it on remote/cloud hosts through the Pixyz Scheduler.

This part will help you to understand how to create your own scripts and how to use the Pixyz Scheduler SDK.

## Create your first script
```python
#!/usr/bin/env python3
import time
from pixyz_worker.script import * # (1) import the SDK

@pixyz_schedule() # (1) (optional) Decorate your function with the pixyz_schedule decorator if you want to set more options like timeout, queue, etc...
def main(pc: ProgramContext, params: dict): # (2) Declare an entrypoint function
   print("sleep 0.1 sec")
   time.sleep(0.1)

if __name__ == '__main__':
    LocalPixyzTask.from_commandline(__file__, os.getcwd(), 'main')
```

### Import the SDK
The python module `pixyz_worker.script` contains the SDK to interact with the Pixyz Scheduler and some tools to help you to.

### The ProgramContext
This a class designed to manage program contexts by manipulating a set of configuration arguments like the shared directory, the 3D file, the script control (local or remote), and the progress tracking.
Take a look in the reference [ProgramContext](#programcontext) for more information.

###

## The `pixyz_execute` task
The `pixyz_execute` task is a Celery task that executes Python scripts on the Pixyz Scheduler. It is designed to run on a remote host and is managed by the Pixyz Scheduler.
It must be not called from a pixyz scheduler script except if you want to create a new task from a task.

## The pixyz_schedule decorator
The `pixyz_schedule` decorator is used to define a task that can be executed by the Pixyz Scheduler. It is used to define the task's behavior, such as the timeout, the wait option, and the task name.



## Security Considerations

- Currently, scripts are executed without sandboxing or chrooting.
- Exercise caution when running scripts and avoid hazardous actions.
- Don't open the scheduler to the public internet without proper security measures.


# API Reference

## ProgramContext
This class is designed to manage program contexts by manipulating a set of configuration arguments:
* worker option (data, tmp directory, ...)
* script control (local or remote)
* progress tracking

A program context **is mandatory** for each script function. It is used to manage the script execution and to interact with the Pixyz Scheduler.

:warning: Every information stored in the ProgramContext must be serializable.

### init

Constructor that initializes a ProgramContext object with arguments passed as keywords.

#### Parameters

- `**kwargs`: Initial configuration parameters.

##### Example

```python
context = ProgramContext(datafile='/path/to/data', islocal=True)
```

##### Default parameters
| Parameter      | Default Value                    | Description                                                                                                                                                                                                                                                                      |
|----------------|----------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `compute_only` | False                            | Don't create a shared space, just compute. Because before each compute task the scheduler create temporary and working directory. When, we don't create any working directory.<BR>This mode is useful when you don't need input or when you input/ouput is stored in other place |
| `data`         | None                             | Data 3D file as input. It can be a zip or a 3D file. By default, this value is filled by the `pixyz_execute` task                                                                                                                                                                |
| `root_file`    | None                             | Name of the root file if different of `data`. `data` may be a zip with a bunch of file, and the root_file the file to load                                                                                                                                                       |
| `tmp`          | True                             | Create a temporary directory if needed                                                                                                                                                                                                                                           |
| `is_local`     | False                            | By default, the task is not local. This boolean stores what is the current behavior of the script                                                                                                                                                                                |
| `entrypoint`   | 'main'                           | The function to call in your script                                                                                                                                                                                                                                              |
| `time_request` | `datetime.utcnow()`              | Request time. This value will be reported by the API and useful for benching from the API to tasks                                                                                                                                                                               |
| `raw`          | False                            | No raw data useful for single task, raw data is used for celery chaining                                                                                                                                                                                                         |

### update
Updates the current object with the given parameters. This function is useful when:
* you want to update the current context like the progress status
* you want to create a new task that comes from the current one but with different parameters

#### Parameters

- `**kwargs`: Key-values to update in the context.

##### Examples
Update the root file for the current running context

```python
@pixyz_schedule(wait=True, timeout=3600)
def main(pc: ProgramContext, params: dict):
    pc.update(root_file='my_file')
```

Create a new context with the same configuration as the current one, but with a different entrypoint.
```python
@pixyz_schedule(wait=True, timeout=3600)
def main(pc: ProgramContext, params: dict):
    new_pc = pc.clone().update(entrypoint='load_file_and_metadata', raw=True)
```
#### Returns

- The updated ProgramContext object.


### progress _function_
| Function                | Description                                                                      | Parameters                |
|-------------------------|----------------------------------------------------------------------------------|---------------------------|
| `progress_start()`      | Start a progress task                                                            | _None_                    | 
| `progress_set_total(n)` | Set the total amount of tasks: It is used for progress percentage calculation    | _n_ number of tasks       |
| `progress_next(info)`   | Move to the next progress step: calculate the new timing with the associate name | _info_ information string | 
| `progress_stop()`       | Stop the progress task                                                           | _None_                    |  


#### Examples
```python
@pixyz_schedule()
def main(pc: ProgramContext, params: dict):
    # Set the number of progress steps to 2
    pc.progress_set_total(2)

    # Step 1
    pc.progress_next("Sleep 2")
    sleep(2)

    # Step 2
    pc.progress_next(f"Sleep 3")
    sleep(3)
    
    # save last progress step duration
    pc.progress_stop()

    return "ok"
```    

In this example, you should have a progress bar with 2 steps:
* Step 1: Sleep 2
* Step 2: Sleep 3

It will be return something like this:
```json
{
        "steps": [
            {
                "info": "Sleep 2",
                "duration": 2.000000238418579
            },
            {
                "name": "Sleep 3",
                "duration": 3.000001337
            }
        ]
}
```

### clone
Creates a new ProgramContext by cloning the existing one and applying any additional modifications if not defined.
This function is useful when you want to create a new task that comes from the current one but with different parameters.

#### Parameters

- **kwargs: Modifications or updates to apply to the clone.

#### Returns

- A new, updated ProgramContext object.



### get_input_dir/get_output_dir

Each job task has a shared directory where the input and output files are stored. This function returns the path to the shared directory or file.

Note: this directory is created by the scheduler and is unique for each task. You can avoid this behavior by setting the `compute_only` parameter to `True`.

#### Parameters

- filename (str, optional): Filename to generate an absolute path.

#### Returns

- Path to the shared directory or file.

#### Examples

```python
@pixyz_schedule()
def main(pc: ProgramContext, params: dict):
  # Get the shared directory path
  # /shared/<JOBUID>/inputs
  shared_dir = pc.get_input_dir()   # Get the shared directory path

  # Get the shared file path
  # /shared/<JOBUID>/outputs/myfile.txt
  shared_file = pc.get_output_dir('myfile.txt')
```

### get_input_file

Returns the path to the data file. This function is useful when you need to access the input data file even if the file is extracted from a zip archive or directly uploaded

* _None_ if no data file is present in the ProgramContext (no 3D files from API).
* The absolute path to the data file if it is present.

#### Examples

```python
@pixyz_schedule()
def main(pc: ProgramContext, params: dict):
  # If you provide a data file, you can access it with this function
  # If
  data_file = pc.get_input_file()

``` 

#### Exceptions

- ValueError: If no data file is present in the ProgramContext.

### is_compute_only

Indicates whether the current configuration is in "compute only" mode. No shared directory has been created.

#### Returns

- Boolean indicating the status.

#### Examples

```python
@pixyz_schedule()
def main(pc: ProgramContext, params: dict):
  # Check if the current context is in compute only mode
  if pc.is_compute_only():
    print("You don't have a shared directory")
  else:
    shared_directory = pc.get_output_dir()
    print(f"Your shared directory is {shared_directory}")
```


### is_local
Indicates if the current context is configured for local execution `true` or a remote `false`.

#### Returns

- Boolean indicating the local status.

### from_local
Static method to create a ProgramContext for local execution.

#### Parameters

- script: Script to execute.
- input_path (optional): Input data path.
- output_dir (optional): Shared output directory.

#### Returns

- A new ProgramContext object.

#### Examples
```python
@pixyz_schedule()
def main(pc: ProgramContext, params: dict):
    # Create a new ProgramContext for local execution
    local_pc = ProgramContext.from_local(__file__, "/tmp/input", "/tmp/output")
``` 

### AsyncResult
Returns an asynchronous result for the configured task. This class will be used to create a new task from a task or to get the result of a task.

#### Parameters

- id: Task identifier.
- backend: Task backend.
- task_name (optional): Task name (deprecated).
- app: Application associated with the task.
- parent: Parent of the task.

### allow_join_result
Allows joining the results of a task, depending on whether it is local or not (cf celery documentation).

Warning: This function will block the current thread until the result is available.

#### Returns

- Function to join the results.

### execute
Executes a task based on the context parameters, either locally or remotely.

#### Parameters

- params: Specific parameters for the task to execute.

#### Returns

- The result of the executed task.

## Exceptions

Certain methods in the class may raise specific exceptions like PixyzSharedDirectoryNotFound, and they must be properly managed by the user of this class.

