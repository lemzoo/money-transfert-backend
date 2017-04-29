from analytics.tools import own_by, diff_json_key
from analytics.recueil_da.tools import load_gu, load_spa


def build_solr_document(results, field, error_type, site, sitepa, date):
    document = {"doc_type": "on_error_pa_realise", "field_s": field, "type_s": error_type,
                "guichet_unique_s": site, "site_pa_s": sitepa, "date_dt": date}
    results.append(document)


def check_error_pa_realise(results, previous, current, date):
    if not current or not previous:
        return
    if previous['statut'] != 'PA_REALISE':
        return
    if 'structure_guichet_unique' not in previous:
        return
    if 'structure_accueil' not in previous:
        return
    if previous['structure_accueil'] == previous['structure_guichet_unique']:
        return

    spa = load_spa(previous)
    gu = load_gu(previous)

    keys = diff_json_key(previous, current)
    for k in keys:
        if own_by(k, previous) and own_by(k, current):
            build_solr_document(results, k, "MODIFY", gu, spa, date)
        elif own_by(k, previous):
            build_solr_document(results, k, "REMOVE", gu, spa, date)
        elif own_by(k, current):
            build_solr_document(results, k, "ADD", gu, spa, date)
