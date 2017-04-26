class ProcessorError(Exception):
    pass


class UnknownProcessorError(ProcessorError):
    pass


class ProcessMessageError(ProcessorError):
    pass


class ProcessMessageEventHandlerConfigError(ProcessMessageError):
    pass


class ProcessMessageBadResponseError(ProcessMessageError):
    pass


class ProcessMessageNoResponseError(ProcessMessageError):
    pass


class ProcessServerNotifyRetryError(ProcessMessageError):
    pass


class ProcessMessageNeedWaitError(ProcessorError):
    pass


class ProcessMessageSkippedError(ProcessorError):
    pass
