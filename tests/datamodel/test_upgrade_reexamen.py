import pytest
from bson import ObjectId
from uuid import uuid4
from datetime import datetime

from .common import DatamodelBaseTest


BASE_DEMANDE_ASILE_DATA = {
    'usager': None
}

BASE_RECUEIL_DATA_DEMANDEUR_IDENTIFIE = {
    'usager_1': {'demandeur': True, 'identifiant_agdref': '0123456789'},
    'usager_2': {'demandeur': True, 'identifiant_agdref': '0123456789'},
    'enfants': [{'demandeur': True, 'identifiant_agdref': '0123456789'},
                {'demandeur': False}, {'demandeur': False},
                {'demandeur': True, 'identifiant_agdref': '0123456781'}],
    'statut': 'DEMANDEURS_IDENTIFIES'
}

BASE_RECUEIL_DATA_PA_REALISE = {
    'usager_1': {'demandeur': True},
    'usager_2': {'demandeur': True},
    'enfants': [{'demandeur': True},
                {'demandeur': False}, {'demandeur': False},
                {'demandeur': True}],
    'statut': 'PA_REALISE'
}

BASE_USAGER_DATA = {
    'nom': 'Goliath',
    'prenom': 'David',
    'identifiant_agdref': '0123456789'
}


def _insert_data(db, number_of_items):
    ids = {'usager_ids': [],
           'recueil_da_ids': [],
           'recueil_da_pa_realise_ids': [],
           'demande_asile_ids': []}
    for i in range(number_of_items):
        usager_data = BASE_USAGER_DATA.copy()
        ids['usager_ids'].append(db.usager.insert(usager_data))
        recueil_da_data = BASE_RECUEIL_DATA_DEMANDEUR_IDENTIFIE.copy()
        ids['recueil_da_ids'].append(db.recueil_d_a.insert(recueil_da_data))
        recueil_da_data = BASE_RECUEIL_DATA_PA_REALISE.copy()
        ids['recueil_da_pa_realise_ids'].append(db.recueil_d_a.insert(recueil_da_data))

    for usager in db.usager.find():
        da_data = BASE_DEMANDE_ASILE_DATA.copy()
        da_data['usager'] = usager['_id']
        ids['demande_asile_ids'].append(db.demande_asile.insert(da_data))
    return ids


