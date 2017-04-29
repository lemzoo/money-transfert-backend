import pytest

from tests import common
from sief.model.utilisateur import Utilisateur


CORS_HEADERS = [
    'Access-Control-Allow-Credentials',
    'Access-Control-Allow-Headers',
    'Access-Control-Allow-Methods',
    'Access-Control-Allow-Origin',
    'Access-Control-Allow-Max-Age'
]


class TestCORS(common.BaseTest):

    def test_no_origin(self):
        # No origin, no access
        r = self.client_app.options('/moi')
        assert r.status_code == 200
        for cors_header in CORS_HEADERS:
            assert cors_header not in r.headers
        # Bad origin, no access
        r = self.client_app.options('/moi', headers={'Origin': 'http://bad-origin.org'})
        assert r.status_code == 200
        for cors_header in CORS_HEADERS:
            assert cors_header not in r.headers

    def test_expose(self):
        origin = self.app.config['CORS_ORIGINS'][0]
        # Just origin should display only expose headers
        r = self.client_app.options('/moi', headers={'Origin': origin})
        assert r.status_code == 200
        assert r.headers.get('Access-Control-Allow-Origin', '<no_value>') == origin
        assert 'Access-Control-Expose-Headers' in r.headers
        assert 'Access-Control-Allow-Credentials' in r.headers

    def test_allow(self):
        headers = {
            'Origin': self.app.config['CORS_ORIGINS'][0],
            'Access-Control-Request-Headers': 'accept, cache-control, authorization',
            'Access-Control-Request-Method': 'GET'
        }
        r = self.client_app.options('/moi', headers=headers)
        assert r.status_code == 200
        assert 'Access-Control-Allow-Methods' in r.headers
        assert 'GET' in r.headers['Access-Control-Allow-Methods'].split(', ')
