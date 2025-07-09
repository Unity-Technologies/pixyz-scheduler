#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__all__ = ['uuid_path_pattern']

from typing import Annotated
from fastapi import Path

uuid_pattern = '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
uuid_path_pattern = Annotated[str, Path(min_length=36, max_length=36, pattern=uuid_pattern)]
