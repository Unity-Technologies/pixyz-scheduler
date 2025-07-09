__all__ = [
            'PixyzException', 'InvalidFile', 'InvalidYamlFile', 'InvalidConfigurationFile', 'InternalError',
            'PixyzWebError', 'PixyzFileNotFound', 'PixyzSecurityViolation', 'PixyzSharedDirectoryNotFound',
            'PixyzExecutionFault', 'PixyzSignalFault', 'PixyzExitFault', 'DiskStateAlreadyExists',
            'InvalidBackendParameter', 'PixyzTimeout',
            'SharePathNotFoundError', 'SharePathInvalidError', 'TaskNotCompletedError', 'TaskProcessingStarted',
            'PixyzExceptionUnpickleableExceptionWrapper'
           ]

# TODO: create a PixyzLicenseError

class PixyzException(Exception):
    def __init__(self, message):
        self.message = message
        # If you don't keep this, exception will be not pickable and not raise by celery
        super(PixyzException, self).__init__(message)

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"

    def __contains__(self, item):
        return item == 'message'

    def dict(self):
        return {"message": self.message}


class InvalidBackendParameter(PixyzException):
    pass


class InvalidFile(PixyzException):
    pass


class InvalidYamlFile(InvalidFile):
    pass


class InvalidConfigurationFile(InvalidYamlFile):
    pass


class InternalError(PixyzException):
    """
    Algorithm design problem an un-excepted error
    You have a problem :)
    """
    pass


class PixyzWebError(PixyzException):
    def __init__(self, status_code, url, message):
        self.status_code = status_code
        self.url = url
        self.message = message
        super(PixyzWebError, self).__init__(str(self))

    def __str__(self):
        return f"HTTP ERROR CODE({self.status_code}): URL {self.url} ({self.message})"


class PixyzFileNotFound(PixyzException):
    pass


class PixyzSharedDirectoryNotFound(PixyzException):
    pass


class PixyzSecurityViolation(PixyzException):
    pass


class PixyzExecutionFault(PixyzException):
    pass


class PixyzSignalFault(PixyzExecutionFault):
    pass


class PixyzExitFault(PixyzExecutionFault):
    pass


class DiskStateAlreadyExists(PixyzException):
    pass


class PixyzTimeout(PixyzException):
    pass


class SharePathNotFoundError(ValueError): 
    pass


class SharePathInvalidError(ValueError): 
    pass

class TaskNotCompletedError(Exception):
    pass

# Not really an exception, but a signal
class TaskProcessingStarted(Exception):
    pass


# When you can't pickle an exception (like exception from a C library)
class PixyzExceptionUnpickleableExceptionWrapper(PixyzException):
    def __init__(self, e):
        message = e.__class__.__module__ + "." + e.__class__.__name__ + ": " + str(e)
        super(PixyzExceptionUnpickleableExceptionWrapper, self).__init__(message)