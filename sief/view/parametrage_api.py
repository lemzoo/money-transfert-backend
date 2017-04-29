from flask import request, url_for

from core import CoreResource, view_util
from core.tools import check_if_match
from sief.model.parametrage import Parametrage
from sief.permissions import POLICIES as p


class ParametrageSchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        route = url_for("ParametrageApi")
        links = {'self': route, 'root': url_for('RootAPI')}
        if p.parametrage.gerer.can():
            links['update'] = route
        return links

    class Meta:
        model = Parametrage
        model_fields_kwargs = {'id': {'dump_only': True, 'load_only': True}}


param_schema = ParametrageSchema()


class ParametrageApi(CoreResource):

    def get(self):
        param = Parametrage.get_singleton()
        return param_schema.dump(param).data

    @p.parametrage.gerer.require(http_exception=403)
    def patch(self):
        param = Parametrage.get_singleton()
        if_match = check_if_match(param)
        param_schema.update(param, request.get_json())
        param.controller.save_or_abort(if_match=if_match)
        return param_schema.dump(param).data
