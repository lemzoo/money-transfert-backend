"""
Patch 1.0.1 => 1.0.2
"""

from mongopatcher import Patch


PS = """ - Solr database must be rebuild"""

patch_v102 = Patch('1.0.1', '1.0.2', patchnote=__doc__, ps=PS)

@patch_v102.fix
def fix_demande_asile_agent_orientation(db):
    col = db['demande_asile']
    errors = []
    for da in col.find():
        da['agent_orientation'] = 'Agent inconnu'
        col.replace_one({'_id': da['_id']}, da)

@patch_v102.fix
def fix_demande_asile_structure_guichet_unique(db):
    col = db['demande_asile']
    errors = []
    for da in col.find():
        if da.get('structure_guichet_unique'):
            continue
        structure_premier_accueil_id = da.get('structure_premier_accueil')
        structure_premier_accueil = next(db['site'].find({'_id': structure_premier_accueil_id}), None)
        if not structure_premier_accueil:
            continue

        guichet_unique = structure_premier_accueil.get('guichets_uniques', [])
        if len(guichet_unique) == 0:
            continue

        da['structure_guichet_unique'] = guichet_unique[0]
        col.replace_one({'_id': da['_id']}, da)
