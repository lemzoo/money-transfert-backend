from analytics.recueil_da.tools import load_gu, load_spa


def build_solr_document(results, personne_number, spa, gu, date):
    document = {"doc_type": "on_pa_realise", "personnes_i": personne_number,
                "site_pa_s": spa, "guichet_unique_s": gu, "date_dt": date}
    results.append(document)


def usager_is_present(document, field, personne_number):
    add = 0
    if field in document:
        usager = document[field]
        if isinstance(usager, (list)):
            for e in usager:
                if 'demandeur' in e and e['demandeur']:
                    add += 1
                elif 'present_au_moment_de_la_demande'in e and e['present_au_moment_de_la_demande']:
                    add += 1
        elif 'demandeur' in usager and usager['demandeur']:
            add += 1
        elif 'present_au_moment_de_la_demande'in usager and \
                usager['present_au_moment_de_la_demande']:
            add += 1
    return add + personne_number


def on_pa_realise(results, previous, current, date):
    if not previous or not current:
        return
    if current.get('statut') != 'PA_REALISE' or previous.get('statut') != 'BROUILLON':
        return
    spa = load_spa(current)
    gu = load_gu(current)
    if gu == spa:
        return

    personne_number = usager_is_present(current, 'usager_1', 0)
    personne_number = usager_is_present(current, 'usager_2', personne_number)
    personne_number = usager_is_present(current, 'enfants', personne_number)

    if gu:
        build_solr_document(results, personne_number, spa, gu, date)
    else:
        build_solr_document(results, personne_number, spa, spa, date)
