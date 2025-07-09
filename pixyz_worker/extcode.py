#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import importlib
import importlib.util
import sys
import os
import string
import secrets
from pixyz_worker.share import *
from pixyz_worker.exception import *
from multiprocessing import Process
from multiprocessing import Manager
from queue import Empty as EmptyQueue
from pixyz_worker.pc import ProgramContext
from tblib import pickling_support
import pickle


__all__ = ['ExternalPythonCode', 'SignalSafeExecution']


class ExceptionWrapper(object):
    @staticmethod
    def is_pickleable(obj):
        ## When you use the pixyz module and a exception from the pixyz module is raised, the exception is not pickable
        ## This is a workaround to make it pickable
        try:
            # Attempt to pickle the object
            pickled_obj = pickle.dumps(obj)
            # Attempt to unpickle the object
            unpickled_obj = pickle.loads(pickled_obj)
            return True
        except (pickle.PicklingError, TypeError):
            return False

    def __init__(self, ee):
        if not self.is_pickleable(ee):
            self.exception = PixyzExceptionUnpickleableExceptionWrapper(ee)
        else:
            self.exception = ee
        __, __, self.tb = sys.exc_info()

    def re_raise(self):
        raise self.exception.with_traceback(self.tb)

# Keep it after the ExceptionWrapper class (otherwise it will not be pickable!!)
pickling_support.install()


