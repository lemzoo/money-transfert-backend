import pytest
from datetime import datetime, timedelta

from tests import common
from tests.fixtures import *
from tests.test_auth import user
from sief.model.impression import ImpressionDocument

from sief.permissions import POLICIES as p


class TestImpression(common.BaseTest):

    def test_links_list(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, ]
        user.save()
        r = user_req.get('/impression/id')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self'])

    def test_id(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, ]
        user.save()
        r = user_req.get('/impression/id')
        assert r.status_code == 200, r
        assert r.data['compteur_journalier'] == 1
        r = user_req.get('/impression/id')
        assert r.data['compteur_journalier'] == 2

    def test_day_change(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, ]
        user.save()
        r = user_req.get('/impression/id')
        assert r.status_code == 200, r
        assert r.data['compteur_journalier'] == 1
        r = user_req.get('/impression/id')
        i = ImpressionDocument.objects().first()
        i.date_derniere_demande -= timedelta(days=2)
        i.save()
        r = user_req.get('/impression/id')
        assert r.data['compteur_journalier'] == 1
