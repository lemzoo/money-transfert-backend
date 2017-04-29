import random
import requests
import string
import xmltodict

from enum import Enum
from flask import current_app
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry


def generate_reservation_number():
    # reservation number is not subject to collision, hence it could be any 32 char string
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(32))


def build_requests_factory(retry, backoff_factor):
    new_req = requests.Session()
    retries = Retry(total=retry, backoff_factor=backoff_factor)
    new_req.mount('http://', HTTPAdapter(max_retries=retries))
    new_req.mount('https://', HTTPAdapter(max_retries=retries))
    return new_req


INTERNAL_CODE = Enum('INTERNAL_CODE', {
    'SERVICE_DISABLED': 'service-disabled',
    'SERVICE_ERROR': 'service-error',
    'SERVICE_CONNECTION_ERROR': 'service-connection-error',
    'SERVICE_OK': 'service-ok',
    'STAMP_UNKNOWN': 'stamp-unknown',
    'CANAL_TYPE_UNKNOWN': 'canal-type-unknown',
    'ACTION_IMPOSSIBLE': 'action-impossible',
    'STAMP_EXPIRED': 'stamp-expired',
    'AUTHENTIFICATION_FAILED': 'authentification-failed',
    'BAD_STAMP_SERIES': 'bad-stamp-series',
    'BAD_RESERVATION_NUMBER': 'bad-reservation-number',
    'RETURN_CODE_UNKNOWN': 'return-code-unknown',
    'STAMP_STATUS_UNKNOWN': 'stamp-status-unknown',
})


PFTD_RETURN_CODE = {
    '-1': INTERNAL_CODE.SERVICE_ERROR,
    '0': INTERNAL_CODE.SERVICE_OK,
    '3': INTERNAL_CODE.STAMP_UNKNOWN,
    '5': INTERNAL_CODE.CANAL_TYPE_UNKNOWN,
    '7': INTERNAL_CODE.ACTION_IMPOSSIBLE,
    '8': INTERNAL_CODE.STAMP_EXPIRED,
    '15': INTERNAL_CODE.AUTHENTIFICATION_FAILED,
    '16': INTERNAL_CODE.BAD_STAMP_SERIES,
    '17': INTERNAL_CODE.BAD_RESERVATION_NUMBER,
}


class StampServiceError(Exception):

    def __init__(self, code=None):
        super().__init__()
        self.code = code


