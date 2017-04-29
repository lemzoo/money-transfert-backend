.. _broker:

Broker
======

The broker is a simple per-queue FIFO message broker, it can be
controlled by ``manage.py`` ::

    ./manage.py broker --help


Overview
--------

.. code ::

                +-----------+
        +-----> | processor |
        |       +-----------+
        |
     +---------------+              +-------+
     | event_handler | -----------> | event |
     +---------------+              +-------+
        |   ^---------------------------+
        v                               |
     +-------+                      +---------+
     | queue | <------------------- | message |
     +-------+                      +---------+


The sief application is full of events (see :file:`sief/events.py`) triggered
inside the api.

The aims of the broker is to dynamically connect async process to those
events though the ``event_handler``.

Furthermore, each event_handler must declare a ``processor`` and a ``queue`` to
process the messages.

A ``processor`` is a function that take a message an process it. The default
processor is the webhook: a simple HTTP POST of the message body on an url
configured in the ``event_handler``.

A ``queue`` is designed to be processed by a single worker at a time
(no concurrency) to ensure the messages are consumed in strict FIFO order.
On top of that, when a message is wrongly processed (i.g. the processor
crashed, the application the processor is supposed to talk to responds an
error) the queue is switched to ``FAILED`` status and must be manually fixed
and resumed.


Startup
-------

Before starting the broker, the queues must be created ::

    ./manage.py broker create inerec dna agdref

This command only need to be run once. Once done a :class:`QueueManager` is
created per queue. This object handle the 


Now the queues are created, they can be started to process the messages ::

    ./manage.py broker start inerec dna agdref

.. note ::
    * only one worker at a time can run on a single queue
    * the ``drop`` command can be used to delete a queue
    * see ``./manage.py broker start --help`` for additional options (i.g.
        daemon mode)


Stopping and repair
-------------------

The queue worker can be in different states:
 * ``RUNNING``: The worker is ready to process (or is currently processing) messages
 * ``FAILURE``: The worker worker has processed a message that returned an error.
 * ``PAUSES``: The worker has been explicitly tell to stop processing messages for the moment.
 * ``STOPPING``: The worker has been ask to stop, it is finishing it current message processing before exit.
 * ``STOPPED``: No worker is attached to the queue.

To display the current state of the queue and their `heartbeat`
(i.e. last time the worker has shown sign of life), we can use the ``list``
command ::

    $ ./manage.py broker list            
    inerec  RUNNING (heartbeat: 2015-08-06 20:17:12.791000)
    dna STOPPED (heartbeat: 2015-08-06 19:49:08.439000)
    agdref  STOPPED (heartbeat: 2015-08-06 19:49:08.442000)

During normal operation the queue worker switches between the first three
states ``RUNNING``, ``FAILURE`` and ``PAUSED``.

Once we want to stop the broker, we can use a ``^C`` (i.e. ``SIGINT``) or
just send a ``SIGTERM`` (automatically send by system during machine
shutdown for example).
This will cause a `warm shutdown`: the queue worker will switch to ``STOPPING``,
finish it current message processing if any, then finally switch to ``STOPPED``
and exit.

In case of a `cold shutdown` (i.g. the server suddenly crashed) the queue status
could not have been updated in the database. In such a case we can no longer
start a new worker given the queue is supposed to be already taken.
To solve this trouble, we have to call the ``repair`` command ::

    ./manage.py broker repair inerec dna agdref

.. note ::
     * This command will force the queue to be passed in ``STOPPED`` state
     * Before running this command, make sure no worker is running on the queue
