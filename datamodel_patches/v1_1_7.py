"""
Patch 1.1.6 => 1.1.7
Ajoute un champ date pour chaque utilisateur afin de verifier si le mot de passe doit etre considere comme expire
"""
from mongopatcher import Patch
from datetime import datetime


patch_v117 = Patch('1.1.6', '1.1.7', patchnote=__doc__)


@patch_v117.fix
def update_utilisateur(db):
    utilisateur_col = db['utilisateur']
    utilisateur_col.update_many({'last_change_of_password': {'$exists': False}}, {
                                '$set': {'last_change_of_password': datetime.utcnow()}})
