import pytest
from bson import ObjectId
from uuid import uuid4
from datetime import datetime

from .common import DatamodelBaseTest


BASE_USER_DATA = {
    'email': 'john.doe@test.com',
    'prenom': 'John',
    'nom': 'Doe',
    'password': uuid4().hex,
    'telephone': '0123456789'
}


class TestV1115_CheckAccreditationsField(DatamodelBaseTest):

    BASE_VERSION = '1.1.14'
    TARGET_VERSION = '1.1.15'

    def test_apply_on_empty(self):
        self.patcher.manifest.initialize('1.1.14')
        self.patcher.apply_patch(self.patch)
        self.patcher.manifest.reload()
        assert self.patcher.manifest.version == '1.1.15'

    def test_basic_apply(self):
        self.patcher.manifest.initialize('1.1.14')
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
            'role': 'MY_ROLE',
            'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
            'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
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
            }]
        }

    def test_apply_on_no_role_and_sites(self):
        self.patcher.manifest.initialize('1.1.14')
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
        })

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com'
        }

    def test_accreditation_field_present(self):
        self.patcher.manifest.initialize('1.1.14')
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
            'role': 'MY_ROLE',
            'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
            'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e"),
            'accreditations': []
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
            }]
        }

    def test_accreditation_already_present(self):
        self.patcher.manifest.initialize('1.1.14')
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
            'role': 'MY_ROLE',
            'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
            'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e"),
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
            }]
        }

    ACCREDITATIONS = [
        [],
        [{'id': 0, 'role': 'ROLE2', 'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8c"),
          'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")}],
        [{'id': 0, 'role': 'ROLE1', 'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
          'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8c")}],
        [{'id': 0, 'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
          'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8c")}],
        [{'id': 0, 'role': 'ROLE1', 'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8c")}],
        [{'id': 0, 'role': 'ROLE1', 'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b")}],
        [{'id': 0, 'role': 'ROLE1'}, {'id': 1, 'role': 'ROLE2'}, {'id': 2, 'role': 'ROLE3'}],
        [{'id': 0, 'role': 'ROLE1', 'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
          'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e"), 'fin_validite': datetime(2016, 8, 10)}],
    ]

    @pytest.mark.parametrize("accreditations", ACCREDITATIONS)
    def test_other_accreditation_present(self, accreditations):
        self.patcher.manifest.initialize('1.1.14')
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
            'role': 'ROLE1',
            'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
            'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e"),
            'accreditations': accreditations
        })

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com',
            'accreditations': accreditations + [{
                'id': len(accreditations),
                'role': 'ROLE1',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }]
        }

    def test_multi_apply(self):
        self.patcher.manifest.initialize('1.1.14')

        BASE_USER_DATA = {
            'email': 'john.doe@test.com',
            'role': 'MY_ROLE',
            'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
            'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
        }
        users_data = []
        for i in range(100):
            data = BASE_USER_DATA.copy()
            data['email'] = 'user%s@test.com' % i
            users_data.append(data)
        self.db.utilisateur.insert_many(users_data)

        self.patcher.apply_patch(self.patch)
        users = self.db.utilisateur.find()
        assert users.count() == 100
        for user in users:
            assert 'role' not in user
            assert 'site_rattache' not in user
            assert 'site_affecte' not in user
            assert user['accreditations'] == [{
                'id': 0,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }]

    def test_idempotent_apply(self):
        self.patcher.manifest.initialize('1.1.14')

        data = {
            'email': 'john.doe@test.com',
            'accreditations': [
                {
                    'id': 0,
                    'role': 'ROLE_A',
                    'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                    'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
                },
                {
                    'id': 1,
                    'role': 'ROLE_B',
                    'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8a"),
                    'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8b")
                },
            ]
        }
        user_id = self.db.utilisateur.insert(data)
        data['_id'] = user_id
        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == data

    def test_apply_on_half_done_db(self):
        self.patcher.manifest.initialize('1.1.14')

        users_data = []
        # Alreay patched users...
        for i in range(10):
            users_data.append({
                'email': 'patched-%s@test.com' % i,
                'accreditations': [
                    {
                        'id': 0,
                        'role': 'MY_ROLE',
                        'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                        'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
                    }
                ]
            })

        # ...and other to patch
        for i in range(10):
            users_data.append({
                'email': 'to-patcht-%s@test.com' % i,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            })

        self.db.utilisateur.insert_many(users_data)
        self.patcher.apply_patch(self.patch)

        users = self.db.utilisateur.find()
        assert users.count() == 20
        for user in users:
            assert 'role' not in user
            assert 'site_rattache' not in user
            assert 'site_affecte' not in user
            assert user['accreditations'] == [{
                'id': 0,
                'role': 'MY_ROLE',
                'site_rattache': ObjectId("5805ee3e1d41c855c4fc3e8b"),
                'site_affecte': ObjectId("5805ee3e1d41c855c4fc3e8e")
            }]