class TestV1112(DatamodelBaseTest):

    BASE_VERSION = '1.1.13'
    TARGET_VERSION = '1.1.14'

    def test_apply_on_empty(self):
        self.patcher.manifest.initialize('1.1.13')
        self.patcher.apply_patch(self.patch)
        self.patcher.manifest.reload()
        assert self.patcher.manifest.version == '1.1.14'

    def test_basic_apply(self):
        self.patcher.manifest.initialize('1.1.13')
        ids = _insert_data(self.db, 1)
        self.patcher.apply_patch(self.patch)
        usager = self.db.usager.find_one(ids['usager_ids'][0])
        assert usager == {
            '_id': ids['usager_ids'][0],
            'nom': 'Goliath',
            'prenom': 'David',
            'identifiant_agdref': '0123456789',
            'identifiants_eurodac': ['0123456789']
        }
        recueil = self.db.recueil_d_a.find_one(ids['recueil_da_ids'][0])
        assert recueil == {
            '_id': ids['recueil_da_ids'][0],
            'enfants': [{'demandeur': True, 'identifiant_agdref': '0123456789', 'identifiant_eurodac': '0123456789', 'type_demande': 'PREMIERE_DEMANDE_ASILE', 'identite_approchante_select': True},
                        {'demandeur': False, 'identite_approchante_select': True}, {
                            'demandeur': False, 'identite_approchante_select': True},
                        {'demandeur': True, 'identifiant_agdref': '0123456781', 'identifiant_eurodac': '0123456781', 'type_demande': 'PREMIERE_DEMANDE_ASILE', 'identite_approchante_select': True}],
            'usager_1': {'demandeur': True, 'identifiant_agdref': '0123456789', 'identifiant_eurodac': '0123456789', 'type_demande': 'PREMIERE_DEMANDE_ASILE', 'identite_approchante_select': True},
            'usager_2': {'demandeur': True, 'identifiant_agdref': '0123456789', 'identifiant_eurodac': '0123456789', 'type_demande': 'PREMIERE_DEMANDE_ASILE', 'identite_approchante_select': True},
            'statut': 'DEMANDEURS_IDENTIFIES'}

        recueil = self.db.recueil_d_a.find_one(ids['recueil_da_pa_realise_ids'][0])
        assert recueil == {
            '_id': ids['recueil_da_pa_realise_ids'][0],
            'usager_1': {'demandeur': True, 'type_demande': 'PREMIERE_DEMANDE_ASILE'},
            'usager_2': {'demandeur': True, 'type_demande': 'PREMIERE_DEMANDE_ASILE'},
            'enfants': [{'demandeur': True, 'type_demande': 'PREMIERE_DEMANDE_ASILE'},
                        {'demandeur': False}, {'demandeur': False},
                        {'demandeur': True, 'type_demande': 'PREMIERE_DEMANDE_ASILE'}],
            'statut': 'PA_REALISE'
        }

        da = self.db.demande_asile.find_one(ids['demande_asile_ids'][0])
        assert da == {
            '_id': ids['demande_asile_ids'][0],
            'usager': ids['usager_ids'][0],
            'usager_identifiant_eurodac': '0123456789',
            'type_demande': 'PREMIERE_DEMANDE_ASILE'
        }

    def test_apply_on_multi(self):
        self.patcher.manifest.initialize('1.1.13')
        ids = _insert_data(self.db, 100)
        self.patcher.apply_patch(self.patch)

        usagers = self.db.usager.find()
        assert usagers.count() == 100
        for usager in usagers:
            assert 'identifiants_eurodac' in usager
            assert usager['identifiants_eurodac'][0] == usager['identifiant_agdref']

        demande_asiles = self.db.demande_asile.find()
        assert demande_asiles.count() == 100
        for demande_asile in demande_asiles:
            assert 'usager_identifiant_eurodac' in demande_asile
            assert demande_asile['type_demande'] == 'PREMIERE_DEMANDE_ASILE'

        recueil_das = self.db.recueil_d_a.find({'statut': 'DEMANDEURS_IDENTIFIES'})
        assert recueil_das.count() == 100
        for recueil_da in recueil_das:
            assert recueil_da['usager_1']['identifiant_eurodac'] == recueil_da[
                'usager_1']['identifiant_agdref']
            assert recueil_da['usager_1']['type_demande'] == 'PREMIERE_DEMANDE_ASILE'

            assert recueil_da['usager_2']['identifiant_eurodac'] == recueil_da[
                'usager_2']['identifiant_agdref']
            assert recueil_da['usager_2']['type_demande'] == 'PREMIERE_DEMANDE_ASILE'

            for enfant in recueil_da['enfants']:
                if enfant['demandeur']:
                    assert enfant['identifiant_eurodac'] == enfant['identifiant_agdref']
                    assert enfant['type_demande'] == 'PREMIERE_DEMANDE_ASILE'
                else:
                    assert 'identifiant_eurodac' not in enfant
                    assert 'type_demande' not in enfant

    def test_multiple_apply(self):
        self.patcher.manifest.initialize('1.1.13')
        ids = _insert_data(self.db, 100)
        self.patcher.apply_patch(self.patch)
        usager = self.db.usager.find_one(ids['usager_ids'][0])
        assert usager == {
            '_id': ids['usager_ids'][0],
            'nom': 'Goliath',
            'prenom': 'David',
            'identifiant_agdref': '0123456789',
            'identifiants_eurodac': ['0123456789']
        }
        ids = _insert_data(self.db, 100)
        self.patcher.apply_patch(self.patch)
