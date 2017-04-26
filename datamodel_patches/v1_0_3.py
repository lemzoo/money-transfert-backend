"""
Patch 1.0.2 => 1.0.3
"""

from mongopatcher import Patch

PS = """ - Solr database must be rebuilt"""

patch_v103 = Patch('1.0.2', '1.0.3', patchnote=__doc__, ps=PS)


@patch_v103.fix
def date_depart_entree(db):
    col_rec = db['recueil_d_a']

    def move_dates(usager, date_depart, date_entree_en_france):
        if usager:
            usager['date_depart'] = date_depart
            usager['date_entree_en_france'] = date_entree_en_france
            usager['date_depart_approximative'] = False
            usager['date_entree_en_france_approximative'] = False

    for recueil in col_rec.find():
        date_depart = recueil.get('date_depart')
        date_entree_en_france = recueil.get('date_entree_en_france')
        if date_depart:
            del recueil['date_depart']
        if date_entree_en_france:
            del recueil['date_entree_en_france']
        move_dates(recueil['usager_1'], date_depart, date_entree_en_france)
        move_dates(recueil.get('usager_2'), date_depart, date_entree_en_france)
        for en in recueil['enfants']:
            move_dates(en, date_depart, date_entree_en_france)
        col_rec.update({'_id': recueil['_id']}, recueil)
