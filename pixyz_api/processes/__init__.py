#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import datetime
import asyncio
import httpx

from fastapi import APIRouter, UploadFile, File, HTTPException, status, BackgroundTasks
from fastapi.responses import Response, FileResponse
from fastapi.encoders import jsonable_encoder

from pixyz_api.models import *
from pixyz_api.patterns import *
from pixyz_api.utils import *

import pixyz_worker.tasks
import pixyz_worker.share
import pixyz_worker.config


from typing import Literal
from pydantic import HttpUrl

from celery.result import AsyncResult
from celery.exceptions import TaskRevokedError
from billiard.exceptions import WorkerLostError

from . import endpoints
