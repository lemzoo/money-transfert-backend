from suds.client import Client
from suds.transport import TransportError
from suds.transport.https import HttpAuthenticated
from urllib.request import HTTPSHandler
from xmltodict import parse
import ssl
from datetime import datetime
import unicodedata
import re
import logging


MACRO_BLOCK_PATTERN = r'[0-9]{6}PREC'

ENTRY_02_CODE_TO_FIELD = {
    '02': 'id_fpr',
    '07': 'sexe',
    '25': 'message',
    '27': 'statut_fiche'
}

ENTRY_03_CODE_TO_FIELD = {
    '11': 'nom',
    '12': 'prenom',
    '13': 'date_naissance',
    # '16': '',
    '18': 'ville',
    '19': 'localisation',
    '20': 'nationalite',
    '27': 'statut_fiche',
    '22': 'conjoint_nom',
    '23': 'conjoint_prenom'
}


class FprError(Exception):
    pass


class FprNotInitializedError(Exception):
    pass


class FprDisabledError(FprError):
    pass


class FprQueryError(FprError):
    pass


class FprConnectionError(FprError):
    pass


class FprHttpAuthenticated(HttpAuthenticated):

    """Custom http suds context to handle https with certificate"""

    def __init__(self, *args, cert=None, **kwargs):
        self.cert = cert
        super().__init__(*args, **kwargs)

    def u2open(self, request):
        # Broken WSDL specify the url as http instead of https
        request.full_url = request.full_url.replace('http://', 'https://')
        return super().u2open(request)

    def u2handlers(self):
        handlers = super().u2handlers()
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        context.set_ciphers('RC4-MD5')
        context.load_verify_locations(self.cert)
        handlers.append(HTTPSHandler(context=context))
        return handlers


def _parse_block(raw):
    # A block is 2 digits code, then 3 digits length and finally the body
    code = raw[:2]
    # If we have hit padding bytes, there is nothing more to do
    if not code.strip():
        return ('', '', None)
    size = int(raw[2:5])
    offset = 5 + size
    body = raw[5: offset]
    assert len(body) == size, 'code %s was marked to have a'  \
                              ' %s long body, got `%s`' % (code, size, body)
    remains = raw[offset:]
    return (code, body, remains)


def _code_to_field(body, index):
    ret = {}
    while body:
        block_code, block_body, body = _parse_block(body)
        field = index.get(block_code)
        if field:
            ret[field] = block_body
    return ret


def _parse_dossiers(raw):
    dossiers = []
    assert re.match(MACRO_BLOCK_PATTERN, raw)
    blocks = re.split(MACRO_BLOCK_PATTERN, raw)[1:]
    for block in blocks:
        # Response consist into a header (that we skip) then some star-separated entries
        for raw_entry in block.split('*')[1:]:
            # Each entry is starts with a `*`, then a code on 2 digits and finally it body
            code = raw_entry[:2]
            body = raw_entry[2:]
            if code == '01':
                if body[:6] == '01001P':
                    dossiers.append({'etats_civils': []})
            elif code == '02':
                dossiers[-1].update(_code_to_field(body, ENTRY_02_CODE_TO_FIELD))
            elif code == '03':
                etat_civil = _code_to_field(body, ENTRY_03_CODE_TO_FIELD)
                dossiers[-1]['etats_civils'].append(etat_civil)
            elif code == '99':
                # FPR not available
                _, msg, _ = _parse_block(body)
                raise FprConnectionError(
                    "Le FPR a notifié son indisponiblité (%s)" % msg)
            elif code == '90':
                # FPR error
                _, msg, _ = _parse_block(body)
                raise FprQueryError('Erreur venant du FPR (%s)' % msg)
    return {
        'resultat': bool(dossiers),
        'dossiers': dossiers
    }


def _config_logger(logger, level):
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
    steam_handler = logging.StreamHandler()
    steam_handler.setLevel(logging.DEBUG)
    steam_handler.setFormatter(formatter)
    logger.addHandler(steam_handler)


