"""
Patch 1.0.0 => 1.0.1
"""

from mongopatcher import Patch


PS = """ - Solr database must be rebuild"""

patch_v101 = Patch('1.0.0', '1.0.1', patchnote=__doc__, ps=PS)

@patch_v101.fix
def fix_recueil_da_photo(db):
    col = db['recueil_d_a']

    def delete_photo(usager):
        if usager and not usager.get('demandeur', '') == True:
            if usager.get('photo'):
                del usager['photo']
            if usager.get('photo_premier_accueil'):
                del usager['photo_premier_accueil']

    for recueil in col.find():
        delete_photo(recueil['usager_1'])
        delete_photo(recueil.get('usager_2'))
        for en in recueil['enfants']:
            delete_photo(en)
        col.replace_one({'_id': recueil['_id']}, recueil)
