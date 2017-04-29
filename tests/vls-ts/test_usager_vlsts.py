import json
import operator
from datetime import datetime

from sief.model import Usager
from sief.model.usager import Localisation
from tests import common
from tests.fixtures import *


def get_response(context, usager):
    user_req = context.make_auth_request(usager)
    if hasattr(context, 'token') and context.token is not None:
        user_req.token = context.token
    return user_req.get(context.route)


class TestUsagerVLSTS(common.BaseTest):
    def test_get_moi(self, usager_with_credentials):
        user = usager_with_credentials
        self.route = '/vlsts/moi'
        response = get_response(self, user)
        assert response.status_code == 200, response
        assert 'change_password_next_login' in response.data
        assert response.data is not None

    def test_change_password_next_login(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        user = usager_with_credentials
        # Sanity check
        self.route = '/vlsts/moi'
        response = get_response(self, user)
        assert response.status_code == 200, response
        assert 'change_password_next_login' in response.data
        assert response.data['change_password_next_login']

        # Change the password
        params = {
            'login': user.basic_auth.login,
            'password': user._raw_password,
            'new_password': 'Password01!'
        }
        response = user_req.post('/usager/login/password', data=params)
        assert response.status_code == 200, response
        assert 'token' in response.data
        # Save token for next request
        self.token = response.data['token']

        # Change the password is not mandatory for next login
        self.route = '/vlsts/moi'
        response = get_response(self, user)
        assert response.status_code == 200, response
        assert 'change_password_next_login' in response.data
        assert not response.data['change_password_next_login']


class TestUsagerVLSTSVerifierNumeroVisa(common.BaseTest):
    def test_usager_give_wrong_visa_number(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        user = usager_with_credentials
        good_visa_number = '123A4B5'
        user.vls_ts_numero_visa = good_visa_number
        user.save()

        bad_visa_number = '123A4B6'
        response = user_req.post('/vlsts/moi/verifier_numero_visa',
                                 data={'numero_visa': bad_visa_number})

        assert response.status_code == 200, response
        assert not response.data['is_valid']

    def test_usager_give_rigth_visa_number(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        user = usager_with_credentials
        good_visa_number = '123A4B5'
        user.vls_ts_numero_visa = good_visa_number
        user.save()

        response = user_req.post('/vlsts/moi/verifier_numero_visa',
                                 data={'numero_visa': good_visa_number})

        assert response.status_code == 200, response
        assert response.data['is_valid']


class TestUsagerVLSTSCoordonnees(common.BaseTest):
    def test_update_usager_contact_details(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        adresse = {
            'chez': 'chez Michel Dupond',
            'numero_voie': '59',
            'voie': 'Rue Pascal Renaud',
            'complement': '5e étage',
            'code_postal': '59000',
            'ville': 'Lille'
        }
        params = {
            'adresse': adresse,
            'telephone': '+3340404040',
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 200, response

        expected_usager = Usager.objects(id=usager_with_credentials.id).first()
        assert expected_usager.telephone == '+3340404040'
        assert expected_usager.email == 'email@test.com'
        assert len(expected_usager.localisations) == 1

        expected_localisation = expected_usager.localisations[0]
        assert isinstance(expected_localisation, Localisation)
        assert json.loads(expected_localisation.adresse.to_json()) == adresse

    def test_return_error_if_phone_is_missing(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': 'Rue Pascal Renaud',
                'complement': '5e étage',
                'code_postal': '59000',
                'ville': 'Lille'
            },
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        assert response.data.get('errors') == [
            {'code_erreur': 'missing-field', 'payload_path': 'telephone'}]

    def test_return_error_if_email_is_missing(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': 'Rue Pascal Renaud',
                'complement': '5e étage',
                'code_postal': '59000',
                'ville': 'Lille'
            },
            'telephone': '+3340404040'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        assert response.data.get('errors') == [
            {'code_erreur': 'missing-field', 'payload_path': 'email'}]

    def test_return_error_if_required_fields_are_empty(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': 'Rue Pascal Renaud',
                'complement': '5e étage',
                'code_postal': '59000',
                'ville': 'Lille'
            },
            'telephone': '',
            'email': ''
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        expected_errors = [
            {'code_erreur': 'empty-field', 'payload_path': 'email'},
            {'code_erreur': 'empty-field', 'payload_path': 'telephone'},
        ]
        errors = sorted(response.data.get('errors'), key=operator.itemgetter('payload_path'))
        assert errors == expected_errors

    def test_return_error_if_address_required_fields_are_missing(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {},
            'telephone': '+3340404040',
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        expected_errors = [
            {'code_erreur': 'missing-field', 'payload_path': 'adresse.code_postal'},
            {'code_erreur': 'missing-field', 'payload_path': 'adresse.ville'},
            {'code_erreur': 'missing-field', 'payload_path': 'adresse.voie'},
        ]
        errors = sorted(response.data.get('errors'), key=operator.itemgetter('payload_path'))
        assert errors == expected_errors

    def test_return_error_if_address_required_fields_are_empty(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': '',
                'complement': '5e étage',
                'code_postal': '',
                'ville': ''
            },
            'telephone': '+3340404040',
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        expected_errors = [
            {'code_erreur': 'empty-field', 'payload_path': 'adresse.code_postal'},
            {'code_erreur': 'empty-field', 'payload_path': 'adresse.ville'},
            {'code_erreur': 'empty-field', 'payload_path': 'adresse.voie'},
        ]
        errors = sorted(response.data.get('errors'), key=operator.itemgetter('payload_path'))
        assert errors == expected_errors

    def test_return_error_if_postal_code_is_not_properly_formatted(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': 'Rue Pascal Renaud',
                'complement': '5e étage',
                'code_postal': '59p',
                'ville': 'Lille'
            },
            'telephone': '+3340404040',
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        expected_errors = [{'code_erreur': 'bad-format-field',
                            'payload_path': 'adresse.code_postal'}]
        assert response.data.get('errors') == expected_errors, response.data

    def test_return_error_if_phone_is_not_properly_formatted(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': 'Rue Pascal Renaud',
                'complement': '5e étage',
                'code_postal': '59000',
                'ville': 'Lille'
            },
            'telephone': 'not-a-correct-number',
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        assert response.data.get('errors') == [
            {'code_erreur': 'bad-format-field', 'payload_path': 'telephone'}], response.data

    def test_return_error_if_phone_is_too_long(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)
        params = {
            'adresse': {
                'chez': 'chez Michel Dupond',
                'numero_voie': '59',
                'voie': 'Rue Pascal Renaud',
                'complement': '5e étage',
                'code_postal': '59000',
                'ville': 'Lille'
            },
            'telephone': '+0123456789012345678901',
            'email': 'email@test.com'
        }

        response = user_req.patch('/vlsts/moi/coordonnees', data=params)

        assert response.status_code == 400, response
        assert response.data.get('errors') == [
            {'code_erreur': 'bad-format-field', 'payload_path': 'telephone'}], response.data


class TestUsagerVLSTSDeclarerDateEntreeEnFrance(common.BaseTest):
    def test_register_arrival_date(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)

        response = user_req.post('/vlsts/moi/declarer_date_entree_en_france',
                                 data={'date_entree_en_france': '2017-01-08'})

        assert response.status_code == 200, response
        expected_usager = Usager.objects(id=usager_with_credentials.id).first()
        assert expected_usager.date_entree_en_france == datetime(2017, 1, 8)

    def test_return_error_if_no_date_is_given(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)

        response = user_req.post('/vlsts/moi/declarer_date_entree_en_france', data={})

        assert response.status_code == 400, response

    def test_return_error_if_given_date_is_badly_formatted(self, usager_with_credentials):
        user_req = self.make_auth_request(usager_with_credentials)

        response = user_req.post('/vlsts/moi/declarer_date_entree_en_france',
                                 data={'date_entree_en_france': 'not a date'})

        assert response.status_code == 400, response
