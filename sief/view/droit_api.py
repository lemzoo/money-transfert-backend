from flask import request, url_for
from marshmallow import post_dump

from core.tools import get_search_urlargs, abort, check_if_match, Export
from core.auth import current_user
from core import CoreResource, view_util
from sief.permissions import POLICIES as p
from sief.events import EVENTS as e
from sief.model.droit import Droit
from sief.model.demande_asile import DemandeAsile

from sief.view.usager_api import usager_schema
from sief.view.demande_asile_api import demande_asile_schema


class DroitSchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        route = url_for("DroitAPI", item_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("DroitListAPI")}
        if p.droit.retirer.can():
            links['retirer'] = route
        if p.droit.support.creer.can():
            links['support_create'] = url_for("DroitSupportsAPI", item_id=obj.pk)
        if p.historique.voir.can():
            links['history'] = url_for("DroitHistoryListAPI", origin_id=obj.pk)
        return links

    @post_dump
    def add_annuler_support_links(self, data):
        if p.droit.support.annuler:
            for dumped_support in data.get('supports', []):
                dumped_support['_links'] = {
                    'annuler': url_for('DroitAnnulerSupportAPI', droit_id=data['id'],
                                       numero_serie=dumped_support['numero_serie'])
                }

    class Meta:
        model = Droit
        model_fields_kwargs = {'agent_createur': {'dump_only': True},
                               'supports': {'dump_only': True},
                               'motif_retrait_autorisation_travail': {'dump_only': True},
                               'date_retrait_attestation': {'dump_only': True},
                               'date_notification_retrait_attestation': {'dump_only': True},
                               'motif_retrait_attestation': {'dump_only': True},
                               'demande_origine': {'required': True}}


class DroitSitesRattachesSchema(view_util.BaseModelSchema):

    class Meta:
        model = Droit
        fields = ('sites_rattaches', )


class DroitPrefectureRattacheeSchema(view_util.BaseModelSchema):

    class Meta:
        model = Droit
        fields = ('prefecture_rattachee', )

droit_schema = DroitSchema()
droit_sites_rattaches_schema = DroitSitesRattachesSchema()
droit_prefecture_rattachee_schema = DroitPrefectureRattacheeSchema()


def _check_prefecture_rattachee(prefecture_rattachee):
    if not p.droit.prefecture_rattachee.sans_limite.can():
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        if getattr(user_site, 'autorite_rattachement', user_site) != prefecture_rattachee:
            abort(403, "Prefecture de rattachement invalide")


def _prefecture_rattachee_lookup(solr=False, overall=False):
    if p.droit.prefecture_rattachee.sans_limite.can() or overall:
        if solr:
            return []
        else:
            return {}
    else:
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        pref = getattr(user_site, 'autorite_rattachement', user_site)
        if solr:
            return ['prefecture_rattachee:%s' % str(pref.pk)]
        else:
            return {'prefecture_rattachee': pref}


def lazy_create_droit(**kwargs):
    """
    Create a droit and check it validity, but don't save it in database
    """
    droit = Droit(**kwargs)
    droit.validate(clean=True)

    def lazy_builder():
        droit.save(validate=False)
        droit_dump = droit_schema.dump(droit).data
        e.droit.cree.send(droit=droit_dump)
        return droit, droit_dump

    return lazy_builder


