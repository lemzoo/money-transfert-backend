from flask import request, url_for
from marshmallow_mongoengine import field_for
from marshmallow import post_load
from mongoengine import ValidationError as MongoValidationError
from datetime import datetime

from core.tools import abort, get_search_urlargs, check_if_match, Export, get_pagination_urlargs
from core.auth import current_user
from core import CoreResource, view_util
from sief.permissions import POLICIES as p
from sief.events import EVENTS as e
from sief.model.recueil_da import RecueilDA, RdvError, ExploiteError, DemandeursIdentifiesError
from sief.model.site import (
    Creneau, GU, StructureAccueil, CreneauReserverError, creneaux_multi_reserver)
from services.agdref import AGDREFNumberError, AGDREFConnectionError, AGDREFDisabled, AGDREFRequiredFieldsError


RecueilDA.set_link_builder_from_api('RecueilDAAPI')


class RecueilDASchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        route = url_for("RecueilDAAPI", item_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("RecueilDAListAPI")}
        if p.historique.voir.can():
            links['history'] = url_for("RecueilDAHistoryListAPI",
                                       origin_id=obj.pk)
        return links

    class Meta:
        model = RecueilDA
        model_fields_kwargs = {
            'prefecture_rattachee': {'dump_only': True},
            'statut': {'dump_only': True},
            'structure_guichet_unique': {'dump_only': True},
            'structure_accueil': {'dump_only': True},
            'agent_accueil': {'dump_only': True},
            'date_transmission': {'dump_only': True},
            'rendez_vous_gu': {'dump_only': True},
            'rendez_vous_gu_anciens': {'dump_only': True},
            'agent_enregistrement': {'dump_only': True},
            'date_enregistrement': {'dump_only': True},
            'agent_annulation': {'dump_only': True},
            'date_annulation': {'dump_only': True},
            'identifiant_famille_dna': {'dump_only': True},
        }
recueil_da_schema = RecueilDASchema()


class RecueilDA_Brouillon_Schema(RecueilDASchema):

    def get_links(self, obj):
        links = super().get_links(obj)
        if p.recueil_da.modifier_brouillon.can():
            links['replace'] = links['self']
            links['pa_realiser'] = url_for("RecueilDA_PARealise_API",
                                           item_id=obj.pk)
            links['delete'] = links['self']
        return links

    class Meta:
        model = RecueilDA
        fields = view_util.BaseModelSchema.BASE_FIELDS + (
            'usager_1', 'usager_2', 'enfants', 'statut', 'structure_accueil',
            'agent_accueil', 'profil_demande')


class RecueilDA_PARealise_Schema(RecueilDASchema):

    @post_load
    def set_statut(self, data):
        data.statut = 'PA_REALISE'
        data.date_transmission = datetime.utcnow()
        return data

    def get_links(self, obj):
        links = super().get_links(obj)
        if p.recueil_da.modifier_pa_realise.can():
            links['replace'] = links['self']
            links['identifier_demandeurs'] = url_for(
                "RecueilDA_DemandeursIdentifies_API", item_id=obj.pk)
            links['annuler'] = url_for("RecueilDA_Annule_API",
                                       item_id=obj.pk)
        if p.recueil_da.rendez_vous.gerer.can():
            if obj.rendez_vous_gu:
                links['rendez_vous_annuler'] = \
                    url_for("RecueilDA_RendezVous_API", item_id=obj.pk)
            else:
                links['rendez_vous_reserver'] = \
                    url_for("RecueilDA_RendezVous_API", item_id=obj.pk)
        return links

    class Meta:
        model = RecueilDA
        fields = RecueilDA_Brouillon_Schema.Meta.fields + (
            'structure_accueil', 'agent_accueil', 'date_transmission',
            'rendez_vous_gu', 'rendez_vous_gu_anciens', 'structure_guichet_unique',
            'identifiant_famille_dna')


class RecueilDA_DemandeursIdentifies_Schema(RecueilDASchema):

    def get_links(self, obj):
        links = super().get_links(obj)
        if p.recueil_da.modifier_demandeurs_identifies.can():
            links['replace'] = links['self']
            links['exploiter'] = url_for("RecueilDA_Exploite_API",
                                         item_id=obj.pk)
            links['annuler'] = url_for("RecueilDA_Annule_API",
                                       item_id=obj.pk)
        return links

    class Meta:
        model = RecueilDA
        fields = RecueilDA_PARealise_Schema.Meta.fields


