from flask import request, url_for
from marshmallow_mongoengine import field_for
from mongoengine import Q, ValidationError
from datetime import datetime
import copy

from core.tools import abort, get_search_urlargs, check_if_match, Export
from core.auth import current_user
from core import CoreResource, view_util
from sief.permissions import POLICIES as p
from sief.events import EVENTS as e
from sief.model.demande_asile import (DemandeAsile, DublinTransfert,
                                      RequalificationError, DecisionAttestation, Recevabilite)
from sief.model.droit import Droit
from sief.view.usager_api import usager_schema


DemandeAsile.set_link_builder_from_api('DemandeAsileAPI')


class DemandeAsileSchema(view_util.BaseModelSchema):

    def get_links(self, obj):
        route = url_for("DemandeAsileAPI", item_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("DemandeAsileListAPI")}
        if p.historique.voir.can():
            links['history'] = url_for("DemandeAsileHistoryListAPI",
                                       origin_id=obj.pk)
        if obj.statut in ('PRETE_EDITION_ATTESTATION',
                          'EN_COURS_PROCEDURE_DUBLIN',
                          'EN_ATTENTE_INTRODUCTION_OFPRA',
                          'EN_COURS_INSTRUCTION_OFPRA'):
            if p.demande_asile.editer_attestation.can():
                links['editer_attestation'] = url_for(
                    "DemandeAsile_editionAttestation_API", item_id=obj.pk)
            if p.demande_asile.orienter.can():
                links['orienter'] = url_for("DemandeAsile_orientation_API",
                                            item_id=obj.pk)
        if obj.statut == 'EN_COURS_PROCEDURE_DUBLIN':
            if p.demande_asile.modifier_dublin.can():
                links['finir_procedure'] = url_for(
                    'DemandeAsile_finirProcedure_API', item_id=obj.pk)
                links['modifier_dublin'] = url_for(
                    "DemandeAsile_dublin_API", item_id=obj.pk)
        elif obj.statut == 'EN_ATTENTE_INTRODUCTION_OFPRA':
            if p.demande_asile.modifier_ofpra.can():
                links['introduire_ofpra'] = url_for(
                    "DemandeAsile_introductionOfpra_API", item_id=obj.pk)
                links['finir_procedure'] = url_for(
                    'DemandeAsile_finirProcedure_API', item_id=obj.pk)
        elif obj.statut in ('EN_COURS_INSTRUCTION_OFPRA', 'DECISION_DEFINITIVE'):
            if p.demande_asile.modifier_ofpra.can():
                links['decision_definitive'] = url_for(
                    'DemandeAsile_decisionDefinitive_API', item_id=obj.pk)
        if p.demande_asile.requalifier_procedure.can():
            if obj.statut in ('EN_COURS_PROCEDURE_DUBLIN',
                              'EN_ATTENTE_INTRODUCTION_OFPRA',
                              'EN_COURS_INSTRUCTION_OFPRA'):
                links['requalifier_procedure'] = url_for(
                    'DemandeAsile_requalification_API', item_id=obj.pk)
        if (hasattr(obj.controller, 'finir_procedure') and
                p.demande_asile.finir_procedure.can()):
            links['finir_procedure'] = url_for(
                'DemandeAsile_finirProcedure_API', item_id=obj.pk)
        return links

    class Meta:
        model = DemandeAsile
        model_fields_kwargs = {'prefecture_rattachee': {'dump_only': True}}


class UpdateDemandeAsileSchema(DemandeAsileSchema):

    class Meta:
        model = DemandeAsile
        model_fields_kwargs = {
            'structure_premier_accueil': {'dump_only': True},
            'referent_premier_accueil': {'dump_only': True},
            'date_demande': {'dump_only': True},
            'agent_enregistrement': {'dump_only': True},
            'date_enregistrement': {'dump_only': True},
            'agent_orientation': {'dump_only': True},
            'date_orientation': {'dump_only': True},
            'date_enregistrement_agdref': {'dump_only': True},
            'identifiant_inerec': {'dump_only': True},
            'date_introduction_ofpra': {'dump_only': True},
            'alerte': {'dump_only': True},
            'documents': {'dump_only': True},
            'statut': {'dump_only': True},
            # TODO : Handle renouvellement_attestation in the backend
            # 'renouvellement_attestation': {'dump_only': True},
            'decisions_definitives': {'dump_only': True},
            'dublin': {'dump_only': True},
            'hebergement': {'dump_only': True},
            'ada': {'dump_only': True},
            'procedure': {'dump_only': True},
            'motif_refus': {'dump_only': True},
            'decision_definitive_resultat': {'dump_only': True}
        }


