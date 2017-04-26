# pylint: disable=C0103
import re
import unicodedata
import requests
from dateutil.parser import parse
from datetime import datetime
from functools import partial

from connector.common import (
    connectors_config, ConnectorException, BackendRequest)
from connector.tools import (
    request_with_broker_retry, retrieve_last_demande_for_given_usager)
from connector.exceptions import (
    ProcessMessageNoResponseError, ProcessMessageSkippedError)

FORBIDDEN_CODE = (r'^976[0-9]{2}$',)


def _register_routes(app):
    """
    Register the routes used by the connector in the main API.
    Keyword arguments:

    - **parameters**, **types**, **return** and **return types**::

    :param app: The app to which you need to register the new routes
    """
    from flask.ext.restful import Api
    from connector.dna.majportail import (MajPortailAPI, MajPortailParams,
                                          MajPortailResponseParams)
    connector_api = Api(app, prefix=app.config['CONNECTOR_DNA_PREFIX'])
    connector_api.add_resource(MajPortailAPI, '/MajPortail')
    connector_api.add_resource(MajPortailParams, '/MajPortailParams.xsd')
    connector_api.add_resource(MajPortailResponseParams, '/MajPortailResponse.xsd')


class DNAConnector:

    """
    Class used to communicate with OFII. It translates json format to
    SOAP XML.
    """

    def __init__(self):
        self.timeout = None
        self.requests = None
        self.disabled_input = None
        self.disabled = True
        self.user = None
        self.password = None
        self.url = None
        self.exp_url = None
        self.proxies = {}
        self.connector_domain = None
        self._backend_requests = None
        self._dna_request = None

    def init_app(self, app):
        app.config.setdefault('DISABLE_CONNECTOR_DNA', False)
        app.config.setdefault('DISABLE_CONNECTOR_DNA_INPUT', False)
        app.config.setdefault('ENFORCE_ID_FAMILLE_DNA', False)
        app.config.setdefault('CONNECTOR_DNA_USERNAME', '')
        app.config.setdefault('CONNECTOR_DNA_PASSWORD', '')
        app.config.setdefault('CONNECTOR_DNA_TOKEN', '')
        app.config.setdefault('CONNECTOR_DNA_URL', '')
        app.config.setdefault('CONNECTOR_DNA_EXPOSED_URL', '')
        app.config.setdefault('CONNECTOR_DNA_PREFIX', '/connectors/dna')
        app.config.setdefault('CONNECTOR_DNA_HTTP_PROXY', '')
        app.config.setdefault('CONNECTOR_DNA_HTTPS_PROXY', '')
        app.config.setdefault('CONNECTOR_DNA_REQUESTS', requests)
        app.config.setdefault('CONNECTOR_DNA_TIMEOUT', 60)

        self.timeout = app.config['CONNECTOR_DNA_TIMEOUT']
        self.requests = app.config['CONNECTOR_DNA_REQUESTS']
        self.disabled_input = app.config.get('DISABLE_CONNECTOR_DNA_INPUT')
        self.disabled = app.config.get('DISABLE_CONNECTOR_DNA')
        self.user = app.config.get('CONNECTOR_DNA_USERNAME')
        self.password = app.config.get('CONNECTOR_DNA_PASSWORD')
        self.url = app.config.get('CONNECTOR_DNA_URL')
        self.exp_url = app.config.get('CONNECTOR_DNA_EXPOSED_URL')
        self.proxies = {}
        self.proxies['http'] = app.config.get('CONNECTOR_DNA_HTTP_PROXY')
        self.proxies['https'] = app.config.get('CONNECTOR_DNA_HTTPS_PROXY')
        _register_routes(app)
        self.connector_domain = app.config[
            'BACKEND_URL_DOMAIN'] + app.config['CONNECTOR_DNA_PREFIX']
        if self.exp_url in (None, ''):
            self.exp_url = self.connector_domain
        self._backend_requests = BackendRequest(
            domain=app.config['BACKEND_URL_DOMAIN'],
            url_prefix=app.config['BACKEND_API_PREFIX'],
            auth=(app.config['CONNECTOR_DNA_USERNAME'], app.config['CONNECTOR_DNA_PASSWORD']),
            token=app.config['CONNECTOR_DNA_TOKEN'],
            requests=app.config['CONNECTOR_DNA_REQUESTS'])
        self._dna_request = request_with_broker_retry(partial(
            app.config['CONNECTOR_DNA_REQUESTS'].request, method='POST',
            url=app.config['CONNECTOR_DNA_URL'], proxies=self.proxies,
            timeout=self.timeout))

    @property
    def backend_requests(self):
        """
        :returns: the handler to make requests to the back-end.
        """
        if self.disabled or not self._backend_requests:
            raise RuntimeError('Connecteur non initialisé')
        return self._backend_requests

    @property
    def dna_request(self):
        """
        :returns: the handler to make requests to the DN@.
        """
        if self.disabled or not self._dna_request:
            raise RuntimeError('Connecteur non initialisé')
        return self._dna_request


dna_config = DNAConnector()
init_connector_dna = dna_config.init_app


