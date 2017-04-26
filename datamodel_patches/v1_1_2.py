"""
Patch 1.1.1 => 1.1.2
Mise à jour des event handlers
"""

from mongopatcher import Patch

patch_v112 = Patch('1.1.1', '1.1.2', patchnote=__doc__)

allowed_event_handlers = [
    "agdref-demande_asile.cree",
    "agdref-demande_asile.decision_definitive",
    "agdref-demande_asile.introduit_ofpra",
    "agdref-demande_asile.procedure_requalifiee",
    "agdref-droit.support.cree",
    "agdref-usager.etat_civil.valide",
    "agdref-usager.localisation.modifie",
    "dna-demande_asile.decision_definitive",
    "dna-demande_asile.dublin_modifie",
    "dna-demande_asile.introduit_ofpra",
    "dna-demande_asile.procedure_finie",
    "dna-demande_asile.procedure_requalifiee",
    "dna-recueil_da.exploite",
    "dna-recueil_da.pa_realise",
    "dna-usager.etat_civil.modifie",
    "dna-usager.etat_civil.valide",
    "dna-usager.modifie",
    "inerec-demande_asile.en_attente_ofpra",
    "inerec-demande_asile.modifie",
    "inerec-demande_asile.procedure_requalifiee",
    "inerec-droit.cree",
    "inerec-droit.modifie",
    "inerec-droit.retire",
    "inerec-droit.support.annule",
    "inerec-droit.support.cree",
    "inerec-droit.support.modifie",
    "inerec-usager.etat_civil.modifie",
    "inerec-usager.localisation.modifie",
    "inerec-usager.modifie",
]


@patch_v112.fix
def remove_handler(db):
    msg = ''
    messages_col = db['message']
    event_handler_col = db['event_handler']

    for evh in event_handler_col.find({}):
        name = evh['queue'] + '-' + evh['event']
        if name not in allowed_event_handlers:
            msg += "Skipped unknown event: %s\n" % evh
        messages_col.update_many({'handler': evh['_id']}, {'$set': {'handler': name}})
    event_handler_col.drop()
    return msg
