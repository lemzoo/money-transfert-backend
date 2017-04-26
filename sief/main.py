import requests
from os.path import abspath, dirname
from flask import current_app, make_response
from core.core_app import CoreApp


def create_app(config=None):
    """
    Build the app build don't initilize it, useful to get back the default
    app config, correct it, then call ``bootstrap_app`` with the now config
    """

    app = CoreApp(__name__)
    if config:
        app.config.update(config)
    app.config.from_pyfile('default_settings.cfg')
    return app


def bootstrap_app(app=None, config=None):
    """
    Create and initilize the sief app
    """

    if not app:
        app = create_app(config)
    elif config:
        app.config.update(config)

    from sief import model, events, roles
    from core.auth import LoginPwdAuthModule
    from sief.view import api
    from sief.tasks.email import mail

    app.bootstrap()

    model.init_app(app)

    app.config['ROLES'] = roles.ROLES

    # Init Auth module for Usager
    LoginPwdAuthModule(
        app=app,
        user_cls=model.Usager,
        url_prefix=app.config['BACKEND_API_PREFIX'] + '/usager',
        auth_field='basic_auth')

    # Init Auth module for Agent
    LoginPwdAuthModule(
        app=app,
        user_cls=model.Utilisateur,
        url_prefix=app.config['BACKEND_API_PREFIX'] + '/agent',
        auth_field='basic_auth')

    # Register Asile API
    api.prefix = app.config['BACKEND_API_PREFIX']
    api.init_app(app)
    mail.init_app(app)

    from connector import init_connectors
    init_connectors(app)
    events.init_events(app)
    from services.fne import fne_config
    fne_config.init_app(app)
    from services.agdref import agdref_requestor
    agdref_requestor.init_app(app)
    from services.fpr import init_fpr
    init_fpr(app)
    from services.ants_pftd import stamp_service
    stamp_service.init_app(app)

    from sief.cache import init_cache
    init_cache(app)

    # Register Blueprint for VLS-TS
    from vlsts import vlsts_blueprint
    app.register_blueprint(vlsts_blueprint)

    # Configure static hosting of the front
    if app.config['FRONTEND_HOSTED']:
        from flask import send_from_directory
        try:
            from flask.ext.cache import Cache
        except ImportError:
            raise ImportError('module `flask_cache` is required to'
                              ' enable FRONTEND_HOSTED')
        cache = Cache(app, config={'CACHE_TYPE': 'simple'})
        app.root_path = abspath(dirname(__file__) + '/..')
        redirect_url = app.config['FRONTEND_HOSTED_REDIRECT_URL']

        @app.route('/')
        @app.route('/<path:path>')
        @cache.cached(timeout=600)
        def host_front(path='index.html'):
            if redirect_url:
                target = '{}/{}'.format(redirect_url, path)
                r = requests.get(target)
                if r.status_code != 200:
                    app.logger.error('cannot fetch {}, error {} : {}'.format(
                        target, r.status_code, r.data))
                response = make_response(r.content, r.status_code)
                for key, value in r.headers.items():
                    response.headers[key] = value
                return response
            return send_from_directory('static', path)

    else:
        # Root access is useful to test if the server is online (no auth needed)
        @app.route('/')
        def index():
            return ''

    # Create a user to test with
    @app.before_first_request
    def create_user():
        if current_app.config.get('DEBUG', False):
            # Create a default admin in debug
            from sief.model.utilisateur import Utilisateur
            try:
                Utilisateur.objects.get(email='admin@test.com')
            except Utilisateur.DoesNotExist:
                current_app.logger.info('Creating default user admin@test.com')
                new_user = Utilisateur(email='admin@test.com', nom='Min', prenom='Ad')
                new_user.controller.add_accreditation(role="ADMINISTRATEUR")
                new_user.controller.init_basic_auth()
                new_user.controller.set_password('P@ssw0rd')
                new_user.save()
    return app
