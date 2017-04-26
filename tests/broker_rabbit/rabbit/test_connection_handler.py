import pytest
from pika import BlockingConnection
from pika.exceptions import ConnectionClosed, ProbableAuthenticationError

from tests import common

from broker_rabbit.rabbit.connection_handler import ConnectionHandler

BROKER_RABBIT_URL = "amqp://guest:guest@localhost:5672/%2F"
BROKER_RABBIT_URL_FAKE_PORT = "amqp://guest:guest@localhost:8225/%2F"
BROKER_RABBIT_URL_FAKE_USER = "amqp://vip:vip@localhost:5672/%2F"


class TestConnnectionHandler(common.BaseRabbitBrokerTest):

    def test_init(self):
        connection_handler = ConnectionHandler(BROKER_RABBIT_URL)
        assert connection_handler._connection.is_open
        assert isinstance(connection_handler._connection, BlockingConnection)
        assert connection_handler._connection is not None

    def test_open_connection_with_bad_port_number(self):
        with pytest.raises(ConnectionClosed):
            connection_handler = ConnectionHandler(BROKER_RABBIT_URL_FAKE_PORT)
            assert connection_handler._connection.is_closed

    def test_open_connection_with_bad_credentials(self):
        with pytest.raises(ProbableAuthenticationError):
            ConnectionHandler(BROKER_RABBIT_URL_FAKE_USER)

    def test_get_connection(self):
        connection_handler = ConnectionHandler(BROKER_RABBIT_URL)
        assert connection_handler._connection.is_open

    def test_close_connection(self):
        connection_handler = ConnectionHandler(BROKER_RABBIT_URL)
        connection_handler.close_connection()
        assert connection_handler._connection.is_closed
        assert not connection_handler._connection.is_open
