'''
Auth Decorator
'''

from functools import wraps
from flask import request, current_app

from ..tools import abort
from .common import load_identity, LoginError
from .tools import decode_token


def login_required_fresh(func):
    """
    Decorator to make mandatory fresh login
    """
    return login_required(func, True)


def login_required(func, must_be_fresh=False):
    """Authenticate decorator for the routes"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not getattr(func, 'authenticated', True):
            return func(*args, **kwargs)
        raw_auth = request.headers.get('Authorization', '')
        if raw_auth == '':
            abort(401)
        else:
            auth_type, auth_value = raw_auth[:6].lower(), raw_auth[6:]
            try:
                if auth_type == 'token ':
                    user = _token_authentication(auth_value, must_be_fresh)
                elif auth_type == 'basic ':
                    user = _basic_authentication(auth_value)
                else:
                    raise LoginError()
            except (TypeError, LoginError) as e:
                abort(401, str(e))
            load_identity(user)
        return func(*args, **kwargs)
    return wrapper


def _basic_authentication(token):
    cut = request.authorization.username.split(':')
    if len(cut) != 2:
        raise LoginError()
    auth_prefix, login = cut
    auth_module = current_app.extensions['auth'].get(auth_prefix)
    if not auth_module:
        raise LoginError()
    return auth_module.basic_authentication(login, request.authorization.password)


def _token_authentication(token, must_be_fresh):
    cooked_token = decode_token(token)
    auth_prefix = cooked_token['url_prefix']
    auth_module = current_app.extensions['auth'][auth_prefix]
    return auth_module.token_authentication(cooked_token, must_be_fresh)
