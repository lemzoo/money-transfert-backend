'''
Login/Password Auth Module
'''

from re import match
from datetime import datetime
from flask import g, request
from flask.ext.restful import Resource, reqparse
from mongoengine import EmbeddedDocument, fields

from core.tools import abort
from core.view_util import UnknownCheckedSchema

from .common import AuthModule, load_identity, LoginError
from .tools import (verify_password, check_expiry_password, decode_token,
                    check_pass_watcher, change_password,
                    generate_access_token, generate_remember_me_token,
                    check_password_strength)


def _bind_to_auth_module_factory(auth_module, api_cls):
    return type('Binded%s' % api_cls.__name__, (api_cls, ), {'auth_module': auth_module})


class LoginPwdDocument(EmbeddedDocument):
    login = fields.StringField(unique=True, sparse=True)
    hashed_password = fields.StringField(max_length=255)
    reset_password_token = fields.StringField(null=True)
    reset_password_token_expire = fields.DateTimeField(null=True)
    change_password_next_login = fields.BooleanField(null=True)
    last_change_of_password = fields.DateTimeField(
        null=True, default=datetime.utcnow)


class LoginPwdSchema(UnknownCheckedSchema):

    class Meta:
        model = LoginPwdDocument
        model_fields_kwargs = {
            'login': {'load_only': True},
            'hashed_password': {'load_only': True},
            'reset_password_token': {'load_only': True},
            'reset_password_token_expire': {'load_only': True},
            'last_change_of_password': {'load_only': True},
        }


class LoginPwdAuthModule(AuthModule):

    """
    Auth module for authentication with login/mdp
    """

    # TODO : Delete /login from the others routes
    def _register_route(self):
        self.api.add_resource(
            _bind_to_auth_module_factory(self, Login), '/login')
        self.api.add_resource(_bind_to_auth_module_factory(
            self, RememberMe), '/login/remember-me')
        self.api.add_resource(_bind_to_auth_module_factory(
            self, ChangePassword), '/login/password')
        self.api.add_resource(_bind_to_auth_module_factory(
            self, ValidatePasswordStrength), '/login/password/validate_strength')
        self.api.add_resource(_bind_to_auth_module_factory(
            self, PasswordRecovery), '/login/password_recovery/<string:login>')

    def basic_authentication(self, login, password):
        user_cls = self.user_cls
        try:
            user = user_cls.objects.get(email=login)
        except user_cls.DoesNotExist:
            raise LoginError()
        if not user.controller.is_user_valid():
            raise LoginError()
        if verify_password(password, self.get_user_auth_field(user).hashed_password):
            check_expiry_password(user)
            return user

    def token_authentication(self, token, must_be_fresh=False):
        # Token must be passed as header (`{"Authorization": "Token <token>"}`)
        g._token = token
        if not token or token['type'] != 'auth' or (
            must_be_fresh and (not token['fresh'] or
                               token['freshness_exp'] < datetime.utcnow().timestamp())):
            raise LoginError()
        user_cls = self.user_cls
        try:
            user_lookup = {'%s__login' % self.auth_field: token['login']}
            user = user_cls.objects.get(**user_lookup)
        except user_cls.DoesNotExist:
            raise LoginError()
        if (not user.controller.is_user_valid() or
                not check_pass_watcher(
                    token['watcher'], self.get_user_auth_field(user).hashed_password)):
            raise LoginError()
        user._token_fresh = token['fresh']
        return user


class Login(Resource):

    """
    Authenticate a user given it email and password then
    issue him an access token
    """

    @property
    def auth_module(self):
        # Should be defined by `bin_to_auth_module_factory`
        raise NotImplementedError()

    def post(self):
        # Tell Flask-Principal the user is anonymous
        load_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('login', type=str, required=True)
        parser.add_argument('password', type=str, required=True)
        parser.add_argument('remember_me', type=bool, default=False)
        args = parser.parse_args()
        remember_me = args.get('remember_me', False)
        login = args['login']
        # Retrieve the user, check it password and issue the tokens
        user_cls = self.auth_module.user_cls
        user_lookup = {'%s__login' % self.auth_module.auth_field: login}
        user = user_cls.objects(**user_lookup).first()
        if not user:
            abort(401)
        auth_field = self.auth_module.get_user_auth_field(user)
        if not auth_field:
            abort(401)
        hashed_password = auth_field.hashed_password
        if not verify_password(args['password'], hashed_password):
            abort(401)
        check_expiry_password(user)
        result = {'token': generate_access_token(
            login, hashed_password, fresh=True, url_prefix=self.auth_module.url_prefix)}
        if remember_me:
            remember_me_token = generate_remember_me_token(
                login, hashed_password, url_prefix=self.auth_module.url_prefix)
            result['remember_me_token'] = remember_me_token
        return result


