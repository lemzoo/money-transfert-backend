from pyrabbit.api import Client
from pyrabbit.http import HTTPError


tags = ['administrator', 'monitoring',
        'policymaker', 'management']


def create_binding(client, vhost_name, exchange, queue):
    """Creates a binding between an exchange and a queue on a given vhost.

    :param Client client : Authentificated client which is ready to use
    :param str exchange : The target exchange of the binding.
    :param str queue : The queue to bind to the exchange
    :return bool: True on success.
    """
    result = client.create_binding(vhost_name, exchange, queue, queue)
    return result


def create_exchange(client, vhost_name, exchange_name, type_exchange='direct'):
    """Creates an exchange in the given vhost with the given name.
    As per the RabbitMQ API documentation, a JSON body also needs to be
    included that “looks something like this”:

    {“type”:”direct”, “auto_delete”:false, “durable”:true,
     “internal”:false, “arguments”:[]}

    On success, the API returns a 204 with no content, in which case this
    function returns True. If any other response is received, it’s raised.

    :param Client client : Authentificated client which is ready to use
    :param str exchange_name : Name of the proposed exchange.
    :param str type_exchange : The AMQP exchange type.
    """
    result = client.create_exchange(vhost_name, exchange_name,
                                    type_exchange)

    return result


def create_queue(client, vhost_name, queue):
    """Create a queue. The API documentation specifies that all of the body
    elements are optional, so this method only requires arguments needed to
    form the URI

    :param Client client : Authentificated client which is ready to use
    :param str vhost_name : The vhost to create the queue in.
    :param str queue : The name of the queue
    """
    result = client.create_queue(vhost_name, queue)
    return result


def create_user(client, username, password, tag='administrator'):
    """Creates a user..

    :param Client client : Authentificated client which is ready to use
    :param str username : The name to give to the new user.
    :param str user_password : Password for the new user.
    :return bool: True on success.
    """
    result = client.create_user(username, password, tag)
    return result


def create_vhost(client, vhost_name):
    """Creates a vhost on the server to house exchanges.

    :param Client client : Authentificated client which is ready to use
    :param Client client : The client to use for api in rabbit.
    :param str vhost_name : The name to give to the vhost on the server.
    :return bool: True on success.
    """
    result = client.create_vhost(vhost_name)
    return result


def delete_exchange(client, exchange):
    """Delete the named exchange from the named vhost.
    The API returns a 204 on success, in which case this method returns True,
    otherwise the error is raised.

    :param Client client : Authentificated client which is ready to use
    :param str exchange : The name of the exchange to delete.
    :return bool: True on success.
    """
    result = client.delete_exchange(exchange)
    return result


def delete_queue(client, vhost_name, queue):
    """Deletes the named queue from the named vhost.

    :param Client client : Authentificated client which is ready to use
    :param str vhost_name : Name of the virtual host ot get exchange
    :param str queue : Name of the queue to delete
    """
    client.delete_queue(vhost_name, queue)


def delete_user(client, username):
    """Deletes a user from the server.

    :param Client client : Authentificated client which is ready to use
    :param str username : Name of the user to delete from the server.
    """
    client.delete_user(username)


def delete_vhost(client, vhost_name):
    """Deletes a vhost from the server. Note that this also deletes any
    exchanges or queues that belong to this vhost.

    :param Client client : Authentificated client which is ready to use
    :param str vhost_name : Name of the virtual host to delete from the server.
    """
    client.delete_vhost(vhost_name)


def get_all_vhost(client):
    """Lists the names of all RabbitMQ vhosts.

    :param Client client : Authentificated client which is ready to use
    :return a list of dicts, each dict representing a vhost on the broker.
    """
    vhosts = client.get_all_vhosts()
    return vhosts


def get_exchange(client, vhost_name, exchange_name):
    """Gets a single exchange which requires a vhost and name.

    :param Client client : Authentificated client which is ready to use
    :param str vhost_name : Name of the virtual host ot get exchange
    :param str exchange_name : The name of the exchange
    :return dict
    """
    exchange = client.get_exchange(vhost_name, exchange_name)
    return exchange


def get_exchanges(client, ):
    """Get exchanges on rabbit

    :param Client client : Authentificated client which is ready to use
    :return list of dicts
    """
    exchanges = client.get_exchanges()
    return exchanges


def get_messages(client, vhost_name, queue):
    """Gets <count> messages from the queue..

    :param Client client : Authentificated client which is ready to use
    :param str queue: Name of the queue to consume from.
    :return list messages: list of dicts. messages[msg-index][‘payload’]
    will contain the message body.
    """
    try:
        messages = client.get_messages(vhost_name, queue)
    except HTTPError as e:
        messages = e
    return messages


