"""
Patch 1.1.10 => 1.1.11
Remplace le code pays KOS par RKS
"""
from functools import partial
from mongopatcher import Patch


patch_v1111 = Patch('1.1.10', '1.1.11', patchnote=__doc__)

OLD_REF = "KOS"
NEW_REF = "RKS"


def update_kosovo_ref(collection, find_path, set_path=None, recursive=False):
    find_path = find_path if find_path.endswith('.code') else find_path + ".code"
    set_path = set_path if set_path else find_path
    set_path = set_path if set_path.endswith('.code') else set_path + ".code"
    if recursive:
        recursive_update(collection.update_many, {find_path: OLD_REF}, {'$set': {set_path: NEW_REF}})
    else:
        collection.update_many({find_path: OLD_REF}, {'$set': {set_path: NEW_REF}})


def recursive_update(*args, **kwargs):
    # MongoDB can only update one occurence at a time in a given document.
    # Thus we run the query multiple time until no more occurence is found.
    update_function = partial(*args, **kwargs)
    needed = True
    while needed:
        ret = update_function()
        needed = ret.modified_count != 0


@patch_v1111.fix
def update_code_pays(db):
    # First thing first, recreate Kosovo referential with it new ID
    if not db['referentiels.pays'].find_one({'_id': NEW_REF}):
        old_kosovo = db['referentiels.pays'].find_one({'_id': OLD_REF})
        new_kosovo = old_kosovo
        new_kosovo['_id'] = NEW_REF
        db['referentiels.pays'].insert_one(new_kosovo)

    # Now correct the fields using the old Kosovo referential

    update_kosovo_ref(db.demande_asile, 'pays_traverses.pays', 'pays_traverses.$.pays', recursive=True)
    db.demande_asile.update_many({'dublin.EM': OLD_REF}, {'$set': {'dublin.EM': NEW_REF}})
    # Update list in list require manual handling
    to_update_docs = db.demande_asile.find({'decisions_definitives.pays_exclus': OLD_REF})
    for doc in to_update_docs:
        for decision in doc['decisions_definitives']:
            decision['pays_exclus'] = [k if k != OLD_REF else NEW_REF for k in decision['pays_exclus']]
        db.demande_asile.update({'_id': doc['_id']}, doc)

    update_kosovo_ref(db.recueil_d_a, 'usager_1.pays_naissance.code')
    update_kosovo_ref(db.recueil_d_a, 'usager_1.adresse.pays.code')
    update_kosovo_ref(db.recueil_d_a, 'usager_2.pays_naissance.code')
    update_kosovo_ref(db.recueil_d_a, 'usager_2.adresse.pays.code')
    update_kosovo_ref(db.recueil_d_a, 'enfants.pays_naissance', 'enfants.$.pays_naissance.code', recursive=True)
    update_kosovo_ref(db.recueil_d_a, 'enfants.adresse.pays', 'enfants.$.adresse.pays.code', recursive=True)

    update_kosovo_ref(db.usager, 'pays_naissance.code')
    update_kosovo_ref(db.usager, 'localisations.adresse.pays', 'localisations.$.adresse.pays', recursive=True)

    # Finally we can destroy old Kosovo referential given nobody still use it
    db['referentiels.pays'].delete_one({'_id': OLD_REF})
