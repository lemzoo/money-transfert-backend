from datetime import datetime

from .common import DatamodelBaseTest


class TestV1117_CheckAuthField(DatamodelBaseTest):

    BASE_VERSION = '1.1.17'
    TARGET_VERSION = '1.1.18'

    BASE_USER_DATA = {
        'email': 'john.doe@test.com',
        'prenom': 'John',
        'nom': 'Doe',
        'telephone': '0123456789',
        'password': '0c6831a5cfcb4085bf1aed7e42342974',
        'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
        'reset_password_token_expire': datetime(2016, 12, 28),
        'change_password_next_login': True,
        'last_change_of_password': datetime(2016, 11, 28),
    }

    def test_apply_on_empty(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        self.patcher.apply_patch(self.patch)
        self.patcher.manifest.reload()
        assert self.patcher.manifest.version == self.TARGET_VERSION

    def test_basic_apply(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        user_id = self.db.utilisateur.insert(self.BASE_USER_DATA)

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com',
            'prenom': 'John',
            'nom': 'Doe',
            'telephone': '0123456789',
            'basic_auth': {
                'login': 'john.doe@test.com',
                'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
                'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                'reset_password_token_expire': datetime(2016, 12, 28),
                'change_password_next_login': True,
                'last_change_of_password': datetime(2016, 11, 28)
            }
        }

    def test_apply_on_no_fields(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        user_id = self.db.utilisateur.insert({
            'email': 'john.doe@test.com',
        })

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com'
        }

    def test_basic_auth_field_present(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        data = self.BASE_USER_DATA.copy()
        data['basic_auth'] = {}
        user_id = self.db.utilisateur.insert(data)

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com',
            'prenom': 'John',
            'nom': 'Doe',
            'telephone': '0123456789',
            'basic_auth': {
                'login': 'john.doe@test.com',
                'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
                'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                'reset_password_token_expire': datetime(2016, 12, 28),
                'change_password_next_login': True,
                'last_change_of_password': datetime(2016, 11, 28)
            }
        }

    def test_basic_auth_field_already_present(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)
        data = self.BASE_USER_DATA.copy()
        data['basic_auth'] = {
            'login': 'john.doe@test.com',
            'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
            'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
            'reset_password_token_expire': datetime(2016, 12, 28),
            'change_password_next_login': True,
            'last_change_of_password': datetime(2016, 11, 28)
        }
        user_id = self.db.utilisateur.insert(data)

        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == {
            '_id': user_id,
            'email': 'john.doe@test.com',
            'prenom': 'John',
            'nom': 'Doe',
            'telephone': '0123456789',
            'basic_auth': {
                'login': 'john.doe@test.com',
                'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
                'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                'reset_password_token_expire': datetime(2016, 12, 28),
                'change_password_next_login': True,
                'last_change_of_password': datetime(2016, 11, 28)
            }
        }

    def test_multi_apply(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)

        USER_DATA = {
            'email': 'john.doe@test.com',
            'password': '0c6831a5cfcb4085bf1aed7e42342974',
            'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
            'reset_password_token_expire': datetime(2016, 12, 28),
            'change_password_next_login': True,
            'last_change_of_password': datetime(2016, 11, 28)
        }

        users_data = []
        for i in range(50):
            data = USER_DATA.copy()
            data['email'] = 'user%s@test.com' % i
            users_data.append(data)
        self.db.utilisateur.insert_many(users_data)

        self.patcher.apply_patch(self.patch)
        users = self.db.utilisateur.find()
        assert users.count() == 50
        for i, user in enumerate(users):
            assert 'password' not in user
            assert 'reset_password_token' not in user
            assert 'reset_password_token_expire' not in user
            assert 'change_password_next_login' not in user
            assert 'last_change_of_password' not in user
            assert user['basic_auth'] == {
                'login': 'user%i@test.com' % i,
                'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
                'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                'reset_password_token_expire': datetime(2016, 12, 28),
                'change_password_next_login': True,
                'last_change_of_password': datetime(2016, 11, 28)
            }

    def test_idempotent_apply(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)

        data = {
            'email': 'john.doe@test.com',
            'basic_auth': {
                'login': 'john.doe@test.com',
                'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
                'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                'reset_password_token_expire': datetime(2016, 12, 28),
                'change_password_next_login': True,
                'last_change_of_password': datetime(2016, 11, 28)
            }
        }
        user_id = self.db.utilisateur.insert(data)
        data['_id'] = user_id
        self.patcher.apply_patch(self.patch)
        user = self.db.utilisateur.find_one(user_id)
        assert user == data

    def test_apply_on_half_donedb(self):
        self.patcher.manifest.initialize(self.BASE_VERSION)

        users_data = []
        # Alreay patched users...
        for i in range(10):
            users_data.append({
                'email': 'patched-%s@test.com' % i,
                'basic_auth': {
                    'login': 'patched-%s@test.com' % i,
                    'hashed_password': '0c6831a5cfcb4085bf1aed7e42342974',
                    'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                    'reset_password_token_expire': datetime(2016, 12, 28),
                    'change_password_next_login': True,
                    'last_change_of_password': datetime(2016, 11, 28)
                }
            })

        # ...and other to patch
        for i in range(10):
            users_data.append({
                'email': 'to-patcht-%s@test.com' % i,
                'password': '0c6831a5cfcb4085bf1aed7e42342974',
                'reset_password_token': '45d2ce19c1ff452fb96608cb0a19a202',
                'reset_password_token_expire': datetime(2016, 12, 28),
                'change_password_next_login': True,
                'last_change_of_password': datetime(2016, 11, 28)
            })

        self.db.utilisateur.insert_many(users_data)
        self.patcher.apply_patch(self.patch)

        users = self.db.utilisateur.find()
        assert users.count() == 20
        for user in users:
            assert 'password' not in user
            assert 'reset_password_token' not in user
            assert 'reset_password_token_expire' not in user
            assert 'change_password_next_login' not in user
            assert 'last_change_of_password' not in user
            assert user['basic_auth'][
                'hashed_password'] == '0c6831a5cfcb4085bf1aed7e42342974'
            assert user['basic_auth'][
                'reset_password_token'] == '45d2ce19c1ff452fb96608cb0a19a202'
            assert user['basic_auth'][
                'reset_password_token_expire'] == datetime(2016, 12, 28)
            assert user['basic_auth']['change_password_next_login'] is True
            assert user['basic_auth']['last_change_of_password'] == datetime(2016, 11, 28)
