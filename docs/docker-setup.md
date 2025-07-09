# Docker Setup Guide

This guide covers setting up Pixyz SDK Scheduler using Docker and Docker Compose for easy deployment and maintenance.

## Prerequisites

- **Docker Engine**: Latest version with Docker Compose v2.24.5 or higher
- **Platform Support**:
  - **Windows**: Docker Desktop (recommended with WSL2 integration)
  - **Linux**: Docker Engine with NVIDIA Container Toolkit for GPU support
  - **macOS (x86_64)**: Docker Desktop (GPU not available, M1 Macs not supported)
- **License**: Valid Pixyz FlexLM license (NodeLock licenses will NOT work with Docker)
- **Optional**: NVIDIA Container Toolkit for GPU acceleration

## Architecture Overview

Docker deployment provides:
- **Easy Setup**: Quick deployment with minimal configuration
- **Consistency**: Same environment as production
- **Scalability**: Easy horizontal scaling with Docker Compose
- **Isolation**: Containerized components for better security

## Quick Start

### 1. Configuration

Create a `pixyz-scheduler.conf` file from the example:

```bash
cp pixyz-scheduler.conf.example pixyz-scheduler.conf
```

Edit the configuration file with your settings:

```ini
# Docker Images
DOCKER_REDIS_IMAGE=redis:latest
DOCKER_API_IMAGE=pixyzinc/pixyz-scheduler-api:latest
DOCKER_WORKER_IMAGE=pixzyinc/pixyz-scheduler-worker:latest

# License Configuration (REQUIRED for Docker)
LICENSE_FLEXLM=true
LICENSE_HOST=your-license-server.com
LICENSE_PORT=27000
LICENSE_ACQUIRE_AT_START=true

# API Authentication (REQUIRED)
GOD_PASSWORD_SHA256=your-sha256-password-hash
API_PORT=8001

# Pixyz SDK Path (Docker Default)
PIXYZ_PYTHON_PATH=/opt/pixyz

# Storage Configuration
SHARE_PATH=/tmp/share
UID=1001
GID=1001
```

### 2. Generate Password Hash

Generate a SHA256 hash for your API password:

**Linux/macOS:**
```bash
echo -n "your_password" | sha256sum
```

**Windows PowerShell:**
```powershell
$mystring = "your_password"
$mystream = [IO.MemoryStream]::new([byte[]][char[]]$mystring)
Get-FileHash -InputStream $mystream -Algorithm SHA256
```

### 3. Basic Deployment

Start with the default configuration:

```bash
docker-compose up
```

This creates:
- 1 API server on http://localhost:8001
- 1 Redis server (internal)
- 1 Worker with solo + control queues
- 0 GPU workers (scaled to 0)
- 0 Flower monitoring (scaled to 0)

## Advanced Configuration

### Scaling Workers

Scale workers based on your needs:

```bash
# Scale to 3 CPU workers + 1 GPU worker + monitoring
docker-compose up --scale worker=3 --scale gpuhigh=1 --scale flower=1 --scale control=1
```

### GPU Support

#### Linux with NVIDIA GPUs

1. Install NVIDIA Container Toolkit:
   ```bash
   # Ubuntu/Debian
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   
   sudo apt-get update
   sudo apt-get install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```

2. Verify GPU access:
   ```bash
   docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
   ```

3. Enable GPU in docker-compose.yml:
   ```yaml
   gpu:
     # ... other config ...
     deploy:
       resources:
         reservations:
           devices:
             - driver: nvidia
               count: 1
               capabilities: [gpu]
   ```

#### Windows

GPU support is not available on Windows with Docker. Use the standalone installation instead.

## Service Configuration

### Docker Compose Services

The `docker-compose.yml` defines these services:

