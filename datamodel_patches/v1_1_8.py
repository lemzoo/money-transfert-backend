"""
Patch 1.1.7 => 1.1.8 : DA link to recueil
"""

from mongopatcher import Patch


patch_v118 = Patch('1.1.7', '1.1.8', patchnote=__doc__)


@patch_v118.fix
def set_recueil_da_origine_in_to_demande_asile(db):
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