class FprService:

    MSG_TEMPLATE = ("0152PREC    "
                    "*020100308002044{lastname:<44}03025{firstname:<25}04008{birthday:<8}"
                    "*010100210020020303008AGDREF  05002PF")
    SERVICE_PAYLOAD_TEMPLATE = """<?xml version="1.0" encoding="ISO-8859-1"?>
    <!DOCTYPE requete SYSTEM "Requete.dtd">
    <requete>
        <identification>
            <application>{app}</application>
            <parametre>{param}</parametre>
            <commande>{cmd}</commande>
        </identification>
        <infotrace>
            <identifiant>{id}</identifiant>
            <poste>{poste}</poste>
            <scom>{scom}</scom>
        </infotrace>
        <message>
            <valeur>{msg}</valeur>
        </message>
    </requete>
"""

    def __init__(self, app=None, debug=False, **kwargs):
        self.wsdl_url = None
        self.force_query_url = None
        self._initialized = False
        self._client = None
        self.proxies = None
        self.disabled = False
        self.testing_stub = False
        self.contact_timeout = 30
        self.service_opts = {}
        self.service_opts.update(**kwargs)
        if app:
            self.init_app(app)

    def init_app(self, app):
        app.config.setdefault('DISABLE_FPR', False)
        app.config.setdefault('FPR_TESTING_STUB', False)
        app.config.setdefault('FPR_WSDL_URL', '')
        app.config.setdefault('FPR_FORCE_QUERY_URL', '')
        app.config.setdefault('FPR_CERTIFICATE', '')
        app.config.setdefault('FPR_HTTP_PROXY', '')
        app.config.setdefault('FPR_HTTPS_PROXY', '')
        app.config.setdefault('FPR_IDENTIFICATION_APPLICATION', '')
        app.config.setdefault('FPR_IDENTIFICATION_PARAMETRE', '')
        app.config.setdefault('FPR_IDENTIFICATION_COMMANDE', '')
        app.config.setdefault('FPR_INFOTRACE_IDENTIFIANT', '')
        app.config.setdefault('FPR_INFOTRACE_POSTE', '')
        app.config.setdefault('FPR_INFOTRACE_SCOM', '')
        self.wsdl_url = app.config['FPR_WSDL_URL']
        self.force_query_url = app.config['FPR_FORCE_QUERY_URL']
        self.cert = app.config['FPR_CERTIFICATE']
        self.baseconf = {
            "app": app.config['FPR_IDENTIFICATION_APPLICATION'],
            "param": app.config['FPR_IDENTIFICATION_PARAMETRE'],
            "cmd": app.config['FPR_IDENTIFICATION_COMMANDE'],
            "id": app.config['FPR_INFOTRACE_IDENTIFIANT'],
            "poste": app.config['FPR_INFOTRACE_POSTE'],
            "scom": app.config['FPR_INFOTRACE_SCOM']
        }
        self.proxies = {'http': app.config['FPR_HTTP_PROXY'],
                        'https': app.config['FPR_HTTPS_PROXY']}
        self.testing_stub = app.config.get('FPR_TESTING_STUB')
        self.disabled = app.config['DISABLE_FPR']
        if not self.testing_stub and not self.wsdl_url:
            self.disabled = True
        self._initialized = True
        self.contact_timeout = app.config['FPR_CONTACT_TIMEOUT']
        self.logger = logging.getLogger('Fpr')
        _config_logger(self.logger, logging.INFO)

    @property
    def client(self):
        if not self._initialized:
            raise FprNotInitializedError()
        if self.disabled:
            raise FprDisabledError()
        if not self._client:
            kwargs = {
                'transport': FprHttpAuthenticated(cert=self.cert),
                'timeout': self.contact_timeout
            }
            if self.force_query_url:
                # Overwrite url provided in the WSDL
                kwargs['location'] = self.force_query_url
            self._client = Client(self.wsdl_url, **kwargs)
        return self._client

    def query(self, firstname, lastname, birthday, **kwargs):
        if not self._initialized:
            raise FprNotInitializedError()
        msg = self._format_msg(firstname, lastname, birthday)
        payload = self._format_service_payload(msg, **kwargs)
        if self.testing_stub:
            # Really simple fake response
            return {'resultat': False, 'dossiers': []}
        try:
            start = datetime.utcnow()
            response = self.client.service.service(payload)
            end = datetime.utcnow()
            self.logger.info('fpr answering time (%s)' % (end - start))
        except TransportError as exc:
            raise FprConnectionError(exc)
        except Exception as e:
            if isinstance(e, tuple):
                if type(e) is Exception and len(e.args) == 2 and isinstance(tuple, e.args[0]) and len(e.args[1]) == 2:
                    if e.args[1][0] >= 500 and e.args[1][0] <= 600:
                        raise FprConnectionError(e)
                    else:
                        FprError(e)
            else:
                raise
        return self._parse_response(response)

    def _parse_response(self, response):
        try:
            raw = parse(response)
            status_code = raw['reponse']['retour']['coderetour']
            value = raw['reponse']['message']['valeur']
        except Exception as exp:
            raise FprQueryError(exp)
        if status_code != '0':
            raise FprQueryError('Le FPR a retourné un code %s' % status_code)
        return _parse_dossiers(value)

    def _format_service_payload(self, msg, **kwargs):
        conf = self.baseconf.copy()
        conf.update(kwargs)
        return self.SERVICE_PAYLOAD_TEMPLATE.format(msg=msg, **conf)

    def _format_msg(self, firstname, lastname, birthday):
        if len(firstname) > 44:
            raise FprQueryError('le nom de famille doit être inférieur à 44 caractères')
        if len(firstname) > 25:
            raise FprQueryError('le prénom doit être inférieur à 25 caractères')
        # Convert accents and make the string uppercase
        firstname = unicodedata.normalize('NFKD', firstname).encode(
            'ascii', 'ignore').decode().upper()
        lastname = unicodedata.normalize('NFKD', lastname).encode(
            'ascii', 'ignore').decode().upper()
        if isinstance(birthday, datetime):
            birthday = birthday.strftime("%Y%m%d")
        elif not birthday:
            birthday = ""
        if len(birthday) > 8:
            raise FprQueryError('la date de naissance doit être inférieur à 8 charactères')
        return self.MSG_TEMPLATE.format(
            lastname=lastname, firstname=firstname, birthday=birthday)


default_fpr = FprService()
fpr_query = default_fpr.query
init_fpr = default_fpr.init_app
