from sief.model import Creneau, GU
from analytics.creneau.open import creneau_open
from analytics.creneau.open import build_open_from_json
from analytics.creneau.delete import creneau_delete
from analytics.tools import logger
from analytics.creneau.tools import load_date

from mongoengine import DoesNotExist
import json


def load_sites(creneau):
    gu = None
    prefecture = None
    try:
        if creneau.site:
            gu = str(creneau.site.id)
            if creneau.site.autorite_rattachement:
                prefecture = str(creneau.site.autorite_rattachement.id)
            else:
                msg = "[Creneau Load sites] Guichet Unique: prefecture not define for " + \
                    str(creneau.site.id)
                logger.log(msg, 'WARNING')
        else:
            msg = "[Creneau Load sites] Site: not define in creneau " + \
                str(creneau.id)
            logger.log(msg, 'WARNING')
    except DoesNotExist as exc:
        logger.log(exc, 'ERROR')
    return gu, prefecture


def build_one_creneau(creneau, results):
    gu, prefecture = load_sites(creneau)
    if gu and prefecture:
        creneau_open(results, creneau, gu, prefecture)


def _build_delete_creneau(creneau_history, results, date_from):
    filters_on_history = {}
    filters_on_history['action'] = 'CREATE'
    filters_on_history['origin'] = creneau_history['origin']
    creneau_origin = Creneau.get_collection_history().objects(**filters_on_history).no_cache().first()
    if not creneau_origin:
        return
    creneau = json.loads(creneau_origin.content)
    gu = GU.objects(id=creneau['site']['$oid']).first()
    prefecture = None
    try:
        if gu.autorite_rattachement:
            prefecture = str(gu.autorite_rattachement.id)
        else:
            msg = "[Creneau Supprime sites] Guichet Unique: prefecture not define for " + \
                str(gu.id)
            logger.log(msg, 'WARNING')

    except DoesNotExist as e:
        logger.log(e, 'ERROR')

    if gu and prefecture:
        creneau_delete(results, creneau, str(gu.id), prefecture, creneau_history['date'])
        if not date_from:
            build_open_from_json(results, str(gu.id), prefecture, load_date(creneau, 'date_debut'))
        elif date_from < creneau_origin['date']:
            # Created/Deleted creneaux beetween two bootstrap. Never created with build_creneau().
            build_open_from_json(results, str(gu.id), prefecture, load_date(creneau, 'date_debut'))


def build_delete_creneau(solr, date_to, date_from=None):
    filters_on_history = {}
    results = []
    if date_from:
        filters_on_history['date__gte'] = str(date_from)
    filters_on_history['date__lte'] = str(date_to)
    filters_on_history['action'] = 'DELETE'
    creneaux = Creneau.get_collection_history().objects(**filters_on_history).no_cache()
    creneaux._cursor.batch_size(50)

    for i, c in enumerate(creneaux):
        _build_delete_creneau(c, results, date_from)
        if not i % 1000:
            print('.', flush=True, end='')
            solr.add(results)
            results[:] = []
    print()
    if len(results):
        solr.add(results)


def build_creneau(solr, date_to, date_from=None):
    filters_on_collection = {}
    if date_from:
        filters_on_collection['doc_created__gte'] = str(date_from)
    filters_on_collection['doc_created__lte'] = str(date_to)
    creneaux = Creneau.objects(**filters_on_collection).no_cache()
    print("Build analytics on creneaux (%s)" % creneaux.count())

    creneaux._cursor.batch_size(50)
    results = []
    for i, c in enumerate(creneaux):
        build_one_creneau(c, results)
        if not i % 1000:
            print('.', flush=True, end='')
            solr.add(results)
            results[:] = []
    if len(results):
        solr.add(results)
        results[:] = []
