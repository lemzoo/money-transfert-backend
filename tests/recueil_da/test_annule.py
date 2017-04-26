import pytest
from datetime import datetime

from tests import common
from tests.fixtures import *

from sief.permissions import POLICIES as p
from sief.model.recueil_da import ALLOWED_MOTIFS_ANNULATION

@pytest.fixture
def annule(request, user, pa_realise):
    pa_realise.controller.annuler(user, 'AUTRE')
    pa_realise.save()
    return pa_realise

def cancel_recueil_with_reason(self, user, pa_realise, motif):
    user_req = self.make_auth_request(user, user._raw_password)
    user.permissions = [p.recueil_da.modifier_pa_realise.name]
    user.save()
    route = '/recueils_da/%s/annule' % pa_realise.pk
    return user_req.post(route, data={'motif': motif})

class TestRecueilDAAnnule(common.BaseTest):

    def test_get_annule(self, user, annule):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/recueils_da')
        assert r.status_code == 403, r
        route = '/recueils_da/%s' % annule.pk
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

    def test_get_links(self, user, annule):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % annule.pk
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent'))
        user.permissions.append(p.historique.voir.name)
        user.permissions.append(p.recueil_da.purger.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent', 'history', 'purger'))

    def test_cant_delete(self, user, annule):
        # Only brouillons can be deleted
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % annule.pk
        user.permissions = [p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 400, r

    def test_switch_to_purge(self, user, annule):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.purger.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.post('/recueils_da/%s/purge' % annule.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'PURGE'

    def test_invalid_switches(self, user, annule):
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
        route = '/recueils_da/%s' % annule.pk
        from tests.test_rendez_vous import add_free_creneaux
        creneaux = add_free_creneaux(4, annule.structure_accueil.guichets_uniques[0])

        r = user_req.put(
            route + '/pa_realise', data={'creneaux': [creneaux[0]['id'], creneaux[1]['id']]})
        assert r.status_code == 400, r
        for action in ['demandeurs_identifies', 'exploite']:
            r = user_req.post(route + '/' + action)
            assert r.status_code == 400, r

    @pytest.mark.parametrize("motif_annulation, expected", [
        ("NON_PRESENTATION_RDV", 200),
        ("BESOIN_INFORMATION_COMPLEMENTAIRE", 200),
        ("INTERPRETE_NON_DISPONIBLE", 200),
        ("RETARD_PRESENTATION_DEMANDEUR", 200),
        ("PANNE_INFORMATIQUE", 200),
        ("FAIT_EXTERIEUR", 200),
        ("ECHEC_PRISE_EMPREINTE", 200),
        ("AUTRE", 200),
    ])
    def test_motif_annulation_allowed_values(self, motif_annulation, expected, user_with_site_affecte, pa_realise):
        result = cancel_recueil_with_reason(self, user_with_site_affecte, pa_realise, motif_annulation)
        assert result.status_code == expected, result
        assert result.data['motif_annulation'] == motif_annulation
