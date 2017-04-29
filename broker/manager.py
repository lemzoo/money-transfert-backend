import csv
import collections
import json
from datetime import datetime, timezone
from re import search
import daemon
from lockfile.pidlockfile import PIDLockFile
from functools import partial
from flask import current_app
from flask.ext.script import Manager, prompt_bool
from flask_mail import Message as FlaskMailMessage
import argparse

from broker.model import Message, QueueManifest

import time

broker_manager = Manager(usage="Perform broker operations")


class DateArgument:

    """Used as a 'type=' argument in option parser to convert a date into the given format."""

    def __init__(self, format):
        self._format = format

    def __call__(self, val):
        from datetime import datetime
        try:
            return datetime.strptime(val, self._format)
        except ValueError:
            raise argparse.ArgumentTypeError('Not a valid date format (must be "{}")'.format(
                self._format))


def _get_broker():
    broker = current_app.extensions.get('broker')
    if not broker:
        raise Exception('Extension broker not initialized')
    return broker


def _get_mail():
    mail = current_app.extensions.get('mail')
    if not mail:
        raise Exception('Extension mail not initialized')
    return mail


def broker_watch_get_state_message():
    allowed_status = ['DONE', 'SKIPPED']
    total_done_skipped = Message.objects(status__in=allowed_status).count()
    total_message = Message.objects().count()
    return total_done_skipped, total_message


def broker_check_state_message(previous_done_skipped, previous_total, alert):
    new_done_skipped, new_total = broker_watch_get_state_message()
    if previous_total != new_total:
        if previous_done_skipped == new_done_skipped:
            alert()
    return new_done_skipped, new_total


def send_mail_alert():
    users = current_app.config['ALERT_MAIL_BROKER']
    subject = "[ALERT] One or more queue is apparently not working"
    body = "A repair and a restart of the queues should be performed"
    msg = FlaskMailMessage(subject=subject, body=body)
    for user in users:
        msg.add_recipient(user)
    _get_mail().send(msg)


def check_queue_status():
    queues = QueueManifest.objects()
    status = {'RUNNING': 0, 'FAILURE': 0, 'STOPPED': 0, 'STOPPING': 0, 'PAUSED': 0}
    for queue in queues:
        status[queue.status] += 1
    return status


@broker_manager.option('-t', '--timer', dest='timer', help='Polling timer', default=300, type=int)
def watch(timer, alert=send_mail_alert):

    users = current_app.config['ALERT_MAIL_BROKER']
    if not users:
        print("Please set a value for the environment variable: ALERT_MAIL_BROKER,\n"
              "This variable must contain a list of mail separate by ','\n"
              "example: 'test@test.com,arthur@martin.com'")
        return 1

    if not _get_mail():
        print('The mailer has not been initialize correctly please relaunch the app')
        return 1
    queue_status = check_queue_status()
    if queue_status['STOPPED'] != 0:
        queues = QueueManifest.objects(status='STOPPED')

        print("Some queues are not started please start them and relaunch the watcher:")
        for queue in queues:
            print("%s %s" % (queue.queue, queue.status))
        return 1

    total_done_skipped, total_message = broker_watch_get_state_message()
    print("And the watch begin")
    while True:
        time.sleep(timer)
        total_done_skipped, total_message = broker_check_state_message(
            total_done_skipped, total_message, alert)
        queue_status = check_queue_status()
        if queue_status['STOPPED'] or queue_status['FAILURE'] or queue_status['STOPPING']:
            alert()


@broker_manager.option('queues', help='Queues to monitor', nargs='+')
@broker_manager.option('--log-level', dest='loglevel', help='Log level', default='INFO')
@broker_manager.option('--log-file', dest='logfile', help='Log file', default=None)
@broker_manager.option('-t', '--timer', dest='timer', help='Polling timer', default=60)
@broker_manager.option('-d', '--daemon', dest='daemonize', action='store_true',
                       help='Daemonize the process', default=False)
@broker_manager.option('-p', '--pid', dest='pid', help='Store the pid of the process',
                       default=None)
def start(queues, loglevel, logfile, timer, daemonize, pid):
    "Start worker on a given queue"
    cmd = partial(_get_broker().run_queues, queues,
                  loglevel=loglevel, timer=timer)
    if daemonize:
        logfile = open(logfile, 'w+') if logfile else None
        pidfile = PIDLockFile(pid) if pid else None
        with daemon.DaemonContext(detach_process=daemonize, pidfile=pidfile,
                                  stdout=logfile, stderr=logfile, umask=0o002):
            cmd()
    else:
        cmd()


@broker_manager.option('queues', help='Queues to repair', nargs='+')
@broker_manager.option('-y', '--yes', help="Don't ask for confirmation",
                       action='store_true', default=False)