class StampService:

    SERVICE_PAYLOAD_TEMPLATE = """
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
       xmlns:tet="TETRATimbreNameSpace">
       <soapenv:Header/>
       <soapenv:Body>
          <tet:{method}>
             <tet:typeCanal>{canal_type}</tet:typeCanal>
             <tet:idCanal>{canal_id}</tet:idCanal>
             <tet:numeroTimbre>{stamp_number}</tet:numeroTimbre>
             <tet:numeroReservation>{reservation_number}</tet:numeroReservation>
          </tet:{method}>
       </soapenv:Body>
    </soapenv:Envelope>
    """

    def __init__(self):
        self.disabled = False
        self.testing_stub = False
        self.requests = None
        self.url = None
        self.cert = None
        self.canal_type = None
        self.canal_id = None
        self.timeout = None
        self.retry = None
        self.backoff_factor = None
        self.proxies = None

    def init_app(self, app):
        app.config.setdefault('DISABLE_PFTD', False)
        app.config.setdefault('PFTD_TESTING_STUB', False)
        app.config.setdefault('PFTD_URL', 'http://127.0.0.1')
        app.config.setdefault('PFTD_CANAL_TYPE', 0)
        app.config.setdefault('PFTD_CANAL_ID', '')
        app.config.setdefault('PFTD_TIMEOUT', 30)
        app.config.setdefault('PFTD_RETRY', 0)
        app.config.setdefault('PFTD_BACKOFF_FACTOR', 0.0)
        app.config.setdefault('PFTD_HTTP_PROXY', '')
        app.config.setdefault('PFTD_HTTPS_PROXY', '')
        app.config.setdefault('PFTD_CERTIFICATE', '')

        self.disabled = app.config.get('DISABLE_PFTD')
        self.testing_stub = app.config.get('PFTD_TESTING_STUB')
        self.url = app.config.get('PFTD_URL')
        self.cert = app.config.get('PFTD_CERTIFICATE')
        self.canal_type = app.config.get('PFTD_CANAL_TYPE')
        self.canal_id = app.config.get('PFTD_CANAL_ID')
        self.timeout = app.config.get('PFTD_TIMEOUT')
        self.retry = app.config.get('PFTD_RETRY')
        self.backoff_factor = app.config.get('PFTD_RETRY_BACKOFF_FACTOR')
        self.proxies = {
            'http': app.config.get('PFTD_HTTP_PROXY'),
            'https': app.config.get('PFTD_HTTPS_PROXY'),
        }
        self.requests = build_requests_factory(self.retry, self.backoff_factor)

        if not self.testing_stub and not self.url:
            self.disabled = True

    def _format_query_payload(self, method, stamp_number, reservation_number):
        return self.SERVICE_PAYLOAD_TEMPLATE.format(method=method, canal_type=self.canal_type,
                                                    canal_id=self.canal_id,
                                                    stamp_number=stamp_number,
                                                    reservation_number=reservation_number)

    def _call_remote_service(self, payload):
        try:
            current_app.logger.info('Call remote service with %s', payload)
            ret = self.requests.post(self.url, data=payload, timeout=self.timeout,
                                     proxies=self.proxies, cert=self.cert)
            current_app.logger.debug('Remote service response %s', ret.text)
            ret.raise_for_status()
            return ret
        except requests.RequestException:
            raise StampServiceError(INTERNAL_CODE.SERVICE_CONNECTION_ERROR.value)

    def _transform_xml_body_into_dict(self, body):
        try:
            content = xmltodict.parse(body)
            # popitem to remove xml headers until the content
            content = content.popitem()[1]
            content = content.popitem()[1]
            content = content.popitem()[1]
            content = content.popitem()[1]
            return content
        except (xmltodict.expat.ExpatError, KeyError, AttributeError):
            raise StampServiceError(INTERNAL_CODE.SERVICE_ERROR.value)

    def _lookup_pftd_code(self, code):
        try:
            return PFTD_RETURN_CODE[code]
        except KeyError:
            return INTERNAL_CODE.RETURN_CODE_UNKNOWN

    def _query(self, method, stamp_number, reservation_number):
        if self.disabled:
            raise StampServiceError(INTERNAL_CODE.SERVICE_DISABLED.value)

        if self.testing_stub:
            # Really simple fake response
            return {}, '0'

        payload = self._format_query_payload(method, stamp_number, reservation_number)
        ret = self._call_remote_service(payload)
        content = self._transform_xml_body_into_dict(ret.text)
        return_code = content.get('codeRetour')

        return content, return_code

    def consume_stamp(self, stamp_number, reservation_number):
        content, code = self._query('reserver', stamp_number, reservation_number)
        lookup_code = self._lookup_pftd_code(code)
        if lookup_code != INTERNAL_CODE.SERVICE_OK:
            raise StampServiceError(lookup_code.value)

        content, code = self._query('consommation', stamp_number, reservation_number)
        lookup_code = self._lookup_pftd_code(code)
        if lookup_code != INTERNAL_CODE.SERVICE_OK:
            raise StampServiceError(lookup_code.value)

        return content

    def get_details(self, stamp_number, reservation_number):

        STATUSES = {
            '1': 'achete',
            '2': 'reserve',
            '3': 'consomme',
            '4': 'annule',
            '5': 'rembourse',
            '6': 'demande-de-remboursement',
            '7': 'brule',
            '8': 'impaye'
        }

        ERROR_CODES = [
            INTERNAL_CODE.SERVICE_ERROR,
            INTERNAL_CODE.STAMP_UNKNOWN,
            INTERNAL_CODE.CANAL_TYPE_UNKNOWN,
            INTERNAL_CODE.AUTHENTIFICATION_FAILED,
            INTERNAL_CODE.BAD_RESERVATION_NUMBER
        ]

        content, code = self._query('isReservable', stamp_number, reservation_number)
        lookup_code = self._lookup_pftd_code(code)
        if lookup_code in ERROR_CODES:
            raise StampServiceError(lookup_code.value)

        try:
            status_key = content.get('etatTimbre').get('id')
            is_bad_stamp_series = (lookup_code == INTERNAL_CODE.BAD_STAMP_SERIES)
            status = 'mauvaise-serie' if is_bad_stamp_series else STATUSES[status_key]
        except (KeyError, AttributeError):
            raise StampServiceError(INTERNAL_CODE.STAMP_STATUS_UNKNOWN.value)

        try:
            amount = convert_cents_to_euros(int(content.get('quotite')))
        except ValueError:
            raise StampServiceError(INTERNAL_CODE.SERVICE_ERROR.value)

        is_consommable = (lookup_code == INTERNAL_CODE.SERVICE_OK)

        return {
            'is_consommable': is_consommable,
            'status': status,
            'amount': amount,
        }


def convert_cents_to_euros(cents):
    return cents / 100


stamp_service = StampService()
