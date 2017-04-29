class WorkerError(Exception):
    pass


class WorkerStartingError(WorkerError):
    pass


class QueueManifestError(WorkerError):
    pass