class RecueilDA_Exploite_Schema(RecueilDASchema):

    def get_links(self, obj):
        links = super().get_links(obj)
        if p.recueil_da.modifier_exploite.can():
            links['replace'] = links['self']
        return links

    class Meta:
        model = RecueilDA
        fields = RecueilDA_PARealise_Schema.Meta.fields + (
            'agent_enregistrement', 'date_enregistrement')


class RecueilDA_Annule_Schema(RecueilDASchema):

    def get_links(self, obj):
        links = super().get_links(obj)
        if p.recueil_da.purger.can():
            links['purger'] = url_for("RecueilDA_Purge_API",
                                      item_id=obj.pk)
        return links

    class Meta:
        model = RecueilDA
        fields = RecueilDA_PARealise_Schema.Meta.fields + (
            'agent_annulation', 'date_annulation', 'motif_annulation')


class RecueilDA_Purge_Schema(RecueilDASchema):

    class Meta:
        model = RecueilDA
        fields = RecueilDA_Annule_Schema.Meta.fields


class RecueilDA_EnregistrementFamilleOFII_Schema(view_util.BaseModelSchema):

    class Meta:
        model = RecueilDA
        fields = ('identifiant_famille_dna', )


class RecueilDA_PrefectureRattachee_Schema(view_util.BaseModelSchema):

    class Meta:
        model = RecueilDA
        fields = ('prefecture_rattachee', )


recueil_da_prefecture_rattachee_schema = RecueilDA_PrefectureRattachee_Schema()


def _schema_router(recueil_da):
    """Retreive the associated schema from the mongoengine document"""
    if recueil_da.statut == "BROUILLON":
        return RecueilDA_Brouillon_Schema()
    elif recueil_da.statut == "PA_REALISE":
        return RecueilDA_PARealise_Schema()
    elif recueil_da.statut == "DEMANDEURS_IDENTIFIES":
        return RecueilDA_DemandeursIdentifies_Schema()
    elif recueil_da.statut == "EXPLOITE":
        return RecueilDA_Exploite_Schema()
    elif recueil_da.statut == "ANNULE":
        return RecueilDA_Annule_Schema()
    elif recueil_da.statut == "PURGE":
        return RecueilDA_Purge_Schema()
    else:
        raise ValueError('recueil_da `%s`: wrong statut `%s`'
                         % (recueil_da.pk, recueil_da.statut))


def _check_prefecture_rattachee(recueil_da):
    if not p.recueil_da.prefecture_rattachee.sans_limite.can():
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        if isinstance(user_site, StructureAccueil):
            if recueil_da.structure_accueil != user_site:
                abort(403, "Seule la structure d'accueil créatrice"
                           " est autorisée à accèder à ce recueil")
        elif getattr(user_site, 'autorite_rattachement', user_site) != recueil_da.prefecture_rattachee:
            abort(403, "Ce recueil dépend d'une autre préfecture")


def _prefecture_rattachee_lookup(solr=False):
    if p.recueil_da.prefecture_rattachee.sans_limite.can():
        if solr:
            return []
        else:
            return {}
    else:
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        if isinstance(user_site, StructureAccueil):
            field = 'structure_accueil'
            value = user_site
        else:
            field = 'prefecture_rattachee'
            value = getattr(user_site, 'autorite_rattachement', user_site)
        if solr:
            return ['%s:%s' % (field, value.pk)]
        else:
            return {field: value}


