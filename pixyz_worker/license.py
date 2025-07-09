#!/usr/bin/env python
# -*- coding: utf-8 -*-
__all__ = ['License']

import pixyz_worker.config

class License(object):
    def __init__(self, host, port, acquire_at_start, flexlm, disable_pixyz):
        from pixyz_worker.share import get_logger
        self.host = host
        self.port = port
        self.acquire_at_start = acquire_at_start
        self.flexlm = flexlm
        self.disable_pixyz = disable_pixyz
        self.logger = get_logger('pixyz_worker.license.License')
        if self.flexlm:
            self.logger.info(f"License configuration with host={host}, port={port}, acquire_at_start={acquire_at_start}, flexlm={flexlm} disable_pixyz={disable_pixyz}")
        else:
            self.logger.info("License configuration with flexlm off, use node-locked license")

    @staticmethod
    def from_config():
        return License(pixyz_worker.config.license_host, pixyz_worker.config.license_port,
                       pixyz_worker.config.license_acquire_at_start, pixyz_worker.config.license_flexlm, pixyz_worker.config.disable_pixyz)

    def is_acquire_at_start(self):
        return self.flexlm and self.acquire_at_start and (not self.disable_pixyz)

    def configure_license(self):
        import pxz
        if (not self.flexlm) or self.disable_pixyz:
            return

        self.logger.info("Checking license")
        if not pxz.core.checkLicense() and self.flexlm:
            self.logger.info(f"Configuring license server {self.host}:{self.port}")
            try:
                pxz.core.configureLicenseServer(self.host, self.port, True)
            except Exception as e:
                self.logger.fatal(f"License server {self.host}:{self.port} not found, invalid or no license available")
                raise RuntimeError(f"License server {self.host}:{self.port} not found, invalid or no license available")

        if not pxz.core.checkLicense():
            self.logger.fatal(f"License server {self.host}:{self.port} not found, invalid or no license available")
            raise RuntimeError(f"License server {self.host}:{self.port} not found, invalid or no license available")
        else:
            self.logger.info(f"License server {self.host}:{self.port} configured and available")
