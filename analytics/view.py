from core import CoreResource
import json
from os import environ
from analytics.manager import connect_to_solr
from sief.permissions import POLICIES as p
from flask import request


def extract_solr_params():
    urlargs = request.args
    filter_queries = []
    params = {}
    for key in urlargs:
        if key == 'rows':
            params['rows'] = urlargs[key]
        elif key == 'sort':
            params['sort'] = urlargs[key]
        elif key == 'facet':
            params['facet'] = urlargs[key]
        elif key == 'facet_fields':
            params['facet.field'] = urlargs.getlist(key)
        elif key == 'facet.pivot':
            params['facet.pivot'] = urlargs[key]
        elif key == 'facet.range':
            params['facet.range'] = urlargs[key]
        elif key == 'facet.range.start':
            params['facet.range.start'] = urlargs[key]
        elif key == 'facet.range.end':
            params['facet.range.end'] = urlargs[key]
        elif key == 'facet.range.gap':
            params['facet.range.gap'] = urlargs[key]
        elif key == 'start':
            params['start'] = urlargs[key]
        elif key == 'group':
            params['group'] = urlargs[key]
        elif key == 'group.limit':
            params['group.limit'] = urlargs[key]
        elif key == 'group.query':
            params['group.query'] = urlargs.getlist(key)
        else:
            filter_queries.extend(urlargs.getlist(key))
    params['fq'] = filter_queries
    return params


class AnalyticsAPI(CoreResource):

    @p.analytics.voir.require(http_exception=403)
    def get(self):
        url = environ.get('SOLR_URL_ANALYTICS')
        params = extract_solr_params()
        results = connect_to_solr(url).search(q='*', **params)
        documents = json.dumps(results, default=lambda o: o.__dict__)
        return documents