class RecueilDAAPI(CoreResource):

    @p.recueil_da.voir.require(http_exception=403)
    def get(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        return _schema_router(recueil_da).dump(recueil_da).data

    def put(self, item_id):
        if not current_user.controller.get_current_site_affecte():
            abort(400, "L'utilisateur doit avoir un site_affecte")
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if not ((recueil_da.statut == 'BROUILLON' and
                 p.recueil_da.modifier_brouillon.can()) or
                (recueil_da.statut == 'PA_REALISE' and
                 p.recueil_da.modifier_pa_realise.can()) or
                (recueil_da.statut == 'DEMANDEURS_IDENTIFIES' and
                 p.recueil_da.modifier_demandeurs_identifies.can()) or
                (recueil_da.statut == 'EXPLOITE' and
                 p.recueil_da.modifier_exploite.can())):
            abort(403)
        schema = _schema_router(recueil_da)
        payload = request.get_json()
        # We have to replace the document with the given payload,
        # To do that, we update the current document with the given payload,
        # then keep the READ_ONLY_FIELDS (i.g. id field) and set to None
        # the remaining ones
        prev_recueil = schema.dump(recueil_da).data
        recueil_da, errors = schema.update(recueil_da, payload)
        if errors:
            abort(400, **errors)
        READ_ONLY_FIELDS = ('id', 'doc_created', 'doc_version', 'statut', 'agent_annulation',
                            'date_annulation', 'motif_annulation', 'agent_enregistrement',
                            'date_enregistrement', 'date_transmission', 'agent_accueil',
                            'structure_accueil', 'rendez_vous_gu', 'rendez_vous_gu_anciens',
                            'structure_guichet_unique', 'prefecture_rattachee',
                            'identifiant_famille_dna')
        for field in recueil_da._fields:
            if field not in payload and field not in READ_ONLY_FIELDS:
                setattr(recueil_da, field, None)
        recueil_da.controller.save_or_abort(if_match=if_match)
        data = schema.dump(recueil_da).data
        e.recueil_da.modifie.send(
            prev_recueil_da=prev_recueil, current_recueil_da=data)
        return data

    @p.recueil_da.modifier_brouillon.require(http_exception=403)
    def delete(self, item_id):
        # Can only delete drafts
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if not recueil_da.statut == 'BROUILLON':
            abort(400, "Action autorisée qu'au statut BROUILLON")
        # TODO: delete linked fichiers as well ?
        recueil_da.delete()
        return {}, 204


class RecueilDAGenererEurodacAPI(CoreResource):

    @p.recueil_da.generer_eurodac.require(http_exception=403)
    def post(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        recueil_da.controller.generate_identifiant_eurodac()
        recueil_da.controller.save_or_abort()
        return _schema_router(recueil_da).dump(recueil_da).data


class RecueilDA_PARealise_API(CoreResource):

    @p.recueil_da.modifier_brouillon.require(http_exception=403)
    def post(self, item_id):

        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        try:
            recueil_da.controller.check_pa_realiser()
        except MongoValidationError as exc:
            error = exc.to_dict()
            abort(400, **error)

        recueil_da.controller.save_or_abort(if_match=if_match)
        data = _schema_router(recueil_da).dump(recueil_da).data
        return data

    @p.recueil_da.modifier_brouillon.require(http_exception=403)
    def put(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)

        payload = request.get_json()
        creneaux_ids = payload.pop('creneaux', None)
        creneaux = None
        # check this before initiate the booking
        if not hasattr(recueil_da.controller, 'pa_realiser'):
            abort(400, "Action autorisée qu'au statut BROUILLON")

        if creneaux_ids:
            creneaux = []
            if len(creneaux_ids) > 2:
                abort(400, "Un rendez-vous ne peut pas faire plus de deux créneaux")
            for ids in creneaux_ids:
                try:
                    tmp = list(Creneau.objects(pk__in=ids, reserve=False))
                except MongoValidationError:
                    abort(400, 'Certains créneaux sont invalides')
                if len(tmp) != 0:
                    creneaux.append(tmp[0])

            if len(creneaux) != len(creneaux_ids):
                abort(400, 'Certains créneaux sont invalides')

            try:
                creneaux_multi_reserver(creneaux, recueil_da)
            except CreneauReserverError as ex:
                abort(400, str(ex))

        try:
            rdv = recueil_da.controller.pa_realiser(creneaux=creneaux)
        except RdvError as ex:
            abort(400, str(ex))
        try:
            recueil_da.controller.save_or_abort(if_match=if_match)
            rdv.confirm()
        except:
            rdv.cancel()
            raise
        data = _schema_router(recueil_da).dump(recueil_da).data
        e.recueil_da.pa_realise.send(recueil_da=data)
        return data


class RecueilDA_DemandeursIdentifies_API(CoreResource):

    @p.recueil_da.modifier_pa_realise.require(http_exception=403)
    def post(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)

        if not hasattr(recueil_da.controller, 'identifier_demandeurs'):
            abort(400, "Action autorisée qu'au statut PA_REALISE")
        try:
            # since the FNE has not been update for the reexamen do not call fne check
            # errors = recueil_da.controller.verifier_statut_fne_demandeurs()
            # if errors != {}:
            #    abort(400, errors)
            recueil_da.controller.identifier_demandeurs(save_recueil=True, if_match=if_match)
        except DemandeursIdentifiesError as exc:
            abort(400, exc.errors)
        except AGDREFConnectionError:
            abort(503, "Le service distant AGDREF n\'a pu être contacté")
        except AGDREFRequiredFieldsError as excp:
            recueil_da.reload()
            abort(400, excp.errors)
        except AGDREFNumberError as excp:
            recueil_da.reload()
            abort(
                400, {'demandeurs_identifies': {
                    'msg': str(excp),
                    'version': recueil_da.doc_version}})
        except AGDREFDisabled:
            abort(503, "Le connecteur AGDREF est desactive")
        data = _schema_router(recueil_da).dump(recueil_da).data
        e.recueil_da.demandeurs_identifies.send(recueil_da=data)
        return data


class RecueilDA_Exploite_API(CoreResource):

    @p.recueil_da.modifier_demandeurs_identifies.require(http_exception=403)
    def post(self, item_id):
        from sief.view.usager_api import usager_schema
        from sief.view.demande_asile_api import demande_asile_schema
        from sief.view.demande_asile_api import send_event_procedure_qualification

        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if not hasattr(recueil_da.controller, 'exploiter'):
            abort(400, "Action autorisée qu'au statut DEMANDEURS_IDENTIFIES")
        try:
            ret = recueil_da.controller.exploiter(current_user._get_current_object())
        except ExploiteError as exc:
            abort(400, exc.errors)

        def dump_entry(entry):
            if not entry:
                return
            if entry.get('usager'):
                entry['usager'] = usager_schema.dump(entry['usager']).data
            if entry.get('demande_asile'):
                demande_asile_dump = demande_asile_schema.dump(entry['demande_asile']).data
                e.demande_asile.cree.send(
                    demande_asile=demande_asile_dump,
                    usager=entry['usager'])
                # since the reexamen, we can create the asylum direct in introduction ofpra
                # so we need to send the event of qualification to OFPRA
                if entry['demande_asile'].statut == 'EN_ATTENTE_INTRODUCTION_OFPRA':
                    send_event_procedure_qualification(entry['demande_asile'])
                    # no right has been create send the notification to agdref
                    e.droit.refus.send(usager=entry['usager'],
                                       demande_asile=demande_asile_dump)
                entry['demande_asile'] = demande_asile_dump

        dump_entry(ret.get('usager_1'))
        dump_entry(ret.get('usager_2'))
        for enfant in ret.get('enfants', []):
            dump_entry(enfant)
        recueil_da.controller.save_or_abort(if_match=if_match)
        recueil_dump = _schema_router(recueil_da).dump(recueil_da).data
        # Check if identifiant_famille_dna exist.
        # If, true we create an exploite event (create msg status 1).
        # Otherwise, we create an specific event (create two msgs -- status 0 then status 1 --)
        if recueil_da.identifiant_famille_dna:
            e.recueil_da.exploite.send(
                recueil_da=dump_recueil_da_full(recueil_da, _schema_router(recueil_da)), **ret)
        else:
            e.recueil_da.exploite_by_step.send(
                recueil_da=dump_recueil_da_full(recueil_da, _schema_router(recueil_da)), **ret)
        return recueil_dump


class RecueilDA_Annule_API(CoreResource):

    class AnnuleSchema(view_util.UnknownCheckedSchema):
        motif = field_for(RecueilDA, 'motif_annulation')

    def __init__(self):
        self.annule_schema = self.AnnuleSchema()

    def post(self, item_id):
        if (not p.recueil_da.modifier_pa_realise.can() and
                not p.recueil_da.modifier_demandeurs_identifies.can()):
            abort(403)
        payload = request.get_json()
        data, errors = self.annule_schema.load(payload)
        if errors:
            abort(400, **errors)
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if not hasattr(recueil_da.controller, 'annuler'):
            abort(400, "Action autorisée qu'aux status "
                       "PA_REALISE et DEMANDEURS_IDENTIFIES")
        # To prevent concurrency issues and inconsistencies, we first deal
        # with the recueil_da (modify&save it) then actually alter the creneaux
        try:
            creneaux_commit = recueil_da.controller.annuler_rendez_vous(lazy=True)
        except RdvError:
            creneaux_commit = None
        recueil_da.controller.annuler(current_user._get_current_object(), data['motif'])
        recueil_da.controller.save_or_abort(if_match=if_match)
        if creneaux_commit:
            creneaux_commit()
        data = _schema_router(recueil_da).dump(recueil_da).data
        e.recueil_da.annule.send(recueil_da=data, payload={'id': id})
        return data


class RecueilDA_Purge_API(CoreResource):

    @p.recueil_da.purger.require(http_exception=403)
    def post(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if not hasattr(recueil_da.controller, 'purger'):
            abort(400, "Action autorisée qu'au statut ANNULE")
        recueil_da.controller.purger()
        recueil_da.controller.save_or_abort(if_match=if_match)
        return _schema_router(recueil_da).dump(recueil_da).data


class RecueilDA_RendezVous_API(CoreResource):

    @p.recueil_da.rendez_vous.gerer.require(http_exception=403)
    def delete(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if not hasattr(recueil_da.controller, 'annuler_rendez_vous'):
            abort(400, "Action autorisée qu'au statut PA_REALISE")
        try:
            recueil_da.controller.annuler_rendez_vous()
        except RdvError as ex:
            abort(400, str(ex))
        recueil_da.controller.save_or_abort(if_match=if_match)
        return _schema_router(recueil_da).dump(recueil_da).data

    @p.recueil_da.rendez_vous.gerer.require(http_exception=403)
    def put(self, item_id):
        payload = request.get_json()
        creneaux_ids = payload.pop('creneaux', None)
        motif = payload.pop('motif', None)
        errors = {}
        for field in payload:
            errors[field] = 'Champ inconnu'
        if errors:
            abort(400, **errors)
        if creneaux_ids:
            if len(creneaux_ids) > 2:
                abort(400, "Un rendez-vous ne peut pas faire plus de deux creneaux")
            try:
                creneaux = [c for c in Creneau.objects(pk__in=creneaux_ids)]
            except MongoValidationError:
                abort(400, 'Certains créneaux sont invalides')
        else:
            creneaux = []
        if len(creneaux) != len(creneaux_ids):
            abort(400, 'Certains créneaux sont invalides')
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if not hasattr(recueil_da.controller, 'prendre_rendez_vous'):
            abort(400, "Action autorisée qu'au statut PA_REALISE")
        try:
            creneaux_multi_reserver(creneaux, recueil_da)
        except CreneauReserverError as ex:
            abort(400, str(ex))
        try:
            rdv = recueil_da.controller.prendre_rendez_vous(
                creneaux=creneaux, motif=motif)
        except RdvError as ex:
            abort(400, str(ex))
        try:
            recueil_da.controller.save_or_abort(if_match=if_match)
            rdv.confirm()
        except:
            rdv.cancel()
            raise
        return _schema_router(recueil_da).dump(recueil_da).data

    def get(self, item_id):
        from workdays import workday as add_days

        page, per_page = get_pagination_urlargs()

        def _have_consecutive_slots(creneaux):
            if len(creneaux) < 2:
                return False

            prev = creneaux[0]
            for c in creneaux:
                if prev.date_fin == c.date_debut:
                    return True
                prev = c

            return False

        def _retrieve_creneaux_by_gu(gu, familly):
            # More informations, look at site.py line 87
            today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            date_begin = add_days(today, 1)
            creneaux = None

            # If no limit, get first three days with free creneaux
            if gu.limite_rdv_jrs is 0:
                get_creneaux_kwargs = {
                    'date_debut__gte': date_begin,
                    'reserve': False,
                    'site': gu.id
                }
                creneaux = Creneau.objects(
                    **get_creneaux_kwargs).order_by('date_debut')

                tmp_creneaux = []
                day_crenaux = []
                nb_days = 0
                last_day = None
                for creneau in creneaux:
                    new_day = creneau.date_debut.strftime("%d/%m/%Y")
                    if last_day != new_day:
                        last_day = new_day
                        # if familly, only keep consecutive slots
                        if familly and not _have_consecutive_slots(day_crenaux):
                            day_crenaux = []

                        if len(day_crenaux) > 0:
                            tmp_creneaux.extend(day_crenaux)
                            day_crenaux = []
                            nb_days += 1

                        if nb_days is 3:
                            break
                    day_crenaux.append(creneau)

                # Check last day
                if nb_days < 3:
                    if familly and not _have_consecutive_slots(day_crenaux):
                        day_crenaux = []
                    tmp_creneaux.extend(day_crenaux)

                creneaux = tmp_creneaux
            else:
                date_end = add_days(date_begin, gu.limite_rdv_jrs)
                get_creneaux_kwargs = {
                    'date_debut__gte': date_begin,
                    'date_debut__lt': date_end,
                    'reserve': False,
                    'site': gu.id
                }
                creneaux = Creneau.objects(
                    **get_creneaux_kwargs).order_by('date_debut')

            if len(creneaux) is 0:
                return []

            sort_creneaux = []
            tmp_sort_creneaux = []

            last_slot = creneaux[0].date_debut.strftime(
                "%Y-%m-%dT%H:%MZ") + ' - ' + creneaux[0].date_fin.strftime("%Y-%m-%dT%H:%MZ")
            for creneau in creneaux:
                new_solt = creneau.date_debut.strftime(
                    "%Y-%m-%dT%H:%MZ") + ' - ' + creneau.date_fin.strftime("%Y-%m-%dT%H:%MZ")
                if last_slot != new_solt:
                    sort_creneaux.append(tmp_sort_creneaux)
                    tmp_sort_creneaux = []
                    last_slot = new_solt

                tmp_sort_creneaux.append(
                    {
                        "id": creneau.id,
                        "gu": gu.id,
                        "date": creneau.date_debut.strftime("%d/%m/%Y"),
                        "slot": new_solt
                    }
                )

            sort_creneaux.append(tmp_sort_creneaux)
            return sort_creneaux

        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        sites = None
        if recueil_da.prefecture_rattachee:
            prefecture_rattachee = recueil_da.prefecture_rattachee.id
            sites = GU.objects(autorite_rattachement=prefecture_rattachee)
        else:
            sites = recueil_da.structure_accueil.guichets_uniques

        data_sites = []
        data_creneaux = []
        for gu in sites:
            familly = len(recueil_da.controller.get_demandeurs()) > 1
            data_creneaux.append(_retrieve_creneaux_by_gu(gu, familly))
            data_sites.append({'libelle': gu.libelle, 'id': gu.id})

        data = {
            '_items': data_creneaux,
            '_sites': data_sites
        }
        return data


class RecueilDAListAPI(CoreResource):

    @p.recueil_da.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            lookup = _prefecture_rattachee_lookup()
            # No need to use the searcher module
            recueils = RecueilDA.objects(**lookup).paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            urlargs['fq'] += _prefecture_rattachee_lookup(solr=True)
            recueils = RecueilDA.search_or_abort(**urlargs)
        route = url_for('RecueilDAListAPI')
        links = {'root': url_for('RootAPI')}
        if p.recueil_da.creer_brouillon.can():
            links['create_brouillon'] = links['root']
        if p.recueil_da.creer_pa_realise.can():
            links['create_pa_realise'] = links['root']
        return view_util.PaginationSerializer(_schema_router, route).dump(
            recueils, links=links).data

    @staticmethod
    def _create_brouillon(payload):
        schema = RecueilDA_Brouillon_Schema()
        recueil_da, errors = schema.load(payload)
        if errors:
            abort(400, **errors)
        current_site_affecte = current_user.controller.get_current_site_affecte()
        if not current_site_affecte or not isinstance(current_site_affecte, StructureAccueil):
            abort(400, "L'utilisateur doit avoir une structure d'accueil comme"
                       " site_affecte pour pouvoir créer un recueil en BROUILLON")
        recueil_da.agent_accueil = current_user._get_current_object()
        recueil_da.structure_accueil = current_site_affecte
        return schema, recueil_da

    @staticmethod
    def _create_pa_realise(payload):
        schema = RecueilDA_PARealise_Schema()
        recueil_da, errors = schema.load(payload)
        if errors:
            abort(400, **errors)
        current_site_affecte = current_user.controller.get_current_site_affecte()
        if not current_site_affecte or not isinstance(current_site_affecte, GU):
            abort(400, "L'utilisateur doit avoir un guichet unique comme"
                       " site_affecte pour pouvoir créer un recueil en PA_REALISE")
        recueil_da.agent_accueil = current_user._get_current_object()
        recueil_da.structure_accueil = current_site_affecte
        recueil_da.structure_guichet_unique = current_site_affecte
        recueil_da.prefecture_rattachee = current_site_affecte.autorite_rattachement
        recueil_da.date_transmission = datetime.utcnow()
        return schema, recueil_da

    def post(self):
        allowed_statut = []
        if p.recueil_da.creer_brouillon.can():
            allowed_statut.append('BROUILLON')
        if p.recueil_da.creer_pa_realise.can():
            allowed_statut.append('PA_REALISE')

        if not allowed_statut:
            abort(403)
        payload = request.get_json()
        statut = payload.pop('statut', 'BROUILLON')
        if statut not in allowed_statut:
            abort(403, statut='Vous ne pouvez que créer des recueils au statut %s' % allowed_statut)
        if statut == 'BROUILLON':
            schema, recueil_da = self._create_brouillon(payload)
            schema = RecueilDA_Brouillon_Schema()
            recueil_da.controller.save_or_abort()
        elif statut == 'PA_REALISE':
            schema, recueil_da = self._create_pa_realise(payload)
            recueil_da.controller.save_or_abort()
            e.recueil_da.pa_realise.send(
                recueil_da=dump_recueil_da_full(recueil_da, schema))
        # No event "cree" given it is just a drafts
        return schema.dump(recueil_da).data, 201


def dump_recueil_da_full(receuil_da, schema):
    from sief.view.usager_api import usager_schema
    payload = schema.dump(receuil_da).data
    if receuil_da.usager_1 and receuil_da.usager_1.usager_existant:
        payload['usager_1'].update(usager_schema.dump(
            receuil_da.usager_1.usager_existant).data)
    if receuil_da.usager_2 and receuil_da.usager_2.usager_existant:
        payload['usager_2'].update(usager_schema.dump(
            receuil_da.usager_2.usager_existant).data)
    for enfant in receuil_da.enfants:
        if enfant.usager_existant:
            my_child = usager_schema.dump(enfant.usager_existant).data
            for pe in payload['enfants']:
                if 'usager_existant' in pe and str(pe['usager_existant']['id']) == my_child['id']:
                    pe.update(my_child)
    return payload


class RecueilDA_PrefectureRattachee_API(CoreResource):

    @p.recueil_da.voir.require(http_exception=403)
    def get(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        return recueil_da_prefecture_rattachee_schema.dump(recueil_da).data


class RecueilDA_ExportAPI(CoreResource):

    @p.recueil_da.export.require(http_exception=403)
    def get(self):
        exporter = Export(RecueilDA)
        return exporter.csv_format(['id', 'usager_1', 'rendez_vous_gu', 'rendez_vous_gu_anciens',
                                    'structure_guichet_unique', 'profil_demande',
                                    'date_transmission', 'enfants', 'doc_updated',
                                    'structure_accueil', 'agent_enregistrement',
                                    'date_enregistrement', 'statut', 'agent_accueil',
                                    'doc_version', 'doc_created', 'prefecture_rattachee',
                                    'identifiant_famille_dna', 'motif_annulation',
                                    'date_annulation', 'agent_annulation', 'usager_2'],
                                   get_search_urlargs(),
                                   url_for('RecueilDA_ExportAPI')), 200


class RecueilDA_EnregistrementFamilleOfii_API(CoreResource):

    @p.recueil_da.enregistrer_famille_ofii.require(http_exception=403)
    def post(self, item_id):
        recueil_da = RecueilDA.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(recueil_da)
        if_match = check_if_match(recueil_da)
        if recueil_da.identifiant_famille_dna:
            abort(400, "L'identifiant famille a déjà été enregistré")
        payload = request.get_json()
        schema = RecueilDA_EnregistrementFamilleOFII_Schema()
        recueil_da, errors = schema.update(recueil_da, payload)
        if errors:
            abort(400, **errors)
        if not recueil_da.identifiant_famille_dna:
            abort(400, identifiant_famille_dna="L'identifiant famille ne doit pas être vide")
        recueil_da.controller.save_or_abort(if_match=if_match)
        return schema.dump(recueil_da).data
