import json
import pytest
from base64 import b64encode
from collections import namedtuple
from pymongo.errors import OperationFailure

from sief.main import bootstrap_app, create_app
from core.auth.tools import generate_access_token

from tests.broker_rabbit.rabbit_api import (
    client_rabbit, delete_queue, get_queues)


DEFAULT_USER_TEST = 'guest'
DEFAULT_PASSWORD_TEST = 'guest'
VHOST_TEST = '/'
RABBIT_URL_FOR_TEST = 'localhost:15672'


class NOT_SET:

    def __repr__(self):
        return '<not_set>'


NOT_SET = NOT_SET()


def get_broker_legacy_db_url():
    from sief.main import create_app
    sief_app = create_app()
    return sief_app.config['BROKER_TEST_DB_URL']


def get_broker_rabbit_db_url():
    from sief.main import create_app
    sief_app = create_app()
    return sief_app.config['BROKER_TEST_RABBIT_MONGODB_URL']


def get_rabbit_url():
    from sief.main import create_app
    sief_app = create_app()
    return sief_app.config['BROKER_TEST_RABBIT_URL']


def get_rabbit_exchange():
    from sief.main import create_app
    sief_app = create_app()
    return sief_app.config['BROKER_TEST_RABBIT_EXCHANGE']


def update_payload(payload, route, value):
    splitted = route.split('.')
    cur_node = payload
    for key in splitted[:-1]:
        if isinstance(cur_node, (list, tuple)):
            key = int(key)
            if len(cur_node) <= key:
                raise ValueError('indice %s is not in list' % key)
        elif isinstance(cur_node, dict):
            if key not in cur_node:
                cur_node[key] = {}
        else:
            raise ValueError('%s must lead to a dict' % key)
        cur_node = cur_node[key]
    last_key = splitted[-1]
    if value is NOT_SET:
        if last_key in cur_node:
            del cur_node[last_key]
    elif isinstance(cur_node, (list, tuple)):
        cur_node[int(last_key)] = value
    else:
        cur_node[last_key] = value


def assert_response_contains_links(response, links):
    assert '_links' in response.data
    data_links = response.data['_links']
    for l in links:
        assert l in data_links, l
    assert not data_links.keys() - set(links)


class AuthRequests:

    """Wrap user model to easily do requests on the api with it credentials"""

    CookedResponse = namedtuple('CookedResponse', ['status_code', 'headers', 'data'])

    def __init__(self, document, app, client_app, url_prefix=None):
        self.document = document
        self.client_app = client_app
        self.app = app
        # generate a token for the requests
        with self.app.app_context():
            self.token = generate_access_token(document.basic_auth.login,
                                               document.basic_auth.hashed_password, fresh=True,
                                               url_prefix=url_prefix)

    def _decode_response(self, response):
        encoded = response.get_data()
        if encoded:
            decoded = json.loads(encoded.decode('utf-8'))
            if isinstance(decoded, str):
                decoded = json.loads(decoded)
            assert isinstance(decoded, dict)
        else:
            decoded = encoded
        return self.CookedResponse(response.status_code, response.headers, decoded)

    def __getattr__(self, name):
        method_name = name.upper()
        if method_name not in ['POST', 'PATCH', 'PUT', 'GET',
                               'OPTIONS', 'HEAD', 'DELETE']:
            raise RuntimeError('Only HTTP verbs are allowed as methods')
        return lambda *args, **kwargs: self._mk_request(method_name)(*args, **kwargs)

    def request(self, method, *args, **kwargs):
        return self._mk_request(method)(*args, **kwargs)

    def _mk_request(self, method_name):
        def caller(route, headers=None, data=None, auth=True, dump_data=True, **kwargs):
            if dump_data:
                serial_data = json.dumps(data, cls=self.app.json_encoder)
            else:
                serial_data = data
            headers = headers or {}
            if auth:
                headers['Authorization'] = 'Token ' + self.token
            params = {
                'headers': headers,
                'content_type': 'application/json',
                'content_length': len(serial_data)
            }
            params.update(kwargs)
            if data or isinstance(data, dict):
                params['data'] = serial_data
            method_fn = getattr(self.client_app, method_name.lower())
            with self.app.app_context():
                raw_ret = method_fn(route, **params)
            return self._decode_response(raw_ret)
        return caller


def build_basic_auth(email, password):
    concat = '%s:%s' % (email, password)
    return 'Basic ' + b64encode(concat.encode()).decode()


