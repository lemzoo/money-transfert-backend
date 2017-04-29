from flask import url_for
from sief.permissions import POLICIES as p
from core import CoreResource, view_util
from sief.model.impression import ImpressionDocument


class ImpressionSchema(view_util.BaseModelSchema):
    _links = view_util.fields.Method('get_links')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_links(self, obj):
        route = url_for("ImpressionAPI")
        links = {'self': route}
        return links

    class Meta:
        model = ImpressionDocument
        model_fields_kwargs = {'id': {'load_only': True},
                               '_updated': {'load_only': True},
                               '_version': {'load_only': True}
                               }

impression_schema = ImpressionSchema()


class ImpressionAPI(CoreResource):

    @p.demande_asile.voir.require(http_exception=403)
    def get(self):
        doc = ImpressionDocument.objects().first()
        if not doc:
            doc = ImpressionDocument()
            doc.save()
        doc.controller.get_printing_id()
        doc.controller.save_or_abort(if_match=True)

        return impression_schema.dump(doc).data, 200
