from .tasks import *

from .config import *
from .exception import *
from .share import *
from .pc import *

from .progress import *
from .signals import *
from .storage import *
from .extcode import *
from .utils import *

from .license import *


__all__ = (config.__all__ + exception.__all__ + share.__all__ + tasks.__all__ + progress.__all__ + storage.__all__ +
           extcode.__all__ + utils.__all__ + pc.__all__ )

def main():
    import os
    from celery import Celery
    import sys
    from datetime import datetime
    import faulthandler
    import socket

    ################################################################
    ## CELERY INITIALIZATION
    ################################################################

    app = Celery(include=['pixyz_worker.tasks'])
    app.config_from_object('pixyz_worker.settings')

    def print_config():
        print(f">>{app.conf.get('solo')}<<")
        for k, v in app.conf.items():
            print(k, v)

    def get_faulthandler_filename():
        current_date = datetime.utcnow().strftime("%m%d%Y_%H%M%S")
        filename = f"{current_date}@{socket.gethostname()}"
        return os.path.join(config.share_dir, filename)


    options = ['worker', '--loglevel=info', '-E', '-Q', config.queue_name, '-c',
               config.concurrency, '-n', 'worker@%h',
               '--without-gossip', '--without-mingle', '-Ofair']
    if sys.platform == 'win32' or not debug:
        # No fork working on windows ... without any errors messages
        # But threading is possible. --pool=threads
        options += ['-P', config.pool_type]
        print("solo mode ON")
    else:
        options += ['-P', config.pool_type]
    if debug:
        with open(get_faulthandler_filename(), "w") as stf:
            faulthandler.enable(file=stf)
        # prevent empty log file
        if os.path.getsize(get_faulthandler_filename()) == 0:
            os.remove(get_faulthandler_filename())
    app.worker_main(options)

