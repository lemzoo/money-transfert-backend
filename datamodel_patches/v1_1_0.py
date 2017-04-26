"""
Patch 1.0.8 => 1.1.0
Implementation de la spec Habilitation
"""

from mongopatcher import Patch

PS = """ - Solr database must be rebuilt"""

patch_v110 = Patch('1.0.8', '1.1.0', patchnote=__doc__, ps=PS)


@patch_v110.fix
def correct_roles(db):
    col = db['utilisateur']

    for old, new in (
            ('Administrateur', 'ADMINISTRATEUR_NATIONAL'),
            ('Premier_accueil', 'GESTIONNAIRE_PA'),
            ('GU_responsable', 'RESPONSABLE_GU_ASILE_PREFECTURE'),
            ('GU_enregistrement', 'GESTIONNAIRE_GU_ASILE_PREFECTURE'),
            ('GU_orientation', 'GESTIONNAIRE_GU_DT_OFII'),
            ('Agent_instruction', 'GESTIONNAIRE_ASILE_PREFECTURE'),
            ('Système - DN@', 'SYSTEME_DNA'),
            ('Système - INEREC', 'SYSTEME_INEREC'),
            ('Système - AGDREF', 'SYSTEME_AGDREF')):
        col.update({'role': old}, {'$set': {'role': new}}, multi=True)
    _correct_site_rattache(db, 'GESTIONNAIRE_PA', inherit_site=False)
    _correct_site_rattache(db, 'RESPONSABLE_GU_ASILE_PREFECTURE', inherit_site=True)
    _correct_site_rattache(db, 'GESTIONNAIRE_GU_ASILE_PREFECTURE', inherit_site=True)
    _correct_site_rattache(db, 'GESTIONNAIRE_GU_DT_OFII', inherit_site=True)
    _correct_site_rattache(db, 'GESTIONNAIRE_ASILE_PREFECTURE', inherit_site=False)


def _correct_site_rattache(db, role, inherit_site):
    col = db['utilisateur']
    col_sites = db['site']
    for user in col.find({'role': role}):
        site_affecte = user.get('site_affecte')
        if not site_affecte:
            continue
        if inherit_site:
            site = col_sites.find_one({'_id': site_affecte})
            site_rattache = site.get('autorite_rattachement')
        else:
            site_rattache = site_affecte
        col.update({'_id': user['_id']}, {'$set': {'site_rattache': site_rattache}})
