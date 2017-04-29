class EventError(Exception):
    pass


class UnknownEventHandlerError(EventError):
    pass


class UnknownEventError(EventError):
    pass
