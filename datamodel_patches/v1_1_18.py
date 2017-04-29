"""
Patch 1.1.17 => 1.1.18

Migrate the old Utilisateur(Agent) model by moving password,
reset_password_token, reset_password_token_expire,
change_password_next_login, last_change_of_password to basic_auth
which is a Login/Password mecanism for authentication.
"""
from mongopatcher import Patch


PS = """ - Solr database must be rebuild on utilisateur collection"""


patch_v1118 = Patch('1.1.17', '1.1.18', patchnote=__doc__, ps=PS)


@patch_v1118.fix
def add_basic_auth_fields_to_agent(db):
    agent_collection = db['utilisateur']

    for user in agent_collection.find():
        basic_auth = {}
        for field in ('password', 'reset_password_token', 'reset_password_token_expire',
                      'change_password_next_login', 'last_change_of_password'):
            if field in user:
                if field == 'password':
                    basic_auth['hashed_password'] = user['password']
                else:
                    basic_auth[field] = user[field]
        if not basic_auth:
            # Skip while field is not present on the document
            continue
        basic_auth = {k: v for k, v in basic_auth.items() if v is not None}
        login = user.get('email')
        if login:
            basic_auth['login'] = login
        update_payload = {'$unset': {'password': True, 'reset_password_token': True,
                          'reset_password_token_expire': True, 'change_password_next_login': True,
                          'last_change_of_password': True}}

        update_payload['$set'] = {'basic_auth': basic_auth}
        agent_collection.update_one({'_id': user['_id']}, update_payload)
