"""
Patch 1.1.11 => 1.1.12
Mise à jour du droit.sous_type_document DEUXIEME_RENOUVELLEMENT -> EN_RENOUVELLEMENT
"""

from mongopatcher import Patch

patch_v1112 = Patch('1.1.11', '1.1.12', patchnote=__doc__)


@patch_v1112.fix
def correct_typo(db):
    db['droit'].update_many({'sous_type_document': "DEUXIEME_RENOUVELLEMENT"}, {
                            '$set': {'sous_type_document': "EN_RENOUVELLEMENT"}})
