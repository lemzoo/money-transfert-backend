import flask
import pytest
import requests

from services.ants_pftd import StampService, StampServiceError, INTERNAL_CODE
from tests import common
from unittest.mock import MagicMock, PropertyMock, patch


RESPONSE_PAYLOAD_TEMPLATE = """<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tet="TETRATimbreNameSpace">
   <soapenv:Header/>
   <soapenv:Body>
      <tet:{method}>
         <tet:return>
            <codeRetour>{codeRetour}</codeRetour>
            <dateFinValidite></dateFinValidite>
            <etatTimbre></etatTimbre>
            <numero>{numero}</numero>
            <numeroReservation>{numeroReservation}</numeroReservation>
            <quotite></quotite>
            <serieTimbre></serieTimbre>
            <typeTimbre></typeTimbre>
         </tet:return>
      </tet:{method}>
   </soapenv:Body>
</soapenv:Envelope>"""

NUMERO_TIMBRE = '4265548913458692'
NUMERO_RESERVATION = '560420176K07CI38Z'


class TestStampService(common.BaseTest):

    def setup_method(self, method):
        self.app_testing = flask.Flask(__name__)
        self.service = StampService()

        self.response = {}
        self.response.update({
            'codeRetour': '0',
            'etatTimbre': {'id': '1'},
            'quotite': '8600'
        })

    def test_init_app_with_config(self):
        self.app_testing.config['DISABLE_PFTD'] = False
        self.app_testing.config['PFTD_TESTING_STUB'] = False
        self.app_testing.config['PFTD_URL'] = 'http://127.0.0.1'
        self.app_testing.config['PFTD_CERTIFICATE'] = '/certificat.cert'
        self.app_testing.config['PFTD_CANAL_TYPE'] = 7
        self.app_testing.config['PFTD_CANAL_ID'] = 'ID:VLSTS'
        self.app_testing.config['PFTD_TIMEOUT'] = 60
        self.app_testing.config['PFTD_RETRY'] = 3
        self.app_testing.config['PFTD_RETRY_BACKOFF_FACTOR'] = 0.1
        self.app_testing.config['PFTD_HTTP_PROXY'] = ''
        self.app_testing.config['PFTD_HTTPS_PROXY'] = ''

        self.service.init_app(self.app_testing)

        assert not self.service.disabled
        assert not self.service.testing_stub
        assert self.service.requests
        assert self.service.url == 'http://127.0.0.1'
        assert self.service.cert == '/certificat.cert'
        assert self.service.canal_type == 7
        assert self.service.canal_id == 'ID:VLSTS'
        assert self.service.timeout == 60
        assert self.service.retry == 3
        assert self.service.backoff_factor == 0.1
        assert 'http' in self.service.proxies and 'https' in self.service.proxies

    def test_service_is_disabled_when_no_stub_and_no_url(self):
        self.app_testing.config['PFTD_TESTING_STUB'] = False
        self.app_testing.config['PFTD_URL'] = ''

        self.service.init_app(self.app_testing)

        assert self.service.disabled is True

    def test_format_query_payload(self):
        self.service.canal_type = 7
        self.service.canal_id = 'ID:VLSTS'
        method = 'consommation'
        stamp_number = '1122334455'
        reservation_number = stamp_number

        payload = self.service._format_query_payload(method, stamp_number, reservation_number)

        assert payload == """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
       xmlns:tet="TETRATimbreNameSpace">
       <soapenv:Header/>
       <soapenv:Body>
          <tet:consommation>
             <tet:typeCanal>7</tet:typeCanal>
             <tet:idCanal>ID:VLSTS</tet:idCanal>
             <tet:numeroTimbre>1122334455</tet:numeroTimbre>
             <tet:numeroReservation>1122334455</tet:numeroReservation>
          </tet:consommation>
       </soapenv:Body>
    </soapenv:Envelope>
    """

    def test_call_remote_service(self):
        payload = '<soapenv:Envelope>...</soapenv:Envelope>'
        response = requests.Response()
        response.status_code = 200
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        ret = self.service._call_remote_service(payload)

        self.service.requests.post.assert_called_once_with(
            None, timeout=None, cert=None, data=payload, proxies=None)
        assert ret.status_code == 200

    def test_call_remote_service_raise_exception_when_request_failed(self):
        response = requests.Response()
        response.status_code = 404
        payload = '<soapenv:Envelope>...</soapenv:Envelope>'
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service._call_remote_service(payload)

        assert e.value.code == INTERNAL_CODE.SERVICE_CONNECTION_ERROR.value

    def test_transform_xml_body_into_dict(self):
        body = RESPONSE_PAYLOAD_TEMPLATE.format(method='consommation', codeRetour='0',
                                                numero=NUMERO_TIMBRE,
                                                numeroReservation=NUMERO_RESERVATION)

        content = self.service._transform_xml_body_into_dict(body)

        assert content == {
            'codeRetour': '0',
            'dateFinValidite': None,
            'etatTimbre': None,
            'numero': NUMERO_TIMBRE,
            'numeroReservation': NUMERO_RESERVATION,
            'quotite': None,
            'serieTimbre': None,
            'typeTimbre': None
        }

    def test_transform_xml_body_into_dict_raise_exception_when_body_is_unexpected(self):
        unexpected_body = """<soapenv:Envelope>...</soapenv:Envelope>"""

        with pytest.raises(StampServiceError) as e:
            self.service._transform_xml_body_into_dict(unexpected_body)

        assert e.value.code == INTERNAL_CODE.SERVICE_ERROR.value

    def test_query(self):
        response = requests.Response()
        response.status_code = 200
        response.encoding = 'utf-8'
        response_text = RESPONSE_PAYLOAD_TEMPLATE.format(method='consommation', codeRetour='0',
                                                         numero='X', numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with patch('requests.Response.text', new_callable=PropertyMock) as mock_text:
            mock_text.return_value = response_text
            data, code = self.service._query('consommation', 'X', 'Y')

        self.service.requests.post.assert_called_once()
        assert data['codeRetour'] == '0'
        assert data['numero'] == 'X'
        assert data['numeroReservation'] == 'Y'
        assert code is not None

    def test_query_return_default_when_testing_stub_is_true(self):
        self.service.testing_stub = True

        data, code = self.service._query('consommation', 'X', 'Y')

        assert data == {}
        assert code == '0'

    def test_query_raise_exception_when_disabled_is_true(self):
        self.service.disabled = True

        with pytest.raises(StampServiceError) as e:
            self.service._query('consommation', 'X', 'Y')

        assert e.value.code == INTERNAL_CODE.SERVICE_DISABLED.value

    def test_lookup_pftd_code_when_code_exist(self):
        code = '0'

        result = self.service._lookup_pftd_code(code)

        assert result == INTERNAL_CODE.SERVICE_OK

    def test_lookup_pftd_code_when_code_do_not_exist(self):
        code = 'X'

        result = self.service._lookup_pftd_code(code)

        assert result == INTERNAL_CODE.RETURN_CODE_UNKNOWN

    def test_consume_stamp_is_ok(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        call_1 = response
        call_1.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                       codeRetour='0',
                                                       numero='X',
                                                       numeroReservation='Y')
        call_2 = response
        call_2.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='consommation',
                                                       codeRetour='0',
                                                       numero='X',
                                                       numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(side_effect=[call_1, call_2])

        data = self.service.consume_stamp('X', 'Y')

        assert self.service.requests.post.call_count == 2
        assert data == {
            'codeRetour': '0',
            'dateFinValidite': None,
            'etatTimbre': None,
            'numero': 'X',
            'numeroReservation': 'Y',
            'quotite': None,
            'serieTimbre': None,
            'typeTimbre': None
        }

    def test_consume_stamp_is_ko_when_remote_service_sent_exception(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='-1',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.SERVICE_ERROR.value

    def test_consume_stamp_is_ko_when_stamp_is_unknown(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='3',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.STAMP_UNKNOWN.value

    def test_consume_stamp_is_ko_when_canal_type_is_unknown(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='5',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.CANAL_TYPE_UNKNOWN.value

    def test_consume_stamp_is_ko_when_action_is_impossible(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='7',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.ACTION_IMPOSSIBLE.value

    def test_consume_stamp_is_ko_when_stamp_is_expired(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='8',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.STAMP_EXPIRED.value

    def test_consume_stamp_is_ko_when_certificate_is_unauthorized(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='15',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.AUTHENTIFICATION_FAILED.value

    def test_consume_stamp_is_ko_when_stamp_is_bad_series(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='16',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.BAD_STAMP_SERIES.value

    def test_consume_stamp_is_ko_when_reservation_number_is_incorrect(self):
        response = MagicMock()
        response.status_code = 200
        response.encoding = 'utf-8'
        response.text = RESPONSE_PAYLOAD_TEMPLATE.format(method='reserver',
                                                         codeRetour='17',
                                                         numero='X',
                                                         numeroReservation='Y')
        self.service.requests = MagicMock(['post'])
        self.service.requests.post = MagicMock(return_value=response)

        with pytest.raises(StampServiceError) as e:
            self.service.consume_stamp('X', 'Y')

        assert e.value.code == INTERNAL_CODE.BAD_RESERVATION_NUMBER.value

    def test_get_details_handle_status_achete(self):
        self.response.update({'etatTimbre': {'id': '1'}})
        self.service._query = MagicMock(return_value=(self.response, '0'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'achete'
        assert data['is_consommable'] == True

    def test_get_details_handle_status_reserve(self):
        self.response.update({'etatTimbre': {'id': '2'}})
        self.service._query = MagicMock(return_value=(self.response, '0'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'reserve'
        assert data['is_consommable'] == True

    def test_get_details_handle_status_consomme(self):
        self.response.update({'etatTimbre': {'id': '3'}})
        self.service._query = MagicMock(return_value=(self.response, '7'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'consomme'
        assert data['is_consommable'] == False

    def test_get_details_handle_status_annule(self):
        self.response.update({'etatTimbre': {'id': '4'}})
        self.service._query = MagicMock(return_value=(self.response, '7'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'annule'
        assert data['is_consommable'] == False

    def test_get_details_handle_status_rembourse(self):
        self.response.update({'etatTimbre': {'id': '5'}})
        self.service._query = MagicMock(return_value=(self.response, '7'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'rembourse'
        assert data['is_consommable'] == False

    def test_get_details_handle_status_demande_de_remboursement(self):
        self.response.update({'etatTimbre': {'id': '6'}})
        self.service._query = MagicMock(return_value=(self.response, '7'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'demande-de-remboursement'
        assert data['is_consommable'] == False

    def test_get_details_handle_status_brule(self):
        self.response.update({'etatTimbre': {'id': '7'}})
        self.service._query = MagicMock(return_value=(self.response, '7'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'brule'
        assert data['is_consommable'] == False

    def test_get_details_handle_status_impaye(self):
        self.response.update({'etatTimbre': {'id': '8'}})
        self.service._query = MagicMock(return_value=(self.response, '7'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'impaye'
        assert data['is_consommable'] == False

    def test_get_details_handle_timbre_mauvaise_serie(self):
        self.service._query = MagicMock(return_value=(self.response, '16'))

        data = self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert data['status'] == 'mauvaise-serie'
        assert data['is_consommable'] == False

    def test_get_details_handle_numero_reservation_incorrect(self):
        self.service._query = MagicMock(return_value=(self.response, '17'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.BAD_RESERVATION_NUMBER.value

    def test_get_details_should_call_remote_service(self):
        self.service._query = MagicMock(return_value=(self.response, '0'))

        self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        self.service._query.assert_called_with('isReservable', NUMERO_TIMBRE, NUMERO_RESERVATION)

    def test_get_details_should_raise_when_quotite_is_unexpected(self):
        self.response.update({'quotite': 'unexpected'})

        self.service._query = MagicMock(return_value=(self.response, '0'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.SERVICE_ERROR.value

    def test_get_details_should_raise_when_stamp_status_is_unknown(self):
        self.response.update({'etatTimbre': {'id': '-1'}})

        self.service._query = MagicMock(return_value=(self.response, '0'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.STAMP_STATUS_UNKNOWN.value

    def test_get_details_should_raise_when_remote_service_failed(self):
        self.service._query = MagicMock(return_value=(self.response, '-1'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.SERVICE_ERROR.value

    def test_get_details_should_raise_when_stamp_is_unknown(self):
        self.service._query = MagicMock(return_value=(self.response, '3'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.STAMP_UNKNOWN.value

    def test_get_details_should_raise_when_canal_type_is_unknown(self):
        self.service._query = MagicMock(return_value=(self.response, '5'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.CANAL_TYPE_UNKNOWN.value

    def test_get_details_should_raise_when_certificate_is_unauthorized(self):
        self.service._query = MagicMock(return_value=(self.response, '15'))

        with pytest.raises(StampServiceError) as e:
            self.service.get_details(NUMERO_TIMBRE, NUMERO_RESERVATION)

        assert e.value.code == INTERNAL_CODE.AUTHENTIFICATION_FAILED.value
