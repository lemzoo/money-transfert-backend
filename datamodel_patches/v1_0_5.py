"""
Patch 1.0.4 => 1.0.5
Evolution Vulnerabilite
"""

from mongopatcher import Patch

PS = """ - Solr database must be rebuilt"""

patch_v105 = Patch('1.0.4', '1.0.5', patchnote=__doc__, ps=PS)


@patch_v105.fix
def fix_vulnerabilites(db):
    col = db['usager']

    def convert_vulnerabilites(vulnerabilite):
        adaptation = vulnerabilite.get('adaptation_hebergement', [])
        for field in ('hebergement', 'structure_hebergement_urgence',
                      'adaptation_hebergement', 'date_prise_medicament',
                      'assistance_tiers_prise_medicament',
                      'duree_hospitalisation', 'adaptation_hebergement'):
            if field in vulnerabilite:
                del vulnerabilite[field]

        if vulnerabilite.get('grossesse_date_terme'):
            vulnerabilite['grossesse'] = True
        if 'MALVOYANT' in adaptation:
            vulnerabilite['malvoyance'] = True
        if 'CHAISE_ROULANTE' in adaptation:
            vulnerabilite['mobilite_reduite'] = True
        if 'SOURD' in adaptation:
            vulnerabilite['malentendance'] = True
        if 'MUET' in adaptation:
            vulnerabilite['interprete_signe'] = True

    for usager in col.find({'vulnerabilite': {'$exists': True, '$ne': None}}):
        convert_vulnerabilites(usager['vulnerabilite'])
        col.update({'_id': usager['_id']}, usager)
