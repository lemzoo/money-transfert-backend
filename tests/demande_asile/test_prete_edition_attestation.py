import pytest
from datetime import datetime

from tests import common
from tests.fixtures import *

from sief.model.recueil_da import Refus
from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p
from sief.events import EVENTS as e
from tests.connector.common import BrokerBox


@pytest.fixture
def da_prete_ea(request, da_orientation):
    return da_orientation


@pytest.fixture
def da_prete_ea_reexamen(request, da_orientation):
    da_orientation.type_demande = 'REEXAMEN'
    da_orientation.numero_reexamen = 1
    da_orientation.save()
    return da_orientation


class TestDemandeAsileOrientation(common.BaseTest):

    def test_links_single(self, user_with_site_affecte, da_prete_ea):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_prete_ea.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions.append(p.demande_asile.editer_attestation.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'editer_attestation'])

    def test_editer_attestation_ofpra(self, user_with_site_affecte, da_prete_ea):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_prete_ea.procedure.type = 'NORMALE'
        da_prete_ea.procedure.motif_qualification = 'NECD'
        da_prete_ea.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00",
                   'date_decision_sur_attestation': "2015-09-22T00:00:03+00:00"}
        # Need permission...
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # ...provide them
        user.permissions.append(p.demande_asile.editer_attestation.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        # We must have switch to new state
        assert r.data['statut'] == 'EN_ATTENTE_INTRODUCTION_OFPRA'
        # Should provide the created droit as well
        assert r.data.get('droit')
        assert r.data['droit']['prefecture_rattachee'][
            'id'] == str(da_prete_ea.prefecture_rattachee.id)
        assert r.data['droit']['date_debut_validite'] == "2015-09-22T00:00:01+00:00"
        assert r.data['droit']['date_fin_validite'] == "2015-09-22T00:00:02+00:00"
        assert r.data['droit']['date_decision_sur_attestation'] == "2015-09-22T00:00:03+00:00"

    def test_editer_attestation_dublin(self, user_with_site_affecte, da_prete_ea):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        da_prete_ea.procedure.type = 'DUBLIN'
        da_prete_ea.procedure.motif_qualification = 'BDS'
        da_prete_ea.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea.pk
        # Need permission...
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # ...provide them
        user.permissions.append(p.demande_asile.editer_attestation.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        # We must have switch to new state
        assert r.data['statut'] == 'EN_COURS_PROCEDURE_DUBLIN'
        # Should provide the created droit as well
        assert r.data.get('droit')
        assert r.data['droit']['prefecture_rattachee'][
            'id'] == str(da_prete_ea.prefecture_rattachee.id)
        assert r.data['droit']['date_debut_validite'] == "2015-09-22T00:00:01+00:00"
        assert r.data['droit']['date_fin_validite'] == "2015-09-22T00:00:02+00:00"
        assert 'date_decision_sur_attestation' not in r.data['droit']

    def test_orientation_update(self, user_with_site_affecte, da_prete_ea):
        user = user_with_site_affecte
        # Orientation stuff can still be modified
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        route = '/demandes_asile/%s/orientation' % da_prete_ea.pk
        payload = {
            'hebergement': {
                'date_sortie_hebergement': "2015-06-10T03:12:58+00:00"
            },
            'ada': {
                'date_ouverture': "2015-06-10T03:12:58+00:00",
                'montant': 1000.42
            },
            'agent_orientation': 'dn@-agent-007',
            'date_orientation': '2015-06-11T12:22:37+00:00'
        }
        # POST is no longer allowed
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['agent_orientation'] == 'dn@-agent-007'
        assert r.data['date_orientation'] == '2015-06-11T12:22:37+00:00'
        assert 'date_sortie_hebergement' in r.data.get('hebergement', {})
        assert 'ada' in r.data and r.data['ada']['montant'] == 1000.42


class TestSitesRattachesDemandeAsile(common.BaseLegacyBrokerTest):

    def test_prefecture_rattachee(self, user, site, da_prete_ea):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check on the site
        assert site != da_prete_ea.prefecture_rattachee

        def _test_view(size):
            r = user_req.get('/demandes_asile')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == size
            if len(r.data['_items']) == 1:
                route = r.data['_items'][0]['_links']['self']
                r = user_req.get(route)
                assert r.status_code == 200, r
                assert r.data['id'] == str(da_prete_ea.id)
        _test_view(0)
        user.test_set_accreditation(site_affecte=da_prete_ea.structure_premier_accueil)
        user.save()
        _test_view(0)
        user.test_set_accreditation(site_affecte=da_prete_ea.structure_guichet_unique.autorite_rattachement)
        user.save()
        _test_view(3)
        user.test_set_accreditation(site_affecte=da_prete_ea.structure_guichet_unique)
        user.save()
        _test_view(3)
        user.test_set_accreditation(site_affecte=None)
        user.permissions.append(p.demande_asile.prefecture_rattachee.sans_limite.name)
        user.save()
        _test_view(3)

    def test_prefecture_rattachee_route(self, user, site, da_prete_ea):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check
        assert site != da_prete_ea.prefecture_rattachee
        # Cannot see this recueil...
        r = user_req.get('/demandes_asile/%s' % da_prete_ea.id)
        assert r.status_code == 403, r
        # ...but can ask who's it belong to
        r = user_req.get('/demandes_asile/%s/prefecture_rattachee' % da_prete_ea.id)
        assert r.status_code == 200, r
        assert r.data.get('prefecture_rattachee', {}).get(
            'id', '<missing>') == str(da_prete_ea.prefecture_rattachee.id)

    def test_flux_en_attente_introductio_ofpra(self, user_with_site_affecte, site, da_prete_ea):
        tester = BrokerBox(
            self.app, e.demande_asile.en_attente_ofpra.name, 'inerec-demande_asile.en_attente_ofpra')

        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['droit']
        msgs = tester.get_messages()
        assert len(msgs) == 1
        assert msgs[0].context['demande_asile']['numero_reexamen'] == 0


class TestReexamenAttestionEdition(common.BaseLegacyBrokerTest):

    def test_edition_attestation(self, user_with_site_affecte, site, da_prete_ea_reexamen):
        user = user_with_site_affecte

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea_reexamen.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['droit']

    def test_edition_attestion_da_from_recueil(self, user_with_site_affecte, site, exploite_pret_reexamen):
        user = user_with_site_affecte

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        exploite_pret_reexamen.save()
        r = user_req.post('/recueils_da/%s/exploite' % exploite_pret_reexamen.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EXPLOITE'
        exploite_pret_reexamen.reload()
        route = '/demandes_asile/%s/attestations' % exploite_pret_reexamen.usager_1.demande_asile_resultante.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['droit']

    def test_refus_edition_attestion_da_from_recueil(self, user_with_site_affecte, site, exploite_pret_reexamen):
        user = user_with_site_affecte

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        exploite_pret_reexamen.usager_1.refus = Refus(motif="why not?")
        exploite_pret_reexamen.save()
        r = user_req.post('/recueils_da/%s/exploite' % exploite_pret_reexamen.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EXPLOITE'
        assert r.data['usager_1']['refus']['motif'] == "why not?"
        exploite_pret_reexamen.reload()
        assert exploite_pret_reexamen.usager_1.demande_asile_resultante.decisions_attestation[
            -1].agent_createur == user
        route = '/demandes_asile/%s/attestations' % exploite_pret_reexamen.usager_1.demande_asile_resultante.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'] == [
            "Impossible d'éditer une attestation au statut EN_ATTENTE_INTRODUCTION_OFPRA"]

    def test_flux_en_attente_introductio_ofpra_demande_exterieur(self, user_with_site_affecte, site, da_prete_ea_reexamen):
        tester = BrokerBox(
            self.app, e.demande_asile.en_attente_ofpra.name, 'inerec-demande_asile.en_attente_ofpra')

        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea_reexamen.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['droit']
        msgs = tester.get_messages()
        assert len(msgs) == 1
        assert msgs[0].context['demande_asile'][
            'numero_reexamen'] == da_prete_ea_reexamen.numero_reexamen
        assert 'identifiant_inerec' not in msgs[0].context['demande_asile']

    def test_flux_en_attente_introductio_ofpra_demande_interne(self, user_with_site_affecte, site, da_decision_def, da_orientation_payload):
        tester = BrokerBox(
            self.app, e.demande_asile.en_attente_ofpra.name, 'inerec-demande_asile.en_attente_ofpra')
        da_orientation_payload['type_demande'] = 'REEXAMEN'
        da_orientation_payload['numero_reexamen'] = 1

        da_prete_ea_reexamen = DemandeAsile(**da_orientation_payload)
        da_prete_ea_reexamen.usager = da_decision_def.usager
        da_prete_ea_reexamen.save()

        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea_reexamen.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert r.data['droit']
        msgs = tester.get_messages()
        assert len(msgs) == 1
        assert msgs[0].context['demande_asile'][
            'numero_reexamen'] == da_prete_ea_reexamen.numero_reexamen
        assert msgs[0].context['demande_asile'][
            'identifiant_inerec'] == da_decision_def.identifiant_inerec
