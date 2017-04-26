"""
Patch 1.0.7 => 1.0.8
Suppression du statut GU_ENREGISTREE, et remplacement par PRETE_EDITION_ATTESTATION
"""

from mongopatcher import Patch

PS = ""

patch_v108 = Patch('1.0.7', '1.0.8', patchnote=__doc__, ps=PS)


@patch_v108.fix
def add_field(db):
    col = db['demande_asile']

    for da in col.find({'statut': 'ENREGISTREE_GU'}):
        col.update({'_id': da['_id']}, {'$set': {'statut': 'PRETE_EDITION_ATTESTATION'}})
