from signal import signal, SIGINT, SIGTERM
from time import sleep
import logging
import random

from broker.exceptions import WorkerStartingError, QueueManifestError
from connector.exceptions import ProcessMessageError,ProcessMessageNeedWaitError


def _config_logger(logger, level):
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(name)s :: %(message)s')
    steam_handler = logging.StreamHandler()
    steam_handler.setLevel(logging.DEBUG)
    steam_handler.setFormatter(formatter)
    logger.addHandler(steam_handler)


class WorkerPool:

    def __init__(self, broker, queues, log_level=logging.WARNING, timer=60,
                 batch_size=50, **kwargs):
        self.workers = [Worker(broker, queue, log_level=log_level, timer=timer, **kwargs)
                        for queue in queues]
        self._stopping = False
        self.timer = float(timer)
        self.batch_size = batch_size
        self.logger = logging.getLogger('WorkerPool')
        _config_logger(self.logger, log_level)

    def _register_signal(self):
        # Allow the worker to close nicely during sigint
        def coldexit(signum, frame):
            self.logger.error("\nCold shutdown, make sure to do a worker"
                              " cleanup before running another worker"
                              " on this queue")
            raise SystemExit(1)

        def warmexit(signum, frame):
            signal(SIGINT, coldexit)
            self.logger.warning('Warm shutdown...')
            self.stop(reason='Stopped by signal %s' % signum)
        signal(SIGINT, warmexit)
        signal(SIGTERM, warmexit)

    def run(self):
        self._register_signal()
        try:
            for worker in self.workers:
                self.logger.info('Start worker %s on queue %s' %
                                 (worker.id, worker.queue))
                worker.start()
        except:
            for worker in self.workers:
                worker.stopped(force=True)
            raise
        while not self._stopping:
            for worker in self.workers:
                worker.tick(self.batch_size)
            sleep(self.timer)
        for worker in self.workers:
            worker.stopped()

    def stop(self, **kwargs):
        self._stopping = True
        for worker in self.workers:
            worker.stopping(**kwargs)


class Worker:

    """
    A worker process the messages from a given queue
    :param broker: Broker to use
    :param queue: Queue to process
    :param timer: Waiting time once all messages has been processed before
                  polling the queue
    :param batch_size: Maximum number of messages to process at once
    """

    def __init__(self, broker, queue, log_level=logging.WARNING, timer=60):
        self.id = ''.join([random.choice('0123456789') for _ in range(5)])
        self.event_handler = broker.event_handler
        self.model = broker.model
        self.queue = queue
        self.timer = float(timer)
        self.manifest = None
        self.logger = logging.getLogger('worker-%s-%s' % (self.queue, self.id))
        _config_logger(self.logger, log_level)
        self._stopping = False

    def tick(self, batch_size=50):
        """
        Process batch_size messages from the queue
        """
        self.logger.debug('Heartbeat & Start sleep')
        self.manifest.controller.heartbeat()
        if self.manifest.status == 'RUNNING':
            return self._process_messages(batch_size)
        return 0

    def _process_messages(self, batch_size):
        # Get back the messages in the queue and process them
        msg_cls = self.model.Message
        count = 0
        try:
            batch = msg_cls.objects(
                queue=self.queue, status__nin=('DONE', 'CANCELLED', 'SKIPPED', 'DELETED')).order_by(
                    '+created')[:batch_size]
            for msg in batch:
                self.event_handler.execute_legacy(msg)
                count += 1
                self.logger.info('Message %s processed' % msg.id)
                if self._stopping:  # Leave early if we have been told to
                    break
        except ProcessMessageNeedWaitError as exc:
            # Message cannot be processed for the moment, wait and retry
            self.manifest.controller.info(str(exc))
        except ProcessMessageError as exc:
            self.manifest.controller.failure(reason=str(exc))
        return count

    def start(self):
        # Make sure no other worker processing this queue is running
        # Get back the queue manifest if it exists
        qm = self.model.QueueManifest.objects(queue=self.queue).first()
        if not qm:
            raise WorkerStartingError("Queue `%s` doesn't exist" % self.queue)
        try:
            qm.controller.start(self.id)
        except QueueManifestError as exc:
            raise WorkerStartingError(exc)
        self.manifest = qm

    def stopped(self, **kwargs):
        if not self.manifest:
            return
        self.manifest.controller.stopped(**kwargs)

    def stopping(self, **kwargs):
        if not self.manifest:
            return
        self._stopping = True
        self.manifest.controller.stopping(**kwargs)


def repair_queue_worker(model, queue):
    qms = model.QueueManifest.objects(queue=queue, status__ne='STOPPED')
    for qm in qms:
        qm.controller.stopped(force=True, reason='Force to STOPPED by repair queue')
        return True
    return False
