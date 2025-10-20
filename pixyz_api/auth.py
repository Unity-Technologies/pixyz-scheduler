#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import os

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from .utils import get_api_logger

__all__ = ['verify_token']

logger = get_api_logger('pixyz_api.auth')

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)
god_hash = os.getenv('GOD_PASSWORD_SHA256', None)

if god_hash is None:
    logger.warning("GOD_PASSWORD_SHA256 environment variable not found, using default and faulty password?")
    god_hash = "not_set"


def validate_sha256(data, expected_hash):
    # Calculate the SHA-256 hash of the data
    sha256_hash = hashlib.sha256(data.encode()).hexdigest()
    # Compare the calculated hash with the expected hash
    return sha256_hash == expected_hash


# Dependency to check the presence and validity of the token
def verify_token(api_key: str = Security(api_key_header)):
    if (api_key is None or
            not validate_sha256(api_key, god_hash)):
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "x-api-key"},
        )
