"""
Patch 1.1.14 => 1.1.15
"""
from mongopatcher import Patch


PS = """ - Solr database must be rebuild on utilisateur collection"""


patch_v1115 = Patch('1.1.14', '1.1.15', patchnote=__doc__, ps=PS)


@patch_v1115.fix
def add_accreditation_to_users(db):
    user_collection = db['utilisateur']
    # Migrate the old utilisateur model by moving role, site_affecte and site_rattache
    # to accreditation which is a list of accreditations linked to user.
    # First one, check if the field to move is on the utilisateur.
    # Check if the accreditations list exists on the utilisateur, then compare the new accreditation
    # with the accreditation available on the list.

    for user in user_collection.find():
        new_accreditation = {}
        for field in ('role', 'site_affecte', 'site_rattache'):
            if field in user:
                new_accreditation[field] = user[field]
        if not new_accreditation:
            # Skip while field is not present on the document
            continue
        new_accreditation = {k: v for k, v in new_accreditation.items() if v is not None}
        fin_validite = user.get('fin_validite')
        if fin_validite:
            new_accreditation['fin_validite'] = fin_validite
        update_payload = {'$unset': {'role': True, 'site_affecte': True, 'site_rattache': True}}

        if 'accreditations' not in user:
            user['accreditations'] = []
        for accreditation in user['accreditations']:
            if new_accreditation == {k: v for k, v in accreditation.items()
                                     if v is not None and k != 'id'}:
                # Accreditation already stored, do nothing
                break
        else:
            new_accreditation['id'] = len(user['accreditations'])
            user['accreditations'].append(new_accreditation)
            update_payload['$set'] = {'accreditations': user['accreditations']}

        user_collection.update_one({'_id': user['_id']}, update_payload)
