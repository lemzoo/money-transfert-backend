from bson import ObjectId

from .common import DatamodelBaseTest


class TestV1116_CheckPreferencesField(DatamodelBaseTest):

    BASE_VERSION = '1.1.15'
    TARGET_VERSION = '1.1.16'

    def test_user_doesnt_have_a_preferences(self):
        self.patcher.manifest.initialize('1.1.15')
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
            'accreditations': [{
                'id': 0,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }]
        })

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com',
            'accreditations': [{
                'id': 0,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }],
            'preferences': {}
        }

    def test_user_has_a_preferences(self):
        self.patcher.manifest.initialize('1.1.15')
        preferences = {
            'key': 'values',
            'list': [],
            '1': 100000
        }
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
            'accreditations': [{
                'id': 0,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }],
            'preferences': preferences
        })

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com',
            'accreditations': [{
                'id': 0,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }],
            'preferences': preferences
        }
