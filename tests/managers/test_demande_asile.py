from tests import common
from tests.fixtures import *
from tests.test_droit import support_payload
from sief.permissions import POLICIES as p
from sief.model import DemandeAsile
from sief.managers.demande_asile_manager import (annulation_deuxieme_renouvellement,
                                                 remove_duplicate_decision_definitive,
                                                 export_demande_reexamen,
                                                 export_refus_prise_empreinte)

from datetime import datetime, timedelta
import os
from filecmp import cmp


def build_payload():
    return {
        'nature': 'TF',
        'date': datetime.utcnow().isoformat(),
        'date_premier_accord': datetime.utcnow().isoformat(),
        'date_notification': datetime.utcnow().isoformat(),
        'entite': 'CNDA',
        'numero_skipper': 'Skiango'
    }


def insert_duplicate_decision_definitive(user_req, da_decision_def):
    route = '/demandes_asile/%s/decisions_definitives' % da_decision_def.pk
    payload = build_payload()
    r = user_req.post(route, data=payload)
    assert r.status_code == 201, r
    r = user_req.post(route, data=payload)
    assert r.status_code == 201, r


class TestDemandeAsileDecisionDefinitive(common.BaseTest):

    def test_manager_decision_definitive(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, p.demande_asile.modifier_ofpra.name]
        user.save()
        payload = {
            'nature': 'TF',
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'CNDA',
            'numero_skipper': 'Skiango'
        }
        insert_duplicate_decision_definitive(user_req, da_decision_def)
        insert_duplicate_decision_definitive(user_req, da_decision_def)

        if os.path.isfile('./temporary'):
            os.remove('./temporary')
        with open('./temporary', 'x') as file:
            file.write('demande_asile\n')
            file.write(str(da_decision_def.pk))
            file.write('\n')
            file.close()
        remove_duplicate_decision_definitive('./temporary')
        assert cmp('./temporary', './temporary.output')
        if os.path.isfile('./temporary'):
            os.remove('./temporary')
        if os.path.isfile('./temporary.output'):
            os.remove('./temporary.output')

        route = '/demandes_asile/%s/decisions_definitives' % da_decision_def.pk

        r = user_req.post(route, data=build_payload())
        assert r.status_code == 201, r
        assert len(r.data['decisions_definitives']) == 4

    def test_manager_annulation_deuxieme_renouvellement_multi_renouvellement(self, user_with_site_affecte, usager, da_orientation, support_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {
            "usager": str(usager.pk),
            "type_document": 'CARTE_SEJOUR_TEMPORAIRE',
            "demande_origine": {'id': str(da_orientation.pk),
                                '_cls': da_orientation._class_name},
            "sous_type_document": 'EN_RENOUVELLEMENT',
            "date_debut_validite": datetime.utcnow().isoformat(),
            "date_fin_validite": (datetime.utcnow() + timedelta(180)).isoformat(),
            "autorisation_travail": True,
            "pourcentage_duree_travail_autorise": 40,
            "date_decision_sur_attestation": "2015-08-22T12:22:24+00:00"
        }
        user.permissions = [p.droit.creer.name, p.droit.support.creer.name, p.droit.voir.name]

        user.save()
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        droit_id_1 = r.data['id']
        route = '/droits/%s/supports' % droit_id_1
        r = user_req.post(route, data=support_payload)
        assert r.status_code == 200, r
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        droit_id = r.data['id']
        route = '/droits/%s/supports' % droit_id
        r = user_req.post(route, data=support_payload)
        assert r.status_code == 200, r
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        droit_id = r.data['id']
        route = '/droits/%s/supports' % droit_id
        r = user_req.post(route, data=support_payload)
        assert r.status_code == 200, r
        da_orientation.renouvellement_attestation = 3
        da_orientation.save()
        if os.path.isfile('./temporary'):
            os.remove('./temporary')
        if os.path.isfile('./temporary.output.real'):
            os.remove('./temporary.output.real')
        with open('./temporary', 'x') as file:
            file.write('demande_asile\n')
            file.write(str(da_orientation.pk))
        with open('./temporary.output.real', 'x') as file:
            file.write("demande_asile\n")
            file.write("%s : done\n" % str(da_orientation.pk))
        annulation_deuxieme_renouvellement('./temporary')
        assert cmp('./temporary.output.real', './temporary.output')
        if os.path.isfile('./temporary'):
            os.remove('./temporary')
        if os.path.isfile('./temporary.output'):
            os.remove('./temporary.output')
        if os.path.isfile('./temporary.err'):
            os.remove('./temporary.err')
        if os.path.isfile('./temporary.output.real'):
            os.remove('./temporary.output.real')

        route = '/droits/%s' % droit_id_1
        r = user_req.get(route)
        assert r.data['supports'][-1].get('motif_annulation') is None
        route = '/droits/%s' % droit_id
        r = user_req.get(route)
        assert r.data['supports'][-1]['motif_annulation'] == 'DEGRADATION'

        da_orientation.reload()
        assert da_orientation.renouvellement_attestation == 3


class TestManagerExportDemandeAsile(common.BaseTest):

    def _init_data(self, da_orientation_payload):
        da_orientation_payload['procedure']['motif_qualification'] = 'REEX'
        da_orientation_payload['procedure']['type'] = 'ACCELEREE'
        das = DemandeAsile.objects()
        for da in das:
            da.delete()
        for i in range(0, 25):
            da = DemandeAsile(**da_orientation_payload)
            da.usager.identifiant_dna = format(i, '08d')
            da.usager.save()
            da.save()
        da_orientation_payload['procedure']['motif_qualification'] = 'EMPR'
        for i in range(0, 25):
            da = DemandeAsile(**da_orientation_payload)
            da.usager.identifiant_dna = format(i, '08d')
            da.usager.save()
            da.save()

    def test_export_demande_reexamen(self, da_orientation_payload):
        self._init_data(da_orientation_payload)
        export_demande_reexamen('./test_export_reexamen.csv')
        with open('./test_export_reexamen.csv') as file:
            lines = [1 for l in file]
            assert sum(lines) == 26
        if os.path.isfile('./test_export_reexamen.csv'):
            os.remove('./test_export_reexamen.csv')

    def test_export_refus_prise_empreinte(self, da_orientation_payload):
        self._init_data(da_orientation_payload)
        export_refus_prise_empreinte('./test_export_refus.csv')
        with open('./test_export_refus.csv') as file:
            lines = [1 for l in file]
            assert sum(lines) == 26
        if os.path.isfile('./test_export_refus.csv'):
            os.remove('./test_export_refus.csv')