class RememberMe(Resource):

    """
    Check the user's remember-me token and reissue an access token
    """

    @property
    def auth_module(self):
        # Should be defined by `bin_to_auth_module_factory`
        raise NotImplementedError()

    def post(self):
        # Tell Flask-Principal the user is anonymous
        load_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('remember_me_token', type=str, required=True)
        args = parser.parse_args()
        remember = decode_token(args['remember_me_token'])
        if not remember or remember['type'] != 'remember-me':
            abort(401)
        login = remember['login']
        user_cls = self.auth_module.user_cls
        user_lookup = {'%s__login' % self.auth_module.auth_field: login}
        user = user_cls.objects(**user_lookup).first()
        if not user:
            abort(401)
        auth_field = self.auth_module.get_user_auth_field(user)
        if not auth_field:
            abort(401)
        hashed_password = auth_field.hashed_password
        if not check_pass_watcher(remember['watcher'], hashed_password):
            abort(401)
        return {'token': generate_access_token(login, hashed_password, fresh=False,
                                               url_prefix=self.auth_module.url_prefix)}


class ChangePassword(Resource):

    """
    Change the password for a user providing a fresh token (i.e. not remembered-me token)
    """

    @property
    def auth_module(self):
        # Should be defined by `bin_to_auth_module_factory`
        raise NotImplementedError()

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('login', type=str, required=True)
        parser.add_argument('password', type=str, required=True)
        parser.add_argument('new_password', type=str, required=True)
        args = parser.parse_args()
        login = args['login']
        password = args['password']
        new_password = args['new_password']
        if new_password == password:
            abort(409, "L'ancien mot de passe et le nouveau doivent être différents.")
        user_cls = self.auth_module.user_cls
        user_lookup = {'%s__login' % self.auth_module.auth_field: login}
        user = user_cls.objects(**user_lookup).first()
        if not user:
            abort(401)
        auth_field = self.auth_module.get_user_auth_field(user)
        if not auth_field:
            abort(401)
        hashed_password = auth_field.hashed_password
        if not verify_password(password, hashed_password):
            abort(401)
        change_password(user, new_password)
        user.controller.restore_password()
        user.save()
        new_hashed_password = self.auth_module.get_user_auth_field(
            user).hashed_password
        return {'token': generate_access_token(login, new_hashed_password, fresh=True,
                                               url_prefix=self.auth_module.url_prefix)}


class ValidatePasswordStrength(Resource):

    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('password', type=str, required=True)
        args = parser.parse_args()
        password_to_validate = args['password']
        response = {
            'is_valid': check_password_strength(password_to_validate)
        }
        return response, 200


class PasswordRecovery(Resource):

    """
    class used for creating a reset password token for a user.

    """

    def get(self, login=None):
        """
        Always return 200 for security purpose (No user discovery and bruteforce)
        """
        from sief.tasks.email import mail
        user_cls = self.auth_module.user_cls
        if not login:
            return {}, 200
        user_lookup = {'%s__login' % self.auth_module.auth_field: login}
        user = user_cls.objects.get(**user_lookup)
        if not user:
            return {}, 200
        if mail.debug:
            token = user.controller.reset_password()
        else:
            user.controller.reset_password()
        user.controller.save_or_abort()
        if mail.debug:
            return {'token': token}
        else:
            return {}, 200

    def post(self, login=None):
        """
        Always return 200 for security purpose (No user discovery and bruteforce)
        """
        user_cls = self.auth_module.user_cls
        payload = request.get_json()
        if not login or not payload.get('token'):
            return {}, 200
        token = payload['token']
        if not match(r'[0-9a-f]{64}', token):
            abort(401, {'token': 'Token invalide'})
        user_lookup = {
            '%s__login' % self.auth_module.auth_field: login,
            '%s__reset_password_token' % self.auth_module.auth_field: token,
            '%s__reset_password_token_expire__gte' % self.auth_module.auth_field: datetime.utcnow()
        }
        user = user_cls.objects(**user_lookup).first()
        if user:
            change_password(user, payload['password'])
            user.controller.save_or_abort()
        else:
            abort(401, {'password': 'Utilisateur inexistant ou token expire'})
        return {}, 200
