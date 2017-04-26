from analytics.recueil_da.tools import load_gu, load_spa
from analytics.creneau.tools import compute_delay_date
from sief.model import Creneau
from analytics.tools import logger


def build_document_gu(results, spa, gu, date_creneau, date_prise, delai):
    document = {"doc_type": "rendez_vous_pris_gu", "site_pa_s": spa,
                "date_creneau_dt": date_creneau,
                "date_pris_dt": date_prise, "delai_i":
                delai}
    results.append(document)


def build_document_spa(results, spa, gu, date_creneau, date_prise, delai):
    document = {"doc_type": "rendez_vous_pris_spa", "site_pa_s": spa,
                "date_creneau_dt": date_creneau, "guichet_unique_s": gu,
                "date_pris_dt": date_prise, "delai_i":
                delai}
    results.append(document)


def _taken_meeting(results, current, date, spa, gu, builder):
    creneaux = current['rendez_vous_gu']['creneaux']
    for c in creneaux:
        id_creneau = c['$oid']

        creneau = Creneau.objects(id=id_creneau).first()
        if not creneau:
            msg = "[Taken Meeting] Creneau: " + c['$oid'] + " not found in database"
            logger.log(msg, 'ERROR')
            return
        day = compute_delay_date(creneau.date_debut, date)
        builder(results, spa, gu, creneau.date_debut, date, day)


def taken_meeting(results, previous, current, date):
    if 'rendez_vous_gu' not in current:
        return
    if previous and 'rendez_vous_gu' in previous and \
            previous['rendez_vous_gu'] == current['rendez_vous_gu']:
        return
    spa = load_spa(current)
    gu = load_gu(current)
    if gu and spa != gu:
        _taken_meeting(results, current, date, spa, gu, build_document_spa)
    else:
        _taken_meeting(results, current, date, spa, gu, build_document_gu)