def build_request(headers=None, auth=None, data=None, dump_data=True):
    kw = {'headers': headers or {}}
    if auth:
        kw['headers']['Authorization'] = build_basic_auth(*auth)
    if data:
        if dump_data:
            kw['data'] = json.dumps(data)
            kw['content_type'] = 'application/json'
        else:
            kw['data'] = data
        kw['content_length'] = len(kw['data'])
    return kw


class ClientAppRouteWrapper(object):

    def __init__(self, app):
        self.app = app
        self.client_app = app.test_client()

    def _wrap(self, fn):
        url_prefix = self.app.config['BACKEND_API_PREFIX']
        if not url_prefix:
            return fn

        def wrapper(route, *args, force_route=False, **kwargs):
            if not force_route and not route.startswith(url_prefix):
                route = url_prefix + route
            return fn(route, *args, **kwargs)
        return wrapper

    def __getattr__(self, method_name):
        if method_name in ['post', 'patch', 'put', 'get',
                           'options', 'head', 'delete']:
            return self._wrap(getattr(self.client_app, method_name))
        return super().__getattr__(method_name)


class BaseTest:

    client_app = None

    def make_auth_request(self, user, password=None, url_prefix=None):
        from sief.model.utilisateur import Utilisateur
        if not url_prefix:
            if isinstance(user, Utilisateur):
                url_prefix = '/agent'
            else:
                url_prefix = '/usager'
        return AuthRequests(user, self.app, self.client_app, url_prefix=url_prefix)

    @classmethod
    def _clean_db(cls):
        cls.app.db.connection.drop_database(
            cls.app.db.connection.get_default_database().name)

    @staticmethod
    def _get_config(app):
        config = {
            'MONGODB_HOST': app.config['MONGODB_TEST_URL'],
            'BROKER_DB_URL': app.config['BROKER_TEST_DB_URL'],
            'BROKER_RABBIT_MONGODB_URL': app.config['BROKER_TEST_RABBIT_MONGODB_URL'],
            'SOLR_URL': app.config['SOLR_TEST_URL'],
            'BROKER_RABBIT_URL': app.config['BROKER_TEST_RABBIT_URL'],
            'BROKER_RABBIT_EXCHANGE': app.config['BROKER_TEST_RABBIT_EXCHANGE'],
            'DISABLE_SOLR': True,
            'DISABLE_EVENTS': True,
            'DISABLE_RABBIT': True,
            'TESTING': True,
            'ENABLE_CACHE': False,
            'MAIL_SUPPRESS_SEND': True,
            'DISABLE_MAIL': False,
            'FPR_TESTING_STUB': True,
            'FNE_TESTING_STUB': True,
            'AGDREF_NUM_TESTING_STUB': True,
            'ALERT_MAIL_BROKER': ['test@test.com', 'arthur@martin.com']
        }

        if (pytest.config.getoption('runsolr') and
                pytest.config.getoption('solr_everywhere')):
            BaseSolrTest._update_config(config)

        if pytest.config.getoption('event_everywhere'):
            BaseLegacyBrokerTest._update_config(config)

        if pytest.config.getoption('runrabbit'):
            BaseRabbitBrokerTest._update_config(config)

        return config

    @classmethod
    def setup_class(cls, config={}):
        """
        Initialize flask app and configure it with a clean test database
        """
        app = create_app()
        app.testing = True
        test_config = cls._get_config(app)

        test_config.update(config)
        bootstrap_app(app=app, config=test_config)

        cls.app = app
        cls.ctx = app.app_context()
        cls.ctx.push()
        cls.client_app = ClientAppRouteWrapper(app)

    def setup_method(self, method):
        self._clean_db()

    @classmethod
    def teardown_class(cls):
        cls.ctx.pop()


@pytest.mark.solr
class BaseSolrTest(BaseTest):

    @staticmethod
    def _update_config(config):
        config['DISABLE_SOLR'] = False
        return config

    @staticmethod
    def _get_config(app):
        config = BaseTest._get_config(app)
        BaseSolrTest._update_config(config)
        return config

    @classmethod
    def _clean_solr(cls):
        if pytest.config.getoption('runsolr'):
            cls.app.solr.delete(q='*:*', waitFlush=True)

    def setup_method(self, method):
        self._clean_solr()
        super().setup_method(method)


class BaseLegacyBrokerTest(BaseTest):

    @staticmethod
    def _update_config(config):
        config['DISABLE_EVENTS'] = False
        return config

    @staticmethod
    def _get_config(app):
        config = BaseTest._get_config(app)
        BaseLegacyBrokerTest._update_config(config)
        return config

    @classmethod
    def _clean_db_broker(cls):
        super()._clean_db()
        broker_app = cls.app.extensions['broker']
        broker_app.connection.drop_database(
            broker_app.connection.get_default_database().name)

    def setup_method(self, method):
        self._clean_db_broker()
        super().setup_method(method)


