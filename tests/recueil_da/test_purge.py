import pytest
from datetime import datetime

from tests import common
from tests.fixtures import *

from sief.model.recueil_da import RecueilDA
from sief.permissions import POLICIES as p


@pytest.fixture
def purge(request, annule):
    annule.controller.purger()
    annule.save()
    return annule


class TestRecueilDAAnnule(common.BaseTest):

    def test_get_annule(self, user, purge):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/recueils_da')
        assert r.status_code == 403, r
        route = '/recueils_da/%s' % purge.pk
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        r = user_req.get(route)
        assert r.status_code == 200, r

    def test_get_links(self, user, purge):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % purge.pk
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent'))
        user.permissions.append(p.historique.voir.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent', 'history'))

    def test_cant_delete(self, user, purge):
        # Only brouillons can be deleted
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % purge.pk
        user.permissions = [p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 400, r

    def test_invalid_switches(self, user, purge):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.recueil_da.modifier_exploite.name,
                            p.recueil_da.purger.name]
        user.save()
        route = '/recueils_da/%s' % purge.pk
        from tests.test_rendez_vous import add_free_creneaux
        creneaux = add_free_creneaux(
            4, purge.structure_accueil.guichets_uniques[0])

        r = user_req.put(
            route + '/pa_realise', data={'creneaux': [creneaux[0]['id'], creneaux[1]['id']]})
        assert r.status_code == 400, r
        for action in ['demandeurs_identifies', 'exploite', 'purge', 'annule']:
            r = user_req.post(route + '/' + action)
            assert r.status_code == 400, r