class CreateDemandeAsileSchema(UpdateDemandeAsileSchema):

    class Meta:
        model = DemandeAsile
        model_fields_kwargs = {'usager': {'dump_only': True}}


class DemandeAsilePrefectureRattacheeSchema(view_util.BaseModelSchema):

    class Meta:
        model = DemandeAsile
        fields = ('prefecture_rattachee', )


demande_asile_schema = DemandeAsileSchema()
create_demande_asile_schema = CreateDemandeAsileSchema()
update_demande_asile_schema = UpdateDemandeAsileSchema()
demande_asile_prefecture_rattachee_schema = DemandeAsilePrefectureRattacheeSchema()


def _check_prefecture_rattachee(prefecture_rattachee, overall=False):
    if not p.demande_asile.prefecture_rattachee.sans_limite.can() and not overall:
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        if getattr(user_site, 'autorite_rattachement', user_site) != prefecture_rattachee:
            abort(403, "Prefecture de rattachement invalide")


def _prefecture_rattachee_lookup(solr=False, overall=False):
    if p.demande_asile.prefecture_rattachee.sans_limite.can() or overall:
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


def _check_conditions_exceptionnelles(payload, da, errors):
    cond_payload = payload.get('conditions_exceptionnelles_accueil', None)
    cond_da = da.conditions_exceptionnelles_accueil
    if cond_payload is None and cond_da is None:
        errors['conditions_exceptionnelles_accueil'] = ['Not a valid choice.']
    elif cond_payload or cond_da:
        motif_payload = payload.get('motif_conditions_exceptionnelles_accueil', None)
        motif_da = da.motif_conditions_exceptionnelles_accueil
        if motif_payload is None and motif_da is None:
            errors['motif_conditions_exceptionnelles_accueil'] = ['Not a valid choice.']


def _check_date_depart_et_entree(payload, da, errors):
    now = datetime.utcnow()

    date_depart_payload = payload.get('date_depart', None)
    date_depart_da = da.date_depart

    date_entree_payload = payload.get('date_entree_en_france', None)
    date_entree_da = da.date_entree_en_france

    if date_depart_payload is None and date_depart_da is None:
        errors['date_depart'] = ['Not a valid choice.']
    elif date_entree_payload is None and date_entree_da is None:
        errors['date_entree_en_france'] = ['Not a valid choice.']
    elif da.date_entree_en_france > now:
        errors['date_entree_en_france'] = [
            'La date ne peut pas être postérieure à la date courante.']
    elif da.date_depart > da.date_entree_en_france:
        errors['date_depart'] = [
            'La date de départ doit être antérieure à celle d\'arrivée en France.']


def dump_da_full(da):
    from sief.model.usager import Usager
    from sief.view.droit_api import droit_schema
    usager = da.usager
    payload = {
        'demande_asile': demande_asile_schema.dump(da).data,
        'usager': usager_schema.dump(usager).data
    }
    if usager.conjoint:
        payload['conjoint'] = usager_schema.dump(usager.conjoint).data
    enfants = Usager.objects(Q(identifiant_pere=usager) |
                             Q(identifiant_mere=usager))
    if enfants:
        payload['enfants'] = [usager_schema.dump(e).data for e in enfants]
    droits = Droit.objects(demande_origine=da).order_by('+created')
    if droits:
        payload['droits'] = [droit_schema.dump(d).data for d in droits]
    return payload


