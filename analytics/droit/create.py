from sief.model import DemandeAsile
from analytics.tools import logger
from mongoengine import DoesNotExist

renouvellements_value = ['PREMIERE_DELIVRANCE', 'PREMIER_RENOUVELLEMENT',
                         'EN_RENOUVELLEMENT']


def load_prefecture(document):
    if 'prefecture_rattachee' not in document:
        return None
    return str(document.prefecture_rattachee.id)


def build_solr_document(results, spa, gu, procedure_type, date_debut_validite,
                        date_fin_validite, prefecture, renouvellement, date):
    document = {"doc_type": "droit_cree",
                "site_pa_s": spa,
                "guichet_unique_s": gu,
                "date_dt": date,
                "procedure_type_s": procedure_type,
                "date_debut_validite_dt": date_debut_validite,
                "date_fin_validite_dt": date_fin_validite,
                "prefecture_s": prefecture,
                "renouvellement_i": renouvellement}
    results.append(document)


def compute_renouvellement(document):
    if not document:
        return -1
    renouvellement = 0
    for i, x in enumerate(renouvellements_value):
        if x == document.sous_type_document:
            renouvellement = i
            break
    return renouvellement


def on_droit_cree(results, current):
    if current.type_document == 'ATTESTATION_DEMANDE_ASILE':
        try:
            id_demande_asile = current.demande_origine.id
            demande_asile = DemandeAsile.objects(id=id_demande_asile).first()
            if not demande_asile:
                msg = "[Droit Cree] Demande d'Asile: " + id_demande_asile + " not found in database"
                logger.log(msg, 'ERROR')
                return
            renouvellement = compute_renouvellement(current)
            spa = demande_asile.structure_premier_accueil.id
            gu = demande_asile.structure_guichet_unique.id
            procedure_type = demande_asile.procedure.type
            date_debut_validite = current.date_debut_validite
            date_fin_validite = current.date_fin_validite
            prefecture = load_prefecture(current)
            if not prefecture:
                return
            build_solr_document(results, spa, gu, procedure_type,
                                date_debut_validite,
                                date_fin_validite, prefecture,
                                renouvellement, current.doc_created)
        except DoesNotExist as exc:
            logger.log(exc, 'ERROR')
