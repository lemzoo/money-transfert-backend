from analytics.recueil_da.tools import load_sites, load_spa
from analytics.recueil_da.done_meeting import build_done
from sief.model.site import Creneau
from analytics.tools import logger


def build_cancel_document(results, gu, date_creneau, prefecture, motif):
    document = {"doc_type": "rendez_vous_annule", "guichet_unique_s": gu,
                "date_creneau_dt": date_creneau,
                "prefecture_s": prefecture, "motif_s":
                motif}
    results.append(document)


def cancel(results, recueil, gu, prefecture):
    if not len(recueil['rendez_vous_gu_anciens']):
        return
    rendez_vous = recueil['rendez_vous_gu_anciens'][-1]
    motif = recueil['rendez_vous_gu']['motif']
    for c in rendez_vous['creneaux']:
        creneau = Creneau.objects(id=c['$oid']).first()
        if not creneau:
            msg = "[Cancel Meeting] Creneau: " + c['$oid'] + " not found in database"
            logger.log(msg, 'ERROR')
            return
        build_cancel_document(results, gu, creneau.date_debut, prefecture, motif)
        build_done(results, gu, creneau.date_fin, prefecture)


def cancel_meeting(results, current, previous_len):
    if len(current['rendez_vous_gu_anciens']) == previous_len:
        return previous_len
    if 'rendez_vous_gu' not in current:
        return previous_len
    gu, prefecture = load_sites(current)
    spa = load_spa(current)
    if gu and spa != gu:
        cancel(results, current, gu, prefecture)
    return len(current['rendez_vous_gu_anciens'])
