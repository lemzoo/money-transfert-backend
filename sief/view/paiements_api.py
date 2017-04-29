from datetime import datetime
from flask import request, url_for
from marshmallow import validate
from marshmallow_mongoengine import field_for, fields
from werkzeug.exceptions import HTTPException

from core import CoreResource, view_util
from core.auth import current_user
from core.tools import abort

from services.ants_pftd import (stamp_service, StampServiceError)
from sief.model import Usager, Droit
from sief.model.droit import Timbre, Taxe, StatutPaiements
from sief.permissions import POLICIES as p
from sief.view.timbre_api import get_reservation_number


def required_field(field):
    return field(required=True, error_messages={'required': 'missing-field'})


def field_for_with_errors(document, field, **kwargs):
    return field_for(document,
                     field,
                     error_messages={'required': 'missing-field', 'invalid': 'bad-type-field'},
                     **kwargs)


def required_list_field(field, validators=None):
    return fields.List(field(),
                       required=True,
                       error_messages={'required': 'missing-field'},
                       validate=validators)


field_not_empty = validate.Length(min=1, error='empty-field')


class EtatCivilSchema(view_util.UnknownCheckedSchema):
    nom = field_for_with_errors(Usager, 'nom')
    prenoms = field_for_with_errors(Usager, 'prenoms', required=True)
    sexe = field_for_with_errors(Usager, 'sexe')
    code_pays_naissance = required_field(fields.String)
    ville_naissance = field_for_with_errors(Usager, 'ville_naissance')
    date_naissance = field_for_with_errors(Usager, 'date_naissance')
    codes_nationalites = required_list_field(fields.String, [field_not_empty])
    situation_familiale = field_for_with_errors(Usager, 'situation_familiale')


class PaiementSchema(view_util.UnknownCheckedSchema):
    type_paiement = required_field(fields.String)
    numero_timbre = field_for_with_errors(Timbre, 'numero')
    numero_etranger = field_for_with_errors(Usager, 'identifiant_agdref', required=True)
    montant = field_for_with_errors(Taxe, 'montant')
    etat_civil = fields.Nested(EtatCivilSchema)


class PaiementsAPI(CoreResource):
    @p.timbre.consommer.require(http_exception=403)
    def post(self):
        input_payload = request.get_json()

        paiement, errors = PaiementSchema().load(input_payload)
        if errors:
            abort(400, errors=get_errors_payload(errors))

        if paiement['type_paiement'] != 'TIMBRE':
            abort(400, errors=[{'code_erreur': 'payment-type-unknown',
                                'payload_path': 'type_paiement'}])

        droits = Droit.objects(taxe__timbre__numero=paiement['numero_timbre'])

        if len(droits) > 0:
            abort_if_timbre_already_consumed(droits, {'code_erreur': 'stamp-already-consumed'})

        reservation_number = get_reservation_number(droits)
        current_droit = get_current_droit(droits, paiement)
        if current_droit:
            current_droit.update(taxe__statut_paiement=StatutPaiements.EN_COURS.value)
        else:
            current_droit = save_current_droit(paiement, reservation_number)

        try:
            data = consume_timbre(current_droit, paiement, reservation_number)
            return {'_links': {'self': url_for('PaiementsAPI')}, 'data': data}, 200
        except StampServiceError as e:
            current_droit.taxe.statut_paiement = StatutPaiements.ECHOUE.value
            current_droit.controller.save_or_abort()
            abort(500, errors=[{'code_erreur': e.code}])


def consume_timbre(current_droit, paiement, reservation_number):
    service_return = stamp_service.consume_stamp(paiement['numero_timbre'], reservation_number)
    now = datetime.utcnow()
    current_droit.taxe.statut_paiement = StatutPaiements.EFFECTUE.value
    current_droit.taxe.date_paiement_effectue = now
    current_droit.controller.save_or_abort()

    return {'timbre_data': service_return, 'date_paiement_effectue': now}



def save_current_droit(paiement, reservation_number):
    current_usager = Usager.objects(identifiant_agdref=paiement['numero_etranger']).first()

    if current_usager is None:
        current_usager = save_current_usager(paiement)

    current_droit = create_droit(current_usager, paiement['numero_timbre'],
                                 paiement['montant'], reservation_number)
    try:
        current_droit.controller.save_or_abort()
    except HTTPException as http_error:
        abort(400, errors=get_processed_http_error(http_error))

    return current_droit


