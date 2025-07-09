#!/usr/bin/env python3
from .config import *
from .utils import *
from .models import *
from .patterns import *
from .auth import *
from .routes import *
from .process import *
__all__ = (config.__all__ + utils.__all__ + models.__all__ + patterns.__all__ + routes.__all__ + auth.__all__ +
           process.__all__)

def main():
    import sys
    import os
    import uvicorn
    import pixyz_worker.config
    from pixyz_api.utils import get_api_logger

    logger = get_api_logger('api')

    # on windows platform, you must set the host to 127.0.0.1
    # on linux/docker-compose/container, you must set to 0.0.0.0 (debug or not)
    if pixyz_worker.config.debug and sys.platform == "win32":
        # On windows, you must set to 127.0.0.1, 0.0.0.0 does not work
        host = "127.0.0.1"
        uvicorn.run('pixyz_api:api_app', host=host, port=pixyz_worker.config.api_port, log_level="info", reload=True, workers=10)
    else:
        host = "0.0.0.0"
        # disable reload in production to enable multiple workers
        uvicorn.run('pixyz_api:api_app', host=host, port=pixyz_worker.config.api_port, log_level="info")