def format_text(txt, max=None, allowed_pattern=None, transform=None):
    """
    Format text to DN@ style
    """
    if not txt:
        return None
    else:
        if transform:
            output = transform(txt)
        else:
            output = txt
        output = unicodedata.normalize('NFKD', output).encode(
            'ascii', 'ignore').decode().upper()
        if max:
            output = output[:max]
        if allowed_pattern:
            return ''.join([c if re.match(allowed_pattern, c) else ' ' for c in output])
        else:
            return output


class ValidationError(Exception):

    """
    class raised when the format does not repestc DN@ format
    """

    def __init__(self, value):
        super().__init__()
        self.value = value

    def __str__(self):
        return self.value


class DoNotSendError(Exception):

    """
    Exception class used when a message should not be sent to the DN@.
    """
    pass


class DnaDumpable():

    """
    Inheritable class used to build the XML message for DN@
    """

    def __init__(self):
        self.meta = {}
        self._meta = {}
        self._meta['nodump'] = ["_str", "meta", "var", "keys", "first", '_meta']

    def dump(self):
        """
        Dump object to text
        """
        try:
            self._meta['nodump'].extend(self.meta['nodump'])
        except:
            pass
        self.var = vars(self)
        self.keys = [key for key in self.var if (key not in self._meta['nodump'] and
                                                 self.var[key])]
        self._str = '{'
        first = True
        for key in self.keys:
            if isinstance(self.var[key], list):
                self._str += '"%s": [' % key
                first = True
                for elem in [item for item in self.var[key] if item]:
                    if first:
                        first = False
                    else:
                        self._str += ', '
                    self._str += elem.dump()
                self._str += ']'
            else:
                if first:
                    first = False
                    self._str += '"%s": %s' % (key, self.var[key].dump())
                else:
                    self._str += ', "%s": %s' % (key, self.var[key].dump())

        self._str += '}'
        return self._str

    def build_xml(self, ns1=None, ns2=None, name=None):
        """
        Dump object to XML
        """
        try:
            self._meta['nodump'].extend(self.meta['nodump'])
        except:
            pass
        self.var = vars(self)
        self._str = ""
        self.keys = [key for key in self.var if (key not in self._meta['nodump'] and
                                                 self.var[key])]
        if name:
            self._str = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
                ' xmlns:ns1=%s >' % (ns1,))
            self._str += ('<soapenv:Header/><soapenv:Body><ns1:%s>' % name)
            self._str += ('<%s>' % self.meta['name'])
        for key in self.keys:
            if isinstance(self.var[key], list):
                for elem in [item for item in self.var[key] if item]:
                    self._str += '<%s>' % key
                    self._str += elem.build_xml()
                    self._str += '</%s>' % key
            else:
                self._str += '<%s>' % key
                self._str += self.var[key].build_xml()
                self._str += '</%s>' % key
        if name:
            self._str += '</%s></ns1:%s>' % (self.meta['name'], name)
            self._str += '</soapenv:Body></soapenv:Envelope>'
        return self._str


class DnaEnum():

    """
    Enumerated type for dna bi-directionnal looks-up
    """

    RENOUVELLEMENT_APS_TYPE = [("PREMIERE_DELIVRANCE", "1"),
                               ("PREMIER_RENOUVELLEMENT", "2"),
                               ("EN_RENOUVELLEMENT", "3")]
    DEMANDEUR_TYPE = [("PRINCIPAL", "Demandeur principal"),
                      ("CONJOINT", "Conjoint"),
                      ("AUTRE", "Autre adulte")]

    SITE_TYPE = [("StructureAccueil", "SPA"), ("GU", "GU"),
                 ("Prefecture", "Préfecture")]

    PROC_TYPE = [("ACCELEREE", "En procédure prioritaire"),
                 ("NORMALE", "En procédure normale"),
                 ("DUBLIN", "Dubliné")]

    MATRIMONIAL_TYPE = [("CELIBATAIRE", "Célibataire"), ("MARIE", "Marié"),
                        ("DIVORCE", "Divorcé"), ("CONCUBIN", "Concubin"),
                        ("", "Isolé"), ("SEPARE", "Séparé"),
                        ("VEUF", "Veuf"), ("PACSE", "Marié")]

    SEXE_TYPE = [("F", "F"), ("M", "M")]

    CONDITION_ENTREE_TYPE = [("REGULIERE", "N"), ("IRREGULIERE", "I"),
                             ("FAMILIALE", "F")]

    from connector.dna.translations import (PAYS_CODE, PAYS, LANGUES_CODE,
                                            NAT_CODE)


class TranslatedType():

    """
    Transformation class to translate to/from DN@
    """

    def __init__(self, translation_table):
        self.tt = translation_table

    # LOAD : VERS API
    def _deserialize(self, value):
        if not value:
            return 'und'
        for api, dna in self.tt:
            if value.lower() == dna.lower():
                return api
        return 'und'

    # DUMP : VERS WSDL
    def translate_to_WSDL(self, value):
        if not value:
            return None
        for api, dna in self.tt:
            if value.lower() == api.lower():
                return dna
        return 'und'