def save_current_usager(paiement):
    current_usager = create_usager(paiement['numero_etranger'], paiement['etat_civil'])

    try:
        current_usager.controller.save_or_abort()
    except HTTPException as http_error:
        abort(400, errors=get_processed_http_error(http_error))

    return current_usager


def get_current_droit(droits, paiement):
    for droit in droits:
        if droit.usager.identifiant_agdref == paiement['numero_etranger']:
            return droit


def abort_if_timbre_already_consumed(droits, error):
    for droit in droits:
        if droit.taxe.statut_paiement == StatutPaiements.EFFECTUE.value:
            raise abort(400, errors=[error])


def get_errors_payload(errors):
    errors_payload = []
    for error_key in errors.keys():
        if error_key == 'etat_civil':
            for etat_civil_error_key in errors.get(error_key):
                etat_civil_error = get_parsed_schema_error(errors.get('etat_civil'),
                                                           etat_civil_error_key,
                                                           'etat_civil.')
                errors_payload.append(etat_civil_error)
        else:
            errors_payload.append(get_parsed_schema_error(errors, error_key))
    return errors_payload


def get_parsed_schema_error(errors, error_key, prefix=''):
    error_code = get_parsed_error_code(errors.get(error_key)[0])

    if error_key == '_schema':
        return {'code_erreur': 'unknown-field',
                'description_erreur': error_code}

    return {'code_erreur': error_code,
            'payload_path': prefix + error_key}


def get_parsed_error_code(error_code):
    if error_code == 'Not a string':
        return 'bad-type-field'

    if error_code == 'Not a valid choice.':
        return 'bad-format-field'

    return error_code


def create_droit(current_usager, numero_timbre, montant, reservation_number):
    droit_payload = {
        'usager': current_usager,
        'agent_createur': current_user._get_current_object(),
        'taxe': {
            'statut_paiement': StatutPaiements.EN_COURS.value,
            'montant': montant,
            'timbre': {
                'numero': numero_timbre,
                'numero_reservation': reservation_number
            }
        }
    }

    return Droit(**droit_payload)


def create_usager(numero_etranger, etat_civil):
    etat_civil_payload = create_etat_civil(etat_civil)
    usager = Usager(**etat_civil_payload)
    usager.identifiant_agdref = numero_etranger

    return usager


def create_etat_civil(etat_civil):
    etat_civil['pays_naissance'] = {'code': etat_civil['code_pays_naissance']}
    etat_civil.pop('code_pays_naissance', None)

    etat_civil['nationalites'] = [{'code': code} for code in etat_civil['codes_nationalites']]
    etat_civil.pop('codes_nationalites', None)

    return etat_civil


def get_parsed_http_error(error_type):
    parsed_errors = {
        'nationalites': {
            'code_erreur': 'unknown-field',
            'payload_path': 'etat_civil.codes_nationalites',
            'description_erreur': 'Nationality code doesn\'t exist in referential'},
        'ville_naissance': {
            'code_erreur': 'bad-format-field',
            'payload_path': 'etat_civil.ville_naissance'},
        'prenoms': {
            'code_erreur': 'bad-format-field',
            'payload_path': 'etat_civil.prenoms'},
        'taxe': {
            'code_erreur': 'bad-format-field',
            'payload_path': 'numero_timbre'},
        'identifiant_agdref': {
            'code_erreur': 'bad-format-field',
            'payload_path': 'numero_etranger'},
        'pays_naissance': {
            'code_erreur': 'unknown-field',
            'payload_path': 'etat_civil.code_pays_naissance',
            'description_erreur': 'Country code doesn\'t exist in referential'},
    }

    default_error = {'code_erreur': 'unknown-http-error',
                     'description_erreur': 'An HTTP error occurred but was not handled'}

    return parsed_errors.get(error_type, default_error)


def get_processed_http_error(http_error):
    errors = []
    for error_type in http_error.data:
        errors.append(get_parsed_http_error(error_type))
    return errors
