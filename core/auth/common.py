"""
Auth module provide two type of authentification
 - basic auth with login/password
 - token based with remember-me handling

On the top of that it handle the "freshness" of the authentification. An
authentification is considered as fresh if it has been generated from
the login/password:
 - basic auth is always fresh
 - token auth generated from login/password is fresh
 - token auth generated from remember-me token is not fresh

A fresh token should be required to do tasks requiring more security (i.g.
changing password)
"""

from werkzeug.local import LocalProxy
from flask import g, current_app, Blueprint, request
from flask.ext.principal import (Identity, UserNeed,
                                 AnonymousIdentity, identity_changed)

from ..tools import abort
from ..api import CoreApi


# A proxy for the current user. If no user is logged in, returns None
current_user = LocalProxy(lambda: g._current_user)


class LoginError(Exception):
    pass


def load_identity(user=None):
    """
    Load a user identity into Flask-Principal
    :param user: current user to load or anonymous user if empty
    """
    if not user:
        # Anonymous user
        identity = AnonymousIdentity()
    else:
        # TODO: find a better place for handling X-Use-Accreditation header
        # X-Use-Accreditation can be used to specy which accreditation to use for the current request
        from sief.model.utilisateur import AccreditationError
        use_accr = request.headers.get('X-Use-Accreditation')
        if use_accr:
            try:
                user.controller.set_current_accreditation(int(use_accr))
            except (TypeError, AccreditationError):
                abort(401, 'Invalid X-Use-Accreditation header')
        # Use str version of objectid to avoid json encoding troubles
        identity = Identity(str(user.id))
        identity.provides.add(UserNeed(user.id))
        for perm in user.controller.get_current_permissions():
            identity.provides.add(perm)
    g._current_user = user
    identity_changed.send(current_app._get_current_object(), identity=identity)


class AuthModule:

    """
    Super class used to bind an auth module to the given app
    """

    def __init__(self, app=None, user_cls=None, url_prefix="",
                 auth_field=None):
        """ Constructor.

        Args:
            user_cls : The model class
            url_prefix : The route api prefix
            auth_field : The model field used to store the Auth module type
        """

        self.user_cls = user_cls
        self.url_prefix = url_prefix
        self.auth_field = auth_field

        # Init blueprint
        self.api_bp = Blueprint(
            '%s-Auth' % self.url_prefix, __name__, url_prefix=self.url_prefix)
        self.api = CoreApi(self.api_bp)
        self._register_route()

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self._register_extension(app)
        app.register_blueprint(self.api_bp)

    def get_user_auth_field(self, user):
        return getattr(user, self.auth_field, None)

    def _register_route(self):
        raise NotImplementedError()

    def _register_extension(self, app):
        """
        Register an extension onto the Flask app.
        Needed to find by url_prefix the auth module which have generated the token
        """

        if not hasattr(app, 'extensions'):
            app.extensions = {}
        if 'auth' not in app.extensions:
            app.extensions['auth'] = {}
        if self.url_prefix not in app.extensions['auth']:
            app.extensions['auth'][self.url_prefix] = self
        else:
            raise Exception('Auth module Extension already initialized')

    def basic_authentication(self):
        abort(401, 'Not Implemented')

    def token_authentification(self, token, must_be_fresh=False):
        abort(401, 'Not Implemented')
