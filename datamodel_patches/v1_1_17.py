"""
Patch 1.1.16 => 1.1.17
"""
from mongopatcher import Patch


PS = """ - Solr database must be rebuild on utilisateur collection"""


patch_v1117 = Patch('1.1.16', '1.1.17', patchnote=__doc__, ps=PS)


@patch_v1117.fix
def add_numero_reexamen_to_recueil(db):
    recueil_da_col = db['recueil_d_a']
    # Check if the preference document exits, if not add it on the collection

    def _update_usager(usager, name_usager, recueil_id):

        if (usager and
                usager.get('type_demande') == "REEXAMEN" and
                not usager.get('numero_reexamen')):
            # update bdd
            update_payload = ({'$set': {"{}.numero_reexamen".format(name_usager): 1}})
            recueil_da_col.update_one({'_id': recueil_id}, update_payload)

    for recueil_da in recueil_da_col.find():
        usager_1 = recueil_da.get('usager_1', None)
        usager_2 = recueil_da.get('usager_2', None)
        enfants = recueil_da.get('enfants', [])

        _update_usager(usager_1, 'usager_1', recueil_da['_id'])
        _update_usager(usager_2, 'usager_2', recueil_da['_id'])

        for index, enfant in enumerate(enfants):
            _update_usager(enfant, 'enfants.{}'.format(index), recueil_da['_id'])
