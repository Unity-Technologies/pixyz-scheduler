FROM python:3.11

# Remove AGPL software
RUN apt-get remove -y "libwmflite*"

WORKDIR /app

COPY ./pixyz_api/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt && mkdir -p /process /app/scripts/process

COPY ./pixyz_api /app/pixyz_api
COPY ./api.py /app/api.py
COPY ./pixyz_worker /app/pixyz_worker
COPY ./pixyz_api/process /app/scripts/process

# For test only
#COPY ./tests /app/tests
#COPY ./client.py /app/client.py

WORKDIR /app/
CMD ["python3", "api.py"]