class BrokerRabbitException(Exception):
    pass


class ExchangeNotDefinedYet(BrokerRabbitException):
    pass


class ExchangeAlreadyExist(BrokerRabbitException):
    pass


class ChannelDoesntExist(BrokerRabbitException):
    pass


class ChannelIsAlreadyInUse(BrokerRabbitException):
    pass


class ConnectionNotOpenedYet(BrokerRabbitException):
    pass


class ConnectionIsAlreadyInUse(BrokerRabbitException):
    pass


class ConnectionIsClosed(BrokerRabbitException):
    pass


class QueueNameDoesntMatch(BrokerRabbitException):
    pass


class ExchangeNameDoesntMatch(BrokerRabbitException):
    pass


class BasicPropertiesIsNotSet(BrokerRabbitException):
    pass


class WorkerExitException(BrokerRabbitException):
    pass


class ChannelRunningException(BrokerRabbitException):
    pass
