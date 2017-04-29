"""
Patch 1.1.9 => 1.1.10
Changement du mécanisme de limite pour la prise de RDV des GU est des pref
"""

from mongopatcher import Patch


patch_v1110 = Patch('1.1.9', '1.1.10', patchnote=__doc__)


@patch_v1110.fix
def site_limite(db):
    db['site'].update_many({"limite_rdv_3_jrs": True},
                           {"$unset": {'limite_rdv_3_jrs': 1}, "$set": {'limite_rdv_jrs': 3}})
    db['site'].update_many({"limite_rdv_3_jrs": False},
                           {"$unset": {'limite_rdv_3_jrs': 1}, "$set": {'limite_rdv_jrs': 0}})


@patch_v1110.fix
def site_actualite_update(db):
    db['site_actualite'].update_many(
        {"type": 'ALERTE_GU_RDV_3JRS'}, {"$set": {"type": 'ALERTE_GU_RDV_LIMITE_JRS'}})