def repair(queues, yes):
    "Reset the queues to a STOPPED state"
    _broker = _get_broker()
    msg = "Make sure queues {green}{queues}{endc} in database {green}{db}{endc} are STOPPED".format(
        green='\033[92m', endc='\033[0m',
        queues=', '.join(queues), db=_broker.db_url)
    if not yes and not prompt_bool(msg):
        raise SystemExit('you changed your mind.')
    for queue in queues:
        if _broker.repair_queue(queue):
            print('Queue `%s` repaired' % queue)
        else:
            print("Queue `%s` doesn't need to be repaired" % queue)


@broker_manager.option('queues', help='Queues to create', nargs='+')
def create(queues):
    "Create a new queue"
    _broker = _get_broker()
    for queue in queues:
        _broker.create_queue(queue)
        print('Queue `%s` created' % queue)


@broker_manager.option('queues', help='Queues to create', nargs='+')
@broker_manager.option('-y', '--yes', help="Don't ask for confirmation",
                       action='store_true', default=False)
def drop(queues, yes):
    "Delete a queue and all it associated message and event handlers"
    _broker = _get_broker()
    msg = "Last chance to save queues {green}{queues}{endc} in database {green}{db}{endc}".format(
        green='\033[92m', endc='\033[0m',
        queues=', '.join(queues), db=_broker.db_url)
    if not yes and not prompt_bool(msg):
        raise SystemExit('you changed your mind.')
    for queue in queues:
        _broker.drop_queue(queue)
        print('Queue `%s` droped' % queue)


@broker_manager.command
def list_queues():
    "List the available queues"
    qm_cls = _get_broker().model.QueueManifest
    for qm in qm_cls.objects():
        print("%s\t%s (heartbeat: %s)" % (qm.queue, qm.status, qm.heartbeat))


@broker_manager.option('--port', help='Port to listen on', default=8080)
@broker_manager.option('--warn', help='Warning delay', default=5)
@broker_manager.option('--error', help='Error delay', default=15)
def run_monitoring_server(port, warn, error):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from datetime import datetime, timedelta
    from json import dumps

    class MonitoringWrapper(BaseHTTPRequestHandler):

        # Handler for the GET requests
        def do_GET(self):

            if self.path != '/monitoring/broker':
                self.send_error(404)
                return

            ret = {}
            ret['globalStatus'] = 'OK'
            ret['details'] = []
            queues_to_check = ['agdref', 'dna', 'inerec']
            delta = {'warning': timedelta(minutes=int(warn)),
                     'error': timedelta(minutes=int(error))
                     }
            db_queues = QueueManifest.objects(
                queue__in=(queues_to_check),
                status__in=('RUNNING', 'FAILURE'))
            if len(db_queues) != len(queues_to_check):
                ret['globalStatus'] = 'ERROR'

            for queue in db_queues:
                local_status = 'OK'
                if queue.status == 'FAILURE':
                    local_status = 'ERROR'
                    ret['details'].append({'name': "Test broker - %s " % queue.queue,
                                           'label': "Check queue %s" % queue.queue,
                                           'status': 'ERROR',
                                           'reason': 'Queue is in FAILURE state.'
                                           })
                elif abs(datetime.utcnow() - queue.heartbeat) > delta['warning']:
                    local_status = 'WARNING'
                    if abs(datetime.utcnow() - queue.heartbeat) > delta['error']:
                        local_status = 'ERROR'
                    ret['details'].append({'name': "Test broker - %s " % queue.queue,
                                           'label': "Check queue %s" % queue.queue,
                                           'status': local_status,
                                           'reason': 'Queue has not responded for more than %s.' % abs(datetime.utcnow() - queue.heartbeat)
                                           })
                else:
                    local_status = 'OK'
                    ret['details'].append({'name': "Test broker - %s " % queue.queue,
                                           'label': "Check queue %s" % queue.queue,
                                           'status': local_status,
                                           'reason': 'Queue is running.'
                                           })
                if ret['globalStatus'] != 'ERROR' and local_status != 'OK':
                    ret['globalStatus'] = local_status
                queues_to_check.remove(queue.queue)
            for queue in queues_to_check:
                ret['globalStatus'] = 'ERROR'
                ret['details'].append({'name': "Test broker - %s " % queue,
                                       'label': "Check queue %s" % queue,
                                       'status': 'ERROR',
                                       'reason': 'Queue is not running.'
                                       })

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(dumps(ret).encode())
    try:
        server = HTTPServer(('', int(port)), MonitoringWrapper)
        server.serve_forever()
    except KeyboardInterrupt:
        server.socket.close()


