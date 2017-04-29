"""
Patch 1.1.8 => 1.1.9
Mise à jour du statut CANCELED => CANCELLED
"""

from mongopatcher import Patch

patch_v119 = Patch('1.1.8', '1.1.9', patchnote=__doc__)


@patch_v119.fix
def correct_typo(db):
    db['message'].update_many({'status': "CANCELED"}, {'$set': {'status': "CANCELLED"}})
