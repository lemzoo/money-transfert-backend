from flask import request, url_for
from datetime import timedelta
from mongoengine import ValidationError as MongoValidationError
from marshmallow import ValidationError as MarshValidationError

from core.tools import (get_pagination_urlargs, abort,
                        list_to_pagination, check_if_match, get_search_urlargs)
from core.auth import current_user
from core import CoreResource, view_util
from sief.model.site import Site, Creneau
from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class CreneauSchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        links = {'self': url_for("CreneauAPI", site_id=obj.site.pk,
                                 creneau_id=obj.pk),
                 'parent': url_for("CreneauListAPI", site_id=obj.site.pk)}
        return links

    class Meta:
        model = Creneau
        model_fields_kwargs = {'document_linked': {'dump_only': True}}


class CreneauAPI(CoreResource):

    @p.site.voir.require(http_exception=403)
    def get(self, site_id, creneau_id):
        creneau = Creneau.objects.get_or_404(pk=creneau_id)
        return CreneauSchema().dump(creneau).data

    @p.site.creneaux.gerer.require(http_exception=403)
    def delete(self, site_id, creneau_id):
        creneau = Creneau.objects.get_or_404(pk=creneau_id)
        if not p.site.sans_limite_site_affecte.can():
            current_site_affecte = current_user.controller.get_current_site_affecte()
            if not current_site_affecte or current_site_affecte.pk != creneau.site.pk:
                abort(403)
        if creneau.reserve:
            abort(400, 'Impossible de supprimer un créneau déjà reservé')
        creneau.delete()
        e.site.creneaux.supprime.send(site_id=site_id, id=creneau_id)
        return {}, 204


class RendezVousAPI(CoreResource):

    @p.site.rendez_vous.gerer.require(http_exception=403)
    def _check_access(self, site_id):
        current_site_affecte = current_user.controller.get_current_site_affecte()
        if not current_site_affecte or site_id != current_site_affecte.pk:
            abort(403, 'Seuls les rendez-vous du site_affecte peuvent être gérés')

    def delete(self, site_id, creneau_id):
        self._check_access(site_id)
        # Release the rendez-vous
        creneau = Creneau.objects.get_or_404(pk=creneau_id)
        if_match = check_if_match(creneau)
        if not creneau.reserve:
            abort(400, 'Creneau déjà libéré')
        creneau.controller.liberer()
        creneau.controller.save_or_abort(if_match=if_match)
        return CreneauSchema().dump(creneau).data

    def put(self, site_id, creneau_id):
        self._check_access(site_id)
        errors = {}
        payload = request.get_json()
        # TODO: replace by GenericReferenceField
        doc_cls_name = payload.pop('document_type', None)
        doc_id = payload.pop('document_id', None)
        if not doc_cls_name:
            errors['document_type'] = 'Champ requis'
        if not doc_id:
            errors['document_id'] = 'Champ requis'
        for field in payload:
            errors[field] = 'Champ inconnu'
        if errors:
            abort(400, **errors)
        creneau = Creneau.objects.get_or_404(pk=creneau_id)
        if_match = check_if_match(creneau)
        if creneau.reserve:
            abort(400, 'Creneau déjà reservé')
        doc_cls = next((c for c in Creneau.document_lie.choices
                        if c.__name__ == doc_cls_name), None)
        if not doc_cls:
            abort(400, document_type='Seul les document %s sont acceptés' %
                  [d.__name__ for d in Creneau.document_lie.choices])
        try:
            doc = doc_cls.objects.get(pk=doc_id)
        except (MongoValidationError, doc_cls.DoesNotExist):
            abort(400, document_id='Document invalide')
        creneau.controller.reserver(doc)
        creneau.controller.save_or_abort(if_match=if_match)
        return CreneauSchema().dump(creneau).data


def _validate_positive(value):
    if value < 0:
        raise MarshValidationError('valeur positive attendue')