def _get_cancelled_msg(queue, from_date=None, to_date=None, event_handler=None):
    from sief.model import DemandeAsile, Usager

    errors = []

    def _extract_from_comment(regexp, comment):
        lookup = search(regexp, comment)
        try:
            return lookup.group(1)
        except (AttributeError, IndexError) as exc:
            errors.append((str(exc), comment))
            return 'Pas de code Erreur'

    def _parse(comment):
        if comment is None:
            return 'Pas de message'
        if queue == "agdref":
            return _extract_from_comment(r'<codeErreur>([0-9]{3})</codeErreur>', comment)
        elif queue == "dna":
            return _extract_from_comment(r'<CODE_ERREUR>([0-9]{2})</CODE_ERREUR>', comment)
        # queue == inerec
        return comment

    def _extract_info(msg):
        if msg.status_comment is None:
            return 'Pas de message'
        comment = msg.status_comment
        numero_ressortissant_etranger = _extract_from_comment(
            r'<numeroRessortissantEtranger>([0-9]{10})</numeroRessortissantEtranger>',
            comment)
        identifiant_si_asile = _extract_from_comment(
            r'<identifiantSIAsile>([0-9a-zA-Z]{12})</identifiantSIAsile>',
            comment)
        date_emission = _extract_from_comment(
            r'<dateEmissionFlux>([0-9]{8})</dateEmissionFlux>',
            comment)
        usager_id = 0
        da_id = 0
        gu = None
        if msg.json_context is not None:
            context = json.loads(msg.json_context)
            usager_id = context.get('usager', {}).get('id', 0)
            da = DemandeAsile.objects(usager=Usager.objects(id=usager_id).first())
            last_da = None
            for d in da:
                last_da = d
            if last_da:
                da_id = last_da.id
                recueil = last_da.recueil_da_origine
                if recueil:
                    gu = recueil.structure_guichet_unique
                    if gu:
                        gu = gu.libelle

        # Get local datetime
        msg_created = msg.created.replace(tzinfo=timezone.utc).astimezone(tz=None)
        msg_created = msg_created.strftime("%Y%m%d %X")

        return [msg.handler, msg_created, str(msg.id),
                numero_ressortissant_etranger, identifiant_si_asile,
                str(usager_id), str(da_id), date_emission, gu]

    kwargs = {"queue": queue, "status": 'CANCELLED'}
    if event_handler is not None:
        kwargs['handler'] = event_handler
    if from_date is not None:
        kwargs['created__gte'] = from_date
    if to_date is not None:
        kwargs['created__lte'] = to_date

    messages = _get_broker().model.Message.objects(**kwargs)

    counts = dict()
    error_info = dict()
    for msg in messages:
        key = _parse(msg.status_comment)
        counts[key] = counts.get(key, 0) + 1
        if queue == 'agdref' and key != 'Pas de code Erreur' and key != 'Pas de message':
            if key in error_info:
                error_info[key].append(_extract_info(msg))
            else:
                error_info[key] = [_extract_info(msg)]

    CancelledMessages = collections.namedtuple('CancelledMessages',
                                               ('error_info', 'errors', 'counts'))

    return CancelledMessages(error_info, errors, counts)


def _write_cancelled_msg_error_log(stream, errors):
    """Write the error log in CSV format to the stream."""
    writer = csv.writer(stream, delimiter=',', quoting=csv.QUOTE_ALL)
    writer.writerow(['message', 'Error'])
    # Write Values into CSV
    for key in errors:
        writer.writerow(key)


def _write_cancelled_msg_count(stream, counts):
    """Write the error count in CSV format to the stream."""
    writer = csv.writer(stream, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Code erreur', 'Nombre de messages'])
    # Write Values into CSV
    for key, value in counts.items():
        writer.writerow([key, value])


def _write_cancelled_msg_error_info(stream, rows):
    """Write the error information in CSV format to the stream."""
    writer = csv.writer(stream, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(['Handler', 'Date creation', 'Id message',
                     'Numero etranger', 'Identifiant SI Asile', 'Id usager',
                     "Id demande d'asile", "Date d'emission", "Guichet Unique"])
    # Write Values into CSV
    for r in rows:
        writer.writerow(r)


@broker_manager.option('--queue', help='Queue to check')
@broker_manager.option('--from', dest='from_date', help='Start date')
@broker_manager.option('--to', dest='to_date', help='End date')
@broker_manager.option('--eh', dest='event_handler', help='Event Handler')
def get_cancelled_msg(queue, from_date=None, to_date=None, event_handler=None):
    "Get cancelled msg into AGDREF queue"
    while not queue:
        queue = prompt("Select Queue between 'agdref', 'dna' and 'inerec'")
        if queue not in ['agdref', 'dna', 'inerec']:
            print('Queue mismatched')
            queue = None
        else:
            break

    msgs_info = _get_cancelled_msg(queue, from_date, to_date, event_handler)

    print(' *** Creating Error File ***')
    with open(queue + '_cancelled_msg_error.log', 'w') as errorfile:
        _write_cancelled_msg_error_log(errorfile, msgs_info.errors)

    print(' *** Creating CSV files ***')
    with open(queue + '_cancelled_msg.csv', 'w') as csvfile:
        _write_cancelled_msg_count(csvfile, msgs_info.counts)

    for key, rows in msgs_info.error_info.items():
        file_name = queue + '_error_' + key + '.csv'
        with open(file_name, 'w') as csvfile:
            _write_cancelled_msg_error_info(csvfile, rows)
