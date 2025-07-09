# Pixyz SDK Scheduler

Pixyz SDK Scheduler is a distributed task scheduling system tailored for 3D workflows. It integrates natively with Pixyz SDK (Python). It triggers tasks via REST API and automates processing on local/cloud infrastructure.
* Robust, scalable, low-latency 3D task manager
* Optimized cost/performance via smart task placement
* Simplified dev-to-prod pipeline
* Supports advanced DAG-based processing


The Pixyz SDK Scheduler is a powerful toolkit designed for orchestrating and executing decentralized tasks across a network of specialized workers. Tailored for seamless integration with the Pixyz framework, this toolkit empowers users to effortlessly submit jobs to distributed workers via an intuitive API.

Each worker operates independently to execute assigned tasks, with jobs routed to specific queues based on their computing needs, such as cpu or gpu. Workers actively monitor these queues for incoming assignments, ensuring efficient task allocation and execution. Leveraging the robust Celery framework, the Pixyz SDK Scheduler efficiently manages and coordinates workers, guaranteeing smooth task execution.


# Overview

[![Unity Pixyz SDK Scheduler](https://img.youtube.com/vi/xxx)](https://www.youtube.com/watch?v=xxxxxx)

**🎥 Click the image above to watch the video on YouTube.**


## Key concepts
The Pixyz Scheduler uses the producer-consumer pattern to distribute tasks to workers.

![Global overview](docs/img/PiXYZScheduler_job_overview.jpg)

1. The user submits a **task**/**job** defined by a python script and if needed a 3D file, and it put it through the **HTTP API**.
2. The Pixyz Scheduler create a **task**/**job**
3. The new **jobs** is placed to the requested **queue**.
4. The **workers** are listening to new tasks in the queue(s) and process them according to their priorities.
5. The **workers** execute the task and save the result
6. The **API** can read the result and send it back to the user.

# Documentation
[Full documentation](docs/README.md)

********************************

# Quick Getting Started

This guide will get you up and running with Pixyz SDK Scheduler in under 15 minutes.

## Prerequisites

Before you begin, make sure you have:

- **Python 3.8+** installed
- **A valid Pixyz license** (NodeLock or FlexLM)
- **Redis server** (we'll help you install this)
- **10GB free disk space**

## Step 1: Choose Your Installation Method


### Option A: Local Development (Recommended for first-time users)

Perfect for learning and testing. Everything runs on your machine.

**Pros:**
- ✅ Quick setup (10 minutes)
- ✅ Easy debugging
- ✅ Works offline
- ✅ Full control over components

**Cons:**
- ❌ Limited to single machine
- ❌ Manual scaling

### Option B: **[Docker Compose](docs/docker-setup.md)** (Recommended for production)

Containerized setup that's production-ready.

**Pros:**
- ✅ Easy deployment
- ✅ Consistent environment
- ✅ Easy scaling
- ✅ Isolated components

**Cons:**
- ❌ Requires Docker knowledge
- ❌ Less debugging flexibility



## Step 2: Local Development Setup
For this getting started, we'll continue with local development option. Please refere this page for contenainerized setup: **[Quick Docker Setup](docs/docker-setup.md)**

### Install Redis

**On Windows:**
```powershell
# Install Windows Subsystem for Linux (WSL2) if not done previously
wsl --install
# Install Ubuntu on Windows if not done previously
# Then in WSL2 command invite:
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server # next time you reboot, you'll only need to start the redis-server
```

**On Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### Install Pixyz SDK Scheduler
Install `distutils` for Linux: `sudo apt-get install python3-distutils` or similar for Windows.

```bash
# 1. Create and activate virtual environment
python -m venv pixyz-scheduler
source pixyz-scheduler/bin/activate  # On Windows: pixyz-scheduler\Scripts\activate

# 2. Install packages
# Clone or download the repository first
pip install -r pixyz_api/requirements.txt
pip install -r pixyz_worker/requirements.txt

# 3. Create configuration file
cp pixyz-scheduler.conf.example pixyz-scheduler.conf # on Windows use "copy" insread of "cp"
```

### Configure the System

Edit `pixyz-scheduler.conf`:

```ini
# Redis Configuration
REDIS_MASTER_SERVICE_HOST=127.0.0.1
REDIS_MASTER_SERVICE_PORT=6379
REDIS_PASSWORD=

# API Configuration
API_PORT=8001
GOD_PASSWORD_SHA256=your_hashed_password_here

# Pixyz Configuration
PIXYZ_PYTHON_PATH=/path/to/your/pixyz/installation
LICENSE_FLEXLM=false  # Set to true if using FlexLM
LICENSE_HOST=your_license_server  # If using FlexLM
LICENSE_PORT=27000  # If using FlexLM

# Storage
SHARE_PATH=./share
PROCESS_PATH=./pixyz_api/processes 
```

### Generate API Password

**On Linux/macOS:**
```bash
echo -n "your_secret_password" | sha256sum
```

**On Windows Powershell:**
```powershell
$password = "your_secret_password"
$hasher = [System.Security.Cryptography.SHA256]::Create()
$hash = $hasher.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($password))
[System.BitConverter]::ToString($hash).Replace("-", "").ToLower()
```

Copy the hash to `GOD_PASSWORD_SHA256` in your config file.

## Step 3: Start the Services

Open three terminal windows:

### Terminal 1: Start the API Server
```bash
source pixyz-scheduler/bin/activate  # Activate virtual environment
python api.py
```

You should see:
```
INFO:     Started server process [2064]
INFO:     Uvicorn running on http://0.0.0.0:8001
```

### Terminal 2: Start a Worker
```bash
source pixyz-scheduler/bin/activate  # Activate virtual environment
python worker.py
```

You should see:
```
-------------- worker@your-computer v5.3.6
--- ***** ----- 
-- ******* ---- 
[2024-07-02 15:41:00] Pixyz ComputeEngine v2024.2.0.19
```

### Terminal 3: Test the Installation
```bash
# Test API connectivity
curl http://localhost:8001/

# List available processes
curl -H "x-api-key: your_secret_password" http://localhost:8001/processes
```

## Step 4: Submit Your First Job

### Using the Python Client

```bash

# Submit a simple test job
python ./client.py --url http://localhost:8001 process -n sleep -t your_secret_password -wr

# Convert a 3D file (if you have one)
python ./client.py --url http://localhost:8001 process -n convert_file -i path/to/your/model.fbx -t your_secret_password -rw

# Execute a custom python script
python ./client.py -u http://127.0.0.1:8001 exec -t your_secret_password -s ./scripts/tutorial/00_convert_a_file.py -i D:\\Models\\cube.cgr -rw
```



### Using the Web Interface

1. Open http://localhost:8001/docs in your browser
2. Click the lock icon and enter `your_secret_password`
3. Try the `/processes` endpoint to see available processes
4. Submit a job using the `/jobs` POST endpoint

## Step 5: Monitor Your Jobs

### Web Dashboard
- **API Documentation**: http://localhost:8001/docs
- **Flower Monitor** (if installed): http://localhost:5555

### Command Line
```bash
# List all jobs
python ./client.py --url http://localhost:8001 jobs -t your_secret_password

# Check specific job status
python ./client.py --url http://localhost:8001 status -j [job-uuid] -t your_secret_password

# Download job outputs
python ./client.py --url http://localhost:8001 download -j [job-uuid] -f output.glb -o /myFolder/output.glb -t your_secret_password
```

## Common First-Time Issues

### ❌ "Connection refused" error
**Problem**: Redis isn't running
**Solution**: Start Redis: `sudo systemctl start redis-server`

### ❌ "License error" 
**Problem**: Pixyz license not configured
**Solution**: Check `PIXYZ_PYTHON_PATH` and run `PiXYZFinishInstall`

### ❌ "401 Unauthorized"
**Problem**: Wrong API password
**Solution**: Verify `GOD_PASSWORD_SHA256` hash matches your password

### ❌ Worker not picking up jobs
**Problem**: Worker not connected to Redis
**Solution**: Check Redis configuration in `pixyz-scheduler.conf`

### ❌ No module named 'pxz'
**Problem**: Worker cannot find Pixyz SDK installation path
**Solution**: Check `PIXYZ_PYTHON_PATH`. Example on Windows: `PIXYZ_PYTHON_PATH="D:\\PiXYZAPI-2025.2.0.1-win64\\bin"`


## Next Steps

### Production Checklist
- [ ] Configure shared storage (NFS/cloud storage)
- [ ] Set up monitoring (Flower, Prometheus)
- [ ] Configure SSL/TLS for API
- [ ] Set up backup for Redis data
- [ ] Configure log rotation
- [ ] Set up health checks

## Need Help?

- **Check logs**: Look in the terminal output for error messages
- **Verify configuration**: Double-check `pixyz-scheduler.conf`
- **Test components individually**: Redis, API, Worker
- **Check firewall**: Ensure ports 6379 (Redis) and 8001 (API) are open

---

**🎉 Congratulations!** You now have a working Pixyz SDK Scheduler setup. Ready to process some 3D files?
