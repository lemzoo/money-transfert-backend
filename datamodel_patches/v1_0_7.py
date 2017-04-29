"""
Patch 1.0.6 => 1.0.7
Initialize 'visa'
"""

from mongopatcher import Patch

PS = ""

patch_v107 = Patch('1.0.6', '1.0.7', patchnote=__doc__, ps=PS)


@patch_v107.fix
def add_field(db):
    col = db['demande_asile']

    for da in col.find():
        indicateur_visa_long_sejour = da.get('indicateur_visa_long_sejour', False)
        if indicateur_visa_long_sejour:
            col.update({'_id': da['_id']}, {'$set': {'visa': 'D'}})
        else:
            col.update({'_id': da['_id']}, {'$set': {'visa': 'AUCUN'}})
