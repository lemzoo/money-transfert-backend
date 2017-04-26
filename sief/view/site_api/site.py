from flask import request, url_for

from core.tools import check_if_match, abort, list_to_pagination, get_search_urlargs, Export
from core.auth import current_user
from core import CoreResource, view_util
from sief.model.site import Site, StructureAccueil, GU, Prefecture, EnsembleZonal, Creneau
from sief.model.utilisateur import Utilisateur
from sief.view.site_api.creneau import CreneauListAPI
from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


Site.set_link_builder_from_api('SiteAPI')
StructureAccueil.set_link_builder_from_api('SiteAPI')
GU.set_link_builder_from_api('SiteAPI')
Prefecture.set_link_builder_from_api('SiteAPI')
EnsembleZonal.set_link_builder_from_api('SiteAPI')


def check_site_affecte(site_id):
    if not p.site.sans_limite_site_affecte.can():
        current_site_affecte = current_user.controller.get_current_site_affecte()
        if (not current_site_affecte or current_site_affecte.pk != site_id):
            abort(403, 'Vous n''avez pas le bon site affecté')


def creneau_link_builder(obj):
    return {'self': url_for('CreneauAPI', site_id=obj.site.pk, creneau_id=obj.pk)}


Creneau.set_link_builder(creneau_link_builder)


class ModeleSchema(view_util.UnknownCheckedSchema):

    class Meta:
        model = GU.modeles.field.document_type_obj


class SiteSchema(view_util.BaseModelSchema):
    type = view_util.fields.Function(
        lambda obj: obj._class_name.split('.')[-1], dump_only=True)

    def get_links(self, obj):
        route = url_for("SiteAPI", item_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("SiteListAPI")}
        if (hasattr(obj.controller, 'add_creneaux') and
                CreneauListAPI._can_post(obj)):
            links['creneaux'] = url_for("CreneauListAPI", site_id=obj.pk)
        if p.site.modifier.can():
            links['update'] = route
        if p.historique.voir.can():
            links['history'] = url_for("SiteHistoryListAPI", origin_id=obj.pk)
        return links


class StructureAccueilSchema(SiteSchema):

    class Meta:
        model = StructureAccueil


class GUSchema(SiteSchema):

    def get_links(self, obj):
        links = super().get_links(obj)
        links['modeles'] = url_for('SiteModelesAPI', site_id=obj.pk)
        return links

    class Meta:
        model = GU
        model_fields_kwargs = {'modeles': {'dump_only': True, 'load_only': True}}


class PrefectureSchema(SiteSchema):

    class Meta:
        model = Prefecture


class EnsembleZonalSchema(SiteSchema):

    class Meta:
        model = EnsembleZonal


def _schema_router(item):
    """Retreive the associated schema from the mongoengine document"""
    if isinstance(item, Prefecture):
        return PrefectureSchema()
    elif isinstance(item, GU):
        return GUSchema()
    elif isinstance(item, StructureAccueil):
        return StructureAccueilSchema()
    elif isinstance(item, EnsembleZonal):
        return EnsembleZonalSchema()
    else:
        # keep more generic last, should not be used in theory
        return SiteSchema()


def _check_address_fields(payload):
    error = {}
    if payload.get('adresse_inconnue', False):
        error["adresse_inconnue"] = "Not a valid choice."
    if not payload.get('voie'):
        error["voie"] = "Missing data for required field."
    if not payload.get('ville'):
        error["ville"] = "Missing data for required field."
    return error


class SiteModelesAPI(CoreResource):

    def _modeles_dump(self, site):
        links = {'site': url_for('SiteAPI', item_id=site.id)}
        route = url_for('SiteModelesAPI', site_id=site.id)
        modeles = list_to_pagination(site.modeles)
        return view_util.PaginationSerializer(
            ModeleSchema(), route).dump(modeles, links=links).data

    @p.site.modele.gerer.require(http_exception=403)
    def get(self, site_id):
        check_site_affecte(site_id)
        site = Site.objects.get_or_404(id=site_id)
        return self._modeles_dump(site)

    @p.site.modele.gerer.require(http_exception=403)
    def post(self, site_id):
        check_site_affecte(site_id)
        site = Site.objects.get_or_404(id=site_id)
        payload = request.get_json()
        modele, errors = ModeleSchema().load(payload)
        if errors:
            abort(400, **errors)
        # Check if modele.libelle field already exist
        for _modele in site.modeles:
            if _modele.libelle == modele.libelle:
                abort(400, {
                    "libelle": "Not a valid choice. Already use for another model: %s."
                    % _modele.type})
        site.modeles.append(modele)
        site.controller.save_or_abort()
        modeles_dump = self._modeles_dump(site)
        return modeles_dump, 201

    @p.site.modele.gerer.require(http_exception=403)
    def patch(self, site_id):
        check_site_affecte(site_id)
        site = Site.objects.get_or_404(id=site_id)
        payload = request.get_json()
        modele, errors = ModeleSchema().load(payload)
        if errors:
            abort(400, **errors)
        # Find modele to PATCH
        index = 0
        for index, _modele in enumerate(site.modeles):
            if _modele.libelle == modele.libelle:
                _modele.type = modele.type
                _modele.plages = modele.plages
                break
        else:
            abort(400, {"libelle": "Not a valid choice."})

        # If empty plage, we remove the modele
        if len(site.modeles[index].plages) == 0:
            site.modeles.pop(index)

        site.controller.save_or_abort()
        modeles_dump = self._modeles_dump(site)
        return modeles_dump, 201