class DroitAnnulerSupportAPI(CoreResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class AnnulerSupportSchema(view_util.UnknownCheckedSchema):

            def make_object(self, data):
                return data

            class Meta:
                model = Droit.supports.field.document_type_obj
                fields = ('motif_annulation',)

        self._annuler_support_schema = AnnulerSupportSchema()

    @p.droit.support.annuler.require(http_exception=403)
    def post(self, droit_id, numero_serie):
        droit = Droit.objects.get_or_404(id=droit_id)
        _check_prefecture_rattachee(droit.prefecture_rattachee)
        if_match = check_if_match(droit)
        support = None
        for support in droit.supports:
            if support.numero_serie == numero_serie:
                break
        if not support:
            abort(404)
        payload = request.get_json()
        data, errors = self._annuler_support_schema.load(payload)
        if errors:
            abort(400, **errors)
        support.motif_annulation = data.get('motif_annulation')
        droit.controller.save_or_abort(if_match=if_match)
        droit_dump = droit_schema.dump(droit).data
        support_dump = next(s for s in droit['supports']
                            if s['numero_serie'] == numero_serie)
        e.droit.support.annule.send(droit=droit_dump,
                                    support=support_dump,
                                    payload=payload)
        return droit_dump


class DroitSupportsAPI(CoreResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class CreerSupportSchema(view_util.UnknownCheckedSchema):

            def make_object(self, data):
                return data

            class Meta:
                model = Droit.supports.field.document_type_obj
                fields = ('date_delivrance', 'lieu_delivrance')

        self._creer_support_schema = CreerSupportSchema()

    @p.droit.support.creer.require(http_exception=403)
    def post(self, item_id):
        droit = Droit.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(droit.prefecture_rattachee)
        if_match = check_if_match(droit)
        payload = request.get_json()
        data, errors = self._creer_support_schema.load(payload)
        if errors:
            abort(400, **errors)

        #  Disable no asking rule
        # if droit.date_fin_validite < datetime.utcnow():
        #    abort(400, "Un droit en fin de validité ne peut plus avoir"
        #               "de nouveau support")
        support = droit.controller.creer_support(
            agent_editeur=current_user._get_current_object(), **data)
        droit.controller.save_or_abort(if_match=if_match)
        droit_dump = droit_schema.dump(droit).data
        support_dump = next(s for s in droit_dump['supports']
                            if s['numero_serie'] == support.numero_serie)
        e.droit.support.cree.send(usager=usager_schema.dump(droit.usager).data,
                                  droit=droit_dump,
                                  support=support_dump,
                                  demande_asile=demande_asile_schema.dump(
                                      droit.demande_origine).data,
                                  payload=payload)
        return droit_dump


class DroitAPI(CoreResource):

    @p.droit.voir.require(http_exception=403)
    def get(self, item_id):
        droit = Droit.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(droit.prefecture_rattachee)
        return droit_schema.dump(droit).data


class DroitRetraitAPI(CoreResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        class DroitAnnulerSchema(view_util.BaseModelSchema):

            class Meta:
                model = Droit
                fields = ('motif_retrait_autorisation_travail',
                          'date_retrait_attestation',
                          'date_notification_retrait_attestation',
                          'motif_retrait_attestation')
        self._droit_annuler_schema = DroitAnnulerSchema()

    @p.droit.retirer.require(http_exception=403)
    def post(self, item_id):
        droit = Droit.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(droit.prefecture_rattachee)
        if_match = check_if_match(droit)
        if droit.date_retrait_attestation:
            abort(400, "Droit déjà retiré")
        payload = request.get_json()
        droit, errors = self._droit_annuler_schema.update(droit, payload)
        if errors:
            abort(400, **errors)
        droit.controller.save_or_abort(if_match=if_match)
        droit_dump = droit_schema.dump(droit).data
        e.droit.retire.send(droit=droit_dump, payload=payload)
        return droit_dump

    @p.droit.retirer.require(http_exception=403)
    def patch(self, item_id):
        droit = Droit.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(droit.prefecture_rattachee)
        if_match = check_if_match(droit)
        if not droit.date_retrait_attestation:
            abort(400, "Le droit doit déjà être retiré pour utiliser cette route")
        payload = request.get_json()
        droit, errors = self._droit_annuler_schema.update(droit, payload)
        if errors:
            abort(400, **errors)
        droit.controller.save_or_abort(if_match=if_match)
        droit_dump = droit_schema.dump(droit).data
        return droit_dump


class DroitListAPI(CoreResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = view_util.PaginationSerializer(
            droit_schema, url_for('DroitListAPI'))

    @p.droit.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        overall = 'overall' in request.args
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            lookup = _prefecture_rattachee_lookup(overall=overall)
            # No need to use the searcher module
            users = Droit.objects(**lookup).paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            urlargs['fq'] += _prefecture_rattachee_lookup(solr=True, overall=overall)
            users = Droit.search_or_abort(**urlargs)
        links = {'root': url_for('RootAPI')}
        if p.droit.creer.can():
            links['create'] = url_for('DroitListAPI')
        return self._serializer.dump(users, links=links).data

    @p.droit.creer.require(http_exception=403)
    def post(self):
        payload = request.get_json()
        droit, errors = droit_schema.load(payload)
        if errors:
            abort(400, **errors)
        da = droit.demande_origine
        if da.decisions_attestation:
            for decision in reversed(da.decisions_attestation):
                if (decision.type_document == droit.type_document and
                        decision.sous_type_document == droit.sous_type_document):
                    if decision.delivrance:
                        break
                    else:
                        abort(
                            400, "Derniere decision sur attestation non favorable a la délivrance d'un droit")
        droit.agent_createur = current_user._get_current_object()
        droit.controller.save_or_abort()
        droit_dump = droit_schema.dump(droit).data
        e.droit.cree.send(droit=droit_dump, payload=payload)
        return droit_dump, 201


class Droit_PrefectureRattachee_API(CoreResource):

    @p.droit.voir.require(http_exception=403)
    def get(self, item_id):
        droit = Droit.objects.get_or_404(id=item_id)
        return droit_prefecture_rattachee_schema.dump(droit).data


class Droit_ExportAPI(CoreResource):

    @p.droit.export.require(http_exception=403)
    def get(self):
        exporter = Export(Droit)
        return exporter.csv_format(['demande_origine', 'type_origine', 'type_document',
                                    'sous_type_document', 'date_debut_validite', 'date_fin_validite',
                                    'autorisation_travail', 'pourcentage_duree_travail_autorise',
                                    'date_retrait_attestation',
                                    'date_notification_retrait_attestation', 'motif_retrait_attestation',
                                    'prefecture_rattachee', 'date_decision_sur_attestation', 'supports'],
                                   get_search_urlargs(),
                                   url_for('Droit_ExportAPI'), attribute_to_exclude_by_field={'supports': ['agent_editeur', 'numero_serie']}), 200
