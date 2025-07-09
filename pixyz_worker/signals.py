# `after_task_publish` is available in celery 3.1+
# for older versions use the deprecated `task_sent` signal
from celery.signals import after_task_publish, task_prerun, task_postrun, worker_process_init, worker_process_shutdown, worker_shutting_down
from celery import current_app

from .watchdog import *
from .share import PiXYZSession,get_logger
from .license import License
from datetime import datetime
import sys
license_ = License.from_config()


@worker_process_init.connect
def setup_celery_worker(sender, **kwargs):
    import logging
    from celery import current_app

    # Set up logging (before the Celery app is created) for manage message between worker start and celery started
    #logging.basicConfig(level=logging.INFO, format='[%(asctime)s: %(levelname)s/%(processName)s] : %(message)s')
    logger = get_logger('pixyz_worker.signals')
    try:
        if license_.is_acquire_at_start():
            PiXYZSession.initialize(mandatory=True)
            license_.configure_license()
    except RuntimeError:
        logger.fatal("License server not found, invalid or no license available")
        current_app.control.broadcast('shutdown')
        sys.exit(100)


@worker_process_shutdown.connect
def teardown_celery_worker(sender, **kwargs):
    logger = get_logger('pixyz_worker.signals')
    logger.info("Teardown down worker, clear latest task id...")
    WatchdogByFileHandler.clear_latest_task_id()
    # release all pixyz module in order to release the license token
    logger.info("Teardown down worker, releasing...")
    PiXYZSession.release()
    logger.info("Teardown down worker, released.")


@worker_shutting_down.connect
def shutdown_celery_worker(sender, **kwargs):
    logger = get_logger('pixyz_worker.signals')
    logger.info("Shutting down worker, releasing PiXYZ session if needed...")
    PiXYZSession.release_at_shutdown_if_needed(license_)
    logger.info("Shutting down worker, released...")


@task_prerun.connect
def before_task_starts(sender=None, task_id=None, task=None, **kwargs):
    WatchdogByFileHandler.set_latest_task_info(task)


@task_postrun.connect
def after_task_completes(sender=None, task_id=None, task=None, **kwargs):
    WatchdogByFileHandler.clear_latest_task_id()
    if TasksWatchdog.is_time_to_shutdown():
        print("You are reached the maximum task acceptable for this worker, goodbye")
        sender.app.control.broadcast('shutdown')

