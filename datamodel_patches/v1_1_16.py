"""
Patch 1.1.15 => 1.1.16
"""
from mongopatcher import Patch


PS = """ - Solr database must be rebuild on utilisateur collection"""


patch_v1116 = Patch('1.1.15', '1.1.16', patchnote=__doc__, ps=PS)


@patch_v1116.fix
def add_preferences_to_users(db):
    user_collection = db['utilisateur']
    # Check if the preference document exits, if not add it on the collection

    for user in user_collection.find():
        if 'preferences' in user:
            # Skip while field is not present on the document
            continue

        update_payload = ({'$set': {'preferences': {}}})

        user_collection.update_one({'_id': user['_id']}, update_payload)
