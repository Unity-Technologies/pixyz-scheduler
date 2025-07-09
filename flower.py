#!/usr/bin/env python3
import subprocess

def start_flower():
    """
    Start Flower programmatically using subprocess.
    """
    # Define the command and its arguments
    command = [
        "celery",
        "-A", "pixyz_worker:app",  # Celery application
        "flower",                  # Start Flower
        "--purge_offline_workers=180",  # Purge offline workers after 180 seconds
        "--loglevel=info",         # Set log level to info
        "-Q", "gpu,cpu,control,gpuhigh,zip,clean"  # Monitor specific queues
    ]

    try:
        # Start Flower as a subprocess
        subprocess.Popen(command)

        print("Flower started successfully!")
        print("Visit http://localhost:5555 to monitor your Celery tasks.")
    except Exception as e:
        print(f"Error starting Flower: {e}")

if __name__ == "__main__":
    start_flower()