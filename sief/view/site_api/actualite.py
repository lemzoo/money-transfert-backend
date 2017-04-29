from flask import request, url_for
from datetime import datetime

from core.tools import get_pagination_urlargs, abort
from core import CoreResource, view_util
from sief.model.site import SiteActualite
from sief.permissions import POLICIES as p
from sief.view.site_api.site import check_site_affecte


class SiteActualiteSchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        route = url_for("SiteActualiteAPI", site_id=obj.site.pk, actualite_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("SiteActualiteListAPI", site_id=obj.site.pk),
                 'site': url_for("SiteAPI", item_id=obj.site.pk)}
        if not obj.cloturee:
            links['cloturer'] = route
        return links

    class Meta:
        model = SiteActualite


class SiteActualiteAPI(CoreResource):

    @p.site.actualite.gerer.require(http_exception=403)
    def get(self, site_id, actualite_id):
        check_site_affecte(site_id)
        actualite = SiteActualite.objects.get_or_404(site=site_id, pk=actualite_id)
        return SiteActualiteSchema().dump(actualite).data

    @p.site.actualite.gerer.require(http_exception=403)
    def delete(self, site_id, actualite_id):
        check_site_affecte(site_id)
        actualite = SiteActualite.objects.get_or_404(site=site_id, pk=actualite_id)
        if actualite.cloturee:
            abort(400, 'Actualité déjà cloturée')
        actualite.cloturee = datetime.utcnow()
        actualite.controller.save_or_abort()
        return SiteActualiteSchema().dump(actualite).data


class SiteActualiteListAPI(CoreResource):

    @p.site.actualite.gerer.require(http_exception=403)
    def get(self, site_id):
        check_site_affecte(site_id)
        page, per_page = get_pagination_urlargs()
        filters = {}
        if request.args.get('skip_cloturee', 'true').lower() == 'true':
            filters['__raw__'] = {'$or': ({'cloturee': {'$exists': False}},
                                          {'cloturee': {'$eq': None}})}
        actualites = SiteActualite.objects(site=site_id, **filters).order_by(
            '+doc_created').paginate(page=page, per_page=per_page)
        route = url_for('SiteActualiteListAPI', site_id=site_id)
        links = {'site': url_for('SiteAPI', item_id=site_id)}
        return view_util.PaginationSerializer(
            SiteActualiteSchema(), route).dump(actualites, links=links).data
