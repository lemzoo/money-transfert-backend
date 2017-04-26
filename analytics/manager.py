from flask.ext.script import Manager
from analytics.recueil_da.builder import build_recueil_da
from analytics.droit.builder import build_droit
from analytics.creneau.builder import build_creneau
from analytics.creneau.builder import build_delete_creneau
from flask import current_app
import pysolr
from datetime import datetime
from flask.ext.mongoengine import Document
from sief.model import fields
from analytics.tools import logger


class AnalyticDate(Document):
    last_run = fields.DateTimeField(required=True)

analytics_manager = Manager(usage="Perform analytics operations")


def connect_to_solr(url):
    if not url:
        return current_app.solr
    decoder = current_app.config['SOLR_DECODER']
    timeout = current_app.config['SOLR_TIMEOUT']
    return pysolr.Solr(url, decoder=decoder, timeout=timeout)


def get_date_from():
    last_run = AnalyticDate.objects()
    if not last_run:
        return None, datetime.utcnow()
    return last_run[0].last_run, datetime.utcnow()


def update_date_from(date_from):
    last_run = AnalyticDate.objects()
    if not last_run:
        last_run = AnalyticDate(last_run=date_from)
        last_run.save()
    else:
        last_run[0].update(set__last_run=date_from)


def bootstrap_recueil_analytics(date_to, core=None, date_from=None):
    build_recueil_da(connect_to_solr(core), date_to, date_from)


def bootstrap_droit_analytics(date_to, core=None, date_from=None):
    build_droit(connect_to_solr(core), date_to, date_from)


def bootstrap_creneau_analytics(date_to, core=None, date_from=None):
    build_creneau(connect_to_solr(core), date_to, date_from)
    build_delete_creneau(connect_to_solr(core), date_to, date_from)


@analytics_manager.option('-c', '--core', help='url for the solr core')
@analytics_manager.option('-l', '--log', help='log the different error')
def bootstrap(core=None, log=None):
    logger.set_log(log)
    date_from, running_date = get_date_from()
    bootstrap_recueil_analytics(running_date, core, date_from)
    bootstrap_droit_analytics(running_date, core, date_from)
    bootstrap_creneau_analytics(running_date, core, date_from)
    update_date_from(running_date)


@analytics_manager.option('-c', '--core', help='url for the solr core')
def drop(core=None):
    solr = connect_to_solr(core)
    solr.delete(q='doc_type:rendez_vous_annule')
    solr.delete(q='doc_type:rendez_vous_honore')
    solr.delete(q='doc_type:RendezVousOuvert')
    solr.delete(q='doc_type:rendez_vous_ouvert')
    solr.delete(q='doc_type:rendez_vous_pris_spa')
    solr.delete(q='doc_type:droit_cree')
    solr.delete(q='doc_type:on_error_pa_realise')
    solr.delete(q='doc_type:on_pa_realise')
    solr.delete(q='doc_type:rendez_vous_pris_gu')
    solr.delete(q='doc_type:rendez_vous_supprime')
    last_run = AnalyticDate.objects()
    if not last_run:
        return
    last_run[0].delete()
