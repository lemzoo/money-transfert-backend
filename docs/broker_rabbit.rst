.. _broker_rabbit:

Installation Guide for Rabbit MQ
--------------------------------

1 - Install Rabbit MQ (Debian, Ubuntu) ::

    echo 'deb http://www.rabbitmq.com/debian/ testing main' | sudo tee /etc/apt/sources.list.d/rabbitmq.list

    wget -O- https://www.rabbitmq.com/rabbitmq-release-signing-key.asc | sudo apt-key add -

    sudo apt-get update

    sudo apt-get install rabbitmq-server

(Source : https://www.rabbitmq.com/install-debian.html)



2 - Configure Rabbit MQ
::
    cd /etc/rabbitmq/

    sudo wget https://raw.githubusercontent.com/rabbitmq/rabbitmq-server/master/docs/rabbitmq.config.example

    sudo mv rabbitmq.config.example rabbitmq.config

Remove comment on line 58 and add ``guest`` at the line containing the users
::
    sudo vi rabbitmq.config
    {loopback_users, ["guest"]},


Remove comment on line 95 and add ``'PLAIN', 'AMQPLAIN'`` (Pay attention to remove the comma)
::
    {auth_mechanisms, ['PLAIN', 'AMQPLAIN', 'EXTERNAL']}

A firewall might blocked communication between the nodes and CLI tools. Verify that the following ports are open :
- 4369 (epmd)
- 5672, 5671 (AMQP 0-9-1 and 1.0 without and with TLS)
- 25672. This port is used for Erlang distributivity ensuring the communication between the nodes and the CLI tools. It's allocated based on a dynamic range (limited at one default port, computed as AMQP+20000 port)
- 15672 (if management-plugin is activated)
- 61613, 61614 (si STOMP is activated)
- 1883, 8883 (if MQTT is activated)

It's possible to configure RabbitMQ on different ports and specific network interfaces.



3 - Install Rabbit MQ Management ::

    sudo rabbitmq-plugins enable rabbitmq_management

The console can be found at : ``http://localhost:15672/``
Connect with default login and password ``guest/guest``



4 - Operations with Rabbit MQ

Show broker status::

    sudo rabbitmqctl status

Stop Erlang node on which RabbitMQ is running ::

    sudo rabbitmqctl stop

Start RabbitMQ::

    sudo rabbitmqctl start_app

Stop RabbitMQ::

    sudo rabbitmqctl stop_app



5 - Broker_Rabbit architecture
``https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=24903696``



6 - References
For more informations about RabbitMQ commands see manual:
``https://www.rabbitmq.com/man/rabbitmqctl.1.man.html``

RabbitMQ tutorials:
``https://www.rabbitmq.com/getstarted.html``
