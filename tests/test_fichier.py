from tests import common
import pytest
from marshmallow import Schema
from io import BytesIO

from tests.test_auth import user

from sief.model.fichier import Fichier
from sief.permissions import POLICIES as p


@pytest.fixture
def fichier(request, user):
    fichier = Fichier(name='test.txt', author=user)
    fichier.data.put(b'1234567890' * 10, content_type='text/plain')
    fichier.save()
    return fichier


class TestFichier(common.BaseTest):

    def test_get_list(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/fichiers'
        # Without proper permissions, the user cannot list the fichiers but
        # can see the links
        r = user_req.get('/fichiers')
        assert r.status_code == 200, r
        # All user has the right to create a new file
        common.assert_response_contains_links(r, ('self', 'root', 'create'))
        assert '_items' not in r.data
        # Now provide the permission
        user.permissions = [p.fichier.gerer.name]
        user.save()
        r = user_req.get('/fichiers')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'root', 'create'))
        assert '_items' in r.data

    def test_get_single(self, user, fichier):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/fichiers/%s' % fichier.pk
        # Without proper permissions, the user cannot see metadata
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.fichier.gerer.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent', 'data', 'delete'))

    def test_delete(self, user, fichier):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/fichiers/%s' % fichier.pk
        r = user_req.delete(route)
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.fichier.gerer.name]
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 204, r
        # Cannot get the fichier anymore
        r = user_req.get(route)
        assert r.status_code == 404, r

    def test_get_data(self, user, fichier):
        # No need to be a registered user to access this route
        route = '/fichiers/%s' % fichier.pk
        r = self.client_app.get(route + '/data')
        assert r.status_code == 403, r
        # But you need a signature to access the route
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.fichier.gerer.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['name'] == fichier.name
        r = self.client_app.get(r.data['_links']['data'])
        assert r.status_code == 200, r
        assert r.data == fichier.data.read()

    def test_post(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        data = b"1234567890" * 10
        r = user_req.post('/fichiers', content_type='multipart/form-data',
                          data={'file': (BytesIO(data), 'fichier.txt')}, dump_data=False)
        assert r.status_code == 201, r
        common.assert_response_contains_links(r, ('self', 'data', 'parent'))
        r = self.client_app.get(r.data['_links']['data'])
        assert r.status_code == 200, r
        assert r.data == data

    def test_bad_post(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        data = b"1234567890" * 10
        r = user_req.post('/fichiers', content_type='multipart/form-data',
                          data={'no_file': (BytesIO(data), 'fichier.txt')}, dump_data=False)
        assert r.status_code == 400, r
        r = user_req.post('/fichiers', content_type='multipart/form-data',
                          data={'file': (BytesIO(data), '')}, dump_data=False)
        assert r.status_code == 400, r


class TestPaginationFichiers(common.BaseTest):

    def test_paginate_fichiers(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.fichier.gerer.name]
        user.save()
        # Start by creating a lot of users
        for i in range(50):
            fichier = Fichier(name='test.txt', author=user)
            fichier.data.put(b'1234567890' * 10, content_type='text/plain')
            fichier.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/fichiers')