demandeur_trans = TranslatedType(DnaEnum.DEMANDEUR_TYPE)
site_trans = TranslatedType(DnaEnum.SITE_TYPE)
proc_trans = TranslatedType(DnaEnum.PROC_TYPE)
matrimonial_trans = TranslatedType(DnaEnum.MATRIMONIAL_TYPE)
sexe_trans = TranslatedType(DnaEnum.SEXE_TYPE)
cond_trans = TranslatedType(DnaEnum.CONDITION_ENTREE_TYPE)
pays_code_trans = TranslatedType(DnaEnum.PAYS_CODE)
pays_trans = TranslatedType(DnaEnum.PAYS)
lang_code_trans = TranslatedType(DnaEnum.LANGUES_CODE)
nat_code_trans = TranslatedType(DnaEnum.NAT_CODE)
droit_trans_renew = TranslatedType(DnaEnum.RENOUVELLEMENT_APS_TYPE)


def is_adult(usager):
    """
    Check if an usager is an adult or not
    """
    # See sief/model/usager.py: function is_adult(usager)
    if not usager or not usager.get('date_naissance'):
        return False

    today = datetime.now()
    birthday = parse(usager.get('date_naissance')).replace(tzinfo=None)
    age = today.year - birthday.year
    if today.month < birthday.month or (today.month == birthday.month and today.day < birthday.day):
        age -= 1
    return age >= 18


class RegexValidatedType():

    def __new__(cls, *args, **kwargs):
        if len(args) == 0 or args[0] is None or args[1] is None:
            return None
        else:
            return object.__new__(cls)

    def __init__(self, regex, value):
        self.rx = re.compile(regex)
        if self.rx.match(value):
            self.value = value
        else:
            self.value = ''

    def dump(self):
        return self.value

    def build_xml(self):
        return str(self.value)


class DnaSimpleType(object):

    def __new__(cls, *args, **kwargs):
        if len(args) == 0 or args[0] is None:
            return None
        else:
            return object.__new__(cls)

    def __init__(self, value=None):
        self.value = value

    def dump(self):
        return self.value

    def build_xml(self):
        return str(self.value)


class DnaString(DnaSimpleType):

    def __repr__(self):
        return str(self.value)

    def dump(self):
        if self.value:
            return self.value
        else:
            return None

    def append(self, value):
        if not value:
            return
        if self.value:
            self.value = self.value + ", " + value
        else:
            self.value = value

    def build_xml(self):
        return str(self.value)


class DnaDate(DnaSimpleType):

    def __init__(self, date):
        super().__init__()
        self.date = parse(date)

    def __repr__(self):
        return self.date.strftime("%Y-%m-%d")

    def dump(self):
        if self.date:
            return self.date.strftime("%Y-%m-%d")
        else:
            return None

    def build_xml(self):
        return self.date.strftime("%Y-%m-%d")


class DnaBool(DnaSimpleType):

    def __init__(self, value=None):
        super().__init__()
        self.value = value

    def build_xml(self):
        if self.value:
            return 'true'
        else:
            return 'false'


class DnaRestricted(DnaString):

    def __init__(self, value, choices):
        super().__init__()
        if value in choices:
            self.value = value
        else:
            self.value = None
            ValidationError("Value {} not in choices".format(value))

    def build_xml(self):
        return str(self.value)


class DnaAdresse(DnaDumpable):

    def __new__(cls, *args, **kwargs):
        if len(args) == 0 or args[0] is None:
            return None
        else:
            if (isinstance(args[0], dict) and not
                    args[0].get('adresse_inconnue') and
                    args[0].get('voie') and
                    args[0].get('ville')):
                return object.__new__(cls)
        return None

    def __init__(self, prop, context=None, is_usager=False):
        super().__init__()
        self.meta['name'] = 'ADRESSE'
        self.NUM_DOMICILIATION = DnaString(format_text(prop.get('numero_voie'), max=20))
        self.NUMERO_VOIE = DnaString(format_text(prop.get('numero_voie'), max=5) or '0')
        self.ADRESSE2 = DnaString(prop.get('chez'))
        if self.ADRESSE2:
            self.ADRESSE2.append(prop.get('complement'))
        else:
            self.ADRESSE2 = DnaString(prop.get('complement'))
        self.LIBELLE_VOIE = DnaString(prop.get('voie')[:50])
        # fix because there was an error in the database contraints
        # Same here
        code_postal = re.search(r'[0-9]{5}', prop.get('code_postal', ''))
        if code_postal:
            self.CODE_POSTAL = DnaString(code_postal.group(0))
        code_insee = re.search(
            r'(2[AB]|[0-9]{2})[0-9]{3}', prop.get('code_insee', '')) or code_postal
        if code_insee:
            self.CODE_INSEE = DnaString(code_insee.group(0))
        self.VILLE = DnaString(prop.get('ville', ''))
        if is_usager:
            self.TELEPHONE = DnaString(
                context.get('usager_1', {}).get('telephone')) or DnaString(
                context.get('usager_2', {}).get('telephone'))

            self.EMAIL = RegexValidatedType(
                r'[^@]+@[^\.]+\..+',
                context.get('usager_1', {}).get('email')) or RegexValidatedType(
                r'[^@]+@[^\.]+\..+',
                context.get('usager_2', {}).get('email'))
        else:
            self.TELEPHONE = DnaString(prop.get('telephone'))
            self.EMAIL = RegexValidatedType(r'[^@]+@[^\.]+\..+', prop.get('email'))


