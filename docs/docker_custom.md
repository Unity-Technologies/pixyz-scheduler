# Building a custom pixyz worker container for the pixyz scheduler with additional python packages
 
In this guide, we'll walk through the steps to build a Docker container, based on an existing container called 
`pixyzworker`, and add Python packages to it.

---

## Prerequisites

Before you begin, ensure you have the following:

1. **Docker Installed**: Download and install Docker from [Docker's official website](https://www.docker.com/).
2. **Basic Docker Knowledge**: Familiarity with Docker commands and concepts is helpful.
3. **Python Package Names**: Decide which Python packages you want to add (e.g., `numpy`, `pandas`, etc.).

---

## Steps to Build the Docker Container

### Step 1: Pull the Base Scheduler Image
Start by pulling the existing `scheduler` container image from Docker Hub or your private registry:

```bash
docker pull pixyzinc/pixyz-scheduler-worker:latest
``` 

### Step 2: Create a Dockerfile

```Dockerfile
# Use the scheduler image as the base
FROM pixyzinc/pixyz-scheduler-worker:latest

# Install new pip packages
pip install --user --no-cache-dir \
    numpy \
    pandas \
    scikit-learn \
    matplotlib
```

### Step 3: Build the Docker Image
Navigate to the directory containing your `Dockerfile` and run the following command to build your custom Docker image:

```bash
docker build -t my_custom_pixyzworker .
```

### Step 4: Configure your new worker image in pixyz scheduler
#### with kubernetes
#### Apply for all workloads
You could change the default image
```yaml
  workers:
    default:
      image:
        repository: 
        pullPolicy: IfNotPresent
        tag: "2025.2.0.1"
```

#### with docker-compose


