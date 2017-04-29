import requests
from functools import partial

from connector.tools import request_with_broker_retry


class ConnectorException(Exception):

    def __init__(self, errcode, value):
        super().__init__()
        self.value = value
        self.errcode = errcode

    def __str__(self):
        return "%s : %s" % (self.errcode, self.value)


class Connectors:

    def init_app(self, app):
        app.config.setdefault('CONNECTORS_API_PREFIX', '/connectors')
        app.config.setdefault('DISABLE_CONNECTORS', False)
        app.config.setdefault('CONNECTORS_DEBUG', False)
        self.disabled = app.config['DISABLE_CONNECTORS']
        self.prefix = app.config['CONNECTORS_API_PREFIX']
        self.server = app.config['BACKEND_URL']

        if not self.disabled:
            from connector.agdref import init_connector_agdref
            from connector.dna import init_connector_dna
            init_connector_agdref(app)
            init_connector_dna(app)

        if app.config['CONNECTORS_DEBUG']:
            from connector.debugger import connector_debug
            app.register_blueprint(connector_debug, url_prefix=self.prefix)


class BackendRequest:

    class TokenAuth(requests.auth.AuthBase):

        def __init__(self, token):
            self.token = token

        def __call__(self):
            return 'Token %s' % self.token

    def __init__(self, domain, url_prefix='', auth=None, token=None, requests=requests,
                 http_proxy=None, https_proxy=None, timeout=None):
        if not auth and not token:
            raise RuntimeError("BackendRequest requires auth or token")
        self.domain = domain
        self.url_prefix = url_prefix
        kwargs = {
            'timeout': timeout,
            'proxies': {'http': http_proxy, 'https': https_proxy},
            'auth': auth
        }
        if token:
            kwargs['auth'] = self.TokenAuth(token)
        self.request = request_with_broker_retry(
            partial(requests.request, **kwargs))

    def _cook_url(self, url):
        if not url.startswith('/'):
            url = '/' + url
        if not url.startswith(self.url_prefix):
            url = self.url_prefix + url
        return self.domain + url

    def get(self, url, *args, **kwargs):
        return self.request('GET', self._cook_url(url), *args, **kwargs)

    def post(self, url, *args, **kwargs):
        return self.request('POST', self._cook_url(url), *args, **kwargs)

    def patch(self, url, *args, **kwargs):
        return self.request('PATCH', self._cook_url(url), *args, **kwargs)

    def put(self, url, *args, **kwargs):
        return self.request('PUT', self._cook_url(url), *args, **kwargs)

    def delete(self, url, *args, **kwargs):
        return self.request('DELETE', self._cook_url(url), *args, **kwargs)


connectors_config = Connectors()
init_connectors = connectors_config.init_app