class DnaSite(DnaDumpable):

    def __new__(cls, *args, **kwargs):
        if len(args) == 0 or args[0] is None:
            return None
        else:
            return object.__new__(cls)

    @staticmethod
    def _check_address(adresse, exception=False):
        if not adresse:
            return True
        code_postal = re.search(r'[0-9]{5}', adresse.get('code_postal', ''))
        if code_postal:
            code_postal = code_postal.group(0)
        code_insee = re.search(r'(2[AB]|[0-9]{2})[0-9]{3}', adresse.get('code_insee', ''))
        if code_insee:
            code_insee = code_insee.group(0)
        for rx in FORBIDDEN_CODE:
            if code_postal and re.match(rx, code_postal):
                if exception:
                    raise DoNotSendError("Code postal non souhaité dans le DN@")
                return False
            if code_insee and re.match(rx, code_insee):
                if exception:
                    raise DoNotSendError("Code insee non souhaité dans le DN@")
                return False
        return True

    def __init__(self, site, context=None):
        super().__init__()
        site_id = site.get('id')
        if site_id:
            route = '%s/sites/%s' % (connectors_config.server, site_id)
            r = dna_config.requests.get(route, auth=(dna_config.user, dna_config.password))
            if not r.ok:
                raise ConnectorException(r.status_code, r.text)
            site_full = r.json()
        self.meta['name'] = 'SITE'
        self.ID_SITE_PORTAIL = DnaString(site_full['id'])
        self.TYPE_SITE = DnaRestricted(
            site_trans.translate_to_WSDL(site_full.get('type')), ("SPA", "GU", "Préfecture"))
        self.LIBELLE_SITE = DnaString(site_full.get('libelle')[:100])
        self._check_address(site_full.get('adresse'), exception=True)
        self.ADRESSE = DnaAdresse(site_full.get('adresse'), context, is_usager=False)


class DnaSites(DnaDumpable):

    def __new__(cls, *args, **kwargs):
        if len(args) == 0 or args[0] is None:
            return None
        else:
            return object.__new__(cls)

    def __init__(self, site, context=None):
        super().__init__()
        self.meta['name'] = 'SITES'
        self.SITE = []
        self.SITE.append(DnaSite(site, context))


def build_type_demande(type_demande, context):
    if not type_demande:
        return None
    if type_demande == 'PREMIERE_DEMANDE_ASILE':
        return None
    if (context['event'] == 'recueil_da.pa_realise' or
            context.get('event') == "recueil_da.modifie"):
        return None
    raise ProcessMessageSkippedError("Message mis en attente car de type reexamen ou reouverture")
    # return DnaString(type_demande)


class DnaEnfant(DnaDumpable):

    def __init__(self, individu):
        super().__init__()
        self.meta['nodump'] = ['child', ]
        self.meta['name'] = 'ENFANT'

        if individu.get('date_naissance'):
            self.DATE_NAISSANCE = DnaDate(individu['date_naissance'])
        if individu.get('nom_usage') in (None, ''):
            self.NOM = DnaString(format_text(individu.get('nom'), max=48))
        else:
            self.NOM = DnaString(format_text(individu.get('nom_usage'), max=48))

        self.PRENOM = DnaString(format_text(individu.get('prenoms', ['INC', ])[0], max=48))
        if individu.get('pays_naissance') and individu.get('ville_naissance'):
            self.LIEU_NAISSANCE = DnaString(", ".join((individu['ville_naissance'],
                                                       pays_trans.translate_to_WSDL(
                pays_code_trans.translate_to_WSDL(
                    individu['pays_naissance']['code']))))[:64])
        self.SEXE = DnaString(sexe_trans.translate_to_WSDL(individu.get('sexe', 'und')))
        if individu.get('nationalites') and len(individu['nationalites']) > 0:
            self.INSEE_PAYS_NATIONALITE = DnaString(
                nat_code_trans.translate_to_WSDL(individu['nationalites'][0]['code']))
        if individu.get('photo'):
            self.URL_PHOTO = DnaString(individu.get('photo', {}).get('data'))
        self.ENFANT_DE_REFUGIE = DnaString("true")  # FIXME


