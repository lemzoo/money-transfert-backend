from unittest.mock import patch
import pytest

from services.ants_pftd import StampServiceError
from sief.permissions import POLICIES as p
from sief.model import Droit
from tests import common
from tests.fixtures import *

STAMP_NUMBER = '1234567812345678'


@pytest.fixture
def user_timbre(user):
    user.permissions.append(p.timbre.voir.name)
    user.save()
    return user


class TestTimbre(common.BaseTest):

    def test_timbre_should_abort_when_unauthorized(self):
        assert self.client_app.get('/timbres/%s' % STAMP_NUMBER).status_code == 401

    def test_timbre_should_abort_when_no_permission(self, user):
        user_req = self.make_auth_request(user, user._raw_password)

        assert user_req.get('/timbres/%s' % STAMP_NUMBER).status_code == 403

    def test_timbre_should_abord_when_stamp_number_is_none(self, user):
        user_req = self.make_auth_request(user, user._raw_password)

        assert user_req.get('/timbres/').status_code == 404

    @patch('services.ants_pftd.stamp_service.get_details')
    def test_timbre_should_return_stamp_details(self, mock_get_details, user_timbre):
        user_req = self.make_auth_request(user_timbre, user_timbre._raw_password)
        mock_get_details.return_value = {
            'is_consommable': True,
            'status': 'consumable',
            'amount': 10.00
        }

        ret = user_req.get('/timbres/%s' % STAMP_NUMBER)

        assert ret.status_code == 200
        assert ret.data['data']['amount'] == 10.00
        assert ret.data['data']['status'] == 'consumable'
        assert ret.data['data']['is_consommable'] is True
        assert ret.data['_links']['self'] == '/timbres/%s' % STAMP_NUMBER

    @patch('services.ants_pftd.stamp_service.get_details')
    def test_timbre_should_call_ants_service(self, mock_get_details, user_timbre):
        user_req = self.make_auth_request(user_timbre, user_timbre._raw_password)
        mock_get_details.return_value = {}

        ret = user_req.get('/timbres/%s' % STAMP_NUMBER)

        assert ret.status_code == 200
        assert mock_get_details.call_count == 1
        args, kwargs = mock_get_details.call_args
        assert args[0] == STAMP_NUMBER
        assert isinstance(args[1], str)

    @patch('services.ants_pftd.stamp_service.get_details')
    def test_timbre_should_abort_when_service_raise_exception(self, mock_get_details, user_timbre):
        user_req = self.make_auth_request(user_timbre, user_timbre._raw_password)
        mock_get_details.side_effect = StampServiceError(code='service-disabled')

        ret = user_req.get('/timbres/%s' % STAMP_NUMBER)

        assert ret.status_code == 500
        assert ret.data['errors'][0]['code_erreur'] == 'service-disabled'

    @patch('services.ants_pftd.stamp_service.get_details')
    def test_return_error_when_stamp_number_has_not_16_chars(self, mock_get_details, user_timbre):
        user_req = self.make_auth_request(user_timbre, user_timbre._raw_password)
        BAD_STAMP_NUMBER = '12345678'

        ret = user_req.get('/timbres/%s' % BAD_STAMP_NUMBER)

        assert ret.status_code == 400
        assert ret.data['errors'][0]['code_erreur'] == 'bad-format'

    @patch('sief.view.timbre_api.generate_reservation_number')
    @patch('services.ants_pftd.stamp_service.get_details')
    def test_reuse_reservation_number_when_stamp_exists_on_droit(self, mock_get_details,
                                                                 mock_gen_resa_num,
                                                                 user_timbre,
                                                                 usager):
        user_req = self.make_auth_request(user_timbre)
        mock_get_details.return_value = {}
        expected_reservation_number = 'A2345678A2345678A2345678A2345678'
        droit_payload = {
            'usager': usager,
            'agent_createur': user_timbre,
            'taxe': {
                'statut_paiement': 'EFFECTUE',
                'montant': 100,
                'timbre': {
                    'numero': STAMP_NUMBER,
                    'numero_reservation': expected_reservation_number
                }
            }
        }
        droit = Droit(**droit_payload)
        droit.controller.save_or_abort()

        ret = user_req.get('/timbres/%s' % STAMP_NUMBER)

        assert ret.status_code == 200
        assert mock_gen_resa_num.call_count == 0
        args, kwargs = mock_get_details.call_args
        actual_reservation_number = args[1]
        assert expected_reservation_number == actual_reservation_number