class ExternalPythonCode(object):
    # source: https://dev.to/charlesw001/plugin-architecture-in-python-jla

    def __init__(self, source, module_name='external'):
        """
        loads a python module from source

        :param source: file to load
        :param module_name: name of module to register in sys.modules
        """
        self.check_if_source_exist_or_raise(source)
        self.source = source
        self.module_name = module_name
        self.logger = get_logger('pixyz_worker.extcode.ExternalPythonCode')
        self.module = self.load_module(source, module_name)

    @staticmethod
    def check_if_source_exist_or_raise(source):
        if not os.path.isfile(source):
            raise ValueError(f"Source file {source} does not exist")

    @staticmethod
    def gensym(length=32, prefix="gensym_"):
        """
        generates a fairly unique symbol, used to make a module name,
        used as a helper function for load_module

        :return: generated symbol
        """
        alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
        symbol = "".join([secrets.choice(alphabet) for i in range(length)])

        return prefix + symbol

    @staticmethod
    def load_module(source, module_name=None):
        """
        reads file source and loads it as a module

        :param source: file to load
        :param module_name: name of module to register in sys.modules
        :return: loaded module
        """

        if module_name is None:
            module_name = ExternalPythonCode.gensym()

        spec = importlib.util.spec_from_file_location(module_name, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        return module

    @staticmethod
    def find_back_frame(tb, script_name):
        if tb is None:
            return None
        if tb.tb_frame.f_code.co_filename == script_name:
            return tb
        else:
            return ExternalPythonCode.find_back_frame(tb.tb_next, script_name)

    @staticmethod
    def raise_with_backtrace(e, source):
        import types
        tb = sys.exc_info()[2]
        # Find the backtrace that contains the script name

        back_frame = ExternalPythonCode.find_back_frame(tb, source)
        # Return the backtrace of the script if found, otherwise return the current backtrace
        if back_frame is not None:
            back_frame = back_frame.tb_frame
        else:
            if tb is not None:
                back_frame = tb.tb_frame
            else:
                back_frame = None

        # Final check if the back_frame is None
        if back_frame is not None:
            back_tb = types.TracebackType(tb_next=None,
                                          tb_frame=back_frame,
                                          tb_lasti=back_frame.f_lasti,
                                          tb_lineno=back_frame.f_lineno)
        else:
            back_tb = tb
        raise e.with_traceback(back_tb) from None

    def execute(self, program_context: ProgramContext):
        """
        executes the loaded module

        :return: result of the module's main function
        """
        params = program_context.get('params', {})
        entrypoint = program_context.get('entrypoint', 'main')
        self.logger.info(f"Executing {self.module_name} with entrypoint {entrypoint}")
        if entrypoint is None:
            entrypoint = 'main'
        if not hasattr(self.module, entrypoint):
            raise ValueError(f"Module {self.module_name} does not have a function {entrypoint}")

        try:
            return getattr(self.module, entrypoint)(program_context, params)
        except Exception as e:
            #self.raise_with_backtrace(e, self.source)
            import types
            ei = sys.exc_info()
            tb = sys.exc_info()[2]
            back_frame = tb.tb_next.tb_frame

            back_tb = types.TracebackType(tb_next=None,
                                          tb_frame=back_frame,
                                          tb_lasti=back_frame.f_lasti,
                                          tb_lineno=back_frame.f_lineno)
            raise ei[0](ei[1]).with_traceback(back_tb) from None



class SignalSafeExecution(object):
    @staticmethod
    def get_default_params(params=None):
        logger = get_logger('pixyz_worker.extcode.SignalSafeExecution')
        # None for time unlimited
        default_params = {'time_limit': None}
        default_params.update(params)
        # Special case, if you request a time_limit too large, the poll function trigger an overflow
        if default_params['time_limit'] is not None and int(default_params['time_limit']) > 86400:
            logger.warning(f"Requested time_limit {default_params['time_limit']} is too large, setting it to unlimited")
            default_params['time_limit'] = None
        return default_params

    @staticmethod
    def run(func, pc:ProgramContext, kwargs=None, **params):
        ret = None
        if kwargs is None:
            kwargs = {}

        default_params = SignalSafeExecution.get_default_params(params)

        def _return_func_shm(_func, _shm, _args, _kwargs):
            _ret = None
            try:
                _ret = _func(_args, **_kwargs)
                _shm.append(_ret)
                _shm.append(_args)
            except Exception as e:
                _ret = ExceptionWrapper(e)
                _shm.append(_ret)
            return _ret

        logger = get_logger('pixyz_worker.extcode.SignalSafeExecution')
        with Manager() as manager:
            shared = manager.list()
            func_with_queue = [func, shared, pc, kwargs]
            process = Process(target=_return_func_shm, args=func_with_queue)

            try:
                import selectors
                logger.debug(f"Executing {func}...")
                process.start()
                process.join(default_params['time_limit'])
                logger.debug(f"execution of {func} finished, get result")
                if process.is_alive():
                    logger.debug(f"wait for kill")
                    # Terminate is not enough
                    #process.terminate()
                    process.kill()
                    logger.debug(f"wait for join")
                    process.join()
                    message = f"function {str(func)}({str(pc)}##{str(kwargs)}) trigger a timeout({default_params['time_limit']})"
                    logger.error(message)
                    raise PixyzTimeout(message)
                if process.exitcode < 0:
                    signal = process.exitcode * -1
                    logger.error(f"function {func} trigger a signal {signal}, raising PixyzExecutionFault")
                    process.terminate()
                    raise PixyzSignalFault(signal)
                elif process.exitcode == 0:
                    logger.debug(f"function {func} trigger a normal exit code, get result...")
                    ret = shared[0]
                    if isinstance(ret, ExceptionWrapper):
                        logger.error(f"function {func} trigger an exception {ret.exception}, raising it")
                        exc = ret
                        process.terminate()
                        # In this case, the exception can be pickled OR NOT
                        # In the pickled exception, exception come from the code itself like user exception
                        # But if the exception come from a C library, the exception is not pickable
                        # If you use a function in ExceptionWrapper, It will fail!
                        exc.re_raise()
                    else:
                        if hasattr(pc, 'update'):
                            pc.update(**shared[1])
                        else:
                            # Not a ProgramContext, we can't update it
                            pass
                else:  # process.exitcode > 0
                    try:
                        if len(shared) > 0:
                            ret = shared[0]
                        if isinstance(ret, ExceptionWrapper):
                            logger.error(f"function {func} trigger an exception {ret.exception}, raising it")
                            exc = ret
                            process.terminate()
                            exc.re_raise()
                        else:
                            # Should not happen because the queue will be empty
                            logger.error(f"function {func} trigger an exit code {process.exitcode} (with ret, should not be happen)")
                            process.terminate()
                            raise PixyzExitFault(process.exitcode)
                    except EmptyQueue:
                        logger.error(f"function {func} trigger an exit code {process.exitcode}")
                        process.terminate()
                        raise PixyzExitFault(process.exitcode)

            except KeyboardInterrupt:
                logger.error(f"CTRL+C")
                pass
            # except Exception as e:
            #     print("From SIGNALSAFEEXECUTION*************" + traceback.format_exc())
            #     raise e
            process.terminate()
            return ret


def main():
    # external = ExternalPythonCode('/home/dmx/remote_latex/pixyz-scheduler/pixyz_worker/snippet/test_import_code.py', 'external')
    # external.execute(ProgramContext(hello='world'), entrypoint='subtask')
    pc1 = ProgramContext(a=10, b=2, c=3)
    d=[pc1.clone().update(a=i) for i in range(4)]
    print(pc1)
    print(d)

if __name__ == '__main__':
    main()