class DnaAdulte(DnaDumpable):

    def __init__(self, individu, context, type_demandeur=None):
        super().__init__()
        self.meta['name'] = 'ADULTE'
        self.meta['nodump'] = ['adult', 'demande']
        self.demande = individu.get('demande_asile')

        if type_demandeur:
            self.TYPE = DnaString(type_demandeur)
            self.PROCEDURE_TYPE = DnaString(
                proc_trans.translate_to_WSDL(individu.get('type_procedure')))
        if self.demande:
            if not type_demandeur:
                self.TYPE = DnaString(
                    demandeur_trans.translate_to_WSDL(self.demande.get('type_demandeur')))
            self.DATE_ENTREE_EN_FRANCE = DnaDate(individu.get('date_entree_en_france'))
            if self.demande.get('procedure'):
                self.PROCEDURE_TYPE = DnaString(
                    proc_trans.translate_to_WSDL(self.demande['procedure']['type']))
        self.DATE_NAISSANCE = DnaDate(individu.get('date_naissance'))
        self.NOM = DnaString(format_text(individu.get('nom_usage'), max=48))
        self.NOM_NAISSANCE = DnaString(format_text(individu.get('nom'), max=48))
        self.PRENOM = DnaString(format_text(individu.get('prenoms', ['INC', ])[0], max=48))

        if individu.get('pays_naissance') and individu.get('ville_naissance'):
            self.LIEU_NAISSANCE = DnaString(", ".join((individu['ville_naissance'],
                                                       pays_trans.translate_to_WSDL(
                pays_code_trans.translate_to_WSDL(
                    individu['pays_naissance']['code']))))[:64])
        self.SEXE = DnaString(sexe_trans.translate_to_WSDL(individu['sexe']))

        if individu.get('nationalites') and len(individu['nationalites']) > 0:
            self.INSEE_PAYS_NATIONALITE = DnaString(
                nat_code_trans.translate_to_WSDL(individu['nationalites'][0]['code']))
        if individu.get('langues'):
            self.LANGUE1 = DnaString(
                lang_code_trans.translate_to_WSDL(individu['langues'][0]['code']))
            if len(individu['langues']) > 1:
                self.LANGUE2 = DnaString(
                    lang_code_trans.translate_to_WSDL(individu['langues'][1]['code']))
        if hasattr(individu, 'situation_familiale'):
            self.MATRIMONIAL = DnaString(
                matrimonial_trans.translate_to_WSDL(individu.get('situation_familiale')))
        else:
            self.MATRIMONIAL = DnaString(matrimonial_trans.translate_to_WSDL(
                context.get('usager_1', {}).get('situation_familiale')))
        if individu.get('photo'):
            self.URL_PHOTO = DnaString(individu['photo']['_links']['data'])


class DnaIndividu(DnaDumpable):

    def __init__(self, individu, context, ischild):
        super().__init__()
        self.meta['name'] = 'INDIVIDU'
        self.meta['nodump'] = []
        if not individu:
            raise ValidationError('Invalid individu')
        if individu.get('usager'):
            individu.update(individu.get('usager'))

        if individu.get('id'):
            self.ID_USAGER_PORTAIL = DnaString(individu['id'])
        if context.get('event') == "recueil_da.exploite":
            if individu.get('identifiant_agdref'):
                self.ID_AGDREF = DnaString(individu['identifiant_agdref'])
            self.DATE_AGDREF = DnaDate(
                individu.get('date_enregistrement_agdref', datetime.utcnow().isoformat()))

        if individu.get('demande_asile'):
            self.CONDITION_ENTREE_FRANCE = DnaString(
                cond_trans.translate_to_WSDL(
                    individu['demande_asile'].get('condition_entree_france')))

            self.ID_DEMANDE_ASILE = DnaString(individu['demande_asile'].get('id'))
            if 'type_demande' in individu.get('demande_asile'):
                self.TYPE_DEMANDE = build_type_demande(
                    individu['demande_asile'].get('type_demande'), context)
        self.DATE_APS = None

        if ischild and not is_adult(individu):
            self.ENFANT = DnaEnfant(individu)
        elif ischild:
            self.ADULTE = DnaAdulte(individu, context=context, type_demandeur='Autre adulte')
        else:
            self.ADULTE = DnaAdulte(individu, context)


class DnaIndividus(DnaDumpable):

    def __init__(self, context):
        super().__init__()
        self.meta['name'] = 'INDIVIDUS'
        self.meta['nodump'] = ['rda', 'children', 'present']
        self.INDIVIDU = []
        self.children = set()

        # Person + child
        self.rda = context.get('recueil_da')
        if self.rda:
            if context.get('event') == "recueil_da.exploite":
                for child in self.rda.get('enfants', []):
                    if child.get('demandeur') or (child.get('present_au_moment_de_la_demande') and not is_adult(child)):
                        self.INDIVIDU.append(DnaIndividu(child, context, True))
            else:
                for child in self.rda.get('enfants', []):
                    if child.get('demandeur') or (child.get('present_au_moment_de_la_demande') and not is_adult(child.get('usager'))):
                        self.INDIVIDU.append(DnaIndividu(child, context, True))

            if self.rda.get('usager_1') and self.rda['usager_1'].get('demandeur'):
                self.INDIVIDU.append(DnaIndividu(context['usager_1'],
                                                 context,
                                                 False))
            if self.rda.get('usager_2') and self.rda['usager_2'].get('demandeur'):
                self.INDIVIDU.append(DnaIndividu(context['usager_2'],
                                                 context,
                                                 False))


