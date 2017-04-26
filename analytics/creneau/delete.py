from analytics.creneau.tools import load_date


def _build_document(results, gu, date_creneau, prefecture, date_delete):
    document = {"doc_type": "rendez_vous_supprime", "guichet_unique_s": gu,
                "date_creneau_dt": date_creneau, 'date_delete_dt': date_delete,
                "prefecture_s": prefecture}
    results.append(document)


def creneau_delete(results, current, gu, prefecture, date_delete):
    _build_document(results, gu, load_date(current, 'date_debut'), prefecture, date_delete)