def get_number_message_on_queue(client, vhost_name, queue):
    """Gets <count> messages from the queue..

    :param Client client : Authentificated client which is ready to use
    :param str queue: Name of the queue to consume from.
    :return int numbe_msg: The number of the message availabale on
                           the specified queue
    """
    single_gotten_message = None
    number_msg = 0
    messages = get_messages(client, vhost_name, queue)
    if isinstance(messages, HTTPError):
        number_msg = 0
    else:
        if messages:
            message_count = messages[0].get('message_count')
            single_gotten_message = messages[0]['payload']
            number_msg = message_count
    if single_gotten_message:
        number_msg = message_count + 1

    return number_msg


def get_queue(client, queue):
    """Get a single queue, which requires both vhost and name.

    :param Client client : Authentificated client which is ready to use
    :param str queue: The name of the queue being requested.
    :return dict properties: A dictionary of queue properties
    """
    properties = client.get_queue(queue)
    return properties


def get_queues(client):
    """Get all queues, or all queues in a vhost if vhost is not None.
    Returns a list.

    :param Client client : Authentificated client which is ready to use
    :return A list of dicts, each representing a queue
    """
    queues = [q['name'] for q in client.get_queues()]
    return queues


def get_queue_depth(client, queue):
    """Get the number of messages currently in a queue.

    :param Client client : Authentificated client which is ready to use
    :param str queue: The name of the queue which you get the number of message
    :return integer number_messages: The number of available message on queue
    """
    number_messages = client.get_queue_depth(queue)
    return number_messages


def get_queue_depths(client, queues):
    """Get the number of messages currently sitting in either the queue names
    listed in ‘names’, or all queues in ‘vhost’ if no ‘names’ are given.

    :param Client client : Authentificated client which is ready to use
    :param str queues: List of the queue which to get the number of message.
    :return list result: A list of dict, each key and value represent the queue
    and the number of message available on the queue.
    """
    result = client.get_queue_depths(queues)
    return result


def get_users(client):
    """Get the number of messages currently sitting in either the queue names
    listed in ‘names’, or all queues in ‘vhost’ if no ‘names’ are given.

    :param Client client : Authentificated client which is ready to use
    :return list users: a list of dictionaries, each representing a user.
    """
    users = client.get_users()
    return users


def purge_queue(client, queue_to_purge):
    """Purge all messages from a single queue. This is a convenience method so
    you aren’t forced to supply a list containing a single tuple to the
    purge_queues method.

    :param Client client : Authentificated client which is ready to use
    :param str queue_to_purge : The name of the queue being purged.
    """
    client.purge_queue(queue_to_purge)


def purge_queues(client, vhost_name, queues):
    """The name of the queue being purged.
    queues (list) – A list of (‘qname’, ‘vhost’) tuples.

    :param Client client : Authentificated client which is ready to use
    :return True on succes.
    """
    liste = []
    for queue in queues:
        tuple = (queue, vhost_name)
        liste.append(tuple)
    result = client.purge_queues(liste)
    return result


def publish(client, vhost_name, xname, rt_key, payload):
    """The name of the queue being purged.
    queues (list) – A list of (‘qname’, ‘vhost’) tuples.

    :param Client client : Authentificated client which is ready to use
    :return True on succes.
    """
    result = client.publish(vhost_name, xname, rt_key, payload)
    return result


def set_vhost_permissions(client, vhost_name, username,
                          config='.*', rd='.*', wr='.*'):
    """Set permissions for a given username on a given vhost.
    Both must already exist.

    :param Client client : Authentificated client which is ready to use
    :param str vhost_name: Name of the vhost to set perms on.
    :param str username: User to set permissions for.
    :param str config:  Permission pattern for configuration operations
                        for this user in this vhost..
    :param str rd: Permission pattern for read operations for this user
                   in this vhost.
    :param str wr : Permission pattern for write operations for this user
                    in this vhost.
    """
    client.set_vhost_permissions(vhost_name, username, config, rd, wr)


def create_user_rabbit(username, password, vhost_name):
    """Create a virtual environment for the given user. By default, it will use
    'guest' user to process that.

    :return True on succes.
    """
    # 1. create vhost
    client = Client('localhost:15672', 'guest', 'guest')
    create_vhost(client, vhost_name)

    # 2. create user
    create_user(client, username, password)

    # 3. set permissions
    set_vhost_permissions(client, vhost_name, username)

    # Create new client based on username and password given
    new_client = Client('localhost:15672', username, password)

    # 4. create queue
    queue_test = 'queue_test'
    create_queue(new_client, vhost_name, queue_test)

    queues = get_queues(new_client)
    return purge_queues(new_client, vhost_name, queues)


def client_rabbit(url, username, password):
    """Configure the client for rabbit

    :param str url: The adresse url of the host where rabbit located
    :param str username: The username id
    :param str password: The password
    :return Client client: Authentificated client which is ready to use
    """
    client = Client(url, username, password)
    return client
