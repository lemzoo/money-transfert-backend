from connector.agdref import init_connector_agdref
from connector.dna import init_connector_dna
from connector.common import init_connectors
from connector.mail import mail_demande_asile_rejected
from connector.webhook import webhook
from connector.debugger import debug_print
from connector.processor import (
    processor_manager, find_and_execute, register_processor)
from connector.exceptions import (
    ProcessorError, UnknownProcessorError, ProcessMessageError,
    ProcessMessageEventHandlerConfigError, ProcessMessageBadResponseError,
    ProcessMessageNoResponseError, ProcessServerNotifyRetryError,
    ProcessMessageNeedWaitError, ProcessMessageSkippedError)


__all__ = (
    'find_and_execute',
    'init_connector_agdref',
    'init_connector_dna',
    'init_connectors',
    'processor_manager',
    'ProcessMessageError',
    'ProcessMessageEventHandlerConfigError',
    'ProcessMessageBadResponseError',
    'ProcessMessageNoResponseError',
    'ProcessServerNotifyRetryError',
    'ProcessMessageNeedWaitError',
    'ProcessMessageSkippedError',
    'ProcessorError',
    'register_processor',
    'UnknownProcessorError',
    'webhook'
)

register_processor(debug_print, name='debug_print')

register_processor(mail_demande_asile_rejected,
                   name='mail_demande_asile_rejected')
