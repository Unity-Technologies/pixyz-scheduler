ARG PIXYZ_IMAGE
FROM $PIXYZ_IMAGE
USER root
ENV TZ="Europe/Paris"
COPY pixyz_worker/requirements.txt /tmp/requirements.txt
RUN apt update \
    && apt-get install --no-install-recommends -y python3-pip vim-tiny \
    && pip install -r /tmp/requirements.txt \
    && mkdir -p /app /app/scripts/process/ /process && chown -R pixyz:pixyz /app \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && rm /tmp/requirements.txt

USER pixyz
COPY ./worker.py /app/worker.py
COPY ./celery_admin.py /app/celery_admin.py
COPY ./pixyz_worker /app/pixyz_worker
COPY ./pixyz_api/process /app/scripts/process
COPY ./pixyz_api/process /process
COPY ./pixyz_worker/entrypoint.sh /opt/entrypoint.sh
RUN cp /app/pixyz_worker/watchdog.py /app/watchdog.py

# For test only
#COPY ./tests /app/tests
#COPY ./client.py /app/client.py


WORKDIR /app/
ENTRYPOINT ["/bin/bash", "/opt/entrypoint.sh"]