class DnaDemande(DnaDumpable):

    def __init__(self, demande, context=None):
        super().__init__()
        self.meta['name'] = 'DEMANDE'
        self.ID_RECUEIL_DEMANDE = DnaString(context['recueil_da']['id'])
        # Get last identifiant_famille_dna from backend
        route = '%s/recueils_da/%s' % (connectors_config.server,
                                       context.get('recueil_da').get('id'))
        r = dna_config.requests.get(route, auth=(dna_config.user, dna_config.password))
        if r.status_code != 200:
            raise ValidationError('Cannot find recueil %s' %
                                  context.get('usager_1', {}).get('id'))
        rda = r.json()
        self.ID_FAMILLE_DNA = DnaString(rda.get('identifiant_famille_dna'))
        if context['event'] == 'recueil_da.pa_realise':
            self.DATE_CREATION_DEMANDE = DnaDate(context['recueil_da'].get('date_transmission'))
        else:
            self.DATE_CREATION_DEMANDE = DnaDate(demande.get('date_enregistrement'))
        if demande.get('agent_enregistrement'):
            self.AGENT_PREF = DnaString(demande['agent_enregistrement']['id'])
        self.DATE_PREF = DnaDate(demande.get('date_enregistrement'))
        if (context['event'] == 'recueil_da.pa_realise' or
                context.get('event') == "recueil_da.modifie"):
            self.PROCEDURE_STATUT = DnaSimpleType(0)
        else:
            self.PROCEDURE_STATUT = DnaSimpleType(1)
        if context['recueil_da'].get('rendez_vous_gu'):
            self.DATE_RDV_GU = DnaDate(context['recueil_da']['rendez_vous_gu']['date'])

        self.INDIVIDUS = DnaIndividus(context)
        if context['event'] == 'recueil_da.pa_realise':
            self.SITES = DnaSites(context.get('recueil_da', {}).get('structure_accueil'), context)
        else:
            self.SITES = DnaSites(
                context.get('recueil_da', {}).get('structure_guichet_unique'), context)
        self.ADRESSE = (DnaAdresse(
            context.get('recueil_da', {}).get('usager_1', {}).get('adresse'), context, is_usager=True) or
            DnaAdresse(
            context.get('recueil_da', {}).get('usager_2', {}).get('adresse'), context, is_usager=True))


class DnaDemandes(DnaDumpable):

    def __init__(self, obj, event):
        super().__init__()
        self.meta['nodump'] = ['obj', 'da', 'context', 'i']
        self.meta['name'] = 'DEMANDES'
        if obj:
            self.context = obj
            self.context['event'] = event
        self.DEMANDE = []
        # Si pa réalisé : créer des fakes demandes asiles pour envoyer les
        # données et go
        if obj and (self.context.get('event') == "recueil_da.pa_realise" or
                    self.context.get('event') == "recueil_da.modifie"):
            rda = self.context.get('recueil_da')
            if rda.get('usager_1'):
                self.context['usager_1'] = {}
                self.context['usager_1']['_id'] = 1
            if rda.get('usager_2'):
                self.context['usager_2'] = {}
                self.context['usager_2']['_id'] = 2

            if rda.get('usager_1', {}).get("demandeur"):
                self.context['usager_1']['demande_asile'] = {}
                self.context['usager_1']['demande_asile']['usager'] = rda['usager_1']
                self.context['usager_1']['demande_asile']['type_demandeur'] = 'PRINCIPAL'
                self.context['usager_1']['demande_asile'][
                    'date_demande'] = rda.get('date_transmission')
                self.context['usager_1']['demande_asile'][
                    'type_demande'] = rda['usager_1']['type_demande']

                self.context['usager_1'].update(rda['usager_1'])

            if rda.get('usager_2', {}).get("demandeur"):
                self.context['usager_2']['demande_asile'] = {}
                self.context['usager_2']['demande_asile']['type_demandeur'] = 'CONJOINT'
                self.context['usager_2']['demande_asile']['usager'] = rda['usager_2']
                self.context['usager_2']['demande_asile'][
                    'date_demande'] = rda.get('date_transmission')
                self.context['usager_2']['demande_asile'][
                    'type_demande'] = rda['usager_2']['type_demande']

                self.context['usager_2'].update(rda['usager_2'])

            for child in rda.get('enfants', []):
                child['usager'] = child
                if child.get('demandeur'):
                    child['demande_asile'] = {}
                    child['demande_asile']['type_demandeur'] = 'AUTRE'
                    child['demande_asile']['usager'] = child
                    child['demande_asile']['date_demande'] = rda.get('date_transmission')
                    child['demande_asile']['type_demande'] = child['type_demande']
        else:
            for child in self.context.get('enfants', []):
                child['usager'] = child

        if self.context:
            if self.context.get('usager_1', {}).get("demande_asile"):
                self.DEMANDE.append(
                    DnaDemande(self.context['usager_1']["demande_asile"], self.context))


class DnaIdentification(DnaDumpable):

    def __init__(self, usager, id_inerec):
        super().__init__()
        self.meta['nodump'] = ['usager', 'route', 'payload', 'r']
        self.ID_USAGER_PORTAIL = DnaString(usager.get('id'))
        self.ID_INEREC = DnaString(id_inerec)
        self.ID_AGDREF = DnaString(usager.get('identifiant_agdref'))
        self.ID_IND_DNA = DnaString(usager.get('identifiant_dna'))


