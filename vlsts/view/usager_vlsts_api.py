from flask import request, url_for
from marshmallow import validate
from marshmallow_mongoengine import field_for, fields

from core import CoreResource, view_util
from core.auth import current_user
from core.auth.login_pwd_auth import LoginPwdSchema
from core.tools import abort
from sief.model import Usager
from sief.model.fields import AddressEmbeddedDocument


class UsagerVLSTSSchema(view_util.BaseModelSchema):
    def get_links(self, obj):
        route = url_for('vlsts.UsagerVLSTSAPI', item_id=obj.pk)
        links = {
            'self': route
        }
        return links

    class Meta:
        model = Usager
        model_fields_kwargs = {
            'basic_auth': {
                'dump_only': True,
                'load_only': True
            },

        }


class UsagerVLSTSAPI(CoreResource):
    def get(self, item_id=None):
        if not item_id:
            user = current_user
            url = url_for('vlsts.UsagerVLSTSAPI')
            links = {'self': url, 'update': url,
                     'root': url_for('vlsts.RootVLSTSAPI')}
        else:
            user = Usager.objects.get_or_404(id=item_id)
            links = None
        data = UsagerVLSTSSchema().dump(user).data
        basic_auth = LoginPwdSchema().dump(user.basic_auth).data
        data['change_password_next_login'] = basic_auth.get(
            'change_password_next_login', True)
        if links:
            data['_links'] = links
        return data, 200


class UsagerVLSTSVerifierNumeroVisa(CoreResource):
    def post(self):
        payload = request.get_json()
        numero_visa_to_check = payload.get('numero_visa', None)
        response = {
            'is_valid': current_user.vls_ts_numero_visa == numero_visa_to_check
        }
        return response, 200


class UsagerVLSTSCoordonnees(CoreResource):
    def __init__(self):
        super().__init__()
        self.field_not_empty = validate.Length(min=1, error='empty-field')

        def field_required_with_validators_for(document, field, validators):
            return field_for(
                document,
                field,
                required=True,
                error_messages={'required': 'missing-field'},
                validate=validators
            )

        def field_required_not_empty_for(document, field):
            return field_required_with_validators_for(document, field, [self.field_not_empty])

        class AdresseMandatorySchema(view_util.UnknownCheckedSchema):
            chez = field_for(AddressEmbeddedDocument, 'chez')
            numero_voie = field_for(AddressEmbeddedDocument, 'numero_voie')
            voie = field_required_not_empty_for(AddressEmbeddedDocument, 'voie')
            complement = field_for(AddressEmbeddedDocument, 'complement')
            code_postal = field_required_with_validators_for(
                AddressEmbeddedDocument,
                'code_postal',
                [
                    self.field_not_empty,
                    # TODO: find a way to refactor this duplicated rule from MongoEngine
                    validate.Regexp(regex=r"[0-9]{5}", error='bad-format-field')
                ]
            )
            ville = field_required_not_empty_for(AddressEmbeddedDocument, 'ville')

        class CoordonneesSchema(view_util.UnknownCheckedSchema):
            telephone = field_required_with_validators_for(
                Usager,
                'telephone',
                [
                    self.field_not_empty,
                    # TODO: find a way to refactor these duplicated rules from MongoEngine
                    validate.Length(max=22, error='bad-format-field'),
                    validate.Regexp(regex=r"^[+]?[0-9][0-9 ]+[0-9]$", error='bad-format-field')
                ]
            )
            email = field_required_not_empty_for(Usager, 'email')
            adresse = fields.Nested(AdresseMandatorySchema)

        self._coordonnees_schema = CoordonneesSchema()

    def patch(self):
        payload = request.get_json()

        coordonnees, errors = self._coordonnees_schema.load(payload)
        if errors:
            errors_payload = []
            for error in errors.keys():
                if error == 'adresse':
                    for adresse_error in errors.get(error):
                        errors_payload.append({
                            'code_erreur': errors.get('adresse').get(adresse_error)[0],
                            'payload_path': 'adresse.' + adresse_error
                        })
                else:
                    errors_payload.append({
                        'code_erreur': errors.get(error)[0],
                        'payload_path': error
                    })

            abort(400, errors=errors_payload)

        current_user.controller.add_coordonnees(**coordonnees)
        current_user.controller.save_or_abort()

        return {}, 200


class UsagerVLSTSDeclarerDateEntreeEnFrance(CoreResource):
    def __init__(self):
        super().__init__()

        class DateEntreeEnFranceSchema(view_util.UnknownCheckedSchema):
            date_entree_en_france = field_for(Usager, 'date_entree_en_france', required=True)

            class Meta:
                model_make_object = False

        self._date_entree_en_france_schema = DateEntreeEnFranceSchema()

    def post(self):
        payload = request.get_json()

        data, errors = self._date_entree_en_france_schema.load(payload)
        if errors:
            abort(400, **errors)

        current_user.controller.arrived_in_france_at(data.get('date_entree_en_france'))
        current_user.controller.save_or_abort()
        return {}, 200
