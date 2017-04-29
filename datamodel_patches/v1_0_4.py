"""
Patch 1.0.3 => 1.0.4 : DA link to recueil
"""

from mongopatcher import Patch

PS = """ - Solr database must be rebuilt"""

patch_v104 = Patch('1.0.3', '1.0.4', patchnote=__doc__, ps=PS)


@patch_v104.fix
def date_depart_entree(db):
    col_rec = db['recueil_d_a']
    col_da = db['demande_asile']

    def update_usager(usager, rc_id):
        if not usager or not rc_id:
            return

        da = usager.get('demande_asile_resultante')
        if da:
            col_da.update_one({"_id": da}, {"$set": {"recueil_da_origine": rc_id}})

    for rc in col_rec.find():
        update_usager(rc.get("usager_1"), rc.get('_id'))
        update_usager(rc.get("usager_2"), rc.get('_id'))
        for child in rc.get("enfants", []):
            update_usager(child, rc.get("_id"))
