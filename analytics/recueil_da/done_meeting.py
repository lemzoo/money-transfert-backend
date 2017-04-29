from analytics.recueil_da.tools import load_sites, load_spa
from sief.model.site import Creneau
from analytics.tools import logger


def build_done(results, gu, date_creneau, prefecture):
    document = {"doc_type": "rendez_vous_honore", "guichet_unique_s": gu,
                "date_creneau_dt": date_creneau,
                "prefecture_s": prefecture}
    results.append(document)


def build_done_meeting(results, current):
    spa = load_spa(current)
    gu, prefecture = load_sites(current)
    if gu and spa != gu:
        if 'rendez_vous_gu' in current:
            for c in current['rendez_vous_gu']['creneaux']:
                creneau = Creneau.objects(id=c['$oid']).first()
                if not creneau:
                    msg = "[Done Meeting] Creneau: " + c['$oid'] + " not found in database"
                    logger.log(msg, 'ERROR')
                    return
                build_done(results, gu, creneau.date_fin, prefecture)


def done_meeting(results, current, previous):
    if not current or not previous:
        return
    if current['statut'] not in ['BROUILLON',
                                 'PA_REALISE',
                                 'ANNULE'] and previous['statut'] == 'PA_REALISE':
        build_done_meeting(results, current)

    if previous['statut'] != 'ANNULE' and\
            current['statut'] == 'ANNULE' and\
            current['motif_annulation'] != 'NON_PRESENTATION_RDV':
        build_done_meeting(results, current)
