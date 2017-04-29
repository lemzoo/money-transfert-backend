import calendar
import json
import operator

from datetime import datetime
from freezegun import freeze_time
from unittest.mock import patch, MagicMock

from services.ants_pftd import StampServiceError
from sief.model import Usager, Droit
from sief.model.referentials import Pays, Nationalite
from tests import common
from tests.fixtures import *


stamp_number = '1234567812345678'
reservation_number = 'A2345678A2345678A2345678A2345678'


def assert_response_contains_errors(response, expected_errors, expected_status_code=400):
    assert response.status_code == expected_status_code
    assert 'errors' in response.data
    assert response.data['errors'] == expected_errors


def assert_droit_is_created(expected_droit, gestionnaire_titres,
                            stamp_number, amount, reservation_number):
    assert expected_droit is not None
    assert expected_droit.agent_createur == gestionnaire_titres
    date_as_timestamp = calendar.timegm(datetime.utcnow().timetuple()) * 1000
    assert json.loads(expected_droit.taxe.to_json()) == {
        'statut_paiement': 'EFFECTUE',
        'montant': amount,
        'devise': 'EUR',
        'date_paiement_effectue': {'$date': date_as_timestamp},
        'timbre': {
            'numero': stamp_number,
            'numero_reservation': reservation_number
        }
    }