class DnaUpdate(DnaDumpable):

    def __init__(self, payload):
        super().__init__()

        if payload.get('date_deces'):
            self.DATE_DECES = DnaDate(payload.get('date_deces'))
        if payload.get('date_naturalisation'):
            self.DATE_NATURALISATION = DnaDate(payload.get('date_naturalisation'))
        if payload.get('eloignement'):
            self.DATE_OQTF = DnaDate(payload.get('eloignement', {}).get('date_execution'))
        if payload.get('date_introduction_ofpra'):
            self.DATE_ENREGISTREMENT_INEREC = DnaDate(payload.get('date_introduction_ofpra'))
        if payload.get('date_decision_sur_attestation'):
            self.DATE_APS = DnaDate(payload.get('date_decision_sur_attestation'))
        if payload.get('sous_type_document'):
            self.RENOUVELLEMENT_APS = DnaSimpleType(
                droit_trans_renew.translate_to_WSDL(payload.get('sous_type_document')))


class DnaTransfert(DnaDumpable):

    def __init__(self, dublin):
        super().__init__()

        if dublin:
            self.DATE_DECISION = DnaDate(dublin.get('date_decision'))
            self.EXECUTION = DnaBool(dublin.get('execution'))
            self.DATE_EXECUTION = DnaDate(dublin.get('date_execution'))


class DnaEloignement(DnaDumpable):

    def __init__(self, eloignement):
        super().__init__()
        if eloignement:
            self.DATE_DECISION = DnaDate(eloignement.get('date_decision'))
            self.EXECUTION = DnaBool(eloignement.get('execution'))
            self.DELAI_DEPART_VOLONTAIRE = DnaSimpleType(eloignement.get('delai_depart_volontaire'))


class DnaFuite(DnaDumpable):

    def __init__(self, fuite):
        super().__init__()
        if fuite:
            self.DATE_FUITE = DnaDate(fuite.get('date_fuite'))


class DnaEtatCivil(DnaDumpable):

    def __init__(self, usager):
        super().__init__()
        self.DATE_NAISSANCE = DnaDate(usager.get('date_naissance'))
        pays = usager.get('pays_naissance')
        if isinstance(pays, dict):
            self.LIEU_NAISSANCE = DnaString(", ".join((usager['ville_naissance'],
                                                       pays_trans.translate_to_WSDL(
                pays_code_trans.translate_to_WSDL(
                    usager['pays_naissance'].get('code'))))))
        elif pays:
            self.LIEU_NAISSANCE = DnaString(", ".join((usager['ville_naissance'],
                                                       pays_trans.translate_to_WSDL(
                pays_code_trans.translate_to_WSDL(usager['pays_naissance'])))))
        self.NOM = DnaString(format_text(usager.get('nom_usage')))
        self.NOM_NAISSANCE = DnaString(format_text(usager.get('nom')))
        if usager.get('prenoms'):
            self.PRENOM = DnaString(format_text(usager.get('prenoms', ['INC', ])[0]))
        self.SEXE = DnaString(sexe_trans.translate_to_WSDL(usager.get('sexe')))

        nationalite = usager.get('nationalites')[0]
        if isinstance(nationalite, dict):
            self.INSEE_PAYS_NATIONALITE = DnaString(
                nat_code_trans.translate_to_WSDL(nationalite.get('code')))
        else:
            self.INSEE_PAYS_NATIONALITE = DnaString(
                nat_code_trans.translate_to_WSDL(nationalite))

        self.MATRIMONIAL = DnaString(
            matrimonial_trans.translate_to_WSDL(usager.get('situation_familiale')))
        if usager.get('photo'):
            self.URL_PHOTO = DnaString(usager['photo'])


class DnaDecision(DnaDumpable):

    def __init__(self, df):
        super().__init__()
        if df:
            self.NATURE = DnaString(df.get('nature'))
            self.DATE_DECISION = DnaDate(df.get('date'))
            self.DATE_NOTIF = DnaDate(df.get('date_notification'))
            self.ENTITE = DnaString(df.get('entite'))


class DnaProcedure(DnaDumpable):

    def __init__(self, procedure):
        super().__init__()
        if procedure.get('type'):
            self.TYPE = DnaString(proc_trans.translate_to_WSDL(procedure['type']))
        self.DATE_PROCEDURE = DnaDate(procedure['requalifications'][-1].get('date'))
        self.DATE_NOTIF = DnaDate(procedure['requalifications'][-1].get('date_notification'))


class DnaTitreSejour(DnaDumpable):

    def __init__(self, titre):
        super().__init__()
        if titre is None:
            return
        self.TYPE = DnaString(titre.get('type_document'))
        self.DATE_DEBUT = DnaDate(titre.get('date_debut_validite'))
        self.DATE_FIN = DnaDate(titre.get('date_fin_validite'))


