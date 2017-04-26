import pytest
from datetime import datetime

from tests import common
from tests.test_auth import user

from sief.permissions import POLICIES as p
from services.fpr import fpr_query, default_fpr


class TestRole(common.BaseTest):

    def test_call_fpr(self):
        assert default_fpr.disabled == False
        assert default_fpr.testing_stub == True
        assert fpr_query("John", "Doe", datetime.utcnow()) == {'resultat': False, 'dossiers': []}

    def test_fpr_api(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do that
        route = '/recherche_fpr?prenom=John&nom=Doe&date_naissance=1985-08-15'
        payload = {}
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Add right permission and retry
        user.permissions.append(p.usager.consulter_fpr.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['resultat'] == {'resultat': False, 'dossiers': []}

    def test_fpr_bad_api(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions.append(p.usager.consulter_fpr.name)
        user.save()
        route = '/recherche_fpr'
        default = object()
        for args in (
                '?prenom=John&nom=Doe&date_naissance=',
                '?prenom=John&nom=Doe&date_naissance=not a date',
                '?prenom=John&nom=Doe',
                '?date_naissance=1985-08-07'):
            r = user_req.get(route + args)
            assert r.status_code == 400, args
