from flask.ext.restful import Resource

from core.concurrency import concurrency_handler
from core.auth import login_required


class CoreResource(Resource):

    """
    Flask-restful resource with automatic authentication and
    concurrency handling
    """
    method_decorators = [concurrency_handler, login_required]  # reversed order


class NoAuthCoreResource(Resource):

    """
    Flask-restful resource without authentication to
        allow user to reset their password. Use with Caution.
    """

    method_decorators = [concurrency_handler, ]