def extract_type_demande(context, demande_asile=None, droit=None, usager=None):
    if (context['event'] == 'recueil_da.pa_realise' or
            context.get('event') == "recueil_da.modifie"):
        return None
    type_demande = None
    if demande_asile:
        type_demande = demande_asile.get('type_demande')
    if usager:
        identifiant_agdref = usager.get('identifiant_agdref')
        route = '%s/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % (
            connectors_config.server, identifiant_agdref)
        r = dna_config.requests.get(route)
        if r.status_code != 200:
            ValidationError('Cannot find recueil associate to following user %s' %
                            identifiant_agdref)
        recueils_da = r.json().get('_items', [])
        usager_recueil = retrieve_last_demande_for_given_usager(
            recueils_da, identifiant_agdref, usager.get('id'))
        if usager_recueil:
            type_demande = usager_recueil['type_demande']
    return build_type_demande(type_demande, context)


class DnaMAJDA(DnaDumpable):

    def __init__(self, obj, event):
        super().__init__()
        self.meta['name'] = 'MAJDA'
        self.meta['nodump'] = ['usager', 'context']

        if obj:
            self.context = obj
            self.context['event'] = event

        if event in ("usager.modifie", "usager.etat_civil.modifie", "usager.etat_civil.valide"):
            usager = obj['usager']
        elif event == "droit.cree":
            usager = obj['droit']['usager']
            route = '%s/demandes_asile/%s' % (connectors_config.server,
                                              obj['droit']['demande_origine'].get('id'))
            r = dna_config.requests.get(route, auth=(dna_config.user, dna_config.password))
            if r.status_code != 200:
                raise ValidationError('Cannot find demande asile %s' %
                                      obj['droit']['demande_origine'].get('id'))
            self.TYPE_DEMANDE = extract_type_demande(self.context, demande_asile=r.json())
        else:
            usager = obj.get('demande_asile', {}).get('usager')
            self.TYPE_DEMANDE = extract_type_demande(
                self.context, demande_asile=obj.get('demande_asile'))

        if not usager.get('id'):
            raise ValidationError('No ID was given for DnaIdentification')
        route = '%s/usagers/%s' % (connectors_config.server, usager.get('id'))
        r = dna_config.requests.get(route, auth=(dna_config.user, dna_config.password))
        if r.status_code != 200:
            raise ValidationError('Cannot find usager %s' % usager.get('id'))
        usager = r.json()

        if usager and not hasattr(self, 'TYPE_DEMANDE'):
            self.TYPE_DEMANDE = extract_type_demande(self.context, usager=usager)

        if not usager.get('identifiant_dna'):
            raise DoNotSendError('Pas de mise à jour possible sans identifiant_dna')

        if usager and (usager.get('identifiant_pere') or
                       usager.get('identifiant_mere')) and not is_adult(usager):
            self.TYPE_PERSONNE = DnaString("Enfant")
        else:
            self.TYPE_PERSONNE = DnaString("Adulte")
        payload = obj.get('payload', {})
        self.IDENTIFICATION = DnaIdentification(usager, payload.get('identifiant_inerec', None))
        if event == "usager.etat_civil.modifie" or event == "usager.etat_civil.valide":
            self.ETATCIVIL = DnaEtatCivil(obj['payload'])
        elif event == "demande_asile.procedure_requalifiee":
            self.PROCEDURE = DnaProcedure(obj['demande_asile'].get('procedure'))
        elif event == "demande_asile.decision_definitive":
            self.DECISION = DnaDecision(payload)
        elif event == "demande_asile.dublin_modifie":
            self.TRANSFERT = DnaTransfert(payload)
        elif event == "usager.modifie":
            self.UPDATE = DnaUpdate(payload=payload)
            # if payload.get('eloignement'):
            #     self.ELOIGNEMENT = DnaEloignement(payload.get('eloignement'))
            if payload.get('date_fuite'):
                self.FUITE = DnaFuite(payload)
            elif not [i for i in vars(self.UPDATE).keys()
                      if i in ['DATE_DECES', 'DATE_NATURALISATION', 'DATE_OQTF',
                               'DATE_ENREGISTREMENT_INEREC', 'DATE_APS',
                               'RENOUVELLEMENT_APS']]:
                raise DoNotSendError(
                    "Le message transmis par la plateforme semble ne contenir aucune information de mise à jour")

        elif event == "demande_asile.introduit_ofpra":
            self.UPDATE = DnaUpdate(payload)
        elif event == "demande_asile.attestation_edite":
            self.TITRE = DnaTitreSejour(payload)
            self.UPDATE = DnaUpdate(payload)
        elif event == "droit.cree":
            self.TITRE = DnaTitreSejour(payload)
            self.UPDATE = DnaUpdate(payload)


def build_demandes_xml(handler, msg):
    if not dna_config.disabled:
        return DnaDemandes(msg.context, handler.event).build_xml(
            ns1='"http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService"',
            # ns2='"http://param.message.webservices.dna.anaem.social.fr/RecupererDonneesPortail"',
                name='getDonneePortail')
    else:
        raise ProcessMessageNoResponseError('Connecteur DNA Désactivé')


def build_majda_xml(handler, msg):
    if not dna_config.disabled:
        return DnaMAJDA(msg.context, handler.event).build_xml(
            ns1='"http://service.webservices.dna.anaem.social.fr/MajDonneesDAService"',
            # ns2='"http://param.message.webservices.dna.anaem.social.fr/MajDonneesDA"',
            name='majDonneesDA')
    else:
        raise ProcessMessageNoResponseError('Connecteur DNA Désactivé')