```yaml
version: '3.8'
services:
  redis:
    image: ${DOCKER_REDIS_IMAGE}
    ports:
      - "6379:6379"
  
  api:
    image: ${DOCKER_API_IMAGE}
    ports:
      - "${API_PORT}:8001"
    depends_on:
      - redis
    environment:
      - REDIS_MASTER_SERVICE_HOST=redis
      - GOD_PASSWORD_SHA256=${GOD_PASSWORD_SHA256}
  
  worker:
    image: ${DOCKER_WORKER_IMAGE}
    depends_on:
      - redis
    environment:
      - REDIS_MASTER_SERVICE_HOST=redis
      - LICENSE_HOST=${LICENSE_HOST}
      - LICENSE_PORT=${LICENSE_PORT}
    volumes:
      - ./share:/app/share
  
  # GPU worker (scaled to 0 by default)
  gpu:
    image: ${DOCKER_WORKER_IMAGE}
    environment:
      - QUEUE_NAME=gpu,gpuhigh
    # GPU configuration enabled when needed
  
  # Monitoring service
  flower:
    image: ${DOCKER_WORKER_IMAGE}
    command: celery -A pixyz_worker:app flower
    ports:
      - "5555:5555"
    depends_on:
      - redis
```

### Environment Variables

Key environment variables for Docker deployment:

| Variable | Description | Default                                  |
|----------|-------------|------------------------------------------|
| `DOCKER_REDIS_IMAGE` | Redis container image | `redis:latest`                           |
| `DOCKER_API_IMAGE` | API container image | `pixyzinc/pixyz-scheduler-api:latest`    |
| `DOCKER_WORKER_IMAGE` | Worker container image | `pixyzinc/pixyz-scheduler-worker:latest` |
| `LICENSE_FLEXLM` | Enable FlexLM licensing | `true`                                   |
| `LICENSE_HOST` | License server hostname | Required                                 |
| `LICENSE_PORT` | License server port | `27000`                                  |
| `GOD_PASSWORD_SHA256` | API password hash | Required                                 |
| `API_PORT` | API listen port | `8001`                                   |
| `UID` | User ID for file permissions | `1001`                                   |
| `GID` | Group ID for file permissions | `1001`                                   |

## Storage and Permissions

### Shared Volume

The shared volume (`./share`) stores job data and must be accessible by both API and workers:

```bash
# Create shared directory
mkdir -p ./share

# Set correct permissions
chown ${UID}:${GID} ./share
chmod 755 ./share
```

### Permission Issues

If you encounter permission issues:

1. Check UID/GID in configuration:
   ```bash
   id -u  # Current user ID
   id -g  # Current group ID
   ```

2. Update configuration:
   ```ini
   UID=1000
   GID=1000
   ```

3. Fix ownership:
   ```bash
   sudo chown -R 1000:1000 ./share
   ```

## Testing the Installation

### 1. Verify Services

Check that all services are running:
```bash
docker-compose ps
```

### 2. Test API

Test the API endpoint:
```bash
curl -H "x-api-key: your-password" http://localhost:8001/jobs
```

### 3. Submit Test Job

Using the Python client:
```bash
python client.py --url http://localhost:8001 \
  process -n sleep -t your-password
```

## Monitoring

### Flower Dashboard

Enable Flower for monitoring:
```bash
docker-compose up --scale flower=1
```

Access at: http://localhost:5555

### Logs

View service logs:
```bash
# All services
docker-compose logs

# Specific service
docker-compose logs api
docker-compose logs worker
docker-compose logs redis
```

## Production Considerations

### Security

1. **Change default passwords**
2. **Use secrets management** for sensitive configuration
3. **Enable TLS** for API endpoints
4. **Restrict network access** with firewall rules

### Performance

1. **Resource limits**: Set appropriate CPU/memory limits
2. **Storage performance**: Use fast storage for shared volumes
3. **Network optimization**: Use dedicated networks for internal communication

### Backup

1. **Redis data**: Configure Redis persistence
2. **Job outputs**: Regular backup of shared storage
3. **Configuration**: Version control for compose files

## Troubleshooting

### Common Issues

1. **Permission denied on shared volume**:
   - Check UID/GID configuration
   - Verify directory ownership

2. **License server connection failed**:
   - Verify LICENSE_HOST and LICENSE_PORT
   - Check network connectivity from containers

3. **Out of memory errors**:
   - Increase Docker memory limits
   - Add resource limits to services

4. **GPU not detected**:
   - Install NVIDIA Container Toolkit
   - Verify GPU configuration in compose file

### Debug Commands

```bash
# Container inspection
docker inspect pixyz-scheduler_worker_1

# Execute commands in container
docker exec -it pixyz-scheduler_worker_1 bash

# Check container logs
docker logs pixyz-scheduler_api_1

# Resource usage
docker stats
```