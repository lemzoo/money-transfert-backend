from flask import url_for

from core.tools import get_search_urlargs
from core import CoreResource, view_util

from sief.model.referentials import (LangueIso6392, LangueOfpra, Nationalite,
                                     Pays, CodeInseeAGDREF)
from sief.cache import cached_from_config


def _build_api(document_cls):
    endpoint = '%sAPI' % document_cls.__name__
    endpoint_list = '%sListAPI' % document_cls.__name__

    class RefSchema(view_util.UnknownCheckedSchema):
        _links = view_util.fields.Method('get_links', dump_only=True)
        id = view_util.fields.String(attribute='code', dump_only=True)

        def get_links(self, obj):
            return {'self': url_for(endpoint, ref_pk=obj.pk),
                    'parent': url_for(endpoint_list)}

        class Meta:
            model = document_cls

    schema = RefSchema()

    class Api(CoreResource):

        @cached_from_config('REFERENTIALS_CACHE_TIMEOUT')
        def get(self, ref_pk):
            ref = document_cls.objects.get_or_404(pk=ref_pk)
            return schema.dump(ref).data

    class ListApi(CoreResource):

        @cached_from_config('REFERENTIALS_CACHE_TIMEOUT')
        def get(self):
            urlargs = get_search_urlargs()
            if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
                # No need to use the searcher module
                refs = document_cls.objects.paginate(
                    page=urlargs['page'], per_page=urlargs['per_page'])
            else:
                refs = document_cls.search_or_abort(**urlargs)
            route = url_for(endpoint_list)
            links = {'parent': url_for('RootReferentialsAPI')}
            return view_util.PaginationSerializer(schema, route).dump(
                refs, links=links).data

    return Api, endpoint, ListApi, endpoint_list


def register_referentials(api, base_route):
    root_endpoints = {'root': 'RootAPI'}
    for document_cls, name in [(Nationalite, "nationalites"),
                               (Pays, "pays"),
                               (LangueOfpra, "langues_OFPRA"),
                               (CodeInseeAGDREF, "insee_agdref"),
                               (LangueIso6392, "langues_iso639_2")]:
        route = '%s/%s' % (base_route, name)
        single_api, endpoint, list_api, endpoint_list = _build_api(document_cls)
        api.add_resource(single_api, '%s/<string:ref_pk>' % route,
                         endpoint=endpoint)
        api.add_resource(list_api, route, endpoint=endpoint_list)
        root_endpoints[name] = endpoint_list

    class RootReferentialsAPI(CoreResource):

        def get(self):
            return {'_links': {k: url_for(v) for k, v in root_endpoints.items()}}

    api.add_resource(RootReferentialsAPI, base_route)
