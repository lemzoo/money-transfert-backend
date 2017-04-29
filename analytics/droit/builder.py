from sief.model import Droit
from analytics.droit.create import on_droit_cree
from analytics.tools import build_filters


def build_droit(solr, date_to, date_from=None):
    filters_collection = build_filters(date_to, date_from)
    filters_collection['type_document'] = 'ATTESTATION_DEMANDE_ASILE'
    rights = Droit.objects(**filters_collection).no_cache()
    print("Build analytics on droit (%s)" % rights.count())

    rights._cursor.batch_size(50)
    results = []
    for i, r in enumerate(rights):
        on_droit_cree(results, r)
        if not i % 1000:
            print('.', flush=True, end='')
            solr.add(results)
            results[:] = []
    print()
    if len(results):
        solr.add(results)