@pytest.mark.rabbit
class BaseRabbitBrokerTest(BaseTest):

    @staticmethod
    def _update_config(config):
        config['DISABLE_EVENTS'] = False
        config['DISABLE_RABBIT'] = False
        config['FF_ENABLE_RABBIT'] = True
        return config

    @staticmethod
    def _get_config(app):
        config = BaseTest._get_config(app)
        BaseRabbitBrokerTest._update_config(config)
        return config

    @classmethod
    def _clean_db_broker_rabbit(cls):
        super()._clean_db()
        broker_app = cls.app.extensions['broker_rabbit']
        broker_app.connection.drop_database(
            broker_app.connection.get_default_database().name)

    def _clean_rabbit(self):
        if pytest.config.getoption('runrabbit'):
            client_api_rabbit = client_rabbit(self.rabbit_url_for_test,
                                              self.user_test, self.password_test)
            queues = get_queues(client_api_rabbit)
            for queue in queues:
                delete_queue(client_api_rabbit, VHOST_TEST, queue)

    def setup_method(self, method):
        self.user_test = DEFAULT_USER_TEST
        self.password_test = DEFAULT_PASSWORD_TEST
        self.rabbit_url_for_test = RABBIT_URL_FOR_TEST
        self._clean_rabbit()
        self._clean_db_broker_rabbit()
        super().setup_method(method)


def pagination_testbed(user_req, route):
    """
    Generic pagination test (just need to populate 50 documents before)
    """
    r = user_req.get(route)
    assert r.status_code == 200
    assert r.data['_meta']['total'] == 50, ('Must be 50 elements in the'
                                            ' ressource to use the testbed !')
    items_len = len(r.data['_items'])
    if items_len < r.data['_meta']['per_page']:
        assert items_len == r.data['_meta']['total']
    else:
        assert items_len == r.data['_meta']['per_page']
    assert '_links' in r.data['_items'][0], r.data['_items'][0]
    assert 'self' in r.data['_items'][0]['_links'], r.data['_items'][0]
    assert 'parent' in r.data['_items'][0]['_links'], r.data['_items'][0]
    # Now let's test the pagination !

    def check_page(data, page, count, per_page, total):
        assert len(r.data['_items']) == count
        assert r.data['_meta']['page'] == page
        assert r.data['_meta']['per_page'] == per_page
        assert r.data['_meta']['total'] == total
    for page, count, per_page in [(1, 20, 20), (2, 20, 20), (3, 10, 20),
                                  (1, 50, 50), (1, 50, 100), (8, 1, 7)]:
        r = user_req.get('%s?page=%s&per_page=%s' % (route, page, per_page))
        assert r.status_code == 200, r
        check_page(r.data, page, count, per_page, 50)
    # Test links
    r = user_req.get('%s?page=1&per_page=100' % route)
    assert r.status_code == 200, r
    assert 'next' not in r.data['_links']
    assert 'previous' not in r.data['_links']
    assert 'self' in r.data['_links']
    r = user_req.get('%s?page=1&per_page=10' % route)
    assert r.status_code == 200, r
    assert 'next' in r.data['_links']
    assert 'previous' not in r.data['_links']
    assert 'self' in r.data['_links']
    r = user_req.get('%s?page=2&per_page=10' % route)
    assert r.status_code == 200, r
    assert 'next' in r.data['_links']
    assert 'previous' in r.data['_links']
    assert 'self' in r.data['_links']
    # Test bad pagination as well
    r = user_req.get('%s?page=2&per_page=60' % route)
    assert r.status_code == 404, r
    for page, per_page in [('', 20), (1, ''), ('nan', 20), (1, 'nan'),
                           (-1, 20), (1, -20)]:
        r = user_req.get('%s?page=%s&per_page=%s' % (route, page, per_page))
        assert r.status_code == 400, (page, per_page)


def assert_indexes(collection, expected, msg=None):
    """
    Provide abstraction between mongodb 2.6 and 3.2 index_information result.
    """

    try:
        indexes = collection.index_information()
    except OperationFailure:
        # If database doesn't exists, mongo 3.2 will throw an OperationFailure
        indexes = {}
    else:
        # mongo 3.2 add a `ns` field to the index description
        for index in indexes.values():
            index.pop('ns', None)
            index.pop('dropDups', None)
        # Since 3.0 dropDups is no longer available
        for index in expected.values():
            index.pop('dropDups', None)
    if msg:
        assert indexes == expected, msg
    else:
        assert indexes == expected
