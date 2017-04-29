import pytest

from connector import (
    find_and_execute, register_processor, ProcessMessageBadResponseError,
    ProcessMessageError, ProcessMessageNeedWaitError,
    ProcessMessageSkippedError, ProcessMessageNoResponseError)

from tests import common
from tests.broker_rabbit.fixtures import *


class TestProcessor(common.BaseRabbitBrokerTest):

    def test_processor(self, event_handler_item,
                       broker_rabbit, message_first_try):
        event_handler_item.modify(processor='good_processor')

        @register_processor
        def good_processor(handler, message):
            return 'ok'

        broker_rabbit.event_handler.execute_rabbit(message_first_try)
        message_first_try.reload()
        assert message_first_try.status == 'DONE'

    def test_bad_processor(self, event_handler_item,
                           broker_rabbit, message_first_try):

        event_handler_item.modify(processor='bad_processor')

        @register_processor
        def good_processor(handler, message):
            raise ValueError('expected exception')

        with pytest.raises(ProcessMessageError):
            broker_rabbit.event_handler.execute_rabbit(message_first_try)
        message_first_try.reload()
        assert message_first_try.status == 'FAILURE'

    def test_message_error(self, event_handler_item, broker_rabbit, message_first_try):

        @register_processor
        def bad_processor(handler, message):
            raise ProcessMessageBadResponseError('404')

        # Given processor should returns a 404
        event_handler_item.modify(processor='bad_processor')

        with pytest.raises(ProcessMessageError):
            broker_rabbit.event_handler.execute_rabbit(message_first_try)

        message_first_try.reload()
        assert message_first_try.status == 'FAILURE'

    def test_message_bad_response_error(self, event_handler_item, message_retry):
        @register_processor
        def bad_processor(handler, message):
            raise ProcessMessageBadResponseError('404')

        # Given processor should returns a 404
        event_handler_item.modify(processor='bad_processor')

        with pytest.raises(ProcessMessageBadResponseError):
            find_and_execute(event_handler_item.processor,
                             event_handler_item, message_retry)

    def test_message_skipped(self, event_handler_item, broker_rabbit, message_retry):
        event_handler_item.modify(processor='skipped_processor')

        @register_processor
        def skipped_processor(handler, message):
            raise ProcessMessageSkippedError('ProcessMessageSkippedError')

        # with pytest.raises(ProcessMessageSkippedError):
        broker_rabbit.event_handler.execute_rabbit(message_retry)
        message_retry.reload()
        assert message_retry.status == 'SKIPPED'

    def test_message_need_wait(self, event_handler_item, broker_rabbit, message_first_try):

        @register_processor
        def bad_processor(handler, message):
            raise ProcessMessageNoResponseError('No Reponse')

        # Given processor should returns a 404
        event_handler_item.modify(processor='bad_processor')

        with pytest.raises(ProcessMessageNeedWaitError):
            broker_rabbit.event_handler.execute_rabbit(message_first_try)

        message_first_try.reload()
        assert message_first_try.status == 'NEED_WAIT'

    def test_bad_handler(self, broker_rabbit, message_retry):
        message_retry.handler = ''
        with pytest.raises(ProcessMessageError):
            broker_rabbit.event_handler.execute_rabbit(message_retry)

        message_retry.reload()
        assert message_retry.status == 'FAILURE'

    def test_message_with_status_skipped(self, broker_rabbit, message_retry):
        message_skipped = message_retry
        message_skipped.status = 'SKIPPED'
        message_skipped.save()
        broker_rabbit.event_handler.execute_rabbit(message_skipped)

        message_skipped.reload()
        assert message_skipped.status == 'SKIPPED'

    def test_message_with_status_failure(self, broker_rabbit, message_retry):
        message_failure = message_retry
        message_failure.status = 'FAILURE'
        message_failure.save()

        with pytest.raises(ProcessMessageError):
            broker_rabbit.event_handler.execute_rabbit(message_failure)

        message_failure.reload()
        assert message_failure.status == 'FAILURE'


class TestErrorFolder(common.BaseRabbitBrokerTest):

    def test_if_error_folder_have_retry_status(self, broker_rabbit, message_retry, message_first_try):
        # Given :
        discriminant_folder_on_error = message_retry.discriminant
        message_first_try.discriminant = discriminant_folder_on_error
        message_first_try.status = 'FAILURE'
        message_first_try.save()

        # When :
        ret = message_retry.is_folder_on_error()
        # Then :
        assert ret

    def test_if_error_folder_have_error_status(self, broker_rabbit, message_retry, message_first_try):
        # Given :

        message_failure = message_retry
        message_failure.status = 'FAILURE'
        message_failure.save()

        discriminant_folder_on_error = message_failure.discriminant
        message_first_try.discriminant = discriminant_folder_on_error
        message_first_try.save()

        # When :
        ret = message_first_try.is_folder_on_error()
        # Then :
        assert ret

    def test_if_error_folder_have_no_error(self, broker_rabbit, message_retry, message_first_try):
        # Given :
        message_done = message_retry
        message_done.status = 'DONE'
        message_done.save()

        # When :
        ret = message_done.is_folder_on_error()

        # Then :
        assert not ret
