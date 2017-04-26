from datetime import datetime, timedelta
from traceback import format_exc

from connector.processor import find_and_execute
from connector.exceptions import (
    ProcessMessageError, ProcessMessageNeedWaitError,
    ProcessMessageNoResponseError, ProcessMessageBadResponseError,
    ProcessMessageSkippedError, ProcessServerNotifyRetryError)


BASE_DELAY = 60
MAX_DELAY = 6 * 60 * 60  # 6 hours


def default_callback(message, exception, origin):
    return 'FAILURE'


class EventHandlerItem:

    def __init__(self, evh):
        self.label = evh['label']
        self.origin = evh.get('origin')
        self.queue = evh.get('queue')
        self.processor = evh.get('processor')
        self.context = evh.get('context')
        self.event = evh.get('event')
        self.to_skip = evh.get('to_skip')
        if 'on_error_callback' in evh:
            self.on_error_callback = evh.get('on_error_callback')
        else:
            self.on_error_callback = default_callback
        self.to_rabbit = evh.get('to_rabbit', False)

    def modify(self, *args, **kwargs):
        if 'label' in kwargs:
            self.label = kwargs['label']
        if 'origin' in kwargs:
            self.origin = kwargs['origin']
        if 'queue' in kwargs:
            self.queue = kwargs['queue']
        if 'processor' in kwargs:
            self.processor = kwargs['processor']
        if 'context' in kwargs:
            self.context = kwargs['context']
        if 'event' in kwargs:
            self.event = kwargs['event']
        if 'to_skip' in kwargs:
            self.event = kwargs['to_skip']
        if 'on_error_callback' in kwargs:
            self.on_error_callback = kwargs['on_error_callback']
        if 'to_rabbit' in kwargs:
            self.to_rabbit = kwargs['to_rabbit']


class EventHandler:

    def __init__(self, handlers):
        self.items = [EventHandlerItem(eh) for eh in handlers]

    def execute_legacy(self, msg):
        handler = self.get(msg.handler)
        if not handler:
            msg.modify(status_comment="Pas de handler pour ce type de message", status='FAILURE',
                       processed=datetime.utcnow(), next_run=None)
            raise ProcessMessageError(
                "Pas de handler pour traiter le message %s: %s n'est pas un handler valide"
                % (msg.id, msg.handler))
        if msg.status in ('DONE', 'SKIPPED', 'CANCELLED', 'DELETED'):
            return
        elif msg.status == 'FAILURE':
            raise ProcessMessageError('Message %s already in status FAILURE' % msg.id)
        elif msg.next_run and datetime.utcnow() < msg.next_run:
            raise ProcessMessageNeedWaitError("Message %s will be processed at %s" % (msg.id, msg.next_run))
        try:
            result_msg = str(find_and_execute(handler.processor, handler, msg))
        except (ProcessMessageNoResponseError, ProcessServerNotifyRetryError) as exc:
            delta = self.get_next_delta_execute(msg)
            msg.modify(status_comment=str(exc), processed=datetime.utcnow(), next_run=datetime.utcnow() + delta)
            raise ProcessMessageNeedWaitError("Message %s will be processed at %s" % (msg.id, msg.next_run))
        except ProcessMessageSkippedError as exc:
            msg.modify(status_comment="Skipped", status='SKIPPED', processed=datetime.utcnow(), next_run=None)
        except ProcessMessageBadResponseError as exc:
            new_status = handler.on_error_callback(message=msg, exception=exc, origin=handler.queue)
            msg.modify(status_comment=str(exc), status=new_status, processed=datetime.utcnow(), next_run=None)
            if new_status == 'FAILURE':
                raise ProcessMessageError("Error processing message %s: %s" % (msg.id, str(exc)))
        except:
            exc_msg = format_exc()
            new_status = handler.on_error_callback(message=msg, exception=exc_msg, origin=handler.queue)
            msg.modify(status_comment=exc_msg, status=new_status, processed=datetime.utcnow(), next_run=None)
            if new_status == 'FAILURE':
                raise ProcessMessageError("Exception occured during processing message %s: %s" % (msg.id, exc_msg))
        else:
            msg.modify(status_comment=result_msg, status='DONE',
                       processed=datetime.utcnow(), next_run=None)

    def execute_rabbit(self, msg):
        handler = self.get(msg.handler)
        if not handler:
            msg.insert_or_update(status_comment="Pas de handler pour ce type de message", status='FAILURE')
            raise ProcessMessageError(
                "Pas de handler pour traiter le message %s: %s n'est pas un handler valide" % (msg.id, msg.handler))

        if msg.status in ('DONE', 'SKIPPED', 'CANCELLED', 'DELETED'):
            return
        elif msg.status == 'FAILURE':
            raise ProcessMessageError('Message %s already in status FAILURE' % msg.id)

        if msg.is_folder_on_error():
            msg.insert_or_update(status_comment="Skipped", status='SKIPPED')
            return

        try:
            result_msg = str(find_and_execute(handler.processor, handler, msg))
        except (ProcessMessageNoResponseError, ProcessServerNotifyRetryError) as exc:
            msg.insert_or_update(status_comment=str(exc), status='NEED_WAIT')
            raise ProcessMessageNeedWaitError("Message %s cannot be processed for the moment, wait and retry" % (msg.id))
        except ProcessMessageSkippedError as exc:
            msg.insert_or_update(status_comment="Skipped", status='SKIPPED')
        except ProcessMessageBadResponseError as exc:
            new_status = handler.on_error_callback(message=msg, exception=exc, origin=handler.queue)
            msg.insert_or_update(status_comment=str(exc), status=new_status)
            if new_status == 'FAILURE':
                raise ProcessMessageError("Error processing message %s: %s" % (msg.id, str(exc)))
        except:
            exc_msg = format_exc()
            new_status = handler.on_error_callback(message=msg, exception=exc_msg, origin=handler.queue)
            msg.insert_or_update(status_comment=exc_msg, status=new_status)
            if new_status == 'FAILURE':
                raise ProcessMessageError("Exception occured during processing message %s: %s" % (msg.id, exc_msg))
        else:
            msg.insert_or_update(status_comment=result_msg, status='DONE')

    @staticmethod
    def get_next_delta_execute(msg):
        if not msg.next_run:
            delta = BASE_DELAY
        else:
            delta = ((msg.next_run - msg.processed) * 2).seconds
            delta = delta if delta < MAX_DELAY else MAX_DELAY
        return timedelta(seconds=delta)

    def get(self, label, default=None):
        try:
            return self[label]
        except IndexError:
            return default

    def __getitem__(self, label):
        for item in self.items:
            if item.label == label:
                return item
        raise IndexError()

    def filter(self, event=None, origin=None):
        ret = self.items
        if event:
            ret = [x for x in ret if x.event == event]
        if origin:
            ret = [x for x in ret if x.origin != origin]
        return ret

    def flush(self):
        self.items = []

    def append(self, item):
        if isinstance(item, EventHandlerItem):
            self.items.append(item)
        elif isinstance(item, dict):
            self.items.append(EventHandlerItem(item))
        else:
            raise ValueError()