class DemandeAsileAPI(CoreResource):

    @p.demande_asile.voir.require(http_exception=403)
    def get(self, item_id):
        overall = 'overall' in request.args
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee, overall=overall)
        return demande_asile_schema.dump(da).data, 200

    @p.demande_asile.modifier.require(http_exception=403)
    def patch(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        payload = request.get_json()
        da, errors = update_demande_asile_schema.update(da, payload)
        _check_conditions_exceptionnelles(payload, da, errors)
        _check_date_depart_et_entree(payload, da, errors)
        if errors:
            abort(400, **errors)
        da.controller.save_or_abort(if_match=if_match)
        da_dump = demande_asile_schema.dump(da).data
        e.demande_asile.modifie.send(demande_asile=da_dump, payload=payload)
        return da_dump, 200


class DemandeAsile_orientation_API(CoreResource):

    def __init__(self):
        super().__init__()

        class OrientationPOSTSchema(DemandeAsileSchema):

            class Meta:
                model = DemandeAsile
                fields = ('hebergement', 'ada', 'agent_orientation', 'date_orientation')
                model_build_obj = False

        self._orientation_post_schema = OrientationPOSTSchema()

    @p.demande_asile.orienter.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if da.statut not in ('PRETE_EDITION_ATTESTATION',
                             'EN_COURS_PROCEDURE_DUBLIN',
                             'EN_ATTENTE_INTRODUCTION_OFPRA',
                             'EN_COURS_INSTRUCTION_OFPRA'):
            abort(400, "Impossible de modifier l'orientation au statut %s" % da.statut)
        payload = request.get_json()
        patch, errors = self._orientation_post_schema.load(payload)
        if errors:
            abort(400, **errors)
        for key, value in patch.items():
            setattr(da, key, value)
        da.controller.save_or_abort(if_match=if_match)
        da_dump = demande_asile_schema.dump(da).data
        e.demande_asile.oriente.send(demande_asile=da_dump, payload=payload)
        return da_dump, 200


def send_event_procedure_qualification(da):
    """The procedure can be assigned to OFPRA or to DUBLIN, we have to send a different event for each."""
    dump = dump_da_full(da)
    dump_to_send = copy.deepcopy(dump)
    if 'numero_reexamen' not in dump_to_send['demande_asile']:
        dump_to_send['demande_asile']['numero_reexamen'] = 0
    if da.statut == 'EN_ATTENTE_INTRODUCTION_OFPRA' and da.type_demande == 'REEXAMEN':
        # since inerec need their previous number to made the link between the old
        # and new asylum, add the number to the da do not save it.
        old_da = DemandeAsile.objects(usager=da.usager, statut__in=["DECISION_DEFINITIVE",
                                                                    "FIN_PROCEDURE_DUBLIN",
                                                                    "FIN_PROCEDURE"]).first()
        # maybe the previous asylum was made in agdref
        if old_da:
            dump_to_send['demande_asile']['identifiant_inerec'] = old_da.identifiant_inerec
    if da.statut == 'EN_ATTENTE_INTRODUCTION_OFPRA':
        e.demande_asile.en_attente_ofpra.send(**dump_to_send)
    elif da.statut == 'EN_COURS_PROCEDURE_DUBLIN':
        e.demande_asile.en_cours_procedure_dublin.send(**dump_to_send)
    return dump


class DemandeAsile_editionAttestation_API(CoreResource):

    def __init__(self):
        super().__init__()

        class EditionAttestationSchema(view_util.UnknownCheckedSchema):
            date_debut_validite = field_for(Droit, 'date_debut_validite', required=True)
            date_fin_validite = field_for(Droit, 'date_fin_validite', required=True)
            date_decision_sur_attestation = field_for(Droit, 'date_decision_sur_attestation')

            class Meta:
                model_make_object = False

        self._edition_attestation_schema = EditionAttestationSchema()

    @p.demande_asile.editer_attestation.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if not hasattr(da.controller, 'editer_attestation'):
            abort(400, "Impossible d'éditer une attestation au statut %s" % da.statut)
        payload = request.get_json()
        data, errors = self._edition_attestation_schema.load(payload)
        if errors:
            abort(400, **errors)
        pret_event = da.statut == 'PRETE_EDITION_ATTESTATION'
        try:
            droit_factory = da.controller.editer_attestation(
                user=current_user._get_current_object(), **data)
        except ValidationError as exc:
            abort(400, 'Contenu invalide pour le droit : %s' % exc)
        da.controller.save_or_abort(if_match=if_match)
        # Wait for the da to be successfuly altered before actually create the droit

        da_dump_full = None
        if pret_event:
            da_dump_full = send_event_procedure_qualification(da)
        else:
            da_dump_full = dump_da_full(da)
        da_dump = da_dump_full['demande_asile']
        if droit_factory:
            _, droit_dump = droit_factory()
            da_dump['droit'] = droit_dump
            e.demande_asile.attestation_edite.send(payload=droit_dump, **da_dump_full)
        return da_dump, 201


class DemandeAsile_requalification_API(CoreResource):

    def __init__(self):
        super().__init__()
        doc_type = DemandeAsile.procedure.document_type

        class RequalificationSchema(view_util.UnknownCheckedSchema):
            type = field_for(doc_type, 'type')
            motif_qualification = field_for(doc_type, 'motif_qualification')
            acteur = field_for(doc_type, 'acteur', required=True)
            date_notification = field_for(doc_type.requalifications.field.document_type,
                                          'date_notification')

            class Meta:
                model_make_object = False

        self._requalification_schema = RequalificationSchema()

    @p.demande_asile.requalifier_procedure.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if not hasattr(da.controller, 'requalifier_procedure'):
            abort(400, "Impossible de requalifier la procédure au statut %s" % da.statut)
        payload = request.get_json()
        data, errors = self._requalification_schema.load(payload)
        if errors:
            abort(400, **errors)
        try:
            da.controller.requalifier_procedure(**data)
        except RequalificationError as ex:
            abort(400, str(ex))
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = send_event_procedure_qualification(da)
        e.demande_asile.procedure_requalifiee.send(payload=payload, **da_dump_full)
        return da_dump_full['demande_asile']


class DemandeAsile_finirProcedure_API(CoreResource):

    def __init__(self):
        super().__init__()

        class FinirProcedureSchema(DemandeAsileSchema):

            class Meta:
                model = DemandeAsile
                fields = ('motif_refus',)

        self._finir_procedure_schema = FinirProcedureSchema()

    @p.demande_asile.finir_procedure.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if not hasattr(da.controller, 'finir_procedure'):
            abort(400, "Impossible de finir la procédure au statut %s" % da.statut)
        payload = request.get_json()
        da, errors = self._finir_procedure_schema.update(da, payload)
        if errors:
            abort(400, **errors)
        da.controller.finir_procedure()
        da.controller.save_or_abort(if_match=if_match)
        da_dump = demande_asile_schema.dump(da).data
        e.demande_asile.procedure_finie.send(demande_asile=da_dump, payload=payload)
        return da_dump, 200


class DemandeAsile_dublin_API(CoreResource):

    def __init__(self):
        super().__init__()

        class DublinSchema(view_util.UnknownCheckedSchema):

            class Meta:
                model = DemandeAsile.dublin.document_type
                model_build_obj = False

        self._dublin_schema = DublinSchema()

    @p.demande_asile.modifier_dublin.require(http_exception=403)
    def patch(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if da.statut != 'EN_COURS_PROCEDURE_DUBLIN':
            abort(400, "Impossible de modifier dublin au statut %s" % da.statut)
        payload = request.get_json()
        data, errors = self._dublin_schema.load(payload)
        if errors:
            abort(400, **errors)
        if not da.dublin:
            da.dublin = DublinTransfert(**data)
        else:
            for field, value in data.items():
                setattr(da.dublin, field, value)
        da.controller.save_or_abort(if_match=if_match)
        da_dump = demande_asile_schema.dump(da).data
        e.demande_asile.dublin_modifie.send(demande_asile=da_dump, payload=payload)
        return da_dump, 200


class DemandeAsile_introductionOfpra_API(CoreResource):

    def __init__(self):
        super().__init__()

        class IntroductionOfpraSchema(view_util.UnknownCheckedSchema):
            identifiant_inerec = field_for(
                DemandeAsile, 'identifiant_inerec', required=True)
            date_introduction_ofpra = field_for(
                DemandeAsile, 'date_introduction_ofpra', required=True)
            numero_reexamen = field_for(
                DemandeAsile, 'numero_reexamen', required=False)

            class Meta:
                model_build_obj = False

        self._introduction_ofpra_schema = IntroductionOfpraSchema()

    @p.demande_asile.modifier_ofpra.require(http_exception=403)
    def post(self, item_id):
        # Introduction
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if not hasattr(da.controller, 'introduire_ofpra'):
            abort(400, "POST possible qu'au statut EN_ATTENTE_INTRODUCTION_OFPRA"
                       ", sinon utiliser PATCH")
        payload = request.get_json()
        data, errors = self._introduction_ofpra_schema.load(payload)
        if errors:
            abort(400, **errors)
        da.controller.introduire_ofpra(**data)
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = dump_da_full(da)
        e.demande_asile.introduit_ofpra.send(payload=payload, **da_dump_full)
        return da_dump_full['demande_asile'], 200


class DemandeAsile_Recevabilite_API(CoreResource):

    """API that allow the user to enter a condition of recevability or irrecevability for an asylum."""

    def __init__(self):
        """Constructor of the class, init the schema of the payload."""
        super().__init__()

        class RecevabiliteOfpraSchema(view_util.UnknownCheckedSchema):
            recevabilite = field_for(
                Recevabilite, 'recevabilite', required=True)
            date_notification = field_for(
                Recevabilite, 'date_notification', required=True)
            date_qualification = field_for(
                Recevabilite, 'date_qualification', required=False)

            class Meta:
                model_build_obj = False

        self._recevabilite_ofpra_schema = RecevabiliteOfpraSchema()

    @p.demande_asile.modifier_ofpra.require(http_exception=403)
    def post(self, item_id):
        """Apply the addition of the condition to the asylum."""
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if da.statut not in ('EN_COURS_INSTRUCTION_OFPRA'):
            abort(400, "Impossible de modifier la recevabilité au statut %s" % da.statut)
        payload = request.get_json()
        data, errors = self._recevabilite_ofpra_schema.load(payload)
        if errors:
            abort(400, **errors)
        try:
            da.controller.recevabilite(**data)
        except ValidationError as exc:
            abort(400, 'Contenu invalide pour la recevabilité : %s' % exc)
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = dump_da_full(da)
        e.demande_asile.recevabilite_ofpra.send(payload=payload, **da_dump_full)
        return da_dump_full['demande_asile'], 200


class DemandeAsile_decisionDefinitive_API(CoreResource):

    def __init__(self):
        super().__init__()

        class DecisionDefinitiveSchema(view_util.UnknownCheckedSchema):

            class Meta:
                model = DemandeAsile.decisions_definitives.field.document_type

        self._decision_definitive_schema = DecisionDefinitiveSchema()

    @p.demande_asile.modifier_ofpra.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if da.statut not in ('EN_COURS_INSTRUCTION_OFPRA',
                             'DECISION_DEFINITIVE'):
            abort(400, "Impossible de modifier l'orientation au statut %s" % da.statut)
        payload = request.get_json()
        decision_def, errors = self._decision_definitive_schema.load(payload)
        if errors:
            abort(400, **errors)
        if hasattr(da.controller, 'passer_decision_definitive'):
            da.controller.passer_decision_definitive()
        da.decisions_definitives.append(decision_def)
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = dump_da_full(da)
        e.demande_asile.decision_definitive.send(payload=payload, **da_dump_full)
        return da_dump_full['demande_asile'], 201


class DemandeAsile_decisionAttestation_API(CoreResource):

    def __init__(self):
        super().__init__()

        class DecisionAttestationSchema(view_util.UnknownCheckedSchema):

            class Meta:
                model = DecisionAttestation
                model_fields_kwargs = {'agent_createur': {'dump_only': True}}

        self._decision_attestation_schema = DecisionAttestationSchema()

    @p.demande_asile.modifier.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        payload = request.get_json()
        decision_attestation, errors = self._decision_attestation_schema.load(payload)
        if errors:
            abort(400, **errors)
        decision_attestation.agent_createur = current_user._get_current_object()
        if not da.decisions_attestation:
            da.decisions_attestation = [decision_attestation]
        else:
            da.decisions_attestation.append(decision_attestation)
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = dump_da_full(da)
        e.demande_asile.decision_attestation.send(payload=payload, **da_dump_full)
        return da_dump_full['demande_asile'], 201


class DemandeAsile_decisionDefinitiveINEREC_API(CoreResource):

    def __init__(self):
        super().__init__()

        class DecisionDefinitiveSchema(view_util.UnknownCheckedSchema):

            class Meta:
                model = DemandeAsile.decisions_definitives.field.document_type

        self._decision_definitive_schema = DecisionDefinitiveSchema()

    @p.demande_asile.modifier_stock_dna.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(identifiant_inerec=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        if da.statut not in ('EN_COURS_INSTRUCTION_OFPRA',
                             'DECISION_DEFINITIVE'):
            abort(400, "Impossible de modifier l'orientation au statut %s" % da.statut)
        payload = request.get_json()
        decision_def, errors = self._decision_definitive_schema.load(payload)
        if errors:
            abort(400, **errors)
        if hasattr(da.controller, 'passer_decision_definitive'):
            da.controller.passer_decision_definitive()
        da.decisions_definitives.append(decision_def)
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = dump_da_full(da)
        e.demande_asile.decision_definitive.send(payload=payload, **da_dump_full)
        return da_dump_full['demande_asile'], 201


class DemandeAsile_decisionClotureOFPRA_API(CoreResource):

    def __init__(self):
        super().__init__()

        class DecisionClotureSchema(view_util.UnknownCheckedSchema):

            class Meta:
                model = DemandeAsile.clotures_ofpra.field.document_type

        self._decision_cloture_schema = DecisionClotureSchema()

    @p.demande_asile.cloture_ofpra.require(http_exception=403)
    def post(self, item_id):
        da = DemandeAsile.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(da.prefecture_rattachee)
        if_match = check_if_match(da)
        payload = request.get_json()
        decision_cloture, errors = self._decision_cloture_schema.load(payload)
        if errors:
            abort(400, **errors)
        if not da.clotures_ofpra:
            da.clotures_ofpra = []
        da.clotures_ofpra.append(decision_cloture)
        if hasattr(da.controller, 'cloture_ofpra'):
            da.controller.cloture_ofpra()
        da.controller.save_or_abort(if_match=if_match)
        da_dump_full = dump_da_full(da)
        return da_dump_full['demande_asile'], 201


class DemandeAsileListAPI(CoreResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = view_util.PaginationSerializer(
            demande_asile_schema, url_for('DemandeAsileListAPI'))

    @p.demande_asile.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        overall = 'overall' in request.args
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            lookup = _prefecture_rattachee_lookup(overall=overall)
            # No need to use the searcher module
            das = DemandeAsile.objects(**lookup).paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            urlargs['fq'] += _prefecture_rattachee_lookup(solr=True, overall=overall)
            das = DemandeAsile.search_or_abort(**urlargs)
        links = {'root': url_for('RootAPI')}
        if p.demande_asile.creer.can():
            links['create'] = url_for('DemandeAsileListAPI')
        return self._serializer.dump(das, links=links).data, 200


class DemandeAsile_ExportAPI(CoreResource):

    @p.demande_asile.export.require(http_exception=403)
    def get(self):
        exporter = Export(DemandeAsile)
        return exporter.csv_format(['id', 'agent_orientation', 'date_decision_sur_attestation',
                                    'referent_premier_accueil', 'date_demande', 'doc_updated',
                                    'documents', 'demandes_rattachees', 'statut',
                                    'renouvellement_attestation',
                                    'agent_enregistrement', 'date_entree_en_france',
                                    'type_demandeur', 'structure_premier_accueil',
                                    'indicateur_visa_long_sejour',
                                    'structure_guichet_unique', 'condition_entree_france',
                                    'doc_version', 'date_depart', 'procedure', 'date_orientation',
                                    'doc_created', 'enfants_presents_au_moment_de_la_demande',
                                    'decision_sur_attestation', 'date_enregistrement',
                                    'decisions_definitives', 'usager',
                                    'recueil_da_origine', 'visa', 'prefecture_rattachee',
                                    'identifiant_inerec',
                                    'date_introduction_ofpra', 'acceptation_opc', 'dublin',
                                    'hebergement', 'ada', 'condition_entree_france', 'motif_refus',
                                    'demande_asile_principale',
                                    'date_depart_approximative',
                                    'date_entree_en_france_approximative', 'pays_traverses'],
                                   get_search_urlargs(),
                                   url_for('DemandeAsile_ExportAPI')), 200


class DemandeAsile_PrefectureRattachee_API(CoreResource):

    @p.demande_asile.voir.require(http_exception=403)
    def get(self, item_id):
        demande_asile = DemandeAsile.objects.get_or_404(id=item_id)
        return demande_asile_prefecture_rattachee_schema.dump(demande_asile).data


def dump_condition_execptionnelle(demande_asile):
    """Dump condition exceptionnelle d'accueil pour les demandes d'asiles."""
    return [demande_asile.motif_conditions_exceptionnelles_accueil,
            demande_asile.usager.nom,
            demande_asile.usager.prenoms,
            "{:%d/%m/%Y}".format(demande_asile.usager.date_naissance),
            demande_asile.usager.identifiant_agdref,
            "{:%d/%m/%Y}".format(demande_asile.date_entree_en_france),
            demande_asile.procedure.type,
            demande_asile.statut,
            [n.libelle for n in demande_asile.usager.nationalites],
            demande_asile.usager.localisations[0].adresse.to_json(),
            demande_asile.structure_guichet_unique.libelle,
            "{:%d/%m/%Y}".format(demande_asile.date_enregistrement)]


class DemandeAsile_Condition_Exceptionnelle_ExportAPI(CoreResource):

    @p.demande_asile.condition_exceptionnelle.export.require(http_exception=403)
    def get(self):
        da_filter = {"motif_conditions_exceptionnelles_accueil__in":
                     ["VISA_D_ASILE",
                      "REINSTALLATION",
                      "RELOCALISATION",
                      "CAO"]}
        exporter = Export(DemandeAsile, da_filter)
        header = ["motifs conditions exceptionnelles d'accueil",
                  "nom",
                  "prénoms",
                  "date de naissance",
                  "Numéro AGDREF",
                  "date arrivée en France",
                  "type de procédure",
                  "statut de la demande",
                  "nationalité",
                  "adresse",
                  "gu de rattachement",
                  "date enregistrement de la demande au GU"]

        return exporter.csv_format_specific(get_search_urlargs(),
                                            url_for(
                                                'DemandeAsile_Condition_Exceptionnelle_ExportAPI'),
                                            header,
                                            dump_condition_execptionnelle)


def dump_en_attente_introduction_ofpra(demande_asile):
    """Dump demande asile en attente introduction ofpra."""
    return [demande_asile.usager.nom,
            demande_asile.usager.prenoms,
            "{:%d/%m/%Y}".format(demande_asile.usager.date_naissance),
            demande_asile.usager.identifiant_agdref,
            "{:%d/%m/%Y}".format(demande_asile.date_entree_en_france),
            demande_asile.procedure.type,
            demande_asile.statut,
            [n.libelle for n in demande_asile.usager.nationalites],
            demande_asile.usager.localisations[0].adresse.to_json(),
            demande_asile.structure_guichet_unique.libelle,
            "{:%d/%m/%Y}".format(demande_asile.date_enregistrement)]


class DemandeAsile_EnAttenteIntroductionOfpra_ExportAPI(CoreResource):

    @p.demande_asile.en_attente_introduction_ofpra.export.require(http_exception=403)
    def get(self):
        da_filter = {"statut": "EN_ATTENTE_INTRODUCTION_OFPRA"}
        exporter = Export(DemandeAsile, da_filter)
        header = ["nom",
                  "prénoms",
                  "date de naissance",
                  "Numéro étranger",
                  "date arrivée en France",
                  "type de procédure",
                  "statut de la demande",
                  "nationalité",
                  "adresse",
                  "gu de rattachement",
                  "date enregistrement de la demande au GU"]

        return exporter.csv_format_specific(get_search_urlargs(),
                                            url_for(
                                                'DemandeAsile_EnAttenteIntroductionOfpra_ExportAPI'),
                                            header,
                                            dump_en_attente_introduction_ofpra)