class SiteAPI(CoreResource):

    @p.site.voir.require(http_exception=403)
    def get(self, item_id):
        site = Site.objects.get_or_404(id=item_id)
        return _schema_router(site).dump(site).data

    @p.site.modifier.require(http_exception=403)
    def patch(self, item_id):
        site = Site.objects.get_or_404(id=item_id)
        check_site_affecte(site.pk)
        if_match = check_if_match(site)
        payload = request.get_json()
        schema = _schema_router(site)
        if 'date_fermeture' in payload:
            if not p.site.fermer.can():
                abort(403)
        # If autorite_rattachement has been changed, we must update all
        # the utilisateurs linked with this site
        site_rattache_changed = 'autorite_rattachement' in payload
        site, errors = schema.update(site, payload)
        if errors:
            abort(400, **errors)
        # Only check adresse fields when we need
        errors = _check_address_fields(payload.get('adresse')) if 'adresse' in payload else None
        if errors:
            abort(400, {'adresse': errors})
        site.controller.save_or_abort(if_match=if_match)
        if site_rattache_changed:
            Utilisateur.objects(site_affecte=site).update(
                set__site_rattache=site.autorite_rattachement)
        data = schema.dump(site).data
        e.site.modifie.send(site=data, payload=payload)
        return data

    @p.site.fermer.require(http_exception=403)
    def delete(self, item_id, date_fermeture=None):
        site = Site.objects.get_or_404(id=item_id)
        check_site_affecte(site.pk)
        if_match = check_if_match(site)
        if not site.controller.close_site(date_fermeture):
            abort(400, 'Site déjà fermé')
        site.controller.save_or_abort(if_match=if_match)
        data = _schema_router(site).dump(site).data
        e.site.ferme.send(site=data, payload={'date_fermeture': site.date_fermeture})
        return data


class SiteListAPI(CoreResource):

    @p.site.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            # No need to use the searcher module
            sites = Site.objects.paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            sites = Site.search_or_abort(**urlargs)
        route = url_for('SiteListAPI')
        links = {'root': url_for('RootAPI')}
        if p.site.creer.can():
            links['create'] = route
        return view_util.PaginationSerializer(_schema_router, route).dump(
            sites, links=links).data

    @p.site.creer.require(http_exception=403)
    def post(self):
        payload = request.get_json()
        type = payload.pop('type', None)
        if type == 'Prefecture':
            schema = PrefectureSchema()
        elif type == 'GU':
            schema = GUSchema()
        elif type == 'StructureAccueil':
            schema = StructureAccueilSchema()
        elif type == 'EnsembleZonal':
            schema = EnsembleZonalSchema()
        else:
            abort(400, type="valeurs autorisées : `GU`, `Prefecture`,"
                  "`StructureAccueil` et `EnsembleZonal`")
        site, errors = schema.load(payload)
        if errors:
            abort(400, **errors)
        errors = _check_address_fields(payload.get('adresse', {}))
        if errors:
            abort(400, {'adresse': errors})
        site.controller.save_or_abort()
        e.site.cree.send(payload={'site': payload})
        return schema.dump(site).data, 201


class SiteExportAPI(CoreResource):

    @p.site.export.require(http_exception=403)
    def get(self):
        exporter = Export(Site)
        return exporter.csv_format(['id', 'doc_version', 'doc_updated', 'doc_created',
                                    '_cls', 'libelle', 'adresse', 'telephone', 'email',
                                    'date_fermeture', 'guichets_uniques', 'autorite_rattachement',
                                    'limite_rdv_jrs', 'code_departement'],
                                   get_search_urlargs(),
                                   url_for('SiteExportAPI')), 200
