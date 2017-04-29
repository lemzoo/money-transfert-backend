def build_document(results, guichet_unique, date_creneau, prefecture):
    document = {"doc_type": "rendez_vous_ouvert", "guichet_unique_s": guichet_unique,
                "date_creneau_dt": date_creneau,
                "prefecture_s": prefecture}
    results.append(document)


def creneau_open(results, current, guichet_unique, prefecture):
    if current.reserve and 'document_lie' not in current:
        return
    build_document(results, guichet_unique, current.date_debut, prefecture)


def build_open_from_json(results, gu, prefecture, date_debut):
    build_document(results, gu, date_debut, prefecture)
