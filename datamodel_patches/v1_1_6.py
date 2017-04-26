"""
Patch 1.1.5 => 1.1.6
Ajout du booléen trasférable sur un usager pour empecher le transfert entre prefecture
"""

from mongopatcher import Patch

patch_v116 = Patch('1.1.5', '1.1.6', patchnote=__doc__)


@patch_v116.fix
def add_transferable_to_usager(db):
    col = db['usager']
    sites = db['site']
    errors = []
    pref = sites.find({'libelle': 'loader-Prefecture'})[0]['_id']
    for u in col.find():
        pref_usager = u.get('prefecture_rattachee')
        transferable = True
        if pref == pref_usager:
            transferable = False
        col.update({'_id': u['_id']}, {'$set': {'transferable': transferable}})
