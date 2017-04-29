import pytest
from bson import ObjectId
from uuid import uuid4
from datetime import datetime

from tests.datamodel.common import DatamodelBaseTest


BASE_RECUEIL_DATA = {
    'usager_1': {'demandeur': True, 'type_demande': 'REEXAMEN'},
    'usager_2': {'demandeur': True, 'type_demande': 'REEXAMEN', 'numero_reexamen': 2},
    'enfants': [{'demandeur': False},
                {'demandeur': True, 'type_demande': 'REEXAMEN'},
                {'demandeur': False},
                {'demandeur': True, 'type_demande': 'PREMIERE_DEMANDE_ASILE'}]
}


def _insert_data(db, number_of_data=1):

    for _ in range(0, number_of_data):
        db.recueil_d_a.insert(BASE_RECUEIL_DATA)


class TestV1117(DatamodelBaseTest):

    BASE_VERSION = '1.1.16'
    TARGET_VERSION = '1.1.17'

    def test_apply_on_empty(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        self.patcher.apply_patch(self.patch)
        self.patcher.manifest.reload()
        assert self.patcher.manifest.version == self.TARGET_VERSION

    def test_basic_apply(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        ids = _insert_data(self.db)
        self.patcher.apply_patch(self.patch)
        self.patcher.manifest.reload()
        assert self.patcher.manifest.version == self.TARGET_VERSION

        recueil_da = self.db.recueil_d_a.find()[0]
        assert recueil_da['usager_1']['numero_reexamen'] == 1
        assert recueil_da['usager_2']['numero_reexamen'] == 2
        assert 'numero_reexamen' not in recueil_da['enfants'][0]
        assert 'numero_reexamen' not in recueil_da['enfants'][2]
        assert 'numero_reexamen' not in recueil_da['enfants'][3]
        assert recueil_da['enfants'][1]['numero_reexamen'] == 1
