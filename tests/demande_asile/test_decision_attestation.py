from tests import common
import pytest
from datetime import datetime, timedelta

from tests.fixtures import *
from sief.permissions import POLICIES as p

class TestDecisionsAttestation(common.BaseTest):

    def test_add_decision(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)

        payload_refus = {'motif': "Do not deliver",
                         'type_document': 'CARTE_SEJOUR_TEMPORAIRE',
                         'sous_type_document': 'PREMIER_RENOUVELLEMENT',
                         'delivrance': False,
                         'date_decision': '2015-08-22T12:22:24+00:00'}

        route = 'demandes_asile/{}/decisions_attestations'.format(da_orientation.pk)
        r = user_req.post(route, data=payload_refus)
        assert r.status_code == 403
        user.permissions = [p.demande_asile.modifier.name]
        user.save()
        r = user_req.post(route, data=payload_refus)
        assert r.status_code == 201
        assert len(r.data['decisions_attestation']) == 1

    def test_no_motif_on_refus(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.modifier.name]
        user.save()

        payload_refus_no_motif = {'type_document': 'CARTE_SEJOUR_TEMPORAIRE',
                                  'sous_type_document': 'PREMIER_RENOUVELLEMENT',
                                  'delivrance': False,
                                  'date_decision': '2015-08-22T12:22:24+00:00'}

        route = 'demandes_asile/{}/decisions_attestations'.format(da_orientation.pk)
        r = user_req.post(route, data=payload_refus_no_motif)
        assert r.status_code == 400
        assert r.data == {'decisions_attestation': {'0': {'__all__': {'motif': "Le motif ne peut etre vide en cas de non délivrance de l'attestation"}}}}

        payload_refus_no_motif['motif'] = 'do not deliver'
        route = 'demandes_asile/{}/decisions_attestations'.format(da_orientation.pk)
        r = user_req.post(route, data=payload_refus_no_motif)
        assert r.status_code == 201

    def test_minimal_payload(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.modifier.name]
        user.save()

        payload_minimal = {'type_document': 'CARTE_SEJOUR_TEMPORAIRE',
                           'sous_type_document': 'PREMIER_RENOUVELLEMENT',
                           'date_decision': '2015-08-22T12:22:24+00:00'}

        route = 'demandes_asile/{}/decisions_attestations'.format(da_orientation.pk)
        r = user_req.post(route, data=payload_minimal)
        assert r.status_code == 201
        assert r.data['decisions_attestation'][0]['delivrance']

    def test_create_droit_refus(self, user_with_site_affecte, usager, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.modifier.name]
        user.save()

        payload_refus = {'motif': "Do not deliver",
                   'type_document': 'CARTE_SEJOUR_TEMPORAIRE',
                   'sous_type_document': 'PREMIER_RENOUVELLEMENT',
                   'delivrance': False,
                   'date_decision': '2015-08-22T12:22:24+00:00'}
        route = 'demandes_asile/{}/decisions_attestations'.format(da_orientation.pk)
        r = user_req.post(route, data=payload_refus)
        assert r.status_code == 201
        assert len(r.data['decisions_attestation']) == 1

        payload = {
            "usager": str(usager.pk),
            "type_document": 'CARTE_SEJOUR_TEMPORAIRE',
            "demande_origine": {'id': str(da_orientation.pk),
                                '_cls': da_orientation._class_name},
            "sous_type_document": 'PREMIER_RENOUVELLEMENT',
            "date_debut_validite": datetime.utcnow().isoformat(),
            "date_fin_validite": (datetime.utcnow() + timedelta(180)).isoformat(),
            "autorisation_travail": True,
            "pourcentage_duree_travail_autorise": 40,
            "date_decision_sur_attestation": "2015-08-22T12:22:24+00:00"
        }
        # Need permission do to it...
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 403, r
        # Provide it
        user.permissions = [p.demande_asile.modifier.name,
                            p.droit.creer.name]
        user.save()
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'] == ["Derniere decision sur attestation non favorable a la délivrance d'un droit"]
        payload['type_document'] = 'ATTESTATION_DEMANDE_ASILE'
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        payload_refus = {'motif': "deliver",
                   'type_document': 'CARTE_SEJOUR_TEMPORAIRE',
                   'sous_type_document': 'PREMIER_RENOUVELLEMENT',
                   'delivrance': True,
                   'date_decision': '2015-08-22T12:22:24+00:00'}
        r = user_req.post(route, data=payload_refus)
        assert r.status_code == 201
        assert len(r.data['decisions_attestation']) == 2

        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r

    def test_bad_payload(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.modifier.name]
        user.save()

        payload_minimal = {'type_document': 'CARTE_SEJOUR_TEMPORAIRE',
                           'sous_type_document': None}

        route = 'demandes_asile/{}/decisions_attestations'.format(da_orientation.pk)
        r = user_req.post(route, data=payload_minimal)
        assert r.status_code == 400
