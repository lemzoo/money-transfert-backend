"""
Patch 1.1.3 => 1.1.4
Supprime l'ancien index identifiant_agdref_1 de la collection usager
"""

from mongopatcher import Patch

patch_v114 = Patch('1.1.3', '1.1.4', patchnote=__doc__)


@patch_v114.fix
def drop_usager_indentifiant_agdref_index(db):
    db['usager'].drop_index("identifiant_agdref_1")
