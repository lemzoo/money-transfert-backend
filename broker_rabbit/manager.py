import daemon

from lockfile.pidlockfile import PIDLockFile
from functools import partial
from flask import current_app
from flask.ext.script import Manager

from broker_rabbit.rabbit.connection_handler import ConnectionHandler
from broker_rabbit.rabbit.worker import Worker

broker_manager_rabbit = Manager(usage="Perform broker rabbitmq operations")


def _get_broker_rabbit():
    broker_rabbit = current_app.extensions.get('broker_rabbit')
    if not broker_rabbit:
        raise Exception('Extension broker rabbit not initialized')
    return broker_rabbit


@broker_manager_rabbit.option('queue', help='Single queue to monitor')
@broker_manager_rabbit.option('--log-level', dest='loglevel',
                              help='Log level', default='INFO')
@broker_manager_rabbit.option('--log-file', dest='logfile',
                              help='Log file', default='inerec.log')
@broker_manager_rabbit.option('-d', '--daemon', dest='daemonize',
                              action='store_true',
                              help='Daemonize the process', default=False)
@broker_manager_rabbit.option('-p', '--pid', dest='pid',
                              help='Store the pid of the process',
                              default='pid_file.pid')
def start(queue, loglevel, logfile, daemonize, pid):
    "Start worker on a given queue"

    rabbit_url = _get_broker_rabbit().rabbit_url
    connection_handler = ConnectionHandler(rabbit_url)
    event_handler = _get_broker_rabbit().event_handler
    message = _get_broker_rabbit().model.Message

    worker = Worker(connection_handler, queue, event_handler, message)
    cmd = partial(worker.consume_message)
    if daemonize:
        logfile = open(logfile, 'w+') if logfile else None
        pidfile = PIDLockFile(pid) if pid else None
        with daemon.DaemonContext(detach_process=daemonize, pidfile=pidfile,
                                  stdout=logfile, stderr=logfile, umask=0o002):
            cmd()
    else:
        cmd()