class TestPaiements(common.BaseTest):
    def setup(self):
        ref_pays = Pays(code='CIV', libelle="COTE D'IVOIRE")
        ref_pays.save()
        ref_nationalites = Nationalite(code='ARM', libelle="arménienne")
        ref_nationalites.save()

        self.payload = {}
        self.payload.update({'type_paiement': 'TIMBRE',
                             'numero_timbre': stamp_number,
                             'numero_etranger': '1234567890',
                             'montant': 45.6,
                             'etat_civil': {
                                 'nom': 'Soon-jeen',
                                 'prenoms': ['Kim'],
                                 'sexe': 'F',
                                 'date_naissance': datetime(1991, 2, 12),
                                 'codes_nationalites': ['ARM'],
                                 'code_pays_naissance': 'CIV',
                                 'ville_naissance': 'Braslou',
                                 'situation_familiale': 'CELIBATAIRE'
                             }})

    def test_abort_when_unauthorized(self):
        assert self.client_app.post('/paiements', data={}).status_code == 401

    def test_abort_when_no_permission(self, user):
        user_req = self.make_auth_request(user)

        assert user_req.post('/paiements', data={}).status_code == 403

    def test_return_error_when_payment_type_is_missing(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.pop('type_paiement', None)

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'missing-field', 'payload_path': 'type_paiement'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_payment_type_is_unknown(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'type_paiement': 'UNKNOWN'})

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'payment-type-unknown', 'payload_path': 'type_paiement'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_stamp_number_is_missing(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.pop('numero_timbre', None)

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'missing-field', 'payload_path': 'numero_timbre'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_stamp_number_has_not_16_chars(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'numero_timbre': '123345678'})

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-format-field', 'payload_path': 'numero_timbre'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_stamp_number_has_not_only_digits(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'numero_timbre': 'abcdefg!abcdefg!'})

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-format-field', 'payload_path': 'numero_timbre'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_numero_etranger_is_missing(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.pop('numero_etranger', None)

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'missing-field', 'payload_path': 'numero_etranger'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_numero_etranger_is_badly_formatted(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'numero_etranger': 'not-a-valid-number'})

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-format-field', 'payload_path': 'numero_etranger'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_montant_is_missing(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.pop('montant', None)

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'missing-field', 'payload_path': 'montant'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_montant_is_not_valid_number(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'montant': 'value'})

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-type-field', 'payload_path': 'montant'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_civil_status_fields_are_missing(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'etat_civil': {}})

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 400
        expected_errors = sorted([
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.code_pays_naissance'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.date_naissance'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.codes_nationalites'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.nom'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.prenoms'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.sexe'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.situation_familiale'},
            {'code_erreur': 'missing-field', 'payload_path': 'etat_civil.ville_naissance'}
        ], key=operator.itemgetter('payload_path'))
        errors = sorted(response.data.get('errors'), key=operator.itemgetter('payload_path'))
        assert errors == expected_errors

    def test_return_error_when_field_is_unknown(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload.update({'unknown_field': 'value'})

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'unknown-field',
                            'description_erreur': 'Unknown field name unknown_field'}]
        assert_response_contains_errors(response, expected_errors)

    @patch('services.ants_pftd.stamp_service')
    def test_return_error_when_stamp_service_raise_exception(self, mock_service,
                                                             gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.side_effect = StampServiceError(code='service-disabled')

        response = user_req.post('/paiements', data=self.payload)

        assert_response_contains_errors(response, [{'code_erreur': 'service-disabled'}], 500)

    @patch('sief.view.paiements_api.stamp_service')
    def test_returned_data_is_not_empty(self, mock_service, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'numero': stamp_number}

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        assert 'data' in response.data
        assert response.data['data'] is not {}

    @patch('sief.view.paiements_api.stamp_service')
    def test_return_links_in_response(self, mock_service, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'data': {}}

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        common.assert_response_contains_links(response, ['self'])

    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_call_consume_stamp(self, mock_service, mock_gen_resa_num, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'data': {}}
        mock_gen_resa_num.return_value = reservation_number

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        assert 'data' in response.data
        assert 'date_paiement_effectue' in response.data['data']
        assert mock_service.consume_stamp.call_count == 1
        assert mock_service.consume_stamp.called_once_with(stamp_number, reservation_number)

    @patch('sief.view.paiements_api.stamp_service')
    def test_create_usager_when_not_exist(self, mock_service, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'data': {}}

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        expected_usager = Usager.objects(identifiant_agdref=self.payload['numero_etranger']).first()
        assert expected_usager is not None

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_create_droit_with_taxe_when_usager_not_exist(self, mock_service, mock_gen_resa_num,
                                                          gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'data': {}}
        mock_gen_resa_num.return_value = reservation_number

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        usager = Usager.objects(identifiant_agdref=self.payload['numero_etranger']).first()
        expected_droit = Droit.objects(usager=usager).first()
        assert_droit_is_created(expected_droit, gestionnaire_titres, self.payload['numero_timbre'],
                                self.payload['montant'], reservation_number)

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_create_droit_with_taxe_when_usager_already_exists(self, mock_service,
                                                               mock_gen_resa_num,
                                                               gestionnaire_titres,
                                                               usager):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'data': {}}
        mock_gen_resa_num.return_value = reservation_number
        usager.identifiant_agdref = self.payload['numero_etranger']
        usager.save()

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        usager = Usager.objects(identifiant_agdref=self.payload['numero_etranger']).first()
        expected_droit = Droit.objects(usager=usager).first()
        assert_droit_is_created(expected_droit, gestionnaire_titres, self.payload['numero_timbre'],
                                self.payload['montant'], reservation_number)

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_create_droit_with_taxe_on_status_echoue_when_stamp_consumption_fail(self, mock_service,
                                                                                 mock_gen_resa_num,
                                                                                 gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.side_effect = StampServiceError(code='stamp-unknown')
        mock_gen_resa_num.return_value = reservation_number

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 500, response
        usager = Usager.objects(identifiant_agdref=self.payload['numero_etranger']).first()
        droit = Droit.objects(usager=usager).first()
        expected_taxe = droit.taxe
        assert expected_taxe.statut_paiement == 'ECHOUE'
        assert expected_taxe.date_paiement_effectue is None

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_return_error_when_stamp_is_known_as_already_consumed(self, mock_service,
                                                                  mock_gen_resa_num,
                                                                  gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        mock_service.consume_stamp.return_value = {'data': {}}
        mock_gen_resa_num.return_value = reservation_number
        # Consume the stamp
        response = user_req.post('/paiements', data=self.payload)
        assert response.status_code == 200

        # Try again to consume the stamp
        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 400, response
        expected_errors = [{'code_erreur': 'stamp-already-consumed'}]
        assert_response_contains_errors(response, expected_errors)

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_create_droit_when_stamp_exists_on_another_usager_but_not_consumed(self, mock_service,
                                                                               mock_gen_resa_num,
                                                                               gestionnaire_titres):
        # Given
        user_req = self.make_auth_request(gestionnaire_titres)
        # Force statut_paiement to be 'ECHOUE' by raising an exception
        mock_service.consume_stamp.side_effect = StampServiceError(code='service-connection-error')
        mock_gen_resa_num.return_value = reservation_number
        # First use of the stamp
        response = user_req.post('/paiements', data=self.payload)
        assert response.status_code == 500

        # Change usager
        self.payload.update({'numero_etranger': '0987654321'})
        # Restore the mock
        mock_service.consume_stamp = MagicMock(return_value={'data': {}})

        # When
        response = user_req.post('/paiements', data=self.payload)

        # Then
        assert response.status_code == 200, response
        usager = Usager.objects(identifiant_agdref=self.payload['numero_etranger']).first()
        expected_droit = Droit.objects(usager=usager).first()
        assert_droit_is_created(expected_droit, gestionnaire_titres, self.payload['numero_timbre'],
                                self.payload['montant'], reservation_number)

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_update_droit_when_stamp_exists_on_the_same_usager_but_not_consumed(self, mock_service,
                                                                                mock_gen_resa_num,
                                                                                gestionnaire_titres):
        # Given
        user_req = self.make_auth_request(gestionnaire_titres)
        # Force statut_paiement to be 'ECHOUE' by raising an exception
        mock_service.consume_stamp.side_effect = StampServiceError(code='service-connection-error')
        mock_gen_resa_num.return_value = reservation_number
        # First use of the stamp
        response = user_req.post('/paiements', data=self.payload)
        assert response.status_code == 500

        # Restore the mock
        mock_service.consume_stamp = MagicMock(return_value={'data': {}})

        # When
        response = user_req.post('/paiements', data=self.payload)

        # Then
        assert response.status_code == 200, response
        usager = Usager.objects(identifiant_agdref=self.payload['numero_etranger']).first()
        expected_droits = Droit.objects(usager=usager)
        assert len(expected_droits) == 1
        assert expected_droits[0].taxe.statut_paiement == 'EFFECTUE'

    @freeze_time('2017-02-15')
    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('sief.view.paiements_api.stamp_service')
    def test_do_not_regenerate_reservation_number_when_stamp_exists(self, mock_service,
                                                                    mock_gen_resa_num,
                                                                    gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        # Force statut_paiement to be 'ECHOUE' by raising an exception
        mock_service.consume_stamp.side_effect = StampServiceError(code='service-connection-error')
        mock_gen_resa_num.return_value = reservation_number
        # First use of the stamp
        response = user_req.post('/paiements', data=self.payload)
        assert response.status_code == 500

        # Change usager
        self.payload.update({'numero_etranger': '0987654321'})
        # Restore the mock
        mock_gen_resa_num.reset_mock()
        mock_service.consume_stamp = MagicMock(return_value={'data': {}})

        response = user_req.post('/paiements', data=self.payload)

        assert response.status_code == 200
        assert mock_gen_resa_num.call_count == 0

    def test_return_error_if_code_pays_naissance_is_unknown(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['code_pays_naissance'] = ''

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'unknown-field',
                            'payload_path': 'etat_civil.code_pays_naissance',
                            'description_erreur': 'Country code doesn\'t exist in referential'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_ville_naissance_is_badly_formatted(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['ville_naissance'] = '1234567890123456789012345678901'

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-format-field',
                            'payload_path': 'etat_civil.ville_naissance'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_ville_naissance_is_not_valid_type(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['ville_naissance'] = {}

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-type-field',
                            'payload_path': 'etat_civil.ville_naissance'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_situation_familiale_is_not_valid(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['situation_familiale'] = 'UNKNOWN'

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-format-field',
                            'payload_path': 'etat_civil.situation_familiale'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_when_prenoms_is_badly_formatted(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['prenoms'] = ['(weird-name)']

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'bad-format-field',
                            'payload_path': 'etat_civil.prenoms'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_if_a_codes_nationalites_is_unknown(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['codes_nationalites'] = ['ARM', '']

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'unknown-field',
                            'payload_path': 'etat_civil.codes_nationalites',
                            'description_erreur': 'Nationality code doesn\'t exist in referential'}]
        assert_response_contains_errors(response, expected_errors)

    def test_return_error_if_a_codes_nationalites_is_empty(self, gestionnaire_titres):
        user_req = self.make_auth_request(gestionnaire_titres)
        self.payload['etat_civil']['codes_nationalites'] = []

        response = user_req.post('/paiements', data=self.payload)

        expected_errors = [{'code_erreur': 'empty-field',
                            'payload_path': 'etat_civil.codes_nationalites'}]
        assert_response_contains_errors(response, expected_errors)
