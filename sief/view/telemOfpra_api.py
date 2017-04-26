from flask import request, url_for

from core import CoreResource, view_util
from core.tools import get_search_urlargs, abort
from sief.model.telemOfpra import TelemOfpra
from sief.permissions import POLICIES as p
from sief.events import EVENTS as e


class TelemOfpraSchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        route = url_for("TelemOfpraListApi")
        links = {'self': route, 'root': url_for('RootAPI')}
        return links

    class Meta:
        model = TelemOfpra

telemOfpra_schema = TelemOfpraSchema()


class TelemOfpraListApi(CoreResource):

    @p.telemOfpra.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            # No need to use the searcher module
            tOfpras = TelemOfpra.objects().paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            tOfpras = TelemOfpra.search_or_abort(**urlargs)
        route = url_for('TelemOfpraListApi')
        links = {'root': url_for('RootAPI'), 'create': route,
                 'self': url_for('TelemOfpraListApi')}
        return view_util.PaginationSerializer(telemOfpra_schema, route).dump(
            tOfpras, links=links).data

    @p.telemOfpra.creer.require(http_exception=403)
    def post(self):
        payload = request.get_json()
        tOfpra, errors = telemOfpra_schema.load(payload)
        if errors:
            abort(400, **errors)
        tOfpra.controller.save_or_abort()
        tOfpra_dump = telemOfpra_schema.dump(tOfpra).data
        e.telemOfpra.cree.send(telemOfpra=tOfpra_dump, payload=payload)
        return tOfpra_dump, 201
