'''
Auth Tools
'''

import jwt
from datetime import datetime
from hashlib import sha256
from passlib.apps import custom_app_context as pwd_context
from passlib.utils import generate_password as gen_pwd
from string import ascii_uppercase, ascii_lowercase, digits, punctuation
from flask import g, current_app

from core.tools import abort


def verify_password(password, pwd_hash):
    return pwd_context.verify(password, pwd_hash)


def encrypt_password(password):
    return pwd_context.encrypt(password)


def check_expiry_password(user):
    setting = 'PASSWORD_EXPIRY_DATE'

    # TODO : Remove me when a third mecanism is implemented for system user
    if hasattr(user, 'system_account') and user.system_account:
        setting = 'SYSTEM_PASSWORD_EXPIRY_DATE'
        if current_app.config['SYSTEM_PASSWORD_EXPIRY_DATE'] is 0:
            return

    if not (datetime.utcnow() - user.basic_auth.last_change_of_password).total_seconds() < current_app.config[setting]:
        abort(401, {'password': 'Password must be refreshed'})


def check_password_strength(password):
    import re
    specials = '!@#$%^&*+-/[]{}\\|=/?><,.;:"\''
    if (len(password) < 8 or
            not re.search(r'[A-Z]', password) or
            not re.search(r'[a-z]', password) or
            not re.search(r'[0-9]', password)):
        return False
    return next((True for l in password if l in specials), False)


def generate_password(length=12):
    choice = ascii_uppercase + ascii_lowercase + digits + punctuation
    pwd = gen_pwd(length, choice)
    while not check_password_strength(pwd):
        pwd = gen_pwd(size=length, charset=choice)
    return pwd


def change_password(user, password):
    if not user.controller.set_password(password):
        abort(409, 'Le mot de passe doit faire au moins 8 caractères '
              'avec au moins une majuscule, une minuscule, un caractère spécial et un chiffre')


def encode_token(payload):
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256').decode()


def decode_token(token):
    try:
        return jwt.decode(token, current_app.config['SECRET_KEY'])
    except jwt.InvalidTokenError:
        return None


def is_fresh_auth():
    token = getattr(g, '_token', None)
    if token:
        return token['fresh']
    else:
        return True


def build_pass_watcher(hashed_password):
    # Create a value that get revoked whenever the
    # user's password is changed
    key = current_app.config['SECRET_KEY'] + hashed_password
    return sha256(key.encode()).hexdigest()


def check_pass_watcher(value, hashed_password):
    key = current_app.config['SECRET_KEY'] + hashed_password
    return value == sha256(key.encode()).hexdigest()


def generate_access_token(login, hashed_password,
                          fresh=False, exp=None, freshness_exp=None, url_prefix=None):
    now = datetime.utcnow().timestamp()
    exp = exp or now + current_app.config['TOKEN_VALIDITY']
    freshness_exp = freshness_exp or now + \
        current_app.config['TOKEN_FRESHNESS_VALIDITY']
    return encode_token({
        'exp': exp,
        'login': login,
        'url_prefix': url_prefix,
        'type': 'auth',
        'fresh': fresh,
        'freshness_exp': freshness_exp,
        'watcher': build_pass_watcher(hashed_password)
    })


def generate_remember_me_token(login, hashed_password, exp=None, url_prefix=None):
    exp = exp or datetime.utcnow().timestamp() + \
        int(current_app.config['REMEMBER_ME_TOKEN_VALIDITY'])
    return encode_token({
        'exp': exp,
        'login': login,
        'url_prefix': url_prefix,
        'type': 'remember-me',
        'watcher': build_pass_watcher(hashed_password)
    })
