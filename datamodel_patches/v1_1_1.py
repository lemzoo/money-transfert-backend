"""
Patch 1.1.0 => 1.1.1
Implementation de la spec Habilitation - ajout des prefecture_rattachee
"""

from mongopatcher import Patch
from bson import DBRef


patch_v111 = Patch('1.1.0', '1.1.1', patchnote=__doc__)


@patch_v111.fix
def prefecture_rattachee(db):
    col_recueil = db['recueil_d_a']
    col_sites = db['site']
    col_da = db['demande_asile']
    col_usager = db['usager']
    col_droit = db['droit']    

    for recueil in col_recueil.find({'structure_guichet_unique': {'$exists': True}}):
        site = col_sites.find_one({'_id': recueil['structure_guichet_unique']})
        pref = site.get('autorite_rattachement')
        col_recueil.update({'_id': recueil['_id']}, {'$set': {'prefecture_rattachee': pref}})

        def _update_usager(usager):
            if not usager:
                return
            usager_id = usager.get('usager_existant')
            if usager_id:
                col_usager.update({'_id': usager_id}, {'$set': {'prefecture_rattachee': pref}})
            da_id = usager.get('demande_asile_resultante')
            if da_id:
                col_da.update({'_id': da_id}, {'$set': {'prefecture_rattachee': pref}})
                col_droit.update({'demande_origine._ref': DBRef('demande_asile', da_id)},
                                 {'$set': {'prefecture_rattachee': pref}})

        _update_usager(recueil.get('usager_1'))
        _update_usager(recueil.get('usager_2'))
        for child in recueil.get('enfants', []):
            _update_usager(child)
