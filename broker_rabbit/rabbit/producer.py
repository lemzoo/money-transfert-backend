from broker_rabbit.rabbit.channels import ProducerChannel
from broker_rabbit.rabbit.exchange_handler import ExchangeHandler
from broker_rabbit.rabbit.queue_handler import QueueHandler


class Producer:
    """Producer component that will publish message and handle
    connection and channel interactions with RabbitMQ.

    """

    def __init__(self, connection, exchange_name, app=None, **kwargs):
        self._channel = None
        self._connection = connection.get_current_connection()
        self._exchange_name = exchange_name

    def init_env_rabbit(self, queues):
        """Initialize the queue on RabbitMQ

        :param list queues: List of queue to setup on rabbit by using default exchange
        """
        producer_channel = ProducerChannel(self._connection)
        producer_channel.open()
        self._channel = producer_channel.get_channel()

        exchange_handler = ExchangeHandler(self._channel, self._exchange_name)
        exchange_handler.setup_exchange()

        queue_handler = QueueHandler(self._channel, self._exchange_name)
        for queue in queues:
            queue_handler.setup_queue(queue)

        producer_channel.close()

    def publish(self, queue, message):
        """Publish the given message in the given queue

        :param str queue : The queue name which to publish the given message
        :param dict message : The message to publish in RabbitMQ
        """
        producer_channel = ProducerChannel(self._connection)
        producer_channel.open()
        producer_channel.send_message(self._exchange_name, queue, message)
        producer_channel.close()
