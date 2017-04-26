"""
Patch 1.1.4 => 1.1.5
Ajout champ "résultat" pour les décisions définitives

"""

from mongopatcher import Patch

patch_v115 = Patch('1.1.4', '1.1.5', patchnote=__doc__)

DECISIONS_DEFINITIVES = {
    # OFPRA
    'CR': 'ACCORD',  # Réfugié statutaire
    'TF': 'ACCORD',  # Transf.protect. Etr.vers Frce
    'PS': 'ACCORD',  # Protection Subsidiaire
    'DC': 'REJET',  # Décès
    'CL': 'REJET',  # Clôture
    'DE': 'REJET',  # Irrecevabilité non suivie de recours
    'DS': 'REJET',  # Rejet de la demande non suivi
    # OFPRA/CNDA
    'IR': 'REJET',  # Irrecevable
    'ANP': 'ACCORD',  # Protec. Subsidiaire
    'AN': 'ACCORD',  # Annulation
    'ANT': 'ACCORD',  # Annulation d'un refus de transfert
    'IAM': 'REJET',  # Irrecevable absence de moyens
    'ILE': 'REJET',  # Irrecevable langue étrangère
    'IND': 'REJET',  # Irrecevable nouvelle demande
    'INR': 'REJET',  # Irrecevable recours non régul.
    'IRR': 'REJET',  # Irrecevable recours en révisio
    'RJ': 'REJET',  # Rejet
    'NOR': 'REJET',  # Rejet par ordonnance
    'RJO': 'REJET',  # Rejet ordonnances nouvelles
    'DSO': 'REJET',  # Désistement ordonnance
    'RIC': 'REJET',  # Incompétence
    'ANP': 'ACCORD',  # Protec. Subsidiaire
    'AN':  'ACCORD',  # Annulation
    'IAM': 'REJET',   # Irrecevable absence de moyens
    'IF':  'REJET',   # Irrecevable forclusion
    'AI':  'REJET',   # Autre irrecevabilité
    'RIC': 'REJET',   # Incompétence
    'AVI': 'REJET',   # Incompétence
    'RJO': 'REJET',   # Rejet ordonnances nouvelles
    'RDR': 'REJET',   # Exclusion
    'NL':  'REJET',   # Non lieu (lorsqu'il constate une situation de rejet)
    'NLE': 'REJET',   # Non lieu (lorsqu'il constate une situation de rejet)
    # ERRORS
    'EE':  'ERREUR',  # Erreur d'enregistrement
    'ERR': 'ERREUR',  # Erreur dans la décision
}


@patch_v115.fix
def add_field(db):
    col = db['demande_asile']
    for demande_asile in col.find():
        decisions_definitives = demande_asile.get('decisions_definitives', {})
        if len(decisions_definitives) > 0 and 'nature' in decisions_definitives[-1]:
            col.update({'_id': demande_asile['_id']}, {'$set': {
                       'decision_definitive_resultat': DECISIONS_DEFINITIVES.get(decisions_definitives[-1]['nature'])}})
