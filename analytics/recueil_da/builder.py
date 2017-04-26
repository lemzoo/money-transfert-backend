from sief.model import RecueilDA
import json

from analytics.recueil_da.error_pa_realise import check_error_pa_realise
from analytics.recueil_da.on_pa_realise import on_pa_realise
from analytics.recueil_da.cancel_meeting import cancel_meeting
from analytics.recueil_da.done_meeting import done_meeting
from analytics.recueil_da.taken_meeting import taken_meeting
from analytics.tools import build_filters


def build_one_recueil_history(recueil, date_from, results):
    filters_history = {'origin': recueil.id}
    history = RecueilDA.get_collection_history().objects(
        **filters_history).order_by('+date').no_cache()
    previous = None
    previous_len = 0
    last_edit = 0
    for element in history:
        current = json.loads(element.content)
        if not date_from or element.date > date_from:
            last_edit = element.date
            check_error_pa_realise(results, previous, current, last_edit)
            on_pa_realise(results, previous, current, last_edit)
            taken_meeting(results, previous, current, last_edit)
            previous_len = cancel_meeting(results, current, previous_len)
            done_meeting(results, current, previous)
        previous = current


def build_recueil_da(solr, date_to, date_from=None):
    filters_collection = build_filters(date_to, date_from)
    recueils = RecueilDA.objects(**filters_collection).no_cache()
    print("Build analytics on recueil_da (%s)" % recueils.count())

    recueils._cursor.batch_size(50)
    results = []
    for i, r in enumerate(recueils):
        build_one_recueil_history(r, date_from, results)
        if not i % 1000:
            print('.', flush=True, end='')
            solr.add(results)
            results[:] = []
    if len(results):
        solr.add(results)
    print()
