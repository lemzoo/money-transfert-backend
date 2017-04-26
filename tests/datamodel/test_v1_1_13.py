import random
import json

from datetime import datetime
from .common import DatamodelBaseTest


def generate_requalification(index, type=None):
    random_type = random.choice(['NORMALE', 'ACCELEREE', 'DUBLIN'])
    return {
        "date": 'fakeDate' + str(index),
        "date_notification": 'fakeDateNotification' + str(index),
        "ancien_type": random_type if type is None else type,
        "ancien_acteur": "PREFECTURE",
        "ancien_motif_qualification": "PNOR"
    }


def generate_demande_asile(has_requalifications=True):
    demande_asile = {
        "_id": 1,
        "procedure": {"requalifications": [generate_requalification(i) for i in range(0, 4)]},
        "date_decision_sur_attestation": FAKE_DATE,
    }

    if not has_requalifications:
        demande_asile['procedure'].pop('requalifications')

    return demande_asile


def generate_demande_asile_history():
    return {
        "_id": 1,
        "version": 2,
        "origin": 1,
        "action": "CREATE",
        "date": 'fakeDateDemandeAsileHistory',
        "content": '{\"_id\": 1, \"doc_version\": 2, \"procedure\": {\"type\": \"NORMALE\", \"motif_qualification\": \"PNOR\", \"acteur\": \"GUICHET_UNIQUE\", \"requalifications\": [{\"ancien_type\":\"DUBLIN\",\"date_notification\":\"fakeDateNotification0\",\"ancien_motif_qualification\":\"PNOR\",\"date\":\"fakeDate0\",\"ancien_acteur\":\"PREFECTURE\"},{\"ancien_type\":\"ACCELEREE\",\"date_notification\":\"fakeDateNotification1\",\"ancien_motif_qualification\":\"PNOR\",\"date\":\"fakeDate1\",\"ancien_acteur\":\"PREFECTURE\"},{\"ancien_type\":\"ACCELEREE\",\"date_notification\":\"fakeDateNotification2\",\"ancien_motif_qualification\":\"PNOR\",\"date\":\"fakeDate2\",\"ancien_acteur\":\"PREFECTURE\"},{\"ancien_type\":\"DUBLIN\",\"date_notification\":\"fakeDateNotification3\",\"ancien_motif_qualification\":\"PNOR\",\"date\":\"fakeDate3\",\"ancien_acteur\":\"PREFECTURE\"}]}, \"date_decision_sur_attestation\": {\"$date\": ' + str(FAKE_DATE) + '}}',
    }


# 2000-01-01T00:00:00
FAKE_DATE = 946681200000


def insert_demande_asile(db):
    demande_asile_id = db.demande_asile.insert(generate_demande_asile())
    db.demande_asile.history.insert(generate_demande_asile_history())
    return demande_asile_id


class TestV1113(DatamodelBaseTest):

    BASE_VERSION = '1.1.12'
    TARGET_VERSION = '1.1.13'


class TestCheckPatchExists(TestV1113):

    def test_patch_1113_exists(self):
        self.patcher.manifest.initialize('1.1.12')
        self.patcher.apply_patch(self.patch)
        self.patcher.manifest.reload()
        assert self.patcher.manifest.version == '1.1.13'


class TestWhenProcedureHasNoRequalifications(TestV1113):

    def test_adds_a_date_notification_when_procedure_has_none(self):
        # Given
        self.patcher.manifest.initialize('1.1.12')
        demande_asile_id = self.db.demande_asile.insert(generate_demande_asile(has_requalifications=False))

        # When
        self.patcher.apply_patch(self.patch)

        # Then
        demande_asile = self.db.demande_asile.find_one(demande_asile_id)
        assert 'date_notification' in demande_asile['procedure']

    def test_initializes_date_notification_to_date_decision_sur_attestation(self):
        # Given
        self.patcher.manifest.initialize('1.1.12')
        demande_asile_id = self.db.demande_asile.insert(generate_demande_asile(has_requalifications=False))

        # When
        self.patcher.apply_patch(self.patch)

        # Then
        demande_asile = self.db.demande_asile.find_one(demande_asile_id)
        assert demande_asile['procedure']['date_notification'] == FAKE_DATE


class TestWhenProcedureHasRequalifications(TestV1113):

    def test_shifts_requalification_date_notification_except_the_oldest(self):
        # Given
        self.patcher.manifest.initialize('1.1.12')
        demande_asile_id = insert_demande_asile(self.db)

        # When
        self.patcher.apply_patch(self.patch)

        # Then
        demande_asile = self.db.demande_asile.find_one(demande_asile_id)
        requalifications = demande_asile['procedure']['requalifications']

        assert requalifications[0]['date_notification'] == 'fakeDateNotification1'
        assert requalifications[1]['date_notification'] == 'fakeDateNotification2'
        assert requalifications[2]['date_notification'] == 'fakeDateNotification3'

    def test_uses_date_decision_sur_attestion_from_oldest_demande_asile_for_oldest_requalification(self):
        # Given
        self.patcher.manifest.initialize('1.1.12')
        demande_asile_id = insert_demande_asile(self.db)

        # When
        self.patcher.apply_patch(self.patch)

        # Then
        demande_asile = self.db.demande_asile.find_one(demande_asile_id)
        oldest_date_notification = demande_asile['procedure']['requalifications'][-1]['date_notification']

        demande_asile_history = self.db.demande_asile.history.find_one({'origin': 1, 'version': 2})
        date = json.loads(demande_asile_history['content'])['date_decision_sur_attestation']['$date']
        original_date_attestation_sur_demande = datetime.fromtimestamp(date / 1000)

        assert oldest_date_notification == original_date_attestation_sur_demande

    def test_uses_most_recent_requalification_date_notification_for_procedure_date_notification(self):
        # Given
        self.patcher.manifest.initialize('1.1.12')
        demande_asile_id = insert_demande_asile(self.db)

        # When
        self.patcher.apply_patch(self.patch)

        # Then
        demande_asile = self.db.demande_asile.find_one(demande_asile_id)
        procedure = demande_asile['procedure']
        procedure_date_notification = procedure['date_notification']
        most_recent_date_notification = procedure['requalifications'][0]['date_notification']

        assert procedure_date_notification == 'fakeDateNotification0'
