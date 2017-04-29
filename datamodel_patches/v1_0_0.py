"""
Patch 0.0.0 => 1.0.0

Version 0.0.0 is considered to be the pre-mongopatcher datamodel.
"""

from mongopatcher import Patch


PS = """ - Solr schema.xml has changed, you need to update it
 - Solr database must be rebuild"""

patch_v100 = Patch('0.0.0', '1.0.0', patchnote=__doc__, ps=PS)


@patch_v100.fix
def fix_usager_nom(db):
    col = db['usager']
    col.update_many({'nom_naissance': {'$exists': True, '$ne': [None]}},
                    {'$rename': {'nom': 'nom_tmp'}})
    col.update_many({'nom_tmp': {'$exists': True}}, {'$rename': {'nom_naissance': 'nom'}})
    col.update_many({'nom_tmp': {'$exists': True}}, {'$rename': {'nom_tmp': 'nom_usage'}})


@patch_v100.fix
def fix_recueil_da_usager_nom(db):
    col = db['recueil_d_a']

    def switch_nom(usager):
        if usager and usager.get('nom_naissance'):
            nom_tmp = usager.get('nom')
            usager['nom'] = usager.get('nom_naissance')
            del usager['nom_naissance']
            usager['nom_usage'] = nom_tmp

    for recueil in col.find():
        switch_nom(recueil['usager_1'])
        switch_nom(recueil.get('usager_2'))
        for en in recueil['enfants']:
            switch_nom(en)
        col.replace_one({'_id': recueil['_id']}, recueil)


@patch_v100.fix
def fix_utilisateur_localisation_to_adresse(db):
    db['utilisateur'].update_many({'localisation': {'$exists': True}},
                                  {'$rename': {'localisation': 'adresse'}})


@patch_v100.fix
def fix_demande_asile_condition_entree_france(db):
    db['demande_asile'].update_many(
        {'condition_entree_france': {'$in': ["NORMALE", "FAMILIALE"]}},
        {'$set': {'condition_entree_france': 'REGULIERE'}})


@patch_v100.fix
def fix_recueil_da_condition_entree_france(db):
    col = db['recueil_d_a']

    def fix_condition_entree_france(usager):
        if usager and (usager.get('condition_entree_france') in
                       ['NORMALE', 'FAMILIALE']):
            usager['condition_entree_france'] = 'REGULIERE'
            return True
        return False

    for recueil in col.find():
        needfix = False
        needfix |= fix_condition_entree_france(recueil['usager_1'])
        needfix |= fix_condition_entree_france(recueil.get('usager_2'))
        for en in recueil['enfants']:
            needfix |= fix_condition_entree_france(en)
        if needfix:
            col.replace_one({'_id': recueil['_id']}, recueil)


@patch_v100.fix
def fix_recueil_da_present_au_moment_de_la_demande(db):
    col = db['recueil_d_a']

    def fix_present_au_moment_de_la_demande(usager):
        if (usager and usager.get('demandeur') and
                not usager.get('present_au_moment_de_la_demande')):
            usager['present_au_moment_de_la_demande'] = True
            return True
        return False

    for recueil in col.find():
        needfix = False
        needfix |= fix_present_au_moment_de_la_demande(recueil['usager_1'])
        needfix |= fix_present_au_moment_de_la_demande(recueil.get('usager_2'))
        for en in recueil['enfants']:
            needfix |= fix_present_au_moment_de_la_demande(en)
        if needfix:
            col.replace_one({'_id': recueil['_id']}, recueil)


@patch_v100.fix
def fix_structure_guichet_unique(db):
    col = db['recueil_d_a']
    errors = []
    recueils = col.find({'statut': {'$in': ["PA_REALISE",
                                            "DEMANDEURS_IDENTIFIES",
                                            "EXPLOITE",
                                            "ANNULE",
                                            "PURGE"]},
                         'structure_guichet_unique': {"$exists": False}})
    for recueil in recueils:
        rdv = recueil.get('rendez_vous_gu')
        old_rdvs = recueil.get('rendez_vous_gu_anciens')
        if rdv:
            site = rdv.get('site')
        elif old_rdvs:
            site = old_rdvs[-1].get('site')
        else:
            errors.append("Cannot determine the `structure_guichet_unique` "
                          "field for recueil_d_a `%s`" % recueil['_id'])
        col.update_one({'_id': recueil['_id']},
                       {'$set': {'structure_guichet_unique': site}})
    return '\n'.join(errors)


@patch_v100.fix
def fix_demande_asile_dublin_delai_depart_volontaire(db):
    """
    delai_depart_volontaire was wrongly considered is a datetime instead of a int
    """
    col = db['demande_asile']
    for da in col.find({'dublin.delai_depart_volontaire': {'$exists': True, '$ne': [None]}}):
        delai = da['dublin']['delai_depart_volontaire'].day
        col.update_one({'_id': da['_id']}, {'$set': {'dublin.delai_depart_volontaire': delai}})