class PlageSchema(view_util.UnknownCheckedSchema):
    plage_debut = view_util.fields.DateTime(required=True)
    plage_fin = view_util.fields.DateTime(required=True)
    plage_guichets = view_util.fields.Integer(validate=_validate_positive, required=True)
    duree_creneau = view_util.fields.Integer(validate=_validate_positive, required=True)
    marge = view_util.fields.Integer(validate=_validate_positive)
    marge_initiale = view_util.fields.StrictBoolean()

    class Meta:
        model_build_obj = False


class CreneauListAPI(CoreResource):

    @staticmethod
    def _can_post(site):
        current_site_affecte = current_user.controller.get_current_site_affecte()
        if (p.site.creneaux.gerer.can() and
                (p.site.sans_limite_site_affecte.can() or
                    (current_site_affecte and current_site_affecte.pk == site.pk))):
            return True
        return False

    @p.site.voir.require(http_exception=403)
    def get(self, site_id):
        urlargs = get_search_urlargs()
        page, per_page = get_pagination_urlargs()
        site = Site.objects.get_or_404(id=site_id)
        if not hasattr(site.controller, 'get_creneaux'):
            abort(404)
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            creneaux = site.controller.get_creneaux().paginate(page=page, per_page=per_page)
        else:
            if not urlargs['fq']:
                urlargs['fq'] = []
            if not 'site:{}'.format(site_id) in urlargs['fq']:
                urlargs['fq'].append('site:{}'.format(site_id))
            creneaux = Creneau.search_or_abort(**urlargs)
        route = url_for('CreneauListAPI', site_id=site_id)
        links = {'site': url_for('SiteAPI', item_id=site_id)}
        if self._can_post(site) and not site.date_fermeture:
            links['create'] = route
        return view_util.PaginationSerializer(CreneauSchema(), route).dump(
            creneaux, links=links).data

    def post(self, site_id):
        site = Site.objects.get_or_404(id=site_id)
        if not hasattr(site.controller, 'add_creneaux'):
            abort(404)
        if not self._can_post(site):
            abort(403)
        if site.date_fermeture:
            abort(400, 'Impossible de créer des creneaux dans un site fermé')
        payload = request.get_json()
        unmarshalled = PlageSchema().load(payload)
        if unmarshalled.errors:
            abort(400, **unmarshalled.errors)
        creneaux = []
        try:
            creneaux = site.controller.add_creneaux(
                plage_start=unmarshalled.data['plage_debut'],
                plage_end=unmarshalled.data['plage_fin'],
                duration=timedelta(minutes=unmarshalled.data['duree_creneau']),
                desks=unmarshalled.data['plage_guichets'],
                marge=unmarshalled.data.get('marge'),
                marge_initiale=unmarshalled.data.get('marge_initiale', False)
            )
        except ValueError as exc:
            abort(400, str(exc))
        route = url_for('CreneauListAPI', site_id=site_id)
        links = {'create': route, 'site': url_for('SiteAPI', item_id=site_id)}
        pagination = list_to_pagination(creneaux)
        e.site.creneaux.cree.send(creneaux=[c.pk for c in creneaux],
                                  site_id=site_id, **payload)
        return view_util.PaginationSerializer(CreneauSchema(), route).dump(
            pagination, links=links).data, 201

    @p.site.creneaux.gerer.require(http_exception=403)
    def delete(self, site_id):
        if not p.site.sans_limite_site_affecte.can():
            current_site_affecte = current_user.controller.get_current_site_affecte()
            if not current_site_affecte or current_site_affecte.pk != site_id:
                abort(403)
        date_debut = request.args.get('date_debut')
        date_fin = request.args.get('date_fin')
        if date_debut is None or date_fin is None:
            abort(400, "date_debut et date_fin sont obligatoires")
        creneaux = Creneau.objects(site=site_id, reserve=False,
                                   date_debut__gte=date_debut,
                                   date_fin__lte=date_fin)
        creneaux.delete()
        return {}, 204
