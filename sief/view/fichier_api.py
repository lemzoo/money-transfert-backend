from flask import request, url_for, make_response, current_app
from werkzeug import secure_filename
from flask.ext.restful import Resource
from datetime import datetime

from core.tools import get_search_urlargs, abort
from core.auth import current_user, encode_token, decode_token
from core import CoreResource, view_util
from sief.model.fichier import Fichier
from sief.permissions import POLICIES as p


def get_fichier_data_url(item_id):
    """Return the url with signature to access the given fichier's data"""
    signature = encode_token({
        'exp': datetime.utcnow().timestamp() + current_app.config['FICHIER_URL_VALIDITY'],
        'type': 'fichier',
        'id': str(item_id)
    })
    return '%s?signature=%s' % (url_for('FichierDataAPI', item_id=item_id), signature)


def link_builder(obj):
    """
    url builder for the Fichier document references
    """
    return {
        'self': url_for('FichierAPI', item_id=obj.pk),
        'data': get_fichier_data_url(obj.pk),
        'name': obj.name
    }
Fichier.set_link_builder(link_builder)


class FichierSchema(view_util.BaseModelSchema):
    _links = view_util.fields.Method('get_links')

    def get_links(self, obj):
        route = url_for("FichierAPI", item_id=obj.pk)
        links = {'self': route,
                 'data': get_fichier_data_url(obj.pk),
                 'parent': url_for("FichierListAPI")}
        if p.fichier.gerer.can():
            links['delete'] = route
        return links

    class Meta:
        model = Fichier


fichier_schema = FichierSchema()


class FichierDataAPI(Resource):

    def get(self, item_id):
        """
        Given files are related with various resources, we can't precisely
        determine their access rules.
        Instead the request must come with a signature which as been provided
        by the in the HATEOAS link of the resource related to this file.
        """
        signature = request.args.get('signature')
        if not signature:
            abort(403)
        decoded = decode_token(signature)
        if (not decoded or decoded['type'] != 'fichier' or
                decoded['id'] != str(item_id)):
            abort(403)
        fichier = Fichier.objects.get_or_404(id=item_id)
        response = make_response(fichier.data.read())
        response.mimetype = fichier.data.content_type or ''
        # response.headers['Content-Type'] = fichier.data.content_type
        response.headers["Content-Disposition"] = "attachment; filename=%s" % fichier.name
        return response


class FichierAPI(CoreResource):

    @p.fichier.gerer.require(http_exception=403)
    def get(self, item_id):
        fichier = Fichier.objects.get_or_404(id=item_id)
        return fichier_schema.dump(fichier).data

    @p.fichier.gerer.require(http_exception=403)
    def delete(self, item_id):
        fichier = Fichier.objects.get_or_404(id=item_id)
        fichier.data.delete()
        fichier.delete()
        return {}, 204


class FichierListAPI(CoreResource):

    @staticmethod
    def _allowed_file(filename):
        return ('.' in filename and filename.rsplit('.', 1)[1].lower() in
                current_app.config['FICHIERS_ALLOWED_EXTENSIONS'])

    def get(self):
        urlargs = get_search_urlargs()
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            # No need to use the searcher module
            fichiers = Fichier.objects().paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            fichiers = Fichier.search_or_abort(**urlargs)
        route = url_for('FichierListAPI')
        links = {'root': url_for('RootAPI'), 'create': route,
                 'self': url_for('FichierListAPI')}
        # Basic users cannot list the files for security reasons
        if not p.fichier.gerer.can():
            return {'_links': links}
        return view_util.PaginationSerializer(fichier_schema, route).dump(
            fichiers, links=links).data

    def post(self):
        # Everybody can create files
        file_ = request.files['file']
        if file_:
            filename = secure_filename(file_.filename)
            fichier = Fichier(name=filename, author=current_user.id)
            fichier.data.put(file_,
                             content_type=file_.content_type or 'application/octet-stream')
            fichier.controller.save_or_abort()
            return fichier_schema.dump(fichier).data, 201
        return {'_error': 'No file provided'}, 400
