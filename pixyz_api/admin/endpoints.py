#!/usr/bin/env python
# -*- coding: utf-8 -*-
from . import *

router = APIRouter()
logger = get_api_logger("api.admin.endpoints")

@router.get("/tasks", status_code=status.HTTP_200_OK)
async def tasks(api_key: APIKey = Depends(verify_token)):
    try:
        i = Inspect(app=pixyz_worker.tasks.app)
        active_tasks = i.active()
        reserved_tasks = i.reserved()
        scheduled_tasks = i.scheduled()

        all_tasks = {
            "active_tasks": active_tasks,
            "reserved_tasks": reserved_tasks,
            "scheduled_tasks": scheduled_tasks,
        }
        return all_tasks
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"EXCEPTION: {str(e)}")


@router.get("/stats", status_code=status.HTTP_200_OK)
async def stats(api_key: str = Depends(verify_token)):
    try:
        i = Inspect(app=pixyz_worker.tasks.app)
        return i.stats()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"EXCEPTION: {str(e)}")

