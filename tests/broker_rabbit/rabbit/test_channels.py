import pytest

from unittest.mock import Mock

from pika.connection import Connection
from pika.spec import Basic

from tests import common

from broker_rabbit.exceptions import (
    ConnectionNotOpenedYet, ChannelRunningException, WorkerExitException, ConnectionIsClosed)
from broker_rabbit.rabbit.channels import ChannelHandler, WorkerChannel
from broker_rabbit.rabbit.connection_handler import ConnectionHandler


BROKER_RABBIT_URL = "amqp://guest:guest@localhost:5672/%2F"


class TestChannelHandler(common.BaseRabbitBrokerTest):

    def setup_method(self):
        self.connection = ConnectionHandler(BROKER_RABBIT_URL)
        self.channel_handler = ChannelHandler(self.connection.get_current_connection())

    def test_if_channel_is_open(self):
        self.channel_handler.open()
        assert self.connection._connection.is_open
        self.channel_handler.close()

    def test_if_channel_is_open_failed(self):
        with pytest.raises(ConnectionNotOpenedYet):
            channel_handler = ChannelHandler(None)
            channel_handler.open()

    def test_if_connection_is_closed(self):
        with pytest.raises(ConnectionIsClosed):
            self.channel_handler._connection.close()
            assert self.connection._connection.is_closed
            self.channel_handler.open()


class TestWorkerChannel(common.BaseRabbitBrokerTest):

    def setup_method(self):
        connection = Mock(Connection)
        connection.is_closed = False
        self.worker_channel = WorkerChannel(connection, None, None, None)
        self.worker_channel.open()

    def test_raising_error_on_keyboard_interput(self):
        self.worker_channel._channel.start_consuming.side_effect = \
            KeyboardInterrupt('Testing Keyboard Exception')
        with pytest.raises(WorkerExitException):
            self.worker_channel.run()

    def test_execute_rabbit_is_not_called_when_exeption_raised(self):
        empty_body_as_bytes = b'{}'
        self.worker_channel.event_handler = Mock()
        # When
        self.worker_channel.on_message(None, Basic.GetOk(), None, empty_body_as_bytes)
        # Then
        assert not self.worker_channel.event_handler.execute_rabbit.called
