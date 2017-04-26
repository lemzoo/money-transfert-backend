import pytest
from datetime import datetime, timedelta
from workdays import workday as add_days
from xmltodict import parse as parse_xml
from freezegun import freeze_time

from broker_dispatcher.event_handler import EventHandlerItem
from broker.model import Message

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p
from connector.dna.majportail import dna_maj_portail
from connector.dna import dna_recuperer_donnees_portail, dna_recuperer_donnees_portail_by_step

from tests import common
from tests.fixtures import *
from tests.test_rendez_vous import add_free_creneaux
from tests.connector.common import BrokerBox


class Response:

    def __init__(self, status_code=200, text='', headers={}, json=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self.ok = 200 <= status_code < 300
        self._json = json

    def json(self):
        return self._json


class MockRequests:

    def __init__(self):
        self.callback_response = None

    def make_default_response(self, *args, **kwargs):
        if self.callback_response:
            return self.callback_response(*args, **kwargs)
        else:
            return Response(200)

    def request(self, *args, **kwargs):
        return self.make_default_response(*args, **kwargs)

    def get(self, *args, **kwargs):
        return self.make_default_response('GET', *args, **kwargs)

    def post(self, *args, **kwargs):
        return self.make_default_response('POST', *args, **kwargs)

    def patch(self, *args, **kwargs):
        return self.make_default_response('PATCH', *args, **kwargs)

    def put(self, *args, **kwargs):
        return self.make_default_response('PUT', *args, **kwargs)

    def delete(self, *args, **kwargs):
        return self.make_default_response('DELETE', *args, **kwargs)


def diff_xml(source, expected, whitelist=(), pop_count=0):
    dict_source = source if isinstance(source, dict) else parse_xml(source)
    dict_expected = expected if isinstance(expected, dict) else parse_xml(expected)
    diff = {}
    for _ in range(pop_count):
        dict_source = dict_source.popitem()[1]
        dict_expected = dict_expected.popitem()[1]

    for k in dict_source:
        if k not in dict_expected:
            diff[k] = {'dict_source': dict_source[k], 'dict_expected': None}

    for k in dict_expected:
        if k not in dict_source:
            diff[k] = {'dict_source': None, 'dict_expected': dict_expected[k]}

    dict_keys = [k for k in dict_source if isinstance(dict_source[k], dict) and
                 isinstance(dict_expected[k], dict)]
    for k in dict_keys:
        if k not in whitelist:
            tempdiff = diff_xml(dict_source[k], dict_expected[k])
            if tempdiff:
                diff[k] = tempdiff
        del dict_source[k]
        del dict_expected[k]

    for k in dict_source:
        if k in whitelist:
            continue
        if isinstance(dict_source[k], list):
            if len(dict_source[k]) != len(dict_expected[k]):
                diff[k] = {'dict_source': dict_source[k], 'dict_expected': dict_expected[k]}
            else:
                for i in range(len(dict_source[k])):
                    tempdiff = diff_xml(dict_source[k][i], dict_expected[k][i])
                    if tempdiff:
                        diff[k] = tempdiff
        elif dict_source[k] != dict_expected[k]:
            diff[k] = {'dict_source': dict_source[k], 'dict_expected': dict_expected[k]}

    return diff


class TestDNAInput(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_DNA_REQUESTS': cls.mock_requests,
            'BACKEND_API_PREFIX': '/pref',
            'BACKEND_URL_DOMAIN': 'https://mydomain.com',
            'BACKEND_URL': 'https://mydomain.com/pref',
            'CONNECTOR_DNA_PREFIX': '/pref/dna'})

    def test_editer_adresse(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
            <maj1:INDIVIDUS>
               <!--Optional:-->
               <maj1:INDIVIDU>
                  <maj1:ID_RECUEIL_DEMANDE>{recueil_id}</maj1:ID_RECUEIL_DEMANDE>
                  <maj1:ID_USAGER_PORTAIL>{usager_id}</maj1:ID_USAGER_PORTAIL>
                  <maj1:TYPE_INDIVIDU>ADULTE</maj1:TYPE_INDIVIDU>
                  <maj1:ID_DNA>205511</maj1:ID_DNA>
                  <maj1:ADRESSE>
                     <!--Optional:-->
                     <maj1:NUMERO_VOIE>10</maj1:NUMERO_VOIE>
                     <!--Optional:-->
                     <maj1:ADRESSE2>?</maj1:ADRESSE2>
                     <maj1:LIBELLE_VOIE>BOULEVARD DU PALAIS</maj1:LIBELLE_VOIE>
                     <maj1:CODE_INSEE>75104</maj1:CODE_INSEE>
                     <maj1:CODE_POSTAL>75004</maj1:CODE_POSTAL>
                     <!--Optional:-->
                     <maj1:VILLE>PARIS 04</maj1:VILLE>
                  </maj1:ADRESSE>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id, usager_id=usager.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager.reload()
        da.reload()
        assert len(usager.localisations) == 2
        loc = usager.localisations[-1]
        assert loc.organisme_origine == 'DNA'
        assert loc.adresse.voie == 'BOULEVARD DU PALAIS'
        assert loc.adresse.numero_voie == '10'
        assert loc.adresse.code_postal == '75004'
        assert loc.adresse.code_insee == '75104'
        assert loc.adresse.ville == 'PARIS 04'
        assert loc.adresse.chez == None
        assert loc.adresse.complement == '?'
        assert loc.adresse.pays == None
        assert not loc.adresse.longlat

    def test_editer_no_recueil(self, exploite):
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
            <maj1:INDIVIDUS>
               <!--Optional:-->
               <maj1:INDIVIDU>
                  <maj1:ID_USAGER_PORTAIL>{usager_id}</maj1:ID_USAGER_PORTAIL>
                  <maj1:TYPE_INDIVIDU>ADULTE</maj1:TYPE_INDIVIDU>
                  <maj1:ADRESSE>
                     <!--Optional:-->
                     <maj1:NUMERO_VOIE>10</maj1:NUMERO_VOIE>
                     <!--Optional:-->
                     <maj1:ADRESSE2>?</maj1:ADRESSE2>
                     <maj1:LIBELLE_VOIE>BOULEVARD DU PALAIS</maj1:LIBELLE_VOIE>
                     <maj1:CODE_INSEE>75104</maj1:CODE_INSEE>
                     <maj1:CODE_POSTAL>75004</maj1:CODE_POSTAL>
                     <!--Optional:-->
                     <maj1:VILLE>PARIS 04</maj1:VILLE>
                  </maj1:ADRESSE>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(usager_id=usager.id)

        def callback(*args, **kwargs):
            assert False, 'Should not send any request'

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>8</tns:CODE_ERREUR>' in dna_maj_portail(payload)

    def test_editer_no_usager_portail(self, exploite):
        recueil = exploite
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
            <maj1:INDIVIDUS>
               <!--Optional:-->
               <maj1:INDIVIDU>
                  <maj1:ID_RECUEIL_DEMANDE>{recueil_id}</maj1:ID_RECUEIL_DEMANDE>
                  <maj1:TYPE_INDIVIDU>ADULTE</maj1:TYPE_INDIVIDU>
                  <maj1:ADRESSE>
                     <!--Optional:-->
                     <maj1:NUMERO_VOIE>10</maj1:NUMERO_VOIE>
                     <!--Optional:-->
                     <maj1:ADRESSE2>?</maj1:ADRESSE2>
                     <maj1:LIBELLE_VOIE>BOULEVARD DU PALAIS</maj1:LIBELLE_VOIE>
                     <maj1:CODE_INSEE>75104</maj1:CODE_INSEE>
                     <maj1:CODE_POSTAL>75004</maj1:CODE_POSTAL>
                     <!--Optional:-->
                     <maj1:VILLE>PARIS 04</maj1:VILLE>
                  </maj1:ADRESSE>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id)

        def callback(*args, **kwargs):
            assert False, 'Should not send any request'

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>7</tns:CODE_ERREUR>' in dna_maj_portail(payload)

    def test_bad_syntax_message(self):
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:BodIL_->
                     <maj1:VILLE>PARIS 04</maj1:VILLE>
                  </maj1:ADRESSE>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>"""

        def callback(*args, **kwargs):
            assert False, 'Should not send any request'

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>1</tns:CODE_ERREUR>' in dna_maj_portail(payload)

    def test_no_individus(self, exploite):
        recueil = exploite
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id)

        def callback(method, url, *args, **kwargs):
            assert False, 'Should not send any request'

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>2</tns:CODE_ERREUR>' in dna_maj_portail(payload)

    def test_OPC(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
            <maj1:INDIVIDUS>
               <!--Optional:-->
               <maj1:INDIVIDU>
            <maj1:ID_RECUEIL_DEMANDE>{recueil_id}</maj1:ID_RECUEIL_DEMANDE>
                  <maj1:ID_USAGER_PORTAIL>{usager_id}</maj1:ID_USAGER_PORTAIL>
                  <maj1:TYPE_INDIVIDU>ADULTE</maj1:TYPE_INDIVIDU>
                  <maj1:ID_DNA>205511</maj1:ID_DNA>
                  <maj1:OPC>
                    <maj1:OPC_ACCEPTE>1</maj1:OPC_ACCEPTE>
                  </maj1:OPC>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id, usager_id=usager.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 3

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager.reload()
        da.reload()
        assert da.acceptation_opc == True

    def test_vulnerabilites(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
            <maj1:INDIVIDUS>
               <!--Optional:-->
               <maj1:INDIVIDU>
            <maj1:ID_RECUEIL_DEMANDE>{recueil_id}</maj1:ID_RECUEIL_DEMANDE>
                  <maj1:ID_USAGER_PORTAIL>{usager_id}</maj1:ID_USAGER_PORTAIL>
                  <maj1:TYPE_INDIVIDU>ADULTE</maj1:TYPE_INDIVIDU>
                  <maj1:ID_DNA>205511</maj1:ID_DNA>
                   <maj1:VULNERABILITE>
                      <maj1:ENCEINTE>false</maj1:ENCEINTE>
                      <!--Optional:-->
                      <maj1:ENCEINTE_DATE_TERME/>
                      <maj1:MALVOYANTE>false</maj1:MALVOYANTE>
                      <maj1:MALENTENDANTE>true</maj1:MALENTENDANTE>
                      <maj1:INTERPRETE_SIGNE>false</maj1:INTERPRETE_SIGNE>
                      <maj1:MOBILITE_REDUITE>false</maj1:MOBILITE_REDUITE>
                   </maj1:VULNERABILITE>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id, usager_id=usager.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager.reload()
        da.reload()
        vulnerabilite = usager.vulnerabilite
        assert vulnerabilite
        assert vulnerabilite.grossesse == False
        assert vulnerabilite.malvoyance == False
        assert vulnerabilite.malentendance == True
        assert vulnerabilite.interprete_signe == False
        assert vulnerabilite.mobilite_reduite == False
        assert vulnerabilite.date_saisie

    def test_vulnerabilites_real_case(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
   <SOAP-ENV:Header />
   <S:Body>
      <ns2:majPortail xmlns:ns2="http://service.webservices.dna.anaem.social.fr/MajPortailService" xmlns="http://response.message.webservices.dna.anaem.social.fr/majPortailResponse" xmlns:ns3="http://param.message.webservices.dna.anaem.social.fr/majPortail">
         <ns2:MAJPORTAIL>
            <ns3:ID_FAMILLE_DNA>193565</ns3:ID_FAMILLE_DNA>
            <ns3:INDIVIDUS>
               <ns3:INDIVIDU>
            <ns3:ID_RECUEIL_DEMANDE>{recueil_id}</ns3:ID_RECUEIL_DEMANDE>
                  <ns3:ID_USAGER_PORTAIL>{usager_id}</ns3:ID_USAGER_PORTAIL>
                  <ns3:TYPE_INDIVIDU>Adulte</ns3:TYPE_INDIVIDU>
                  <ns3:ID_DNA>233641</ns3:ID_DNA>
                  <ns3:VULNERABILITE>
                     <ns3:VULNERABLE>1</ns3:VULNERABLE>
                     <ns3:ENCEINTE>1</ns3:ENCEINTE>
                     <ns3:ENCEINTE_DATE_TERME>2016-03-01</ns3:ENCEINTE_DATE_TERME>
                     <ns3:MALVOYANTE>0</ns3:MALVOYANTE>
                     <ns3:MALENTENDANTE>1</ns3:MALENTENDANTE>
                     <ns3:INTERPRETE_SIGNE>0</ns3:INTERPRETE_SIGNE>
                     <ns3:MOBILITE_REDUITE>1</ns3:MOBILITE_REDUITE>
                     <ns3:INDISPONIBILITE_POTENTIELLE>0</ns3:INDISPONIBILITE_POTENTIELLE>
                  </ns3:VULNERABILITE>
               </ns3:INDIVIDU>
            </ns3:INDIVIDUS>
         </ns2:MAJPORTAIL>
      </ns2:majPortail>
   </S:Body>
</S:Envelope>
        """.format(recueil_id=recueil.id, usager_id=usager.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager.reload()
        da.reload()
        vulnerabilite = usager.vulnerabilite
        assert vulnerabilite
        assert vulnerabilite.grossesse == True
        assert vulnerabilite.malvoyance == False
        assert vulnerabilite.malentendance == True
        assert vulnerabilite.interprete_signe == False
        assert vulnerabilite.mobilite_reduite == True
        assert vulnerabilite.date_saisie

    def test_bad_vulnerabilites(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
      <maj:MajPortail>
         <!--Optional:-->
         <maj:MAJPORTAIL>
            <maj1:ID_FAMILLE_DNA>168486</maj1:ID_FAMILLE_DNA>
            <!--Optional:-->
            <maj1:INDIVIDUS>
               <!--Optional:-->
               <maj1:INDIVIDU>
            <maj1:ID_RECUEIL_DEMANDE>{recueil_id}</maj1:ID_RECUEIL_DEMANDE>
                  <maj1:ID_USAGER_PORTAIL>{usager_id}</maj1:ID_USAGER_PORTAIL>
                  <maj1:TYPE_INDIVIDU>ADULTE</maj1:TYPE_INDIVIDU>
                  <maj1:ID_DNA>205511</maj1:ID_DNA>
                   <maj1:VULNERABILITE>
                      <maj1:VULNERABLE>false</maj1:VULNERABLE>
                      <maj1:FAUX>false</maj1:FAUX>
                      <maj1:ENCEINTE>false</maj1:ENCEINTE>
                      <!--Optional:-->
                      <maj1:ENCEINTE_DATE_TERME/>
                      <maj1:MALVOYANTES>false</maj1:MALVOYANTES>
                      <maj1:MALENTENDANTE>false</maj1:MALENTENDANTE>
                      <maj1:INTERPRETE_SIGNE>false</maj1:INTERPRETE_SIGNE>
                      <maj1:MOBILITE_REDUITE>false</maj1:MOBILITE_REDUITE>
                   </maj1:VULNERABILITE>
               </maj1:INDIVIDU>
            </maj1:INDIVIDUS>
         </maj:MAJPORTAIL>
      </maj:MajPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id, usager_id=usager.id)

        def callback(*args, **kwargs):
            assert False, 'Should not send any request'

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>11</tns:CODE_ERREUR>' in dna_maj_portail(payload)

    def test_full(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205511"
        usager.identifiant_famille_dna = "168486"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
    <majPortail>
      <MAJPORTAIL>
        <ID_FAMILLE_DNA>168486</ID_FAMILLE_DNA>
        <INDIVIDUS>
          <INDIVIDU>        <ID_RECUEIL_DEMANDE>{recueil_id}</ID_RECUEIL_DEMANDE>
            <TYPE_INDIVIDU>Adulte</TYPE_INDIVIDU>
            <ID_DNA>205511</ID_DNA>
            <ID_USAGER_PORTAIL>{usager_id}</ID_USAGER_PORTAIL>
            <OPC>
              <OPC_ACCEPTE>1</OPC_ACCEPTE>
            </OPC>
            <VULNERABILITE>
              <ENCEINTE>true</ENCEINTE>
              <ENCEINTE_DATE_TERME></ENCEINTE_DATE_TERME>
              <MALVOYANTE>false</MALVOYANTE>
              <MALENTENDANTE>false</MALENTENDANTE>
              <INTERPRETE_SIGNE>true</INTERPRETE_SIGNE>
              <MOBILITE_REDUITE>false</MOBILITE_REDUITE>
            </VULNERABILITE>
            <ORIENTATION>
              <AGENT_OFII>Agent OFII</AGENT_OFII>
              <DATE_SAISIE>2015-09-01</DATE_SAISIE>
            </ORIENTATION>
            <HEBERGEMENT>
              <TYPE_HEBERGEMENT>Hébergement pérenne</TYPE_HEBERGEMENT>
              <DATE_ENTREE>2015-09-09</DATE_ENTREE>
              <DATE_SORTIE></DATE_SORTIE>
              <DATE_REFUS></DATE_REFUS>
            </HEBERGEMENT>
            <ADRESSE>
              <NUMERO_VOIE>123</NUMERO_VOIE>
              <LIBELLE_VOIE>RUE DE LA VOIE</LIBELLE_VOIE>
              <ADRESSE2></ADRESSE2>
              <CODE_POSTAL>75123</CODE_POSTAL>
              <VILLE>PARIS</VILLE>
              <TELEPHONE></TELEPHONE>
              <EMAIL></EMAIL>
            <NUM_DOMICILIATION></NUM_DOMICILIATION>
            </ADRESSE>
          </INDIVIDU>
        </INDIVIDUS>
      </MAJPORTAIL>
    </majPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(recueil_id=recueil.id, usager_id=usager.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 6

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager.reload()
        da.reload()
        loc = usager.localisations[-1]
        assert loc.organisme_origine == 'DNA'
        assert loc.adresse.voie == 'RUE DE LA VOIE'
        assert loc.adresse.numero_voie == '123'
        assert loc.adresse.code_postal == '75123'
        assert loc.adresse.ville == 'PARIS'
        assert loc.adresse.chez == None
        assert loc.adresse.pays == None
        assert not loc.adresse.longlat
        assert da.acceptation_opc == True
        assert da.agent_orientation == 'Agent OFII'
        assert da.date_orientation == datetime(2015, 9, 1)
        vulnerabilite = usager.vulnerabilite
        assert vulnerabilite
        assert vulnerabilite.objective == None
        assert vulnerabilite.grossesse == True
        assert vulnerabilite.grossesse_date_terme == None
        assert vulnerabilite.malvoyance == False
        assert vulnerabilite.malentendance == False
        assert vulnerabilite.interprete_signe == True
        assert vulnerabilite.mobilite_reduite == False
        assert vulnerabilite.absence_raison_medicale == None
        assert vulnerabilite.date_saisie
        hebergement = da.hebergement
        assert hebergement
        assert hebergement.type == 'CADA'
        assert hebergement.date_entre_hebergement == datetime(2015, 9, 9)
        assert hebergement.date_sortie_hebergement == None
        assert hebergement.date_refus_hebergement == None

    def test_multi_full(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager_1 = recueil.usager_1.usager_existant
        usager_2 = recueil.usager_2.usager_existant
        da_1 = recueil.usager_1.demande_asile_resultante
        da_2 = recueil.usager_2.demande_asile_resultante
        # Sanity check
        assert da_1
        assert da_2
        usager_1.identifiant_dna = "205511"
        usager_1.identifiant_famille_dna = "168486"
        usager_1.save()
        usager_2.identifiant_dna = "205512"
        usager_2.identifiant_famille_dna = "168486"
        usager_2.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:maj="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortail"
xmlns:maj1="http://qualification.asile.sief.apps.cloudmi.minint.fr/api/connectors/dna/MajPortailNS">
   <soapenv:Header/>
   <soapenv:Body>
    <majPortail>
      <MAJPORTAIL>
        <ID_FAMILLE_DNA>168486</ID_FAMILLE_DNA>
        <INDIVIDUS>
          <INDIVIDU>
        <ID_RECUEIL_DEMANDE>{recueil_id}</ID_RECUEIL_DEMANDE>
            <TYPE_INDIVIDU>Adulte</TYPE_INDIVIDU>
            <ID_DNA>205511</ID_DNA>
            <ID_USAGER_PORTAIL>{usager_1_id}</ID_USAGER_PORTAIL>
            <OPC>
              <OPC_ACCEPTE>1</OPC_ACCEPTE>
            </OPC>
            <VULNERABILITE>
              <VULNERABLE>true</VULNERABLE>
              <ENCEINTE>false</ENCEINTE>
              <ENCEINTE_DATE_TERME></ENCEINTE_DATE_TERME>
              <MALVOYANTE>false</MALVOYANTE>
              <MALENTENDANTE>false</MALENTENDANTE>
              <INTERPRETE_SIGNE>true</INTERPRETE_SIGNE>
              <MOBILITE_REDUITE>false</MOBILITE_REDUITE>
            </VULNERABILITE>
            <ORIENTATION>
              <AGENT_OFII>Agent OFII 1</AGENT_OFII>
              <DATE_SAISIE>2015-09-01</DATE_SAISIE>
            </ORIENTATION>
            <HEBERGEMENT>
              <TYPE_HEBERGEMENT>Hébergement pérenne</TYPE_HEBERGEMENT>
              <DATE_ENTREE>2015-09-09</DATE_ENTREE>
              <DATE_SORTIE></DATE_SORTIE>
              <DATE_REFUS></DATE_REFUS>
            </HEBERGEMENT>
            <ADRESSE>
              <NUMERO_VOIE>123</NUMERO_VOIE>
              <LIBELLE_VOIE>RUE DE LA VOIE</LIBELLE_VOIE>
              <ADRESSE2></ADRESSE2>
              <CODE_POSTAL>75123</CODE_POSTAL>
              <VILLE>PARIS</VILLE>
              <TELEPHONE></TELEPHONE>
              <EMAIL></EMAIL>
            <NUM_DOMICILIATION></NUM_DOMICILIATION>
            </ADRESSE>
          </INDIVIDU>
          <INDIVIDU>
            <TYPE_INDIVIDU>Adulte</TYPE_INDIVIDU>
        <ID_RECUEIL_DEMANDE>{recueil_id}</ID_RECUEIL_DEMANDE>
            <ID_DNA>205512</ID_DNA>
            <ID_USAGER_PORTAIL>{usager_2_id}</ID_USAGER_PORTAIL>
            <OPC>
              <OPC_ACCEPTE>1</OPC_ACCEPTE>
            </OPC>
            <VULNERABILITE>
              <VULNERABLE>true</VULNERABLE>
              <ENCEINTE>false</ENCEINTE>
              <ENCEINTE_DATE_TERME></ENCEINTE_DATE_TERME>
              <MALVOYANTE>false</MALVOYANTE>
              <MALENTENDANTE>false</MALENTENDANTE>
              <INTERPRETE_SIGNE>true</INTERPRETE_SIGNE>
              <MOBILITE_REDUITE>false</MOBILITE_REDUITE>
            </VULNERABILITE>
            <ORIENTATION>
              <AGENT_OFII>Agent OFII 2</AGENT_OFII>
              <DATE_SAISIE>2015-09-01</DATE_SAISIE>
            </ORIENTATION>
            <HEBERGEMENT>
              <TYPE_HEBERGEMENT>Hébergement pérenne</TYPE_HEBERGEMENT>
              <DATE_ENTREE>2015-09-09</DATE_ENTREE>
              <DATE_SORTIE></DATE_SORTIE>
              <DATE_REFUS></DATE_REFUS>
            </HEBERGEMENT>
            <ADRESSE>
              <NUMERO_VOIE>123</NUMERO_VOIE>
              <LIBELLE_VOIE>RUE DE LA VOIE</LIBELLE_VOIE>
              <ADRESSE2></ADRESSE2>
              <CODE_POSTAL>75123</CODE_POSTAL>
              <VILLE>PARIS</VILLE>
              <TELEPHONE></TELEPHONE>
              <EMAIL></EMAIL>
            <NUM_DOMICILIATION></NUM_DOMICILIATION>
            </ADRESSE>
          </INDIVIDU>
        </INDIVIDUS>
      </MAJPORTAIL>
    </majPortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(usager_1_id=usager_1.id, usager_2_id=usager_2.id, recueil_id=recueil.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)
        callbacks = [callback_get_backend] * 12

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager_1.reload()
        da_1.reload()
        loc = usager_1.localisations[-1]
        assert loc.organisme_origine == 'DNA'
        assert loc.adresse.voie == 'RUE DE LA VOIE'
        assert loc.adresse.numero_voie == '123'
        assert loc.adresse.code_postal == '75123'
        assert loc.adresse.ville == 'PARIS'
        assert loc.adresse.chez == None
        assert loc.adresse.pays == None
        assert not loc.adresse.longlat
        assert da_1.acceptation_opc == True
        assert da_1.agent_orientation == 'Agent OFII 1'
        assert da_1.date_orientation == datetime(2015, 9, 1)
        vulnerabilite = usager_1.vulnerabilite
        assert vulnerabilite
        assert vulnerabilite.objective == True
        assert vulnerabilite.grossesse == False
        assert vulnerabilite.grossesse_date_terme == None
        assert vulnerabilite.malvoyance == False
        assert vulnerabilite.malentendance == False
        assert vulnerabilite.interprete_signe == True
        assert vulnerabilite.mobilite_reduite == False
        assert vulnerabilite.absence_raison_medicale == None
        assert vulnerabilite.date_saisie
        hebergement = da_1.hebergement
        assert hebergement
        assert hebergement.type == 'CADA'
        assert hebergement.date_entre_hebergement == datetime(2015, 9, 9)
        assert hebergement.date_sortie_hebergement == None
        assert hebergement.date_refus_hebergement == None
        usager_2.reload()
        da_2.reload()
        loc = usager_2.localisations[-1]
        assert loc.organisme_origine == 'DNA'
        assert loc.adresse.voie == 'RUE DE LA VOIE'
        assert loc.adresse.numero_voie == '123'
        assert loc.adresse.code_postal == '75123'
        assert loc.adresse.ville == 'PARIS'
        assert loc.adresse.chez == None
        assert loc.adresse.pays == None
        assert not loc.adresse.longlat
        assert da_2.acceptation_opc == True
        assert da_2.agent_orientation == 'Agent OFII 2'
        assert da_2.date_orientation == datetime(2015, 9, 1)
        vulnerabilite = usager_2.vulnerabilite
        assert vulnerabilite
        assert vulnerabilite.objective == True
        assert vulnerabilite.grossesse == False
        assert vulnerabilite.grossesse_date_terme == None
        assert vulnerabilite.malvoyance == False
        assert vulnerabilite.malentendance == False
        assert vulnerabilite.interprete_signe == True
        assert vulnerabilite.mobilite_reduite == False
        assert vulnerabilite.absence_raison_medicale == None
        assert vulnerabilite.date_saisie
        hebergement = da_2.hebergement
        assert hebergement
        assert hebergement.type == 'CADA'
        assert hebergement.date_entre_hebergement == datetime(2015, 9, 9)
        assert hebergement.date_sortie_hebergement == None
        assert hebergement.date_refus_hebergement == None

    def test_maj_adresse_2(self, user, exploite):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = exploite
        usager = recueil.usager_1.usager_existant
        da = recueil.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "205543"
        usager.identifiant_famille_dna = "168513"
        usager.save()
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/">
   <S:Body>
      <ns2:majPortail xmlns:ns2="http://service.webservices.dna.anaem.social.fr/MajPortailService" xmlns="http://response.message.webservices.dna.anaem.social.fr/majPortailResponse" xmlns:ns3="http://param.message.webservices.dna.anaem.social.fr/majPortail">
         <ns2:MAJPORTAIL>
            <ns3:ID_FAMILLE_DNA>168513</ns3:ID_FAMILLE_DNA>
            <ns3:INDIVIDUS>
               <ns3:INDIVIDU>
            <ns3:ID_RECUEIL_DEMANDE>{recueil_id}</ns3:ID_RECUEIL_DEMANDE>
                  <ns3:ID_USAGER_PORTAIL>{usager_id}</ns3:ID_USAGER_PORTAIL>
                  <ns3:TYPE_INDIVIDU>Adulte</ns3:TYPE_INDIVIDU>
                  <ns3:ID_DNA>205543</ns3:ID_DNA>
                  <ns3:ADRESSE>
                     <ns3:NUMERO_VOIE>10</ns3:NUMERO_VOIE>
                     <ns3:ADRESSE2 />
                     <ns3:LIBELLE_VOIE>BOULEVARD
DE
SEBASTOPOL</ns3:LIBELLE_VOIE>
                     <ns3:CODE_INSEE>75104</ns3:CODE_INSEE>
                     <ns3:CODE_POSTAL>75004</ns3:CODE_POSTAL>
                     <ns3:VILLE>PARIS
04</ns3:VILLE>
                  </ns3:ADRESSE>
               </ns3:INDIVIDU>
            </ns3:INDIVIDUS>
         </ns2:MAJPORTAIL>
      </ns2:majPortail>
   </S:Body>
</S:Envelope>""".format(recueil_id=recueil.id, usager_id=usager.id)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert '<tns:CODE_ERREUR>0</tns:CODE_ERREUR>' in dna_maj_portail(payload)
        assert not len(callbacks)
        usager.reload()
        da.reload()
        assert len(usager.localisations) == 2
        loc = usager.localisations[-1]
        assert loc.organisme_origine == 'DNA'
        assert loc.adresse.voie == 'BOULEVARD\nDE\nSEBASTOPOL'
        assert loc.adresse.numero_voie == '10'
        assert loc.adresse.code_postal == '75004'
        assert loc.adresse.code_insee == '75104'
        assert loc.adresse.ville == 'PARIS\n04'
        assert loc.adresse.chez == None
        assert loc.adresse.complement == None
        assert loc.adresse.pays == None
        assert not loc.adresse.longlat

    def test_get_wsdl(self):
        r = self.client_app.get('%s/MajPortail?wsdl' % self.app.config['CONNECTOR_DNA_PREFIX'])
        assert r.status_code == 200
        assert r.headers['Content-Type'] == 'text/xml; charset=utf-8'
        wsdl_domain = self.app.config['BACKEND_URL_DOMAIN'] + \
            self.app.config['CONNECTOR_DNA_PREFIX']
        assert wsdl_domain in r.data.decode()

    def test_dna_recuperer_donnees_portail_mineur_accompagnant(self, site_structure_accueil, pa_realise, user):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert False
        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{{
   "recueil_da": {{
      "id": "135",
      "usager_1": {{
         "_cls": "UsagerPrincipalRecueil",
         "adresse": {{
            "adresse_inconnue": true
         }},
         "nom": "Chu",
         "date_naissance": "1986-06-12T00:00:00+00:00",
         "situation_familiale": "CELIBATAIRE",
         "nationalites": [
            {{
               "libelle": "Chinoise (rpc) ",
               "code": "CHN"
            }}
         ],
         "ville_naissance": "P\\u00e9kin",
         "sexe": "F",
         "present_au_moment_de_la_demande": true,
         "prenoms": [
            "Lei"
         ],
         "demandeur": false,
         "pays_naissance": {{
            "libelle": "Chine",
            "code": "CHN"
         }}
      }},
      "agent_accueil": {{
         "id": "5603fe65000c67212242b31f",
         "_links": {{
            "self": "/api/utilisateurs/5603fe65000c67212242b31f"
         }}
      }},
      "_updated": "2015-10-02T09:46:03.817444+00:00",
      "_links": {{
         "self": "/api/recueils_da/135",
         "parent": "/api/recueils_da"
      }},
      "structure_accueil": {{
         "id": "{0}",
         "_links": {{
            "self": "/api/sites/{0}"
         }}
      }},
      "rendez_vous_gu": {{
         "marge": 30,
         "site": {{
            "id": "{0}",
            "_links": {{
               "self": "/api/sites/{0}"
            }}
         }},
         "creneaux": [
            {{
               "id": "560e3ddc000c6763315bc9bb",
               "_links": {{
                  "self": "/api/sites/5603fdd1000c672120fdce01/creneaux/560e3ddc000c6763315bc9bb"
               }}
            }}
         ],
         "motif": "PREMIER_RDV_GU",
         "date": "2015-10-05T09:15:00+00:00"
      }},
      "_created": "2015-10-02T09:44:58.530000+00:00",
      "date_transmission": "2015-10-02T09:46:03.778752+00:00",
      "statut": "PA_REALISE",
      "_version": 5,
      "enfants": [
         {{
            "representant_legal_nom": "Chu",
            "adresse": {{"code_postal": "75016",
            "adresse_inconnue": false,
            "pays": {{"libelle": "FRANCE", "code": "FRA"}},
            "voie": "Avenue Mozart", "code_insee": "75116",
            "identifiant_ban": "ADRNIVX_0000000270771092",
            "ville": "Paris", "chez": "",
            "longlat": [2.27449, 48.858034],
            "numero_voie": "1", "complement": ""}},
            "usager_1": true,
            "nom": "Chu",
            "date_naissance": "1999-06-16T00:00:00+00:00",
            "photo_premier_accueil": {{
               "id": "560e51c4000c67633491bae0",
               "_links": {{
                  "self": "/api/fichiers/560e51c4000c67633491bae0",
                  "data": "/api/fichiers/560e51c4000c67633491bae0/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE0NDM4NTgzNjMuODg0MDMxLCJpZCI6IjU2MGU1MWM0MDAwYzY3NjMzNDkxYmFlMCIsInR5cGUiOiJmaWNoaWVyIn0.Yyt2zvxTo4vqN7EosvkdMzcnfL_2ZYdUv9p5wrOf5NI",
                  "name": "Liu_2.png"
               }}
            }},
            "date_entree_en_france": "2015-08-14T00:00:00+00:00",
            "_cls": "UsagerEnfantRecueil",
            "langues": [
               {{
                  "libelle": "chinois",
                  "code": "chi"
               }}
            ],
            "ville_naissance": "P\\u00e9kin",
            "langues_audition_OFPRA": [
               {{
                  "libelle": "Chinois (Mandarin, Cantonais)",
                  "code": "CHINOIS"
               }}
            ],
            "representant_legal_prenom": "Lei",
            "sexe": "M",
            "present_au_moment_de_la_demande": true,
            "prenoms": [
               "Jan"
            ],
            "demandeur": true,
            "date_depart": "2015-08-14T00:00:00+00:00",
            "pays_naissance": {{
               "libelle": "Chine",
               "code": "CHN"
            }},
            "representant_legal_personne_morale":false,
            "nationalites": [
               {{
                  "libelle": "Chinoise (rpc) ",
                  "code": "CHN"
               }}
            ],
            "situation_familiale": "CELIBATAIRE"
         }}
      ],
      "profil_demande": "MINEUR_ACCOMPAGNANT",
      "structure_guichet_unique": {{
         "id": "{0}",
         "_links": {{
            "self": "/api/sites/{0}"
         }}
      }}
   }}
}}""".format(site_structure_accueil.id),
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_sites]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert 'Pas de demande pour MINEUR_ACCOMPAGNANT sans parent demandeur.' in dna_recuperer_donnees_portail(
            handler, msg)
        assert callbacks

    def test_reponse_dna_recuperer_donnees_portail(self):
        from connector.dna.recupererdonneesportail import process_response

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            assert method == 'PATCH'
            assert 'https://mydomain.com/pref/usagers/691' == url
            return Response(200)

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        payload = """<?xml version='1.0' encoding='UTF-8'?><S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"><SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService"><REPONSES><REPONSE><ID_RECUEIL_DEMANDE>961</ID_RECUEIL_DEMANDE><ID_FAMILLE_DNA>193776</ID_FAMILLE_DNA><CODE_ERREUR>00</CODE_ERREUR><LIBELLE_ERREUR>OK</LIBELLE_ERREUR><USAGERS><USAGER><ID_USAGER_PORTAIL>691</ID_USAGER_PORTAIL><ID_DNA>233916</ID_DNA></USAGER></USAGERS></REPONSE></REPONSES></ns2:getDonneePortailResponse></S:Body></S:Envelope>"""
        self.mock_requests.callback_response = callback_post_backend
        process_response(handler, payload)

    def test_dna_recuperer_donnees_portail_mineur_isole(self, site_structure_accueil, pa_realise, user):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert False

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            assert False

        def callback_dna(method, url, *args, **kwargs):
            assert False

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{{
   "recueil_da": {{
      "id": "136",
      "usager_1": {{
         "_cls": "UsagerPrincipalRecueil",
         "adresse": {{
            "adresse_inconnue": true
         }},
         "nom": "Chu",
         "date_naissance": "1986-06-12T00:00:00+00:00",
         "situation_familiale": "CELIBATAIRE",
         "nationalites": [
            {{
               "libelle": "Chinoise (rpc) ",
               "code": "CHN"
            }}
         ],
         "ville_naissance": "P\\u00e9kin",
         "sexe": "F",
         "present_au_moment_de_la_demande": true,
         "prenoms": [
            "Lei"
         ],
         "demandeur": false,
         "pays_naissance": {{
            "libelle": "Chine",
            "code": "CHN"
         }}
      }},
      "agent_accueil": {{
         "id": "5603fe65000c67212242b31f",
         "_links": {{
            "self": "/api/utilisateurs/5603fe65000c67212242b31f"
         }}
      }},
      "_updated": "2015-10-02T09:46:03.817444+00:00",
      "_links": {{
         "self": "/api/recueils_da/135",
         "parent": "/api/recueils_da"
      }},
      "structure_accueil": {{
         "id": "{0}",
         "_links": {{
            "self": "/api/sites/{0}"
         }}
      }},
      "rendez_vous_gu": {{
         "marge": 30,
         "site": {{
            "id": "{0}",
            "_links": {{
               "self": "/api/sites/{0}"
            }}
         }},
         "creneaux": [
            {{
               "id": "560e3ddc000c6763315bc9bb",
               "_links": {{
                  "self": "/api/sites/5603fdd1000c672120fdce01/creneaux/560e3ddc000c6763315bc9bb"
               }}
            }}
         ],
         "motif": "PREMIER_RDV_GU",
         "date": "2015-10-05T09:15:00+00:00"
      }},
      "_created": "2015-10-02T09:44:58.530000+00:00",
      "date_transmission": "2015-10-02T09:46:03.778752+00:00",
      "statut": "PA_REALISE",
      "_version": 5,
      "enfants": [
         {{
            "representant_legal_nom": "Chu",
            "adresse": {{
               "adresse_inconnue": true
            }},
            "usager_1": true,
            "nom": "Chu",
            "date_naissance": "1999-06-16T00:00:00+00:00",
            "photo_premier_accueil": {{
               "id": "560e51c4000c67633491bae0",
               "_links": {{
                  "self": "/api/fichiers/560e51c4000c67633491bae0",
                  "data": "/api/fichiers/560e51c4000c67633491bae0/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE0NDM4NTgzNjMuODg0MDMxLCJpZCI6IjU2MGU1MWM0MDAwYzY3NjMzNDkxYmFlMCIsInR5cGUiOiJmaWNoaWVyIn0.Yyt2zvxTo4vqN7EosvkdMzcnfL_2ZYdUv9p5wrOf5NI",
                  "name": "Liu_2.png"
               }}
            }},
            "date_entree_en_france": "2015-08-14T00:00:00+00:00",
            "_cls": "UsagerEnfantRecueil",
            "langues": [
               {{
                  "libelle": "chinois",
                  "code": "chi"
               }}
            ],
            "ville_naissance": "P\\u00e9kin",
            "langues_audition_OFPRA": [
               {{
                  "libelle": "Chinois (Mandarin, Cantonais)",
                  "code": "CHINOIS"
               }}
            ],
            "representant_legal_prenom": "Lei",
            "sexe": "M",
            "present_au_moment_de_la_demande": true,
            "prenoms": [
               "Jan"
            ],
            "demandeur": true,
            "date_depart": "2015-08-14T00:00:00+00:00",
            "pays_naissance": {{
               "libelle": "Chine",
               "code": "CHN"
            }},
            "representant_legal_personne_morale":false,
            "nationalites": [
               {{
                  "libelle": "Chinoise (rpc) ",
                  "code": "CHN"
               }}
            ],
            "situation_familiale": "CELIBATAIRE"
         }}
      ],
      "profil_demande": "MINEUR_ISOLE",
      "structure_guichet_unique": {{
         "id": "{0}",
         "_links": {{
            "self": "/api/sites/{0}"
         }}
      }}
   }}
}}""".format(site_structure_accueil.id),
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_sites]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert 'Pas de demande pour MINEUR_ISOLE.' in dna_recuperer_donnees_portail(handler, msg)
        assert callbacks

    def test_dna_recuperer_donnees_portail_enfant_majeur_demandeur(self, site_structure_accueil, pa_realise, user,
                                                                   payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
   <soapenv:Header />
   <soapenv:Body>
      <ns1:getDonneePortail>
         <DEMANDES>
            <DEMANDE>
               <DATE_CREATION_DEMANDE>2015-11-24</DATE_CREATION_DEMANDE>
               <INDIVIDUS>
                  <INDIVIDU>
                     <ADULTE>
                        <TYPE>Autre adulte</TYPE>
                        <LIEU_NAISSANCE>RDC, REPUBLIQUE DEMO. DU CONGO</LIEU_NAISSANCE>
                        <MATRIMONIAL>Divorcé</MATRIMONIAL>
                        <INSEE_PAYS_NATIONALITE>356</INSEE_PAYS_NATIONALITE>
                        <LANGUE1>34</LANGUE1>
                        <PRENOM>KOLI</PRENOM>
                        <NOM_NAISSANCE>JABBOUR</NOM_NAISSANCE>
                        <SEXE>M</SEXE>
                        <DATE_NAISSANCE>1992-06-10</DATE_NAISSANCE>
                        <DATE_ENTREE_EN_FRANCE>2015-07-17</DATE_ENTREE_EN_FRANCE>
                     </ADULTE>
                  </INDIVIDU>
                  <INDIVIDU>
                     <ADULTE>
                        <LIEU_NAISSANCE>RDC, REPUBLIQUE DEMO. DU CONGO</LIEU_NAISSANCE>
                        <TYPE>Demandeur principal</TYPE>
                        <MATRIMONIAL>Divorcé</MATRIMONIAL>
                        <INSEE_PAYS_NATIONALITE>356</INSEE_PAYS_NATIONALITE>
                        <LANGUE1>34</LANGUE1>
                        <PRENOM>JO</PRENOM>
                        <NOM_NAISSANCE>JABBOUR</NOM_NAISSANCE>
                        <SEXE>M</SEXE>
                        <DATE_NAISSANCE>1979-01-16</DATE_NAISSANCE>
                        <DATE_ENTREE_EN_FRANCE>2015-07-17</DATE_ENTREE_EN_FRANCE>
                     </ADULTE>
                  </INDIVIDU>
               </INDIVIDUS>
               <SITES>
                  <SITE>
                     <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
                     <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                     <ADRESSE>
                        <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                        <CODE_POSTAL>33000</CODE_POSTAL>
                        <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                        <VILLE>Bordeaux</VILLE>
                        <CODE_INSEE>33000</CODE_INSEE>
                        <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                        <NUMERO_VOIE>3</NUMERO_VOIE>
                     </ADRESSE>
                     <TYPE_SITE>SPA</TYPE_SITE>
                  </SITE>
               </SITES>
               <DATE_RDV_GU>2015-11-26</DATE_RDV_GU>
               <PROCEDURE_STATUT>0</PROCEDURE_STATUT>
               <ADRESSE><LIBELLE_VOIE>Avenue Mozart</LIBELLE_VOIE>
               <CODE_INSEE>75116</CODE_INSEE><TELEPHONE>0123456789</TELEPHONE>
               <VILLE>Paris</VILLE>
               <NUM_DOMICILIATION>1</NUM_DOMICILIATION>
               <NUMERO_VOIE>1</NUMERO_VOIE>
               <CODE_POSTAL>75016</CODE_POSTAL><ADRESSE2/></ADRESSE>
               <ID_RECUEIL_DEMANDE>559</ID_RECUEIL_DEMANDE>
            </DEMANDE>
         </DEMANDES>
      </ns1:getDonneePortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(
                date=date.strftime("%Y-%m-%d"),
                date_rdv=(date + timedelta(days=1)).strftime("%Y-%m-%d"),
                site=site_structure_accueil.pk)

            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context=""" {{ "recueil_da": {{ "statut": "PA_REALISE",
            "enfants": [ {{ "sexe": "M", "ville_naissance": "RDC",
            "present_au_moment_de_la_demande": true,
            "type_demande": "PREMIERE_DEMANDE_ASILE",
            "date_entree_en_france": "2015-07-17T00:00:00+00:00",
            "cls": "UsagerEnfantRecueil",
            "photo_premier_accueil": {{ "links": {{
            "self": "/api/fichiers/5654a03f000c67331d42e6c5",
            "name": "Ngoma_Moise.png" }}, "id": "5654a03f000c67331d42e6c5" }},
            "adresse": {{ "adresse_inconnue": true }},
            "pays_naissance": {{ "code": "COD", "libelle": "REPUBLIQUE DEMO. DU CONGO" }},
            "usager_1": true, "langues_audition_OFPRA": [ {{ "code": "FRE",
            "libelle": "FRANCAIS" }} ], "nom": "Jabbour", "nationalites": [ {{ "code": "COD",
            "libelle": "congolaise (rdc)" }} ], "situation_familiale": "DIVORCE",
            "date_depart": "2015-07-17T00:00:00+00:00",
            "langues": [ {{ "code": "fre", "libelle": "français" }} ],
            "demandeur": true, "prenoms": [ "Koli" ],
            "date_naissance": "1992-06-10T00:00:00+00:00" }} ],
            "updated": "2015-11-24T17:37:53.626114+00:00",
            "date_transmission": "2015-11-24T17:37:53.562190+00:00",
            "usager_1": {{ "telephone": "0123456789", "ville_naissance": "RDC",
            "present_au_moment_de_la_demande": true,
            "type_demande": "PREMIERE_DEMANDE_ASILE",
            "date_entree_en_france": "2015-07-17T00:00:00+00:00", "cls": "UsagerPrincipalRecueil",
            "photopremier_accueil": {{ "links": {{ "self": "/api/fichiers/56549fef000c6733102b6f85",
            "name": "congolais.png" }}, "id": "56549fef000c6733102b6f85" }},
            "adresse": {{"code_postal": "75016",
            "adresse_inconnue": false,
            "pays": {{"libelle": "FRANCE", "code": "FRA"}},
            "voie": "Avenue Mozart", "code_insee": "75116",
            "identifiant_ban": "ADRNIVX_0000000270771092",
            "ville": "Paris", "chez": "",
            "longlat": [2.27449, 48.858034],
            "numero_voie": "1", "complement": ""}},
            "pays_naissance": {{ "code": "COD", "libelle": "REPUBLIQUE DEMO. DU CONGO" }},
            "langues_audition_OFPRA": [ {{ "code": "FRE", "libelle": "FRANCAIS" }} ],
            "nom": "Jabbour", "nationalites": [ {{ "code": "COD",
            "libelle": "congolaise (rdc)" }} ],
            "situation_familiale": "DIVORCE", "date_depart": "2015-07-17T00:00:00+00:00",
            "langues": [ {{ "code": "fre", "libelle": "français" }} ],
            "date_naissance": "1979-01-16T00:00:00+00:00",
            "demandeur": true, "prenoms": [ "Jo" ], "sexe": "M" }},
            "rendez_vous_gu": {{ "motif": "PREMIER_RDV_GU",
            "creneaux": [ {{ "_links": {{
            "self": "/api/sites/{0}" }},
            "id": "5652d28e000c6726c7a6bed8" }},
            {{ "_links": {{
            "self": "/api/sites/{0}" }},
            "id": "5652d28e000c6726c7a6bee0" }} ],
            "site": {{ "links": {{ "self": "/api/sites/{0}" }},
            "id": "{0}" }},
            "date": "2015-11-26T09:00:00+00:00" }},
            "structure_accueil": {{ "links": {{ "self": "/api/sites/{0}" }},
            "id": "{0}" }},
            "structure_guichet_unique": {{ "links": {{
            "self": "/api/sites/{0}" }},
            "id": "{0}" }},
            "agent_accueil": {{ "links": {{ "self": "/api/utilisateurs/5603fe65000c67212242b31f" }},
            "id": "5603fe65000c67212242b31f" }}, "links": {{ "self": "/api/recueils_da/559",
            "parent": "/api/recueils_da" }}, "created": "2015-11-24T17:37:46.639000+00:00",
            "_version": 4, "profildemande": "FAMILLE", "id": "559" }} }}
            """.format(site_structure_accueil.id),
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_enfant_majeur_non_demandeur(self, site_structure_accueil, pa_realise, user,
                                                                       payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
   <soapenv:Header />
   <soapenv:Body>
      <ns1:getDonneePortail>
         <DEMANDES>
            <DEMANDE>
               <DATE_CREATION_DEMANDE>2015-11-24</DATE_CREATION_DEMANDE>
               <INDIVIDUS>
                  <INDIVIDU>
                     <ADULTE>
                        <LIEU_NAISSANCE>RDC, REPUBLIQUE DEMO. DU CONGO</LIEU_NAISSANCE>
                        <TYPE>Demandeur principal</TYPE>
                        <MATRIMONIAL>Divorcé</MATRIMONIAL>
                        <INSEE_PAYS_NATIONALITE>356</INSEE_PAYS_NATIONALITE>
                        <LANGUE1>34</LANGUE1>
                        <DATE_ENTREE_EN_FRANCE>2015-07-17</DATE_ENTREE_EN_FRANCE>
                        <PRENOM>JO</PRENOM>
                        <NOM_NAISSANCE>JABBOUR</NOM_NAISSANCE>
                        <SEXE>M</SEXE>
                        <DATE_NAISSANCE>1979-01-16</DATE_NAISSANCE>
                     </ADULTE>
                  </INDIVIDU>
               </INDIVIDUS>
               <SITES>
                  <SITE>
                     <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
                     <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                     <ADRESSE>
                        <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                        <CODE_POSTAL>33000</CODE_POSTAL>
                        <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                        <VILLE>Bordeaux</VILLE>
                        <CODE_INSEE>33000</CODE_INSEE>
                        <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                        <NUMERO_VOIE>3</NUMERO_VOIE>
                     </ADRESSE>
                     <TYPE_SITE>SPA</TYPE_SITE>
                  </SITE>
               </SITES>
               <DATE_RDV_GU>2015-11-26</DATE_RDV_GU>
               <PROCEDURE_STATUT>0</PROCEDURE_STATUT>
               <ADRESSE><LIBELLE_VOIE>Avenue Mozart</LIBELLE_VOIE>
               <CODE_INSEE>75116</CODE_INSEE><TELEPHONE>0123456789</TELEPHONE>
               <VILLE>Paris</VILLE>
               <NUM_DOMICILIATION>1</NUM_DOMICILIATION>
               <NUMERO_VOIE>1</NUMERO_VOIE>
               <CODE_POSTAL>75016</CODE_POSTAL><ADRESSE2/></ADRESSE>
               <ID_RECUEIL_DEMANDE>559</ID_RECUEIL_DEMANDE>
            </DEMANDE>
         </DEMANDES>
      </ns1:getDonneePortail>
   </soapenv:Body>
</soapenv:Envelope>""".format(site=site_structure_accueil.pk)

            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context=""" {{ "recueil_da": {{ "statut": "PA_REALISE",
            "enfants": [ {{ "sexe": "M", "ville_naissance": "RDC",
            "present_au_moment_de_la_demande": true,
             "date_entree_en_france": "2015-07-17T00:00:00+00:00",
            "cls": "UsagerEnfantRecueil",
             "photo_premier_accueil": {{ "links": {{
             "self": "/api/fichiers/5654a03f000c67331d42e6c5",
             "name": "Ngoma_Moise.png" }}, "id": "5654a03f000c67331d42e6c5" }},
            "adresse": {{ "adresse_inconnue": true }},
            "pays_naissance": {{ "code": "COD", "libelle": "REPUBLIQUE DEMO. DU CONGO" }},
            "usager_1": true, "langues_audition_OFPRA": [ {{ "code": "FRE",
            "libelle": "FRANCAIS" }} ], "nom": "Jabbour", "nationalites": [ {{ "code": "COD",
            "libelle": "congolaise (rdc)" }} ], "situation_familiale": "CELIBATAIRE",
            "date_depart": "2015-07-17T00:00:00+00:00",
            "langues": [ {{ "code": "fre", "libelle": "français" }} ],
            "demandeur": false, "prenoms": [ "Koli" ],
            "date_naissance": "1992-06-10T00:00:00+00:00" }} ],
            "updated": "2015-11-24T17:37:53.626114+00:00",
            "date_transmission": "2015-11-24T17:37:53.562190+00:00",
            "usager_1": {{ "telephone": "0123456789", "ville_naissance": "RDC",
            "present_au_moment_de_la_demande": true,
            "date_entree_en_france": "2015-07-17T00:00:00+00:00", "cls": "UsagerPrincipalRecueil",
            "photopremier_accueil": {{ "links": {{ "self": "/api/fichiers/56549fef000c6733102b6f85",
            "name": "congolais.png" }}, "id": "56549fef000c6733102b6f85" }},
            "type_demande":"PREMIERE_DEMANDE_ASILE",
            "adresse": {{"code_postal": "75016",
            "adresse_inconnue": false,
            "pays": {{"libelle": "FRANCE", "code": "FRA"}},
            "voie": "Avenue Mozart", "code_insee": "75116",
            "identifiant_ban": "ADRNIVX_0000000270771092",
            "ville": "Paris", "chez": "",
            "longlat": [2.27449, 48.858034],
            "numero_voie": "1", "complement": ""}},
            "pays_naissance": {{ "code": "COD", "libelle": "REPUBLIQUE DEMO. DU CONGO" }},
            "langues_audition_OFPRA": [ {{ "code": "FRE", "libelle": "FRANCAIS" }} ],
            "nom": "Jabbour", "nationalites": [ {{ "code": "COD",
            "libelle": "congolaise (rdc)" }} ],
            "situation_familiale": "DIVORCE", "date_depart": "2015-07-17T00:00:00+00:00",
            "langues": [ {{ "code": "fre", "libelle": "français" }} ],
            "date_naissance": "1979-01-16T00:00:00+00:00",
            "demandeur": true, "prenoms": [ "Jo" ], "sexe": "M" }},
            "rendez_vous_gu": {{ "motif": "PREMIER_RDV_GU",
            "creneaux": [ {{ "_links": {{
            "self": "/api/sites/{0}" }},
            "id": "5652d28e000c6726c7a6bed8" }},
            {{ "_links": {{
            "self": "/api/sites/{0}" }},
            "id": "5652d28e000c6726c7a6bee0" }} ],
            "site": {{ "links": {{ "self": "/api/sites/{0}" }},
            "id": "{0}" }},
            "date": "2015-11-26T09:00:00+00:00" }},
            "structure_accueil": {{ "links": {{ "self": "/api/sites/{0}" }},
            "id": "{0}" }},
            "structure_guichet_unique": {{ "links": {{
            "self": "/api/sites/{0}" }},
            "id": "{0}" }},
            "agent_accueil": {{ "links": {{ "self": "/api/utilisateurs/5603fe65000c67212242b31f" }},
            "id": "5603fe65000c67212242b31f" }}, "links": {{ "self": "/api/recueils_da/559",
            "parent": "/api/recueils_da" }}, "created": "2015-11-24T17:37:46.639000+00:00",
            "_version": 4, "profildemande": "FAMILLE", "id": "559" }} }}
            """.format(site_structure_accueil.id),
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_enfant_majeur_demandeur_exploite(self, site_structure_accueil, pa_realise, user,
                                                                            payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService" >
            <soapenv:Header/>
            <soapenv:Body>
            <ns1:getDonneePortail>
                <DEMANDES>
                    <DEMANDE>
                        <ADRESSE><CODE_POSTAL>75011</CODE_POSTAL><LIBELLE_VOIE>Avenue Parmentier</LIBELLE_VOIE><NUMERO_VOIE>1</NUMERO_VOIE><ADRESSE2></ADRESSE2><VILLE>Paris</VILLE><NUM_DOMICILIATION>1</NUM_DOMICILIATION><CODE_INSEE>75111</CODE_INSEE></ADRESSE>
                        <INDIVIDUS>
                            <INDIVIDU>
                                <DATE_AGDREF>2016-06-06</DATE_AGDREF>
                                <ADULTE>
                                    <NOM_NAISSANCE>ELLOP</NOM_NAISSANCE>
                                    <PRENOM>RAN</PRENOM>
                                    <LIEU_NAISSANCE>dd, REPUBLIQUE DEMO. DU CONGO</LIEU_NAISSANCE>
                                    <SEXE>M</SEXE>
                                    <TYPE>Autre adulte</TYPE>
                                    <INSEE_PAYS_NATIONALITE>356</INSEE_PAYS_NATIONALITE>
                                    <DATE_NAISSANCE>1992-08-15</DATE_NAISSANCE>
                                </ADULTE>
                                <ID_USAGER_PORTAIL>1459</ID_USAGER_PORTAIL>
                            </INDIVIDU>
                            <INDIVIDU>
                                <ID_DEMANDE_ASILE>1206</ID_DEMANDE_ASILE>
                                <DATE_AGDREF>2016-06-06</DATE_AGDREF>
                                <ADULTE>
                                    <MATRIMONIAL>Célibataire</MATRIMONIAL>
                                    <PROCEDURE_TYPE>En procédure normale</PROCEDURE_TYPE>
                                    <NOM_NAISSANCE>ELLOP</NOM_NAISSANCE>
                                    <PRENOM>OLI</PRENOM>
                                    <LIEU_NAISSANCE>dd, REPUBLIQUE DEMO. DU CONGO</LIEU_NAISSANCE>
                                    <SEXE>M</SEXE>
                                    <URL_PHOTO>/api/fichiers/57555b7adc105724ca7d2687/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjU3NTU1YjdhZGMxMDU3MjRjYTdkMjY4NyIsImV4cCI6MTQ2NTI5MTExMy42MDk3NjYsInR5cGUiOiJmaWNoaWVyIn0.4MmYKTUeyP7tOLrbCLwTZLQoDB0pixoO93HjiPfU2cs</URL_PHOTO>
                                    <TYPE>Demandeur principal</TYPE>
                                    <INSEE_PAYS_NATIONALITE>356</INSEE_PAYS_NATIONALITE>
                                    <DATE_NAISSANCE>1979-01-10</DATE_NAISSANCE>
                                    <LANGUE1>34</LANGUE1>
                                </ADULTE>
                                <CONDITION_ENTREE_FRANCE>N</CONDITION_ENTREE_FRANCE>
                                <ID_USAGER_PORTAIL>1458</ID_USAGER_PORTAIL>
                                <ID_AGDREF>7503002801</ID_AGDREF>
                            </INDIVIDU>
                        </INDIVIDUS>
                        <PROCEDURE_STATUT>1</PROCEDURE_STATUT>
                        <SITES>
                            <SITE>
                                <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                                <ADRESSE>
                                    <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                                    <VILLE>Bordeaux</VILLE>
                                    <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                                    <CODE_POSTAL>33000</CODE_POSTAL>
                                    <NUMERO_VOIE>3</NUMERO_VOIE>
                                    <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                                    <CODE_INSEE>33000</CODE_INSEE>
                                </ADRESSE>
                                <TYPE_SITE>SPA</TYPE_SITE>
                                <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
                            </SITE>
                        </SITES>
                        <DATE_PREF>2016-06-06</DATE_PREF>
                        <ID_RECUEIL_DEMANDE>1807</ID_RECUEIL_DEMANDE>
                        <AGENT_PREF>5603fe39000c672118021314</AGENT_PREF>
                        <DATE_CREATION_DEMANDE>2016-06-06</DATE_CREATION_DEMANDE>
                    </DEMANDE>
                </DEMANDES>
            </ns1:getDonneePortail>
            </soapenv:Body>
            </soapenv:Envelope>""".format(site=site_structure_accueil.pk)

            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context=""" {
                "enfants": [ { "usager": { "id": "1459", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "_updated": "2016-06-06T11:18:33.566875+00:00", "prenoms": [ "Ran" ], "transferable": true, "ecv_valide": false, "_links": { "localisation_update": "/api/usagers/1459/localisations", "update": "/api/usagers/1459", "localisations": "/api/usagers/1459/localisations", "prefecture_rattachee": "/api/usagers/1459/prefecture_rattachee", "etat_civil_update": "/api/usagers/1459/etat_civil", "self": "/api/usagers/1459", "parent": "/api/usagers" }, "date_naissance": "1992-08-15T00:00:00+00:00", "_created": "2016-06-06T11:18:33.564664+00:00", "ville_naissance": "dd", "sexe": "M", "localisation": { "date_maj": "2016-06-06T11:18:33.563541+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "nom": "Ellop", "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "identifiant_pere": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "_version": 2, "date_enregistrement_agdref": "2016-06-06T13:23:49+00:00" } } ],
                "usager_1": { "demande_asile": { "conditions_exceptionnelles_accueil": false, "structure_premier_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "date_depart": "2015-07-17T00:00:00+00:00", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "decision_sur_attestation": true, "date_decision_sur_attestation": "2016-06-06T00:00:00+00:00", "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_links": { "editer_attestation": "/api/demandes_asile/1206/attestations", "self": "/api/demandes_asile/1206", "orienter": "/api/demandes_asile/1206/orientation", "parent": "/api/demandes_asile" }, "_updated": "2016-06-06T11:18:33.588514+00:00", "_created": "2016-06-06T11:18:33.586416+00:00", "recueil_da_origine": { "id": 1807, "_links": { "self": "/api/recueils_da/1807" } }, "usager": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "condition_entree_france": "REGULIERE", "referent_premier_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "id": "1206", "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "procedure": { "acteur": "GUICHET_UNIQUE", "type": "NORMALE", "motif_qualification": "PNOR" }, "indicateur_visa_long_sejour": false, "renouvellement_attestation": 1, "statut": "PRETE_EDITION_ATTESTATION", "type_demandeur": "PRINCIPAL", "enfants_presents_au_moment_de_la_demande": [ { "id": 1459, "_links": { "self": "/api/usagers/1459" } } ], "date_enregistrement": "2016-06-06T11:18:33.517110+00:00", "visa": "C", "_version": 2, "date_demande": "2016-06-06T11:17:31.745000+00:00" }, "usager": { "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "sexe": "M", "ecv_valide": false, "identifiant_portail_agdref": "hO3iHZU1ZGi6", "identifiant_agdref": "7503002801", "_links": { "localisation_update": "/api/usagers/1458/localisations", "update": "/api/usagers/1458", "localisations": "/api/usagers/1458/localisations", "prefecture_rattachee": "/api/usagers/1458/prefecture_rattachee", "etat_civil_update": "/api/usagers/1458/etat_civil", "self": "/api/usagers/1458", "parent": "/api/usagers" }, "date_naissance": "1979-01-10T00:00:00+00:00", "_created": "2016-06-06T11:18:33.530216+00:00", "localisation": { "date_maj": "2016-06-06T11:18:33.529280+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "langues_audition_OFPRA": [ { "libelle": "FRANCAIS", "code": "FRE" } ], "nom": "Ellop", "_version": 2, "id": "1458", "_updated": "2016-06-06T11:18:33.532635+00:00", "prenoms": [ "Oli" ], "transferable": true, "langues": [ { "libelle": "français", "code": "fre" } ], "date_enregistrement_agdref": "2016-06-06T13:23:49+00:00", "origine_nom": "EUROPE", "photo": { "id": "57555b7adc105724ca7d2687", "_links": { "name": "2875206.png", "self": "/api/fichiers/57555b7adc105724ca7d2687", "data": "/api/fichiers/57555b7adc105724ca7d2687/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjU3NTU1YjdhZGMxMDU3MjRjYTdkMjY4NyIsImV4cCI6MTQ2NTI5MTExMy42MDk3NjYsInR5cGUiOiJmaWNoaWVyIn0.4MmYKTUeyP7tOLrbCLwTZLQoDB0pixoO93HjiPfU2cs" } }, "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "ville_naissance": "dd" } },
                "usager_2": {},
                "recueil_da": { "id": "1807", "date_enregistrement": "2016-06-06T11:18:33.517110+00:00", "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "date_transmission": "2016-06-06T11:17:31.745000+00:00", "statut": "EXPLOITE", "enfants": [ { "usager_2": false, "ecv_valide": false, "_created": "2016-06-06T11:18:33.564664+00:00", "_cls": "UsagerEnfantRecueil", "nom": "Ellop", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "date_naissance": "1992-08-15T00:00:00+00:00", "date_enregistrement_agdref": "2016-06-06T13:23:49+00:00", "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "_version": 2, "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "identifiant_pere": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "sexe": "M", "_links": { "localisation_update": "/api/usagers/1459/localisations", "update": "/api/usagers/1459", "localisations": "/api/usagers/1459/localisations", "prefecture_rattachee": "/api/usagers/1459/prefecture_rattachee", "etat_civil_update": "/api/usagers/1459/etat_civil", "self": "/api/usagers/1459", "parent": "/api/usagers" }, "_updated": "2016-06-06T11:18:33.566875+00:00", "usager_1": true, "localisation": { "date_maj": "2016-06-06T11:18:33.563541+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "present_au_moment_de_la_demande": true, "id": "1459", "usager_existant": { "id": 1459, "_links": { "self": "/api/usagers/1459" } }, "prenoms": [ "Ran" ], "transferable": true, "demandeur": true, "ville_naissance": "dd" } ], "agent_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "structure_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_links": { "self": "/api/recueils_da/1807", "parent": "/api/recueils_da" }, "_updated": "2016-06-06T11:18:33.628979+00:00", "usager_1": { "date_entree_en_france": "2015-07-17T00:00:00+00:00", "demande_asile_resultante": { "id": 1206, "_links": { "self": "/api/demandes_asile/1206" } }, "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "ecv_valide": false, "_updated": "2016-06-06T11:18:33.532635+00:00", "_created": "2016-06-06T11:18:33.530216+00:00", "_cls": "UsagerPrincipalRecueil", "langues_audition_OFPRA": [ { "libelle": "FRANCAIS", "code": "FRE" } ], "nom": "Ellop", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "sexe": "M", "motif_qualification_procedure": "PNOR", "date_enregistrement_agdref": "2016-06-06T13:23:49+00:00", "transferable": true, "visa": "C", "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "_version": 2, "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "conditions_exceptionnelles_accueil": false, "date_depart": "2015-07-17T00:00:00+00:00", "identifiant_portail_agdref": "hO3iHZU1ZGi6", "decision_sur_attestation": true, "identifiant_agdref": "7503002801", "_links": { "localisation_update": "/api/usagers/1458/localisations", "update": "/api/usagers/1458", "localisations": "/api/usagers/1458/localisations", "prefecture_rattachee": "/api/usagers/1458/prefecture_rattachee", "etat_civil_update": "/api/usagers/1458/etat_civil", "self": "/api/usagers/1458", "parent": "/api/usagers" }, "date_naissance": "1979-01-10T00:00:00+00:00", "date_decision_sur_attestation": "2016-06-06T00:00:00+00:00", "localisation": { "date_maj": "2016-06-06T11:18:33.529280+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "condition_entree_france": "REGULIERE", "present_au_moment_de_la_demande": true, "id": "1458", "usager_existant": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "prenoms": [ "Oli" ], "indicateur_visa_long_sejour": false, "langues": [ { "libelle": "français", "code": "fre" } ], "origine_nom": "EUROPE", "demandeur": true, "photo": { "id": "57555b7adc105724ca7d2687", "_links": { "name": "2875206.png", "self": "/api/fichiers/57555b7adc105724ca7d2687", "data": "/api/fichiers/57555b7adc105724ca7d2687/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjU3NTU1YjdhZGMxMDU3MjRjYTdkMjY4NyIsImV4cCI6MTQ2NTI5MTExMy43MDEwNTksInR5cGUiOiJmaWNoaWVyIn0.4OtF7z8h6mT7DPljf99xfz5dMYmTu4YT94Ib5w1a9Gg" } }, "type_procedure": "NORMALE", "ville_naissance": "dd" }, "profil_demande": "FAMILLE", "_created": "2016-06-06T11:17:31.737000+00:00", "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_version": 8 }
            }""",
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_enfant_majeur_non_demandeur_exploite(self, site_structure_accueil, pa_realise, user,
                                                                                payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService" >
            <soapenv:Header/>
            <soapenv:Body>
            <ns1:getDonneePortail>
                <DEMANDES>
                    <DEMANDE>
                        <ADRESSE><CODE_POSTAL>75011</CODE_POSTAL><LIBELLE_VOIE>Avenue Parmentier</LIBELLE_VOIE><NUMERO_VOIE>1</NUMERO_VOIE><ADRESSE2></ADRESSE2><VILLE>Paris</VILLE><NUM_DOMICILIATION>1</NUM_DOMICILIATION><CODE_INSEE>75111</CODE_INSEE></ADRESSE>
                        <INDIVIDUS>
                            <INDIVIDU>
                                <ID_DEMANDE_ASILE>1206</ID_DEMANDE_ASILE>
                                <DATE_AGDREF>2016-06-06</DATE_AGDREF>
                                <ADULTE>
                                    <MATRIMONIAL>Célibataire</MATRIMONIAL>
                                    <PROCEDURE_TYPE>En procédure normale</PROCEDURE_TYPE>
                                    <NOM_NAISSANCE>ELLOP</NOM_NAISSANCE>
                                    <PRENOM>OLI</PRENOM>
                                    <LIEU_NAISSANCE>dd, REPUBLIQUE DEMO. DU CONGO</LIEU_NAISSANCE>
                                    <SEXE>M</SEXE>
                                    <URL_PHOTO>/api/fichiers/57555b7adc105724ca7d2687/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjU3NTU1YjdhZGMxMDU3MjRjYTdkMjY4NyIsImV4cCI6MTQ2NTI5MTExMy42MDk3NjYsInR5cGUiOiJmaWNoaWVyIn0.4MmYKTUeyP7tOLrbCLwTZLQoDB0pixoO93HjiPfU2cs</URL_PHOTO>
                                    <TYPE>Demandeur principal</TYPE>
                                    <INSEE_PAYS_NATIONALITE>356</INSEE_PAYS_NATIONALITE>
                                    <DATE_NAISSANCE>1979-01-10</DATE_NAISSANCE>
                                    <LANGUE1>34</LANGUE1>
                                </ADULTE>
                                <CONDITION_ENTREE_FRANCE>N</CONDITION_ENTREE_FRANCE>
                                <ID_USAGER_PORTAIL>1458</ID_USAGER_PORTAIL>
                                <ID_AGDREF>7503002801</ID_AGDREF>
                            </INDIVIDU>
                        </INDIVIDUS>
                        <PROCEDURE_STATUT>1</PROCEDURE_STATUT>
                        <SITES>
                            <SITE>
                                <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                                <ADRESSE>
                                    <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                                    <VILLE>Bordeaux</VILLE>
                                    <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                                    <CODE_POSTAL>33000</CODE_POSTAL>
                                    <NUMERO_VOIE>3</NUMERO_VOIE>
                                    <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                                    <CODE_INSEE>33000</CODE_INSEE>
                                </ADRESSE>
                                <TYPE_SITE>SPA</TYPE_SITE>
                                <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
                            </SITE>
                        </SITES>
                        <DATE_PREF>2016-06-06</DATE_PREF>
                        <ID_RECUEIL_DEMANDE>1807</ID_RECUEIL_DEMANDE>
                        <AGENT_PREF>5603fe39000c672118021314</AGENT_PREF>
                        <DATE_CREATION_DEMANDE>2016-06-06</DATE_CREATION_DEMANDE>
                    </DEMANDE>
                </DEMANDES>
            </ns1:getDonneePortail>
            </soapenv:Body>
            </soapenv:Envelope>""".format(site=site_structure_accueil.pk)

            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context=""" {
                "enfants": [ { "usager": { "id": "1459", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "_updated": "2016-06-06T11:18:33.566875+00:00", "prenoms": [ "Ran" ], "transferable": true, "ecv_valide": false, "_links": { "localisation_update": "/api/usagers/1459/localisations", "update": "/api/usagers/1459", "localisations": "/api/usagers/1459/localisations", "prefecture_rattachee": "/api/usagers/1459/prefecture_rattachee", "etat_civil_update": "/api/usagers/1459/etat_civil", "self": "/api/usagers/1459", "parent": "/api/usagers" }, "date_naissance": "1992-08-15T00:00:00+00:00", "_created": "2016-06-06T11:18:33.564664+00:00", "ville_naissance": "dd", "sexe": "M", "localisation": { "date_maj": "2016-06-06T11:18:33.563541+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "nom": "Ellop", "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "identifiant_pere": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "_version": 2 } } ],
                "usager_1": { "demande_asile": { "conditions_exceptionnelles_accueil": false, "structure_premier_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "date_depart": "2015-07-17T00:00:00+00:00", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "decision_sur_attestation": true, "date_decision_sur_attestation": "2016-06-06T00:00:00+00:00", "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_links": { "editer_attestation": "/api/demandes_asile/1206/attestations", "self": "/api/demandes_asile/1206", "orienter": "/api/demandes_asile/1206/orientation", "parent": "/api/demandes_asile" }, "_updated": "2016-06-06T11:18:33.588514+00:00", "_created": "2016-06-06T11:18:33.586416+00:00", "recueil_da_origine": { "id": 1807, "_links": { "self": "/api/recueils_da/1807" } }, "usager": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "condition_entree_france": "REGULIERE", "referent_premier_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "id": "1206", "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "procedure": { "acteur": "GUICHET_UNIQUE", "type": "NORMALE", "motif_qualification": "PNOR" }, "indicateur_visa_long_sejour": false, "renouvellement_attestation": 1, "statut": "PRETE_EDITION_ATTESTATION", "type_demandeur": "PRINCIPAL", "enfants_presents_au_moment_de_la_demande": [ { "id": 1459, "_links": { "self": "/api/usagers/1459" } } ], "date_enregistrement": "2016-06-06T11:18:33.517110+00:00", "visa": "C", "_version": 2, "date_demande": "2016-06-06T11:17:31.745000+00:00" }, "usager": { "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "sexe": "M", "ecv_valide": false, "identifiant_portail_agdref": "hO3iHZU1ZGi6", "identifiant_agdref": "7503002801", "_links": { "localisation_update": "/api/usagers/1458/localisations", "update": "/api/usagers/1458", "localisations": "/api/usagers/1458/localisations", "prefecture_rattachee": "/api/usagers/1458/prefecture_rattachee", "etat_civil_update": "/api/usagers/1458/etat_civil", "self": "/api/usagers/1458", "parent": "/api/usagers" }, "date_naissance": "1979-01-10T00:00:00+00:00", "_created": "2016-06-06T11:18:33.530216+00:00", "localisation": { "date_maj": "2016-06-06T11:18:33.529280+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "langues_audition_OFPRA": [ { "libelle": "FRANCAIS", "code": "FRE" } ], "nom": "Ellop", "_version": 2, "id": "1458", "_updated": "2016-06-06T11:18:33.532635+00:00", "prenoms": [ "Oli" ], "transferable": true, "langues": [ { "libelle": "français", "code": "fre" } ], "date_enregistrement_agdref": "2016-06-06T13:23:49+00:00", "origine_nom": "EUROPE", "photo": { "id": "57555b7adc105724ca7d2687", "_links": { "name": "2875206.png", "self": "/api/fichiers/57555b7adc105724ca7d2687", "data": "/api/fichiers/57555b7adc105724ca7d2687/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjU3NTU1YjdhZGMxMDU3MjRjYTdkMjY4NyIsImV4cCI6MTQ2NTI5MTExMy42MDk3NjYsInR5cGUiOiJmaWNoaWVyIn0.4MmYKTUeyP7tOLrbCLwTZLQoDB0pixoO93HjiPfU2cs" } }, "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "ville_naissance": "dd" } },
                "usager_2": {},
                "recueil_da": { "id": "1807", "date_enregistrement": "2016-06-06T11:18:33.517110+00:00", "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "date_transmission": "2016-06-06T11:17:31.745000+00:00", "statut": "EXPLOITE", "enfants": [ { "usager_2": false, "ecv_valide": false, "_created": "2016-06-06T11:18:33.564664+00:00", "_cls": "UsagerEnfantRecueil", "nom": "Ellop", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "date_naissance": "1992-08-15T00:00:00+00:00", "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "_version": 2, "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "identifiant_pere": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "sexe": "M", "_links": { "localisation_update": "/api/usagers/1459/localisations", "update": "/api/usagers/1459", "localisations": "/api/usagers/1459/localisations", "prefecture_rattachee": "/api/usagers/1459/prefecture_rattachee", "etat_civil_update": "/api/usagers/1459/etat_civil", "self": "/api/usagers/1459", "parent": "/api/usagers" }, "_updated": "2016-06-06T11:18:33.566875+00:00", "usager_1": true, "localisation": { "date_maj": "2016-06-06T11:18:33.563541+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "present_au_moment_de_la_demande": true, "id": "1459", "usager_existant": { "id": 1459, "_links": { "self": "/api/usagers/1459" } }, "prenoms": [ "Ran" ], "transferable": true, "demandeur": false, "ville_naissance": "dd" } ], "agent_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "structure_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_links": { "self": "/api/recueils_da/1807", "parent": "/api/recueils_da" }, "_updated": "2016-06-06T11:18:33.628979+00:00", "usager_1": { "date_entree_en_france": "2015-07-17T00:00:00+00:00", "demande_asile_resultante": { "id": 1206, "_links": { "self": "/api/demandes_asile/1206" } }, "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "ecv_valide": false, "_updated": "2016-06-06T11:18:33.532635+00:00", "_created": "2016-06-06T11:18:33.530216+00:00", "_cls": "UsagerPrincipalRecueil", "langues_audition_OFPRA": [ { "libelle": "FRANCAIS", "code": "FRE" } ], "nom": "Ellop", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "sexe": "M", "motif_qualification_procedure": "PNOR", "date_enregistrement_agdref": "2016-06-06T13:23:49+00:00", "transferable": true, "visa": "C", "nationalites": [ { "libelle": "congolaise (rdc)", "code": "COD" } ], "situation_familiale": "CELIBATAIRE", "_version": 2, "pays_naissance": { "libelle": "REPUBLIQUE DEMO. DU CONGO", "code": "COD" }, "conditions_exceptionnelles_accueil": false, "date_depart": "2015-07-17T00:00:00+00:00", "identifiant_portail_agdref": "hO3iHZU1ZGi6", "decision_sur_attestation": true, "identifiant_agdref": "7503002801", "_links": { "localisation_update": "/api/usagers/1458/localisations", "update": "/api/usagers/1458", "localisations": "/api/usagers/1458/localisations", "prefecture_rattachee": "/api/usagers/1458/prefecture_rattachee", "etat_civil_update": "/api/usagers/1458/etat_civil", "self": "/api/usagers/1458", "parent": "/api/usagers" }, "date_naissance": "1979-01-10T00:00:00+00:00", "date_decision_sur_attestation": "2016-06-06T00:00:00+00:00", "localisation": { "date_maj": "2016-06-06T11:18:33.529280+00:00", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "numero_voie": "1", "complement": "", "adresse_inconnue": false, "longlat": [ 2.379496, 48.858814 ], "code_postal": "75011", "identifiant_ban": "ADRNIVX_0000000270770411", "chez": "", "voie": "Avenue Parmentier", "ville": "Paris", "code_insee": "75111" }, "organisme_origine": "PORTAIL" }, "condition_entree_france": "REGULIERE", "present_au_moment_de_la_demande": true, "id": "1458", "usager_existant": { "id": 1458, "_links": { "self": "/api/usagers/1458" } }, "prenoms": [ "Oli" ], "indicateur_visa_long_sejour": false, "langues": [ { "libelle": "français", "code": "fre" } ], "origine_nom": "EUROPE", "demandeur": true, "photo": { "id": "57555b7adc105724ca7d2687", "_links": { "name": "2875206.png", "self": "/api/fichiers/57555b7adc105724ca7d2687", "data": "/api/fichiers/57555b7adc105724ca7d2687/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpZCI6IjU3NTU1YjdhZGMxMDU3MjRjYTdkMjY4NyIsImV4cCI6MTQ2NTI5MTExMy43MDEwNTksInR5cGUiOiJmaWNoaWVyIn0.4OtF7z8h6mT7DPljf99xfz5dMYmTu4YT94Ib5w1a9Gg" } }, "type_procedure": "NORMALE", "ville_naissance": "dd" }, "profil_demande": "FAMILLE", "_created": "2016-06-06T11:17:31.737000+00:00", "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_version": 8 }
            }""",
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t428(self, site_structure_accueil, pa_realise, user,
                                                payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            # Do not check XML as it is noit the main goal of this test
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "usager_2": {}, "usager_1": { "usager": { "ville_naissance": "damas", "telephone": "01 54 87 54 87", "origine_nom": "EUROPE", "email": "t@test.com", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "_created": "2016-01-12T13:53:00.510203+00:00", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "situation_familiale": "CELIBATAIRE", "prenoms": [ "Rb" ], "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }, "_version": 2, "identifiant_portail_agdref": "tbC5ejKFhbl1", "id": "619", "identifiant_famille_dna": "193676", "date_naissance": "1988-12-26T00:00:00+00:00", "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" }, "sexe": "M", "nom": "Pop", "_links": { "update": "/api/usagers/619", "localisations": "/api/usagers/619/localisations", "prefecture_rattachee": "/api/usagers/619/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/619/etat_civil", "self": "/api/usagers/619", "localisation_update": "/api/usagers/619/localisations" }, "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE" }, "id": "5695042fdc10573e2b530a51" }, "ecv_valide": false, "identifiant_agdref": "7503002367", "langues": [ { "code": "ara", "libelle": "arabe" } ], "_updated": "2016-01-12T13:53:00.512797+00:00", "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "demande_asile": { "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" }, "usager": { "_links": { "self": "/api/usagers/619" }, "id": 619 }, "_links": { "editer_attestation": "/api/demandes_asile/548/attestations", "self": "/api/demandes_asile/548", "orienter": "/api/demandes_asile/548/orientation", "parent": "/api/demandes_asile" }, "enfants_presents_au_moment_de_la_demande": [ { "_links": { "self": "/api/usagers/620" }, "id": 620 } ], "statut": "PRETE_EDITION_ATTESTATION", "renouvellement_attestation": 1, "_created": "2016-01-12T13:53:00.598737+00:00", "indicateur_visa_long_sejour": false, "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 }, "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "date_demande": "2016-01-12T13:50:45.945000+00:00", "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "type_demandeur": "PRINCIPAL", "_version": 2, "date_depart": "2015-07-17T00:00:00+00:00", "date_enregistrement": "2016-01-12T13:53:00.494490+00:00", "id": "548", "visa": "C", "decision_sur_attestation": true, "_updated": "2016-01-12T13:53:00.601390+00:00", "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" } } }, "recueil_da": { "identifiant_famille_dna": "193676", "_updated": "2016-01-12T13:53:00.640771+00:00", "statut": "EXPLOITE", "usager_1": { "ville_naissance": "damas", "type_procedure": "NORMALE", "telephone": "01 54 87 54 87", "origine_nom": "EUROPE", "email": "t@test.com", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "_cls": "UsagerPrincipalRecueil", "visa": "C", "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "indicateur_visa_long_sejour": false, "situation_familiale": "CELIBATAIRE", "prenoms": [ "Rb" ], "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/548" }, "id": 548 }, "identifiant_portail_agdref": "tbC5ejKFhbl1", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "demandeur": true, "date_naissance": "1988-12-26T00:00:00+00:00", "motif_qualification_procedure": "PNOR", "sexe": "M", "nom": "Pop", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "present_au_moment_de_la_demande": true, "date_depart": "2015-07-17T00:00:00+00:00", "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDExMiwiaWQiOiI1Njk1MDQyZmRjMTA1NzNlMmI1MzBhNTEifQ.JAw2IgBr6SQAmnJ-UODDY3zaEGG4gf2WNZ-wBpITNTw" }, "id": "5695042fdc10573e2b530a51" }, "usager_existant": { "_links": { "self": "/api/usagers/619" }, "id": 619 }, "identifiant_agdref": "7503002367", "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "decision_sur_attestation": true, "langues": [ { "code": "ara", "libelle": "arabe" } ], "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "_created": "2016-01-12T13:50:45.938000+00:00", "profil_demande": "MINEUR_ACCOMPAGNANT", "_links": { "self": "/api/recueils_da/881", "parent": "/api/recueils_da" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "enfants": [ { "ville_naissance": "damas", "type_procedure": "NORMALE", "telephone": "01 54 87 95 45", "usager_existant": { "_links": { "self": "/api/usagers/620" }, "id": 620 }, "origine_nom": "EUROPE", "date_depart": "2015-07-17T00:00:00+00:00", "identifiant_agdref": "7503002368", "_cls": "UsagerEnfantRecueil", "visa": "AUCUN", "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "indicateur_visa_long_sejour": false, "situation_familiale": "CELIBATAIRE", "prenoms": [ "Bob" ], "representant_legal_nom": "Pop", "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/547" }, "id": 547 }, "identifiant_portail_agdref": "JKYcYjxpCszc", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "email": "j@test.com", "demandeur": true, "date_naissance": "2010-02-03T00:00:00+00:00", "usager_1": true, "motif_qualification_procedure": "PNOR", "sexe": "M", "nom": "Pop", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "present_au_moment_de_la_demande": true, "photo": { "_links": { "name": "image_preview.png", "self": "/api/fichiers/5695048bdc10573e23edb204", "data": "/api/fichiers/5695048bdc10573e23edb204/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDUwNTksImlkIjoiNTY5NTA0OGJkYzEwNTczZTIzZWRiMjA0In0.4oPwKnb-Wfa8T844uTGf01s-v4ewkliAvtB0A8pU0oU" }, "id": "5695048bdc10573e23edb204" }, "representant_legal_prenom": "Rb", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "decision_sur_attestation": true, "langues": [ { "code": "ara", "libelle": "arabe" } ], "representant_legal_personne_morale": false, "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } } ], "id": "881", "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "date_enregistrement": "2016-01-12T13:53:00.494490+00:00", "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "_version": 10, "date_transmission": "2016-01-12T13:50:45.945000+00:00" }, "enfants": [ { "usager": { "ville_naissance": "damas", "representant_legal_nom": "Pop", "origine_nom": "EUROPE", "identifiant_agdref": "7503002368", "id": "620", "_created": "2016-01-12T13:53:00.546584+00:00", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "situation_familiale": "CELIBATAIRE", "prenoms": [ "Bob" ], "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }, "telephone": "01 54 87 95 45", "_version": 2, "identifiant_portail_agdref": "JKYcYjxpCszc", "identifiant_pere": { "_links": { "self": "/api/usagers/619" }, "id": 619 }, "email": "j@test.com", "identifiant_famille_dna": "193676", "date_naissance": "2010-02-03T00:00:00+00:00", "ecv_valide": false, "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.545886+00:00" }, "sexe": "M", "nom": "Pop", "_links": { "update": "/api/usagers/620", "localisations": "/api/usagers/620/localisations", "prefecture_rattachee": "/api/usagers/620/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/620/etat_civil", "self": "/api/usagers/620", "localisation_update": "/api/usagers/620/localisations" }, "photo": { "_links": { "name": "image_preview.png", "self": "/api/fichiers/5695048bdc10573e23edb204", "data": "/api/fichiers/5695048bdc10573e23edb204/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MzEwNzEsImlkIjoiNTY5NTA0OGJkYzEwNTczZTIzZWRiMjA0In0.mzZknLjxTVTvsnT_Ce0sKs2gu17WaRPYOO5x_xBqCTs" }, "id": "5695048bdc10573e23edb204" }, "representant_legal_prenom": "Rb", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "langues": [ { "code": "ara", "libelle": "arabe" } ], "_updated": "2016-01-12T13:53:00.549606+00:00", "representant_legal_personne_morale": false, "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "demande_asile": { "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" }, "usager": { "_links": { "self": "/api/usagers/620" }, "id": 620 }, "_links": { "editer_attestation": "/api/demandes_asile/547/attestations", "self": "/api/demandes_asile/547", "orienter": "/api/demandes_asile/547/orientation", "parent": "/api/demandes_asile" }, "statut": "PRETE_EDITION_ATTESTATION", "renouvellement_attestation": 1, "_created": "2016-01-12T13:53:00.576972+00:00", "indicateur_visa_long_sejour": false, "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 }, "visa": "AUCUN", "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "date_demande": "2016-01-12T13:50:45.945000+00:00", "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "type_demandeur": "PRINCIPAL", "_version": 2, "date_depart": "2015-07-17T00:00:00+00:00", "date_enregistrement": "2016-01-12T13:53:00.494490+00:00", "id": "547", "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "decision_sur_attestation": true, "_updated": "2016-01-12T13:53:00.579597+00:00", "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" } } } ] }
            """,
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t428_2(self, site_structure_accueil, pa_realise, user,
                                                  payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            # Do not check XML as it is noit the main goal of this test
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "usager_2": {}, "usager_1": { "usager": { "ville_naissance": "damas", "telephone": "01 54 87 54 87", "origine_nom": "EUROPE", "email": "t@test.com", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "_created": "2016-01-12T13:53:00.510203+00:00", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "situation_familiale": "CELIBATAIRE", "prenoms": [ "Rb" ], "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }, "_version": 2, "identifiant_portail_agdref": "tbC5ejKFhbl1", "id": "619", "identifiant_famille_dna": "193676", "date_naissance": "1988-12-26T00:00:00+00:00", "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" }, "sexe": "M", "nom": "Pop", "_links": { "update": "/api/usagers/619", "localisations": "/api/usagers/619/localisations", "prefecture_rattachee": "/api/usagers/619/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/619/etat_civil", "self": "/api/usagers/619", "localisation_update": "/api/usagers/619/localisations" }, "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE" }, "id": "5695042fdc10573e2b530a51" }, "ecv_valide": false, "identifiant_agdref": "7503002367", "langues": [ { "code": "ara", "libelle": "arabe" } ], "_updated": "2016-01-12T13:53:00.512797+00:00", "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "demande_asile": { "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" }, "usager": { "_links": { "self": "/api/usagers/619" }, "id": 619 }, "_links": { "editer_attestation": "/api/demandes_asile/548/attestations", "self": "/api/demandes_asile/548", "orienter": "/api/demandes_asile/548/orientation", "parent": "/api/demandes_asile" }, "enfants_presents_au_moment_de_la_demande": [ { "_links": { "self": "/api/usagers/620" }, "id": 620 } ], "statut": "PRETE_EDITION_ATTESTATION", "renouvellement_attestation": 1, "_created": "2016-01-12T13:53:00.598737+00:00", "indicateur_visa_long_sejour": false, "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 }, "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "date_demande": "2016-01-12T13:50:45.945000+00:00", "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "type_demandeur": "PRINCIPAL", "_version": 2, "date_depart": "2015-07-17T00:00:00+00:00", "date_enregistrement": "2016-01-12T13:53:00.494490+00:00", "id": "548", "visa": "C", "decision_sur_attestation": true, "_updated": "2016-01-12T13:53:00.601390+00:00", "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" } } }, "recueil_da": { "identifiant_famille_dna": "193676", "_updated": "2016-01-12T13:53:00.640771+00:00", "statut": "EXPLOITE", "usager_1": { "ville_naissance": "damas", "type_procedure": "NORMALE", "telephone": "01 54 87 54 87", "origine_nom": "EUROPE", "email": "t@test.com", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "_cls": "UsagerPrincipalRecueil", "visa": "C", "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "indicateur_visa_long_sejour": false, "situation_familiale": "CELIBATAIRE", "prenoms": [ "Rb" ], "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/548" }, "id": 548 }, "identifiant_portail_agdref": "tbC5ejKFhbl1", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "demandeur": true, "date_naissance": "1988-12-26T00:00:00+00:00", "motif_qualification_procedure": "PNOR", "sexe": "M", "nom": "Pop", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "present_au_moment_de_la_demande": true, "date_depart": "2015-07-17T00:00:00+00:00", "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDExMiwiaWQiOiI1Njk1MDQyZmRjMTA1NzNlMmI1MzBhNTEifQ.JAw2IgBr6SQAmnJ-UODDY3zaEGG4gf2WNZ-wBpITNTw" }, "id": "5695042fdc10573e2b530a51" }, "usager_existant": { "_links": { "self": "/api/usagers/619" }, "id": 619 }, "identifiant_agdref": "7503002367", "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "decision_sur_attestation": true, "langues": [ { "code": "ara", "libelle": "arabe" } ], "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "_created": "2016-01-12T13:50:45.938000+00:00", "profil_demande": "MINEUR_ACCOMPAGNANT", "_links": { "self": "/api/recueils_da/881", "parent": "/api/recueils_da" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "enfants": [ { "ville_naissance": "damas", "type_procedure": "NORMALE", "telephone": "01 54 87 95 45", "usager_existant": { "_links": { "self": "/api/usagers/620" }, "id": 620 }, "origine_nom": "EUROPE", "date_depart": "2015-07-17T00:00:00+00:00", "identifiant_agdref": "7503002368", "_cls": "UsagerEnfantRecueil", "visa": "AUCUN", "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "indicateur_visa_long_sejour": false, "situation_familiale": "CELIBATAIRE", "prenoms": [ "Bob" ], "representant_legal_nom": "Pop", "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/547" }, "id": 547 }, "identifiant_portail_agdref": "JKYcYjxpCszc", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "email": "j@test.com", "demandeur": true, "date_naissance": "2010-02-03T00:00:00+00:00", "usager_1": true, "motif_qualification_procedure": "PNOR", "sexe": "M", "nom": "Pop", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "present_au_moment_de_la_demande": true, "photo": { "_links": { "name": "image_preview.png", "self": "/api/fichiers/5695048bdc10573e23edb204", "data": "/api/fichiers/5695048bdc10573e23edb204/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDUwNTksImlkIjoiNTY5NTA0OGJkYzEwNTczZTIzZWRiMjA0In0.4oPwKnb-Wfa8T844uTGf01s-v4ewkliAvtB0A8pU0oU" }, "id": "5695048bdc10573e23edb204" }, "representant_legal_prenom": "Rb", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "decision_sur_attestation": true, "langues": [ { "code": "ara", "libelle": "arabe" } ], "representant_legal_personne_morale": false, "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } } ], "id": "881", "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "date_enregistrement": "2016-01-12T13:53:00.494490+00:00", "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "_version": 10, "date_transmission": "2016-01-12T13:50:45.945000+00:00" }, "enfants": [ { "usager": { "ville_naissance": "damas", "representant_legal_nom": "Pop", "origine_nom": "EUROPE", "identifiant_agdref": "7503002368", "id": "620", "_created": "2016-01-12T13:53:00.546584+00:00", "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "situation_familiale": "CELIBATAIRE", "prenoms": [ "Bob" ], "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }, "telephone": "01 54 87 95 45", "_version": 2, "identifiant_portail_agdref": "JKYcYjxpCszc", "identifiant_pere": { "_links": { "self": "/api/usagers/619" }, "id": 619 }, "email": "j@test.com", "identifiant_famille_dna": "193676", "date_naissance": "2010-02-03T00:00:00+00:00", "ecv_valide": false, "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.545886+00:00" }, "sexe": "M", "nom": "Pop", "_links": { "update": "/api/usagers/620", "localisations": "/api/usagers/620/localisations", "prefecture_rattachee": "/api/usagers/620/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/620/etat_civil", "self": "/api/usagers/620", "localisation_update": "/api/usagers/620/localisations" }, "photo": { "_links": { "name": "image_preview.png", "self": "/api/fichiers/5695048bdc10573e23edb204", "data": "/api/fichiers/5695048bdc10573e23edb204/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MzEwNzEsImlkIjoiNTY5NTA0OGJkYzEwNTczZTIzZWRiMjA0In0.mzZknLjxTVTvsnT_Ce0sKs2gu17WaRPYOO5x_xBqCTs" }, "id": "5695048bdc10573e23edb204" }, "representant_legal_prenom": "Rb", "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "langues": [ { "code": "ara", "libelle": "arabe" } ], "_updated": "2016-01-12T13:53:00.549606+00:00", "representant_legal_personne_morale": false, "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00", "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "demande_asile": { "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" }, "usager": { "_links": { "self": "/api/usagers/620" }, "id": 620 }, "_links": { "editer_attestation": "/api/demandes_asile/547/attestations", "self": "/api/demandes_asile/547", "orienter": "/api/demandes_asile/547/orientation", "parent": "/api/demandes_asile" }, "statut": "PRETE_EDITION_ATTESTATION", "renouvellement_attestation": 1, "_created": "2016-01-12T13:53:00.576972+00:00", "indicateur_visa_long_sejour": false, "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 }, "visa": "AUCUN", "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "date_demande": "2016-01-12T13:50:45.945000+00:00", "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "type_demandeur": "PRINCIPAL", "_version": 2, "date_depart": "2015-07-17T00:00:00+00:00", "date_enregistrement": "2016-01-12T13:53:00.494490+00:00", "id": "547", "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "decision_sur_attestation": true, "_updated": "2016-01-12T13:53:00.579597+00:00", "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" } } } ] }
            """,
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t428_3(self, site_structure_accueil, pa_realise, user,
                                                  payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            # Do not check XML as it is noit the main goal of this test
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "recueil_da": { "usager_2": { "nationalites": [ { "libelle": "soudanaise", "code": "SDN" } ], "sexe": "M", "pays_naissance": { "libelle": "SOUDAN", "code": "SDN" }, "date_naissance": "1979-01-02T00:00:00+00:00", "nom": "SOUDANI", "prenoms": [ "RAED" ], "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "code_postal": "75012", "ville": "Paris", "voie": "Avenue Daumesnil", "numero_voie": "1", "code_insee": "75112", "adresse_inconnue": false, "complement": "", "identifiant_ban": "ADRNIVX_0000000270788337", "longlat": [ 2.372098, 48.849148 ], "chez": "" }, "_cls": "UsagerSecondaireRecueil", "present_au_moment_de_la_demande": true, "identifiant_agdref": "7503002435", "demandeur": false, "ville_naissance": "KHARTOUM", "identifiant_portail_agdref": "lh76tToyFKmZ" }, "date_transmission": "2016-02-03T09:23:24.468251+00:00", "_version": 2, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "_links": { "rendez_vous_reserver": "/api/recueils_da/949/rendez_vous", "identifier_demandeurs": "/api/recueils_da/949/demandeurs_identifies", "parent": "/api/recueils_da", "replace": "/api/recueils_da/949", "annuler": "/api/recueils_da/949/annule", "self": "/api/recueils_da/949" }, "id": "949", "usager_1": { "date_entree_en_france": "2015-07-15T00:00:00+00:00", "_cls": "UsagerPrincipalRecueil", "present_au_moment_de_la_demande": true, "usager": { "_version": 6, "sexe": "F", "localisation": { "date_maj": "2016-02-03T09:23:24.361000+00:00", "organisme_origine": "PORTAIL", "adresse": { "pays": { "libelle": "FRANCE", "code": "FRA" }, "code_postal": "75012", "ville": "Paris", "voie": "Avenue Daumesnil", "numero_voie": "1", "code_insee": "75112", "adresse_inconnue": false, "complement": "Bat", "identifiant_ban": "ADRNIVX_0000000270788337", "longlat": [ 2.372098, 48.849148 ], "chez": "FJT" } }, "nom": "Soudani", "situation_familiale": "MARIE", "_updated": "2016-02-03T09:23:24.362000+00:00", "_created": "2016-02-03T09:07:09.217000+00:00", "photo": { "_links": { "data": "/api/fichiers/56b1c393dc1057563daa7c72/data?signature=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1NDU3NDIwNC41MTcxMDQsImlkIjoiNTZiMWMzOTNkYzEwNTc1NjNkYWE3YzcyIn0.he5LYxdXCT02RsgumaHW5FIQ99-8zvZEHE8Mw4vkfVw", "name": "femme-russe.png", "self": "/api/fichiers/56b1c393dc1057563daa7c72" }, "id": "56b1c393dc1057563daa7c72" }, "ville_naissance": "Khartoum", "identifiant_famille_dna": "193749", "conjoint": { "_links": { "self": "/api/usagers/680" }, "id": 680 }, "langues_audition_OFPRA": [ { "libelle": "ARABE", "code": "ARA" } ], "_links": { "etat_civil_update": "/api/usagers/681/etat_civil", "update": "/api/usagers/681", "prefecture_rattachee": "/api/usagers/681/prefecture_rattachee", "parent": "/api/usagers", "localisations": "/api/usagers/681/localisations", "localisation_update": "/api/usagers/681/localisations", "self": "/api/usagers/681" }, "nationalites": [ { "libelle": "soudanaise", "code": "SDN" } ], "date_naissance": "1979-01-02T00:00:00+00:00", "ecv_valide": false, "id": "681", "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }, "langues": [ { "libelle": "arabe", "code": "ara" } ], "prenoms": [ "Nahli" ], "origine_nom": "ARABE", "pays_naissance": { "libelle": "SOUDAN", "code": "SDN" } }, "demandeur": true, "type_demande":"PREMIERE_DEMANDE_ASILE", "date_depart": "2015-07-15T00:00:00+00:00", "usager_existant": { "_links": { "self": "/api/usagers/681" }, "id": 681 } }, "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "profil_demande": "FAMILLE", "_created": "2016-02-03T09:23:24.462766+00:00", "statut": "PA_REALISE", "_updated": "2016-02-03T09:23:24.469843+00:00", "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" } } }
            """,
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t445_pa_realise(self, site_structure_accueil, pa_realise, user,
                                                           payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            assert kwargs['data']
            assert "Avenue Daumesnil" in kwargs['data'].decode()
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "recueil_da": { "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "statut": "PA_REALISE", "usager_1": { "ville_naissance": "Damas", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "telephone": "01 54 95 47 85", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "demandeur": true, "type_demande": "PREMIERE_DEMANDE_ASILE", "date_naissance": "1988-12-27T00:00:00+00:00", "email": "t@test.com", "present_au_moment_de_la_demande": true, "_cls": "UsagerPrincipalRecueil", "sexe": "M", "nom": "Test", "situation_familiale": "CELIBATAIRE", "prenoms": [ "Adresse" ], "date_depart": "2015-07-17T00:00:00+00:00", "photo": { "_links": { "name": "homme-russe.png", "self": "/api/fichiers/5695065ddc10573e3f5f09bc", "data": "/api/fichiers/5695065ddc10573e3f5f09bc/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTkxMC45NTU5NjksImlkIjoiNTY5NTA2NWRkYzEwNTczZTNmNWYwOWJjIn0.MV2kAAkKt8mqkJfGb_Ab9sg3v8F5i0NXZrazhJ7fVP0" }, "id": "5695065ddc10573e3f5f09bc" }, "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "langues": [ { "code": "ara", "libelle": "arabe" } ], "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "_created": "2016-01-12T13:58:30.911130+00:00", "_version": 2, "profil_demande": "ADULTE_ISOLE", "_links": { "replace": "/api/recueils_da/882", "identifier_demandeurs": "/api/recueils_da/882/demandeurs_identifies", "parent": "/api/recueils_da", "annuler": "/api/recueils_da/882/annule", "self": "/api/recueils_da/882", "rendez_vous_reserver": "/api/recueils_da/882/rendez_vous" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "date_transmission": "2016-01-12T13:58:30.916323+00:00", "id": "882", "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "_updated": "2016-01-12T13:58:30.917924+00:00" } }
            """,
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_code_postal_interdit(self, site_structure_accueil, pa_realise, user,
                                      payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        site_structure_accueil.adresse.code_insee = '97612 TEST'
        site_structure_accueil.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "recueil_da": { "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "statut": "PA_REALISE", "usager_1": { "ville_naissance": "Damas", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "telephone": "01 54 95 47 85", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "demandeur": true, "type_demande": "PREMIERE_DEMANDE_ASILE", "date_naissance": "1988-12-27T00:00:00+00:00", "email": "t@test.com", "present_au_moment_de_la_demande": true, "_cls": "UsagerPrincipalRecueil", "sexe": "M", "nom": "Test", "situation_familiale": "CELIBATAIRE", "prenoms": [ "Adresse" ], "date_depart": "2015-07-17T00:00:00+00:00", "photo": { "_links": { "name": "homme-russe.png", "self": "/api/fichiers/5695065ddc10573e3f5f09bc", "data": "/api/fichiers/5695065ddc10573e3f5f09bc/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTkxMC45NTU5NjksImlkIjoiNTY5NTA2NWRkYzEwNTczZTNmNWYwOWJjIn0.MV2kAAkKt8mqkJfGb_Ab9sg3v8F5i0NXZrazhJ7fVP0" }, "id": "5695065ddc10573e3f5f09bc" }, "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "langues": [ { "code": "ara", "libelle": "arabe" } ], "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "_created": "2016-01-12T13:58:30.911130+00:00", "_version": 2, "profil_demande": "ADULTE_ISOLE", "_links": { "replace": "/api/recueils_da/882", "identifier_demandeurs": "/api/recueils_da/882/demandeurs_identifies", "parent": "/api/recueils_da", "annuler": "/api/recueils_da/882/annule", "self": "/api/recueils_da/882", "rendez_vous_reserver": "/api/recueils_da/882/rendez_vous" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "date_transmission": "2016-01-12T13:58:30.916323+00:00", "id": "882", "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "_updated": "2016-01-12T13:58:30.917924+00:00" } }
            """,
            handler=handler.label
        )

        callbacks = [callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        from connector.dna.common import DoNotSendError
        assert dna_recuperer_donnees_portail(handler, msg) == 'Code insee non souhaité dans le DN@'
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t284_proc_enfant(self, site_structure_accueil, pa_realise, user,
                                                            payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            assert kwargs['data']
            assert "Avenue Daumesnil" in kwargs['data'].decode()
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "usager_2": {}, "enfants": [ { "usager": { "identifiant_pere": { "id": 760, "_links": { "self": "/api/usagers/760" } }, "pays_naissance": { "code": "COG", "libelle": "CONGO" }, "transferable": true, "sexe": "M", "photo": { "id": "56dd4c5cdc10573912533954", "_links": { "self": "/api/fichiers/56dd4c5cdc10573912533954", "data": "/api/fichiers/56dd4c5cdc10573912533954/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1NzQyNjUyNi4wMzIwNjMsImlkIjoiNTZkZDRjNWNkYzEwNTczOTEyNTMzOTU0In0.QPcAHtCVFZIgYEfekdoqCYv1LvFHfRY__PsiD6lOanY", "name": "femme-russe.png" } }, "ville_naissance": "inc", "langues_audition_OFPRA": [ { "code": "FRE", "libelle": "FRANCAIS" } ], "nom": "Hatey", "id": "761", "date_naissance": "1994-06-15T00:00:00+00:00", "telephone": "01 54 87 54 21", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "ecv_valide": false, "identifiant_portail_agdref": "5hCIvP9vncnr", "origine_nom": "EUROPE", "_created": "2016-03-07T09:42:05.940236+00:00", "identifiant_famille_dna": "193860", "prenoms": [ "Hozier" ], "nationalites": [ { "code": "COG", "libelle": "congolaise (brazza)" } ], "langues": [ { "code": "fre", "libelle": "français" } ], "localisation": { "organisme_origine": "PORTAIL", "date_maj": "2016-03-07T09:42:05.939600+00:00", "adresse": { "adresse_inconnue": true } }, "identifiant_agdref": "7503002577", "date_enregistrement_agdref": "2016-03-07T10:45:32+00:00", "_updated": "2016-03-07T09:42:05.943045+00:00", "_version": 2, "situation_familiale": "CELIBATAIRE", "_links": { "parent": "/api/usagers", "self": "/api/usagers/761", "etat_civil_update": "/api/usagers/761/etat_civil", "prefecture_rattachee": "/api/usagers/761/prefecture_rattachee", "localisations": "/api/usagers/761/localisations", "update": "/api/usagers/761", "localisation_update": "/api/usagers/761/localisations" } }, "demande_asile": { "usager": { "id": 761, "_links": { "self": "/api/usagers/761" } }, "date_depart": "2015-07-17T00:00:00+00:00", "indicateur_visa_long_sejour": false, "statut": "PRETE_EDITION_ATTESTATION", "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "id": "674", "renouvellement_attestation": 1, "date_demande": "2016-03-07T09:40:26.047000+00:00", "type_demandeur": "PRINCIPAL", "structure_premier_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_updated": "2016-03-07T09:42:05.971276+00:00", "visa": "AUCUN", "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_created": "2016-03-07T09:42:05.968243+00:00", "_links": { "parent": "/api/demandes_asile", "self": "/api/demandes_asile/674", "orienter": "/api/demandes_asile/674/orientation", "editer_attestation": "/api/demandes_asile/674/attestations" }, "date_enregistrement": "2016-03-07T09:42:05.881351+00:00", "referent_premier_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "recueil_da_origine": { "id": 1041, "_links": { "self": "/api/recueils_da/1041" } }, "procedure": { "type": "NORMALE", "motif_qualification": "PNOR", "acteur": "GUICHET_UNIQUE" }, "date_decision_sur_attestation": "2016-03-07T00:00:00+00:00", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "_version": 2, "decision_sur_attestation": true, "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } } } } ], "usager_1": { "usager": { "ecv_valide": false, "transferable": true, "sexe": "M", "photo": { "id": "56dd4c03dc10573903356216", "_links": { "self": "/api/fichiers/56dd4c03dc10573903356216", "data": "/api/fichiers/56dd4c03dc10573903356216/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1NzQyNjUyNi4wMDg5MjIsImlkIjoiNTZkZDRjMDNkYzEwNTczOTAzMzU2MjE2In0.eqJt0JTii5TXwunCjxDsQqQMDVSbB-wu75WAAqOVGN0", "name": "7503001898.png" } }, "ville_naissance": "inc", "langues_audition_OFPRA": [ { "code": "FRE", "libelle": "FRANCAIS" } ], "nom": "Hatey", "id": "760", "date_naissance": "1979-01-01T00:00:00+00:00", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "pays_naissance": { "code": "FRA", "libelle": "FRANCE" }, "identifiant_portail_agdref": "RjoZ7MrVmHU2", "origine_nom": "EUROPE", "_created": "2016-03-07T09:42:05.897886+00:00", "identifiant_famille_dna": "193860", "prenoms": [ "Josh" ], "email": "t@t.com", "nationalites": [ { "code": "COD", "libelle": "congolaise (rdc)" } ], "langues": [ { "code": "fre", "libelle": "français" } ], "localisation": { "organisme_origine": "PORTAIL", "date_maj": "2016-03-07T09:42:05.897054+00:00", "adresse": { "voie": "Avenue Daumesnil", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "adresse_inconnue": false, "code_postal": "75012", "ville": "Paris", "identifiant_ban": "ADRNIVX_0000000270788337", "longlat": [ 2.372098, 48.849148 ], "numero_voie": "1", "chez": "", "code_insee": "75112" } }, "identifiant_agdref": "7503002576", "date_enregistrement_agdref": "2016-03-07T10:45:31+00:00", "_updated": "2016-03-07T09:42:05.901508+00:00", "_version": 2, "situation_familiale": "CELIBATAIRE", "_links": { "parent": "/api/usagers", "self": "/api/usagers/760", "etat_civil_update": "/api/usagers/760/etat_civil", "prefecture_rattachee": "/api/usagers/760/prefecture_rattachee", "localisations": "/api/usagers/760/localisations", "update": "/api/usagers/760", "localisation_update": "/api/usagers/760/localisations" } }, "demande_asile": { "usager": { "id": 760, "_links": { "self": "/api/usagers/760" } }, "date_depart": "2015-07-10T00:00:00+00:00", "indicateur_visa_long_sejour": false, "statut": "PRETE_EDITION_ATTESTATION", "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "id": "675", "enfants_presents_au_moment_de_la_demande": [ { "id": 761, "_links": { "self": "/api/usagers/761" } } ], "renouvellement_attestation": 1, "date_demande": "2016-03-07T09:40:26.047000+00:00", "type_demandeur": "PRINCIPAL", "structure_premier_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_updated": "2016-03-07T09:42:05.993994+00:00", "visa": "AUCUN", "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "_created": "2016-03-07T09:42:05.991691+00:00", "_links": { "parent": "/api/demandes_asile", "self": "/api/demandes_asile/675", "orienter": "/api/demandes_asile/675/orientation", "editer_attestation": "/api/demandes_asile/675/attestations" }, "date_enregistrement": "2016-03-07T09:42:05.881351+00:00", "referent_premier_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "date_entree_en_france": "2015-07-10T00:00:00+00:00", "recueil_da_origine": { "id": 1041, "_links": { "self": "/api/recueils_da/1041" } }, "procedure": { "type": "NORMALE", "motif_qualification": "PNOR", "acteur": "GUICHET_UNIQUE" }, "date_decision_sur_attestation": "2016-03-07T00:00:00+00:00", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "_version": 2, "decision_sur_attestation": true, "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } } } }, "recueil_da": { "agent_accueil": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } }, "structure_guichet_unique": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "usager_1": { "date_depart": "2015-07-10T00:00:00+00:00", "pays_naissance": { "code": "FRA", "libelle": "FRANCE" }, "transferable": true, "sexe": "M", "photo": { "id": "56dd4c03dc10573903356216", "_links": { "self": "/api/fichiers/56dd4c03dc10573903356216", "data": "/api/fichiers/56dd4c03dc10573903356216/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1NzQyNjUyNi4xMjA4MDMsImlkIjoiNTZkZDRjMDNkYzEwNTczOTAzMzU2MjE2In0.HwlvGkrXhnsAOZTLZ-svtl_oRKqSuBS6JpIqd0MS-Aw", "name": "7503001898.png" } }, "adresse": { "voie": "Avenue Daumesnil", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "adresse_inconnue": false, "code_postal": "75012", "ville": "Paris", "identifiant_ban": "ADRNIVX_0000000270788337", "longlat": [ 2.372098, 48.849148 ], "numero_voie": "1", "chez": "", "code_insee": "75112" }, "langues_audition_OFPRA": [ { "code": "FRE", "libelle": "FRANCAIS" } ], "nom": "Hatey", "_created": "2016-03-07T09:42:05.897886+00:00", "demandeur": true, "ecv_valide": false, "date_entree_en_france": "2015-07-10T00:00:00+00:00", "visa": "AUCUN", "usager_existant": { "id": 760, "_links": { "self": "/api/usagers/760" } }, "identifiant_famille_dna": "193860", "prenoms": [ "Josh" ], "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "demande_asile_resultante": { "id": 675, "_links": { "self": "/api/demandes_asile/675" } }, "nationalites": [ { "code": "COD", "libelle": "congolaise (rdc)" } ], "localisation": { "organisme_origine": "PORTAIL", "date_maj": "2016-03-07T09:42:05.897054+00:00", "adresse": { "voie": "Avenue Daumesnil", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "adresse_inconnue": false, "code_postal": "75012", "ville": "Paris", "identifiant_ban": "ADRNIVX_0000000270788337", "longlat": [ 2.372098, 48.849148 ], "numero_voie": "1", "chez": "", "code_insee": "75112" } }, "identifiant_agdref": "7503002576", "date_enregistrement_agdref": "2016-03-07T10:45:31+00:00", "_updated": "2016-03-07T09:42:05.901508+00:00", "_version": 2, "situation_familiale": "CELIBATAIRE", "type_procedure": "NORMALE", "decision_sur_attestation": true, "_links": { "parent": "/api/usagers", "self": "/api/usagers/760", "etat_civil_update": "/api/usagers/760/etat_civil", "prefecture_rattachee": "/api/usagers/760/prefecture_rattachee", "localisations": "/api/usagers/760/localisations", "update": "/api/usagers/760", "localisation_update": "/api/usagers/760/localisations" }, "motif_qualification_procedure": "PNOR", "id": "760", "date_naissance": "1979-01-01T00:00:00+00:00", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "_cls": "UsagerPrincipalRecueil", "identifiant_portail_agdref": "RjoZ7MrVmHU2", "indicateur_visa_long_sejour": false, "email": "t@t.com", "origine_nom": "EUROPE", "langues": [ { "code": "fre", "libelle": "français" } ], "present_au_moment_de_la_demande": true, "date_decision_sur_attestation": "2016-03-07T00:00:00+00:00", "ville_naissance": "inc" }, "statut": "EXPLOITE", "profil_demande": "FAMILLE", "_links": { "parent": "/api/recueils_da", "self": "/api/recueils_da/1041" }, "identifiant_famille_dna": "193860", "date_enregistrement": "2016-03-07T09:42:05.881351+00:00", "_created": "2016-03-07T09:40:26.038000+00:00", "structure_accueil": { "id": "5603fdd1000c672120fdce01", "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" } }, "date_transmission": "2016-03-07T09:40:26.047000+00:00", "enfants": [ { "date_depart": "2015-07-17T00:00:00+00:00", "identifiant_pere": { "id": 760, "_links": { "self": "/api/usagers/760" } }, "pays_naissance": { "code": "COG", "libelle": "CONGO" }, "transferable": true, "sexe": "M", "photo": { "id": "56dd4c5cdc10573912533954", "_links": { "self": "/api/fichiers/56dd4c5cdc10573912533954", "data": "/api/fichiers/56dd4c5cdc10573912533954/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1NzQyNjUyNi4xMjU4MTIsImlkIjoiNTZkZDRjNWNkYzEwNTczOTEyNTMzOTU0In0.jU0R1pTvcxapq8wV-kg8lKqBqh9QiSPhg5Ed42eD5Gk", "name": "femme-russe.png" } }, "adresse": { "adresse_inconnue": true }, "langues_audition_OFPRA": [ { "code": "FRE", "libelle": "FRANCAIS" } ], "nom": "Hatey", "_created": "2016-03-07T09:42:05.940236+00:00", "demandeur": true, "ecv_valide": false, "visa": "AUCUN", "usager_existant": { "id": 761, "_links": { "self": "/api/usagers/761" } }, "identifiant_famille_dna": "193860", "prenoms": [ "Hozier" ], "condition_entree_france": "REGULIERE", "conditions_exceptionnelles_accueil": false, "demande_asile_resultante": { "id": 674, "_links": { "self": "/api/demandes_asile/674" } }, "nationalites": [ { "code": "COG", "libelle": "congolaise (brazza)" } ], "localisation": { "organisme_origine": "PORTAIL", "date_maj": "2016-03-07T09:42:05.939600+00:00", "adresse": { "adresse_inconnue": true } }, "identifiant_agdref": "7503002577", "date_enregistrement_agdref": "2016-03-07T10:45:32+00:00", "_updated": "2016-03-07T09:42:05.943045+00:00", "_version": 2, "situation_familiale": "CELIBATAIRE", "type_procedure": "NORMALE", "decision_sur_attestation": true, "_links": { "parent": "/api/usagers", "self": "/api/usagers/761", "etat_civil_update": "/api/usagers/761/etat_civil", "prefecture_rattachee": "/api/usagers/761/prefecture_rattachee", "localisations": "/api/usagers/761/localisations", "update": "/api/usagers/761", "localisation_update": "/api/usagers/761/localisations" }, "motif_qualification_procedure": "PNOR", "usager_1": true, "id": "761", "date_naissance": "1994-06-15T00:00:00+00:00", "telephone": "01 54 87 54 21", "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } }, "_cls": "UsagerEnfantRecueil", "identifiant_portail_agdref": "5hCIvP9vncnr", "indicateur_visa_long_sejour": false, "date_entree_en_france": "2015-07-17T00:00:00+00:00", "origine_nom": "EUROPE", "langues": [ { "code": "fre", "libelle": "français" } ], "present_au_moment_de_la_demande": true, "date_decision_sur_attestation": "2016-03-07T00:00:00+00:00", "ville_naissance": "inc" } ], "_updated": "2016-03-07T09:42:06.043738+00:00", "_version": 10, "id": "1041", "agent_enregistrement": { "id": "5603fe39000c672118021314", "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" } } } }
            """,
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t445_da_exploite(self, site_structure_accueil, pa_realise, user,
                                                            payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'
            assert kwargs['data']
            assert "Avenue Daumesnil" in kwargs['data'].decode()
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{ "recueil_da": { "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" }, "statut": "PA_REALISE", "usager_1": { "ville_naissance": "Damas", "date_entree_en_france": "2015-07-17T00:00:00+00:00", "telephone": "01 54 95 47 85", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "demandeur": true, "type_demande": "PREMIERE_DEMANDE_ASILE", "date_naissance": "1988-12-27T00:00:00+00:00", "email": "t@test.com", "present_au_moment_de_la_demande": true, "_cls": "UsagerPrincipalRecueil", "sexe": "M", "nom": "Test", "situation_familiale": "CELIBATAIRE", "prenoms": [ "Adresse" ], "date_depart": "2015-07-17T00:00:00+00:00", "photo": { "_links": { "name": "homme-russe.png", "self": "/api/fichiers/5695065ddc10573e3f5f09bc", "data": "/api/fichiers/5695065ddc10573e3f5f09bc/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTkxMC45NTU5NjksImlkIjoiNTY5NTA2NWRkYzEwNTczZTNmNWYwOWJjIn0.MV2kAAkKt8mqkJfGb_Ab9sg3v8F5i0NXZrazhJ7fVP0" }, "id": "5695065ddc10573e3f5f09bc" }, "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ], "langues": [ { "code": "ara", "libelle": "arabe" } ], "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ], "pays_naissance": { "code": "SYR", "libelle": "SYRIE" } }, "_created": "2016-01-12T13:58:30.911130+00:00", "_version": 2, "profil_demande": "ADULTE_ISOLE", "_links": { "replace": "/api/recueils_da/882", "identifier_demandeurs": "/api/recueils_da/882/demandeurs_identifies", "parent": "/api/recueils_da", "annuler": "/api/recueils_da/882/annule", "self": "/api/recueils_da/882", "rendez_vous_reserver": "/api/recueils_da/882/rendez_vous" }, "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "date_transmission": "2016-01-12T13:58:30.916323+00:00", "id": "882", "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" }, "_updated": "2016-01-12T13:58:30.917924+00:00" } }
            """,
            handler=handler.label
        )

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def dna_recuperer_donnees_portail_usager_existant_pa_realise(self, user, site_structure_accueil,
                                                                 site_gu, payload):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        tester = BrokerBox(self.app, e.recueil_da.pa_realise.name, 'dna_recuperer_donnees_portail')
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_exploite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(site_affecte=site_gu)
        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()

        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.get(route)
        assert r.status_code == 200, r
        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_post_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            ret = user_req.get('/recueils_da/%s' % url.rsplit('/', 1)[1])
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        callbacks = [callback_post_backend, callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_usager1_existant_pa_realise(self, user, site_structure_accueil,
                                                                       usager, ref_pays, ref_nationalites, site_gu):
        usager['situation_familiale'] = 'MARIE'
        usager.save()
        link = "api/usagers/" + str(usager.id)
        payload = {
            "usager_1": {
                "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                "demandeur": True,
                "present_au_moment_de_la_demande": True,
                "date_depart": "2015-07-17T00:00:00+00:00",
                "usager_existant": {
                    "_links": {"self": link},
                    "id": usager.id
                },
                "_cls": "UsagerPrincipalRecueil"},
            "usager_2": {
                "nom": "BOUS",
                "prenoms": ["JULES"],
                "demandeur": False,
                "pays_naissance": ref_pays[0].code,
                "present_au_moment_de_la_demande": True,
                "_cls": "UsagerSecondaireRecueil",
                "ville_naissance": "Kiev",
                "adresse": {"ville": "PARIS20", "adresse_inconnue": False, "numero_voie": "1", "voie": "GAMBETTA", "code_postal": "75020"},
                "sexe": "M",
                "identifiant_agdref": "7503002401",
                "identifiant_portail_agdref": "DA9ubn3TVz08",
                "nationalites": [ref_nationalites[0].code],
                "date_naissance": "1988-12-27T00:00:00+00:00",
                "vulnerabilite": {"mobilite_reduite": False}
            },
            "statut": "PA_REALISE",
            "profil_demande": "FAMILLE"}
        self.dna_recuperer_donnees_portail_usager_existant_pa_realise(
            user, site_structure_accueil, site_gu, payload)

    def test_dna_recuperer_donnees_portail_usager2_existant_pa_realise(self, user, site_structure_accueil,
                                                                       usager, ref_pays, ref_nationalites, ref_langues_ofpra, ref_langues_iso, site_gu):
        from sief.model.fichier import Fichier
        link = "api/usagers/" + str(usager.id)
        photo = Fichier(name='photo.png').save()
        payload = {
            "usager_1": {
                "nom": "BOUS",
                "prenoms": ["JULES"],
                "demandeur": True,
                "pays_naissance": ref_pays[0].code,
                "present_au_moment_de_la_demande": True,
                "_cls": "UsagerPrincipalRecueil",
                "ville_naissance": "Kiev",
                "adresse": {"ville": "PARIS20", "adresse_inconnue": False, "numero_voie": "1", "voie": "GAMBETTA", "code_postal": "75020"},
                "sexe": "M",
                "identifiant_agdref": "7503002401",
                "identifiant_portail_agdref": "DA9ubn3TVz08",
                "nationalites": [ref_nationalites[0].code],
                "situation_familiale": 'MARIE',
                "photo_premier_accueil": str(photo.pk),
                "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                "date_depart": "2015-07-17T00:00:00+00:00",
                "date_naissance": "1958-12-27T00:00:00+00:00",
                "langues_audition_OFPRA": [{'code': str(ref_langues_ofpra[0].pk)}],
                "langues": [{'code': str(ref_langues_iso[0].pk)}],
                "vulnerabilite": {"mobilite_reduite": False}
            },
            "usager_2": {
                "demandeur": False,
                "present_au_moment_de_la_demande": True,
                "usager_existant": {
                    "_links": {"self": link},
                    "id": usager.id
                },
                "_cls": "UsagerSecondaireRecueil"
            },
            "statut": "PA_REALISE",
            "profil_demande": "FAMILLE"}
        self.dna_recuperer_donnees_portail_usager_existant_pa_realise(
            user, site_structure_accueil, site_gu, payload)

    def test_dna_recuperer_donnees_portail_enfant_existant_pa_realise(self, user, site_structure_accueil,
                                                                      usager, ref_pays, ref_nationalites, ref_langues_ofpra, ref_langues_iso, site_gu):
        from sief.model.fichier import Fichier
        link = "api/usagers/" + str(usager.id)
        photo = Fichier(name='photo.png').save()
        payload = {
            "usager_1": {
                "nom": "BOUS",
                "prenoms": ["JULES"],
                "demandeur": True,
                "pays_naissance": ref_pays[0].code,
                "present_au_moment_de_la_demande": True,
                "_cls": "UsagerPrincipalRecueil",
                "ville_naissance": "Kiev",
                "adresse": {"ville": "PARIS20", "adresse_inconnue": False, "numero_voie": "1", "voie": "GAMBETTA", "code_postal": "75020"},
                "sexe": "M",
                "identifiant_agdref": "7503002401",
                "identifiant_portail_agdref": "DA9ubn3TVz08",
                "nationalites": [ref_nationalites[0].code],
                "situation_familiale": 'MARIE',
                "photo_premier_accueil": str(photo.pk),
                "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                "date_depart": "2015-07-17T00:00:00+00:00",
                "date_naissance": "1958-12-27T00:00:00+00:00",
                "langues_audition_OFPRA": [{'code': str(ref_langues_ofpra[0].pk)}],
                "langues": [{'code': str(ref_langues_iso[0].pk)}],
                "vulnerabilite": {"mobilite_reduite": False}
            },
            "usager_2": {
                "nom": "BOUS",
                "prenoms": ["JULIES"],
                "demandeur": False,
                "pays_naissance": ref_pays[0].code,
                "present_au_moment_de_la_demande": True,
                "_cls": "UsagerSecondaireRecueil",
                "ville_naissance": "Kiev",
                "adresse": {"ville": "PARIS20", "adresse_inconnue": False, "numero_voie": "1", "voie": "GAMBETTA", "code_postal": "75020"},
                "sexe": "F",
                "identifiant_agdref": "7503002401",
                "identifiant_portail_agdref": "DA9ubn3TVz08",
                "nationalites": [ref_nationalites[0].code],
                "date_naissance": "1958-12-27T00:00:00+00:00",
                "vulnerabilite": {"mobilite_reduite": False}
            },
            "enfants": [
                {
                    "nom": "BOUS",
                    "prenoms": ["Geoffroy", "VI"],
                    "sexe": "M",
                    "usager_1": True,
                    "demandeur": False,
                    "present_au_moment_de_la_demande": True,
                    "pays_naissance": ref_pays[0].code,
                    "ville_naissance": "Kiev",
                    "nationalites": [ref_nationalites[0].code],
                    "identifiant_agdref": "7503002481",
                    "identifiant_portail_agdref": "DA9ubn3TVzR8",
                    "situation_familiale": "CELIBATAIRE",
                    "adresse": {"ville": "PARIS20", "adresse_inconnue": False, "numero_voie": "1", "voie": "GAMBETTA", "code_postal": "75020"},
                    "date_naissance": "1988-12-27T00:00:00+00:00",
                    "vulnerabilite": {"mobilite_reduite": False}
                },
                {
                    "usager_existant": {
                        "_links": {"self": link},
                        "id": usager.id
                    },
                    "demandeur": False,
                    "present_au_moment_de_la_demande": True,
                    "_cls": "UsagerEnfantRecueil"
                },
                {
                    "nom": "BOUS",
                    "prenoms": ["Guillaume"],
                    "sexe": "M",
                    "usager_1": True,
                    "demandeur": False,
                    "present_au_moment_de_la_demande": True,
                    "pays_naissance": ref_pays[0].code,
                    "ville_naissance": "Kiev",
                    "nationalites": [ref_nationalites[0].code],
                    "identifiant_agdref": "7503002421",
                    "identifiant_portail_agdref": "DA9ubn3TVzO8",
                    "situation_familiale": "CELIBATAIRE",
                    "adresse": {"ville": "PARIS20", "adresse_inconnue": False, "numero_voie": "1", "voie": "GAMBETTA", "code_postal": "75020"},
                    "date_naissance": "1989-12-27T00:00:00+00:00",
                    "vulnerabilite": {"mobilite_reduite": False}
                }
            ],
            "statut": "PA_REALISE",
            "profil_demande": "FAMILLE"}
        self.dna_recuperer_donnees_portail_usager_existant_pa_realise(
            user, site_structure_accueil, site_gu, payload)

    def test_dna_recuperer_donnees_portail_t538_cond_entree_fr(self, site_structure_accueil, pa_realise, user):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna == None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'

            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
    <soapenv:Header/>
    <soapenv:Body>
        <ns1:getDonneePortail>
            <DEMANDES>
                <DEMANDE>
                    <INDIVIDUS>
                        <INDIVIDU>
                            <ID_DEMANDE_ASILE>548</ID_DEMANDE_ASILE>
                            <ID_USAGER_PORTAIL>619</ID_USAGER_PORTAIL>
                            <CONDITION_ENTREE_FRANCE>N</CONDITION_ENTREE_FRANCE>
                            <DATE_AGDREF>2016-01-12</DATE_AGDREF>
                            <ID_AGDREF>7503002367</ID_AGDREF>
                            <ADULTE>
                                <NOM_NAISSANCE>POP</NOM_NAISSANCE>
                                <PRENOM>RB</PRENOM>
                                <LIEU_NAISSANCE>damas, SYRIE</LIEU_NAISSANCE>
                                <MATRIMONIAL>Célibataire</MATRIMONIAL>
                                <PROCEDURE_TYPE>En procédure normale</PROCEDURE_TYPE>
                                <DATE_NAISSANCE>1988-12-26</DATE_NAISSANCE>
                                <LANGUE1>6</LANGUE1>
                                <SEXE>M</SEXE>
                                <INSEE_PAYS_NATIONALITE>254</INSEE_PAYS_NATIONALITE>
                                <TYPE>Demandeur principal</TYPE>
                                <URL_PHOTO>/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE</URL_PHOTO>
                            </ADULTE>
                        </INDIVIDU>
                    </INDIVIDUS>
                    <ADRESSE>
                        <EMAIL>t@test.com</EMAIL>
                        <NUM_DOMICILIATION>1</NUM_DOMICILIATION>
                        <VILLE>Paris</VILLE>
                        <ADRESSE2></ADRESSE2>
                        <TELEPHONE>01 54 87 54 87</TELEPHONE>
                        <CODE_POSTAL>75012</CODE_POSTAL>
                        <NUMERO_VOIE>1</NUMERO_VOIE>
                        <LIBELLE_VOIE>Avenue Daumesnil</LIBELLE_VOIE>
                        <CODE_INSEE>75112</CODE_INSEE>
                    </ADRESSE>
                    <DATE_CREATION_DEMANDE>2016-01-12</DATE_CREATION_DEMANDE>
                    <PROCEDURE_STATUT>1</PROCEDURE_STATUT>
                    <AGENT_PREF>5603fe39000c672118021314</AGENT_PREF>
                    <DATE_PREF>2016-01-12</DATE_PREF>
                    <SITES>
                        <SITE>
                            <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                            <ADRESSE>
                                <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                                <VILLE>Bordeaux</VILLE>
                                <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                                <CODE_POSTAL>33000</CODE_POSTAL>
                                <NUMERO_VOIE>3</NUMERO_VOIE>
                                <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                                <CODE_INSEE>33000</CODE_INSEE>
                            </ADRESSE>
                            <TYPE_SITE>SPA</TYPE_SITE>
                            <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
                        </SITE>
                    </SITES>
                    <ID_RECUEIL_DEMANDE>881</ID_RECUEIL_DEMANDE>
                </DEMANDE>
            </DEMANDES>
        </ns1:getDonneePortail>
    </soapenv:Body>
</soapenv:Envelope>""".format(site=site_structure_accueil.pk)

            assert not diff_xml(kwargs['data'], expected, whitelist=(), pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{
            "usager_2": {},
            "usager_1": {
                "usager": {
                    "ville_naissance": "damas",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE",
                    "email": "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_created": "2016-01-12T13:53:00.510203+00:00",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Rb" ],
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" },
                    "_version": 2,
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "id": "619",
                    "identifiant_famille_dna": "193676",
                    "date_naissance": "1988-12-26T00:00:00+00:00",
                    "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" },
                    "sexe": "M",
                    "nom": "Pop",
                    "_links": { "update": "/api/usagers/619", "localisations": "/api/usagers/619/localisations", "prefecture_rattachee": "/api/usagers/619/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/619/etat_civil", "self": "/api/usagers/619", "localisation_update": "/api/usagers/619/localisations" },
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE" }, "id": "5695042fdc10573e2b530a51" },
                    "ecv_valide": false,
                    "identifiant_agdref": "7503002367",
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "_updated": "2016-01-12T13:53:00.512797+00:00",
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                },
                "demande_asile": {
                    "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" },
                    "id": "5603fdd1000c672120fdce01" },
                    "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" },
                    "usager": { "_links": { "self": "/api/usagers/619" }, "id": 619 },
                    "_links": { "editer_attestation": "/api/demandes_asile/548/attestations", "self": "/api/demandes_asile/548", "orienter": "/api/demandes_asile/548/orientation", "parent": "/api/demandes_asile" },
                    "enfants_presents_au_moment_de_la_demande": [ ],
                    "statut": "PRETE_EDITION_ATTESTATION",
                    "renouvellement_attestation": 1,
                    "_created": "2016-01-12T13:53:00.598737+00:00",
                    "indicateur_visa_long_sejour": false,
                    "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 },
                    "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                    "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                    "condition_entree_france": "REGULIERE",
                    "conditions_exceptionnelles_accueil": true,
                    "motif_conditions_exceptionnelles_accueil": "RELOCALISATION",
                    "date_demande": "2016-01-12T13:50:45.945000+00:00",
                    "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                    "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00",
                    "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                    "type_demandeur": "PRINCIPAL",
                    "_version": 2,
                    "date_depart": "2015-07-17T00:00:00+00:00",
                    "date_enregistrement": "2016-01-12T13:53:00.494490+00:00",
                    "id": "548",
                    "visa": "C",
                    "decision_sur_attestation": true,
                    "_updated": "2016-01-12T13:53:00.601390+00:00",
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }
                }
            },
            "recueil_da": {
                "identifiant_famille_dna": "193676",
                "_updated": "2016-01-12T13:53:00.640771+00:00",
                "statut": "EXPLOITE",
                "usager_1": {
                    "ville_naissance": "damas",
                    "type_procedure": "NORMALE",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE", "email":
                    "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_cls": "UsagerPrincipalRecueil",
                    "visa": "C",
                    "condition_entree_france": "REGULIERE",
                    "conditions_exceptionnelles_accueil": true,
                    "motif_conditions_exceptionnelles_accueil": "RELOCALISATION",
                    "indicateur_visa_long_sejour": false,
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Rb" ],
                    "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/548" }, "id": 548 },
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Avenue Daumesnil", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] },
                    "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                    "demandeur": true,
                    "date_naissance": "1988-12-26T00:00:00+00:00",
                    "motif_qualification_procedure": "PNOR",
                    "sexe": "M",
                    "nom": "Pop",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "present_au_moment_de_la_demande": true,
                    "date_depart": "2015-07-17T00:00:00+00:00",
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDExMiwiaWQiOiI1Njk1MDQyZmRjMTA1NzNlMmI1MzBhNTEifQ.JAw2IgBr6SQAmnJ-UODDY3zaEGG4gf2WNZ-wBpITNTw" }, "id": "5695042fdc10573e2b530a51" },
                    "usager_existant": { "_links": { "self": "/api/usagers/619" }, "id": 619 },
                    "identifiant_agdref": "7503002367",
                    "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00",
                    "decision_sur_attestation": true,
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                },
                "_created": "2016-01-12T13:50:45.938000+00:00",
                "profil_demande": "MINEUR_ACCOMPAGNANT",
                "_links": { "self": "/api/recueils_da/881", "parent": "/api/recueils_da" },
                "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                "enfants": [ ],
                "id": "881",
                "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                "date_enregistrement": "2016-01-12T13:53:00.494490+00:00",
                "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                "_version": 10,
                "date_transmission": "2016-01-12T13:50:45.945000+00:00"
            },
            "enfants": [ ]
            }
            """,
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    @freeze_time("2015-10-3")  # Fix time to avoid child to grow up ;-)
    def test_dna_recuperer_donnees_portail_t599(self, site_structure_accueil, pa_realise, user):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        site_structure_accueil.libelle = "Structure d'accueil de Bordeaux - %s - Un Libelle De Plus De Cent Caracteres De Long" % site_structure_accueil.pk
        site_structure_accueil.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna is None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            return Response(200, json={})

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, *args, **kwargs):
            assert method == 'POST'

            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
<soapenv:Header/>
<soapenv:Body>
    <ns1:getDonneePortail>
        <DEMANDES>
            <DEMANDE>
                <INDIVIDUS>
                    <INDIVIDU>
                        <ID_USAGER_PORTAIL>620</ID_USAGER_PORTAIL>
                        <DATE_AGDREF>{date}</DATE_AGDREF>
                        <ENFANT>
                            <DATE_NAISSANCE>1998-12-26</DATE_NAISSANCE>
                            <SEXE>M</SEXE>
                            <NOM>UN NOM DE PLUS DE QUARANTE HUIT CARACTERES DE LO</NOM>
                            <ENFANT_DE_REFUGIE>true</ENFANT_DE_REFUGIE>
                            <PRENOM>UN PRENOM DE PLUS DE QUARANTE HUIT CARACTERES DE</PRENOM>
                            <INSEE_PAYS_NATIONALITE>254</INSEE_PAYS_NATIONALITE>
                            <LIEU_NAISSANCE>Une Ville De Naissance De Plus De Soixante Quatre Caracteres De </LIEU_NAISSANCE>
                        </ENFANT>
                    </INDIVIDU>
                    <INDIVIDU>
                        <ID_DEMANDE_ASILE>548</ID_DEMANDE_ASILE>
                        <ID_USAGER_PORTAIL>619</ID_USAGER_PORTAIL>
                        <CONDITION_ENTREE_FRANCE>N</CONDITION_ENTREE_FRANCE>
                        <DATE_AGDREF>2016-01-12</DATE_AGDREF>
                        <ID_AGDREF>7503002367</ID_AGDREF>
                        <ADULTE>
                            <NOM_NAISSANCE>UN NOM DE PLUS DE QUARANTE HUIT CARACTERES DE LO</NOM_NAISSANCE>
                            <PRENOM>UN PRENOM DE PLUS DE QUARANTE HUIT CARACTERES DE</PRENOM>
                            <LIEU_NAISSANCE>Une Ville De Naissance De Plus De Soixante Quatre Caracteres De </LIEU_NAISSANCE>
                            <MATRIMONIAL>Célibataire</MATRIMONIAL>
                            <PROCEDURE_TYPE>En procédure normale</PROCEDURE_TYPE>
                            <DATE_NAISSANCE>1988-12-26</DATE_NAISSANCE>
                            <LANGUE1>6</LANGUE1>
                            <SEXE>M</SEXE>
                            <INSEE_PAYS_NATIONALITE>254</INSEE_PAYS_NATIONALITE>
                            <TYPE>Demandeur principal</TYPE>
                            <URL_PHOTO>/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE</URL_PHOTO>
                        </ADULTE>
                    </INDIVIDU>
                </INDIVIDUS>
                <ADRESSE>
                    <EMAIL>t@test.com</EMAIL>
                    <NUM_DOMICILIATION>1</NUM_DOMICILIATION>
                    <VILLE>Paris</VILLE>
                    <ADRESSE2></ADRESSE2>
                    <TELEPHONE>01 54 87 54 87</TELEPHONE>
                    <CODE_POSTAL>75012</CODE_POSTAL>
                    <NUMERO_VOIE>1</NUMERO_VOIE>
                    <LIBELLE_VOIE>Libelle Voie De Plus De Cinquante Caracteres De Lo</LIBELLE_VOIE>
                    <CODE_INSEE>75112</CODE_INSEE>
                </ADRESSE>
                <DATE_CREATION_DEMANDE>2016-01-12</DATE_CREATION_DEMANDE>
                <PROCEDURE_STATUT>1</PROCEDURE_STATUT>
                <AGENT_PREF>5603fe39000c672118021314</AGENT_PREF>
                <DATE_PREF>2016-01-12</DATE_PREF>
                <SITES>
                    <SITE>
                        <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                        <ADRESSE>
                            <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                            <VILLE>Bordeaux</VILLE>
                            <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                            <CODE_POSTAL>33000</CODE_POSTAL>
                            <NUMERO_VOIE>3</NUMERO_VOIE>
                            <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                            <CODE_INSEE>33000</CODE_INSEE>
                        </ADRESSE>
                        <TYPE_SITE>SPA</TYPE_SITE>
                        <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site} - Un Libelle De Plus De Cent Caracteres D</LIBELLE_SITE>
                    </SITE>
                </SITES>
                <ID_RECUEIL_DEMANDE>881</ID_RECUEIL_DEMANDE>
            </DEMANDE>
        </DEMANDES>
    </ns1:getDonneePortail>
</soapenv:Body>
</soapenv:Envelope>""".format(site=site_structure_accueil.pk, date=date.strftime("%Y-%m-%d"))
            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite',
            'processor': 'dna_recuperer_donnees_portail'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{
            "usager_2": {},
            "usager_1": {
                "usager": {
                    "ville_naissance": "Une Ville De Naissance De Plus De Soixante Quatre Caracteres De Long",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE",
                    "email": "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_created": "2016-01-12T13:53:00.510203+00:00",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Un Prenom De Plus De Quarante Huit Caracteres De Long" ],
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" },
                    "_version": 2,
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "id": "619",
                    "identifiant_famille_dna": "193676",
                    "date_naissance": "1988-12-26T00:00:00+00:00",
                    "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Libelle Voie De Plus De Cinquante Caracteres De Long", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" },
                    "sexe": "M",
                    "nom": "Un Nom De Plus De Quarante Huit Caracteres De Long",
                    "_links": { "update": "/api/usagers/619", "localisations": "/api/usagers/619/localisations", "prefecture_rattachee": "/api/usagers/619/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/619/etat_civil", "self": "/api/usagers/619", "localisation_update": "/api/usagers/619/localisations" },
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE" }, "id": "5695042fdc10573e2b530a51" },
                    "ecv_valide": false,
                    "identifiant_agdref": "7503002367",
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "_updated": "2016-01-12T13:53:00.512797+00:00",
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                },
                "demande_asile": {
                    "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" },
                    "id": "5603fdd1000c672120fdce01" },
                    "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" },
                    "usager": { "_links": { "self": "/api/usagers/619" }, "id": 619 },
                    "_links": { "editer_attestation": "/api/demandes_asile/548/attestations", "self": "/api/demandes_asile/548", "orienter": "/api/demandes_asile/548/orientation", "parent": "/api/demandes_asile" },
                    "enfants_presents_au_moment_de_la_demande": [ { "id": 620, "_links": { "self": "/api/usagers/620" } } ],
                    "statut": "PRETE_EDITION_ATTESTATION",
                    "renouvellement_attestation": 1,
                    "_created": "2016-01-12T13:53:00.598737+00:00",
                    "indicateur_visa_long_sejour": false,
                    "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 },
                    "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                    "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                    "condition_entree_france": "REGULIERE",
                    "conditions_exceptionnelles_accueil": true,
                    "motif_conditions_exceptionnelles_accueil": "RELOCALISATION",
                    "date_demande": "2016-01-12T13:50:45.945000+00:00",
                    "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                    "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00",
                    "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                    "type_demandeur": "PRINCIPAL",
                    "_version": 2,
                    "date_depart": "2015-07-17T00:00:00+00:00",
                    "date_enregistrement": "2016-01-12T13:53:00.494490+00:00",
                    "id": "548",
                    "visa": "C",
                    "decision_sur_attestation": true,
                    "_updated": "2016-01-12T13:53:00.601390+00:00",
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }
                }
            },
            "recueil_da": {
                "identifiant_famille_dna": "193676",
                "_updated": "2016-01-12T13:53:00.640771+00:00",
                "statut": "EXPLOITE",
                "usager_1": {
                    "ville_naissance": "Une Ville De Naissance De Plus De Soixante Quatre Caracteres De Long",
                    "type_procedure": "NORMALE",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE", "email":
                    "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_cls": "UsagerPrincipalRecueil",
                    "visa": "C",
                    "condition_entree_france": "REGULIERE",
                    "conditions_exceptionnelles_accueil": true,
                    "motif_conditions_exceptionnelles_accueil": "RELOCALISATION",
                    "indicateur_visa_long_sejour": false,
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Un Prenom De Plus De Quarante Huit Caracteres De Long" ],
                    "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/548" }, "id": 548 },
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Libelle Voie De Plus De Cinquante Caracteres De Long", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] },
                    "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                    "demandeur": true,
                    "date_naissance": "1988-12-26T00:00:00+00:00",
                    "motif_qualification_procedure": "PNOR",
                    "sexe": "M",
                    "nom": "Un Nom De Plus De Quarante Huit Caracteres De Long",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "present_au_moment_de_la_demande": true,
                    "date_depart": "2015-07-17T00:00:00+00:00",
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDExMiwiaWQiOiI1Njk1MDQyZmRjMTA1NzNlMmI1MzBhNTEifQ.JAw2IgBr6SQAmnJ-UODDY3zaEGG4gf2WNZ-wBpITNTw" }, "id": "5695042fdc10573e2b530a51" },
                    "usager_existant": { "_links": { "self": "/api/usagers/619" }, "id": 619 },
                    "identifiant_agdref": "7503002367",
                    "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00",
                    "decision_sur_attestation": true,
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                },
                "_created": "2016-01-12T13:50:45.938000+00:00",
                "profil_demande": "MINEUR_ACCOMPAGNANT",
                "_links": { "self": "/api/recueils_da/881", "parent": "/api/recueils_da" },
                "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                "enfants": [ {
                    "usager_2": false,
                    "ecv_valide": false,
                    "_created": "2016-01-12T13:53:00.510203+00:00",
                    "_cls": "UsagerEnfantRecueil",
                    "nom": "Un Nom De Plus De Quarante Huit Caracteres De Long",
                    "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Libelle Voie De Plus De Cinquante Caracteres De Long", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] },
                    "date_naissance": "1998-12-26T00:00:00+00:00",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "situation_familiale": "CELIBATAIRE",
                    "_version": 2,
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" },
                    "identifiant_pere": { "id": 1458, "_links": { "self": "/api/usagers/1458" } },
                    "prefecture_rattachee": { "id": "5603fd96000c67212242b31c", "_links": { "self": "/api/sites/5603fd96000c67212242b31c" } },
                    "sexe": "M",
                    "_links": { "localisation_update": "/api/usagers/620/localisations", "update": "/api/usagers/620", "localisations": "/api/usagers/620/localisations", "prefecture_rattachee": "/api/usagers/620/prefecture_rattachee", "etat_civil_update": "/api/usagers/620/etat_civil", "self": "/api/usagers/620", "parent": "/api/usagers" },
                    "_updated": "2016-06-06T11:18:33.566875+00:00",
                    "usager_1": true,
                    "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Libelle Voie De Plus De Cinquante Caracteres De Long", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" },
                    "present_au_moment_de_la_demande": true,
                    "id": "620",
                    "usager_existant": { "id": 620, "_links": { "self": "/api/usagers/620" } },
                    "prenoms": [ "Un Prenom De Plus De Quarante Huit Caracteres De Long" ],
                    "transferable": true,
                    "demandeur": true,
                    "ville_naissance": "Une Ville De Naissance De Plus De Soixante Quatre Caracteres De Long"
                }],
                "id": "881",
                "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                "date_enregistrement": "2016-01-12T13:53:00.494490+00:00",
                "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                "_version": 10,
                "date_transmission": "2016-01-12T13:50:45.945000+00:00"
            },
            "enfants": [ {
                "usager": {
                    "ville_naissance": "Une Ville De Naissance De Plus De Soixante Quatre Caracteres De Long",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE",
                    "email": "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_created": "2016-01-12T13:53:00.510203+00:00",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Un Prenom De Plus De Quarante Huit Caracteres De Long" ],
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" },
                    "_version": 2,
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "id": "620",
                    "identifiant_famille_dna": "193676",
                    "date_naissance": "1998-12-26T00:00:00+00:00",
                    "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "Libelle Voie De Plus De Cinquante Caracteres De Long", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" },
                    "sexe": "M",
                    "nom": "Un Nom De Plus De Quarante Huit Caracteres De Long",
                    "_links": { "update": "/api/usagers/620", "localisations": "/api/usagers/620/localisations", "prefecture_rattachee": "/api/usagers/620/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/620/etat_civil", "self": "/api/usagers/620", "localisation_update": "/api/usagers/620/localisations" },
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE" }, "id": "5695042fdc10573e2b530a51" },
                    "ecv_valide": false,
                    "identifiant_agdref": "7503002367",
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "_updated": "2016-01-12T13:53:00.512797+00:00",
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                }
            }]
            }
            """,
            handler=handler.label
        )

        callbacks = [callback_dna,
                     callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail(handler, msg)
        assert not callbacks

    def test_dna_recuperer_donnees_portail_t584(self, site_structure_accueil, pa_realise, user):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        recueil = pa_realise
        assert recueil.identifiant_famille_dna is None

        def callback_sites(method, url, *args, **kwargs):
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % site_structure_accueil.pk)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/recueils_da/%s' % recueil.id)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_post_backend(method, url, *args, json=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert url.endswith('/enregistrement_famille_ofii')
            ret = user_req.post('/recueils_da/%s/enregistrement_famille_ofii' % recueil.id, data=json)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna_step1(method, url, *args, **kwargs):
            assert method == 'POST'

            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
<soapenv:Header/>
<soapenv:Body>
    <ns1:getDonneePortail>
        <DEMANDES>
            <DEMANDE>
                <INDIVIDUS>
                    <INDIVIDU>
                        <ADULTE>
                            <DATE_ENTREE_EN_FRANCE>2015-07-17</DATE_ENTREE_EN_FRANCE>
                            <NOM_NAISSANCE>POP</NOM_NAISSANCE>
                            <PRENOM>RB</PRENOM>
                            <LIEU_NAISSANCE>damas, SYRIE</LIEU_NAISSANCE>
                            <MATRIMONIAL>Célibataire</MATRIMONIAL>
                            <DATE_NAISSANCE>1988-12-26</DATE_NAISSANCE>
                            <LANGUE1>6</LANGUE1>
                            <SEXE>M</SEXE>
                            <INSEE_PAYS_NATIONALITE>254</INSEE_PAYS_NATIONALITE>
                            <TYPE>Demandeur principal</TYPE>
                            <URL_PHOTO>/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDExMiwiaWQiOiI1Njk1MDQyZmRjMTA1NzNlMmI1MzBhNTEifQ.JAw2IgBr6SQAmnJ-UODDY3zaEGG4gf2WNZ-wBpITNTw</URL_PHOTO>                        </ADULTE>
                    </INDIVIDU>
                </INDIVIDUS>
                <ADRESSE>
                    <EMAIL>t@test.com</EMAIL>
                    <NUM_DOMICILIATION>1</NUM_DOMICILIATION>
                    <VILLE>Paris</VILLE>
                    <ADRESSE2></ADRESSE2>
                    <TELEPHONE>01 54 87 54 87</TELEPHONE>
                    <CODE_POSTAL>75012</CODE_POSTAL>
                    <NUMERO_VOIE>1</NUMERO_VOIE>
                    <LIBELLE_VOIE>BOULEVARD DU PALAIS</LIBELLE_VOIE>
                    <CODE_INSEE>75112</CODE_INSEE>
                </ADRESSE>
                <SITES>
                    <SITE>
                        <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                        <ADRESSE>
                            <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                            <VILLE>Bordeaux</VILLE>
                            <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                            <CODE_POSTAL>33000</CODE_POSTAL>
                            <NUMERO_VOIE>3</NUMERO_VOIE>
                            <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                            <CODE_INSEE>33000</CODE_INSEE>
                        </ADRESSE>
                        <TYPE_SITE>SPA</TYPE_SITE>
                        <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
                    </SITE>
                </SITES>
                <PROCEDURE_STATUT>0</PROCEDURE_STATUT>
                <ID_RECUEIL_DEMANDE>881</ID_RECUEIL_DEMANDE>
                <DATE_CREATION_DEMANDE>2016-01-12</DATE_CREATION_DEMANDE>
            </DEMANDE>
        </DEMANDES>
    </ns1:getDonneePortail>
</soapenv:Body>
</soapenv:Envelope>""".format(site=site_structure_accueil.pk, date=date.strftime("%Y-%m-%d"))
            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        def callback_dna_step2(method, url, *args, **kwargs):
            assert method == 'POST'

            date = datetime.utcnow()
            expected = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
<soapenv:Header/>
<soapenv:Body>
<ns1:getDonneePortail>
<DEMANDES>
    <DEMANDE>
        <INDIVIDUS>
            <INDIVIDU>
                <DATE_AGDREF>2016-01-12</DATE_AGDREF>
                <ID_AGDREF>7503002367</ID_AGDREF>
                <ID_DEMANDE_ASILE>548</ID_DEMANDE_ASILE>
                <ID_USAGER_PORTAIL>619</ID_USAGER_PORTAIL>
                <CONDITION_ENTREE_FRANCE>N</CONDITION_ENTREE_FRANCE>
                <ADULTE>
                    <NOM_NAISSANCE>POP</NOM_NAISSANCE>
                    <PRENOM>RB</PRENOM>
                    <LIEU_NAISSANCE>damas, SYRIE</LIEU_NAISSANCE>
                    <MATRIMONIAL>Célibataire</MATRIMONIAL>
                    <PROCEDURE_TYPE>En procédure normale</PROCEDURE_TYPE>
                    <DATE_NAISSANCE>1988-12-26</DATE_NAISSANCE>
                    <LANGUE1>6</LANGUE1>
                    <SEXE>M</SEXE>
                    <INSEE_PAYS_NATIONALITE>254</INSEE_PAYS_NATIONALITE>
                    <TYPE>Demandeur principal</TYPE>
                    <URL_PHOTO>/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE</URL_PHOTO>
                </ADULTE>
            </INDIVIDU>
        </INDIVIDUS>
        <ADRESSE>
            <EMAIL>t@test.com</EMAIL>
            <NUM_DOMICILIATION>1</NUM_DOMICILIATION>
            <VILLE>Paris</VILLE>
            <ADRESSE2></ADRESSE2>
            <TELEPHONE>01 54 87 54 87</TELEPHONE>
            <CODE_POSTAL>75012</CODE_POSTAL>
            <NUMERO_VOIE>1</NUMERO_VOIE>
            <LIBELLE_VOIE>BOULEVARD DU PALAIS</LIBELLE_VOIE>
            <CODE_INSEE>75112</CODE_INSEE>
        </ADRESSE>
        <DATE_CREATION_DEMANDE>2016-01-12</DATE_CREATION_DEMANDE>
        <PROCEDURE_STATUT>1</PROCEDURE_STATUT>
        <ID_FAMILLE_DNA>123</ID_FAMILLE_DNA>
        <AGENT_PREF>5603fe39000c672118021314</AGENT_PREF>
        <DATE_PREF>2016-01-12</DATE_PREF>
        <SITES>
            <SITE>
                <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
                <ADRESSE>
                    <NUM_DOMICILIATION>3</NUM_DOMICILIATION>
                    <VILLE>Bordeaux</VILLE>
                    <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
                    <CODE_POSTAL>33000</CODE_POSTAL>
                    <NUMERO_VOIE>3</NUMERO_VOIE>
                    <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
                    <CODE_INSEE>33000</CODE_INSEE>
                </ADRESSE>
                <TYPE_SITE>SPA</TYPE_SITE>
                <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}</LIBELLE_SITE>
            </SITE>
        </SITES>
        <ID_RECUEIL_DEMANDE>881</ID_RECUEIL_DEMANDE>
    </DEMANDE>
</DEMANDES>
</ns1:getDonneePortail>
</soapenv:Body>
</soapenv:Envelope>""".format(site=site_structure_accueil.pk, date=date.strftime("%Y-%m-%d"))
            assert not diff_xml(kwargs['data'], expected, pop_count=3)

            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.exploite_by_step',
            'processor': 'dna_recuperer_donnees_portail_by_step'
        })
        msg = Message(
            status="READY",
            queue="dna",
            created=datetime(2015, 10, 2, 9, 46, 3),
            json_context="""{
            "usager_2": {},
            "usager_1": {
                "usager": {
                    "ville_naissance": "damas",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE",
                    "email": "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_created": "2016-01-12T13:53:00.510203+00:00",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Rb" ],
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" },
                    "_version": 2,
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "id": "619",
                    "date_naissance": "1988-12-26T00:00:00+00:00",
                    "localisation": { "organisme_origine": "PORTAIL", "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "BOULEVARD DU PALAIS", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] }, "date_maj": "2016-01-12T13:53:00.509513+00:00" },
                    "sexe": "M",
                    "nom": "Pop",
                    "_links": { "update": "/api/usagers/619", "localisations": "/api/usagers/619/localisations", "prefecture_rattachee": "/api/usagers/619/prefecture_rattachee", "parent": "/api/usagers", "etat_civil_update": "/api/usagers/619/etat_civil", "self": "/api/usagers/619", "localisation_update": "/api/usagers/619/localisations" },
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC42MTgyMDcsImlkIjoiNTY5NTA0MmZkYzEwNTczZTJiNTMwYTUxIn0.57vZOVDUNbmaHF8onHK8wXEmZEiNitBM5SJU1Yn50UE" }, "id": "5695042fdc10573e2b530a51" },
                    "ecv_valide": false,
                    "identifiant_agdref": "7503002367",
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "_updated": "2016-01-12T13:53:00.512797+00:00",
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                },
                "demande_asile": {
                    "structure_premier_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" },
                    "id": "5603fdd1000c672120fdce01" },
                    "procedure": { "type": "NORMALE", "acteur": "GUICHET_UNIQUE", "motif_qualification": "PNOR" },
                    "usager": { "_links": { "self": "/api/usagers/619" }, "id": 619 },
                    "_links": { "editer_attestation": "/api/demandes_asile/548/attestations", "self": "/api/demandes_asile/548", "orienter": "/api/demandes_asile/548/orientation", "parent": "/api/demandes_asile" },
                    "enfants_presents_au_moment_de_la_demande": [ { "id": 620, "_links": { "self": "/api/usagers/620" } } ],
                    "statut": "PRETE_EDITION_ATTESTATION",
                    "renouvellement_attestation": 1,
                    "_created": "2016-01-12T13:53:00.598737+00:00",
                    "indicateur_visa_long_sejour": false,
                    "recueil_da_origine": { "_links": { "self": "/api/recueils_da/881" }, "id": 881 },
                    "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                    "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                    "condition_entree_france": "REGULIERE",
                    "conditions_exceptionnelles_accueil": true,
                    "motif_conditions_exceptionnelles_accueil": "RELOCALISATION",
                    "date_demande": "2016-01-12T13:50:45.945000+00:00",
                    "referent_premier_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                    "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00",
                    "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                    "type_demandeur": "PRINCIPAL",
                    "_version": 2,
                    "date_depart": "2015-07-17T00:00:00+00:00",
                    "date_enregistrement": "2016-01-12T13:53:00.494490+00:00",
                    "id": "548",
                    "visa": "C",
                    "decision_sur_attestation": true,
                    "type_demande": "PREMIERE_DEMANDE_ASILE",
                    "_updated": "2016-01-12T13:53:00.601390+00:00",
                    "prefecture_rattachee": { "_links": { "self": "/api/sites/5603fd96000c67212242b31c" }, "id": "5603fd96000c67212242b31c" }
                }
            },
            "recueil_da": {
                "_updated": "2016-01-12T13:53:00.640771+00:00",
                "statut": "EXPLOITE",
                "usager_1": {
                    "ville_naissance": "damas",
                    "type_procedure": "NORMALE",
                    "telephone": "01 54 87 54 87",
                    "origine_nom": "EUROPE", "email":
                    "t@test.com",
                    "nationalites": [ { "code": "SYR", "libelle": "syrienne" } ],
                    "_cls": "UsagerPrincipalRecueil",
                    "visa": "C",
                    "condition_entree_france": "REGULIERE",
                    "conditions_exceptionnelles_accueil": true,
                    "motif_conditions_exceptionnelles_accueil": "RELOCALISATION",
                    "indicateur_visa_long_sejour": false,
                    "situation_familiale": "CELIBATAIRE",
                    "prenoms": [ "Rb" ],
                    "demande_asile_resultante": { "_links": { "self": "/api/demandes_asile/548" }, "id": 548 },
                    "identifiant_portail_agdref": "tbC5ejKFhbl1",
                    "adresse": { "code_insee": "75112", "identifiant_ban": "ADRNIVX_0000000270788337", "adresse_inconnue": false, "ville": "Paris", "pays": { "code": "FRA", "libelle": "FRANCE" }, "complement": "", "voie": "BOULEVARD DU PALAIS", "code_postal": "75012", "chez": "", "numero_voie": "1", "longlat": [ 2.372098, 48.849148 ] },
                    "date_entree_en_france": "2015-07-17T00:00:00+00:00",
                    "demandeur": true,
                    "date_naissance": "1988-12-26T00:00:00+00:00",
                    "motif_qualification_procedure": "PNOR",
                    "sexe": "M",
                    "nom": "Pop",
                    "langues_audition_OFPRA": [ { "code": "ARA", "libelle": "ARABE" } ],
                    "present_au_moment_de_la_demande": true,
                    "date_depart": "2015-07-17T00:00:00+00:00",
                    "photo": { "_links": { "name": "7503001898.png", "self": "/api/fichiers/5695042fdc10573e2b530a51", "data": "/api/fichiers/5695042fdc10573e2b530a51/data?signature=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoiZmljaGllciIsImV4cCI6MTQ1MjY4OTU4MC43MDExMiwiaWQiOiI1Njk1MDQyZmRjMTA1NzNlMmI1MzBhNTEifQ.JAw2IgBr6SQAmnJ-UODDY3zaEGG4gf2WNZ-wBpITNTw" }, "id": "5695042fdc10573e2b530a51" },
                    "usager_existant": { "_links": { "self": "/api/usagers/619" }, "id": 619 },
                    "date_decision_sur_attestation": "2016-01-12T00:00:00+00:00",
                    "decision_sur_attestation": true,
                    "langues": [ { "code": "ara", "libelle": "arabe" } ],
                    "type_demande": "PREMIERE_DEMANDE_ASILE",
                    "date_enregistrement_agdref": "2016-01-12T14:54:17+00:00",
                    "pays_naissance": { "code": "SYR", "libelle": "SYRIE" }
                },
                "_created": "2016-01-12T13:50:45.938000+00:00",
                "profil_demande": "MAJEUR_ISOLE",
                "_links": { "self": "/api/recueils_da/881", "parent": "/api/recueils_da" },
                "structure_guichet_unique": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                "enfants": [],
                "id": "881",
                "agent_enregistrement": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                "date_enregistrement": "2016-01-12T13:53:00.494490+00:00",
                "structure_accueil": { "_links": { "self": "/api/sites/5603fdd1000c672120fdce01" }, "id": "5603fdd1000c672120fdce01" },
                "agent_accueil": { "_links": { "self": "/api/utilisateurs/5603fe39000c672118021314" }, "id": "5603fe39000c672118021314" },
                "_version": 10,
                "date_transmission": "2016-01-12T13:50:45.945000+00:00"
            },
            "enfants": []
            }
            """,
            handler=handler.label
        )

        callbacks = [callback_dna_step2, callback_sites, callback_get_recueil_backend,
                     callback_post_backend, callback_dna_step1, callback_sites, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        assert dna_recuperer_donnees_portail_by_step(handler, msg)
        assert not callbacks


class TestDNAProcessResponse(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={'CONNECTOR_DNA_REQUESTS': cls.mock_requests})

    def test_dna_responses_empty(self):
        from connector.dna.recupererdonneesportail import process_response
        callback_called = False
        payload = """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES/></ns2:getDonneePortailResponse></S:Body></S:Envelope>"""

        def callback(*args, **kwargs):
            assert False, 'Should not send any request'

        handler = EventHandlerItem({
            'label': 'test-event-handler',
            'queue': 'dna',
            'event': 'recueil_da.pa_realise',
            'processor': 'dna_recuperer_donnees_portail'
        })
        self.mock_requests.callback_response = callback
        process_response(handler, payload)


class TestDNAOutput(common.BaseSolrTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_DNA_REQUESTS': cls.mock_requests,
            'BACKEND_API_PREFIX': '/pref',
            'BACKEND_URL_DOMAIN': 'https://mydomain.com',
            'BACKEND_URL': 'https://mydomain.com/pref',
            'CONNECTOR_DNA_PREFIX': '/pref/dna',
            'DISABLE_EVENTS': False
        })

    def test_dna_recuperer_donnees_portail_usager_unique(self, user, site_structure_accueil,
                                                         payload_pa_fini):
        tester = BrokerBox(self.app, e.recueil_da.pa_realise.name, 'dna_recuperer_donnees_portail')
        # Switch to pa_realise
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]

        creneaux = add_free_creneaux(4, site_structure_accueil.guichets_uniques[0])
        user.test_set_accreditation(site_affecte=site_structure_accueil)
        user.save()
        payload_pa_fini['usager_1']['langues'] = ['eng']
        payload_pa_fini['usager_1']['situation_familiale'] = 'CELIBATAIRE'
        payload_pa_fini['usager_1']['nationalites'][0]['code'] = 'ukr'
        del payload_pa_fini['usager_2']
        del payload_pa_fini['enfants']
        payload_pa_fini['usager_1']['adresse']['complement'] = "appartement 4, 2eme étage"
        payload_pa_fini['usager_1']['adresse']['numero_voie'] = "3"
        payload_pa_fini['usager_1']['adresse']['voie'] = "3 Place Lucien Victor Meunier"
        payload_pa_fini['usager_1']['adresse']['ville'] = "Bordeaux"
        payload_pa_fini['usager_1']['adresse']['code_insee'] = "33000"
        payload_pa_fini['usager_1']['adresse']['code_postal'] = "33000"

        r = user_req.post('/recueils_da', data=payload_pa_fini)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.put(
            route + '/pa_realise', data={'creneaux': [[creneaux[0]['id'], creneaux[1]['id']]]})
        assert r.status_code == 200, r
        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        def callback_post_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'POST'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            assert kwargs['json']['identifiant_famille_dna'] == '123'
            return Response(200)

        def callback_get_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/sites/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/sites/%s' % url.rsplit('/', 1)[1])
            return Response(ret.status_code, json=ret.data)

        def callback_get_recueil_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert url.startswith('%s/recueils_da/' % self.app.config['BACKEND_URL'])
            ret = user_req.get('/recueils_da/%s' % url.rsplit('/', 1)[1])
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            date = datetime.utcnow()
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <soapenv:Header/><soapenv:Body><ns1:getDonneePortail><DEMANDES><DEMANDE><ADRESSE>
            <NUM_DOMICILIATION>3</NUM_DOMICILIATION><ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
            <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
            <CODE_POSTAL>33000</CODE_POSTAL>
            <CODE_INSEE>33000</CODE_INSEE><NUMERO_VOIE>3</NUMERO_VOIE><VILLE>Bordeaux</VILLE>
            </ADRESSE><DATE_CREATION_DEMANDE>{date}</DATE_CREATION_DEMANDE>
            <PROCEDURE_STATUT>0</PROCEDURE_STATUT><DATE_RDV_GU>{date_rdv}</DATE_RDV_GU>
            <SITES><SITE><TYPE_SITE>SPA</TYPE_SITE><ADRESSE><NUM_DOMICILIATION>3</NUM_DOMICILIATION>
            <ADRESSE2>appartement 4, 2eme étage</ADRESSE2>
            <LIBELLE_VOIE>3 Place Lucien Victor Meunier</LIBELLE_VOIE>
            <CODE_POSTAL>33000</CODE_POSTAL><CODE_INSEE>33000</CODE_INSEE>
            <NUMERO_VOIE>3</NUMERO_VOIE><VILLE>Bordeaux</VILLE></ADRESSE>
            <ID_SITE_PORTAIL>{site}</ID_SITE_PORTAIL>
            <LIBELLE_SITE>Structure d'accueil de Bordeaux - {site}
            </LIBELLE_SITE></SITE></SITES>
            <ID_RECUEIL_DEMANDE>1</ID_RECUEIL_DEMANDE><INDIVIDUS>
            <INDIVIDU><ADULTE><TYPE>Demandeur principal</TYPE><LANGUE1>5</LANGUE1>
            <NOM_NAISSANCE>PLANTAGENET</NOM_NAISSANCE>
            <LIEU_NAISSANCE>Château-du-Loir, UKRAINE</LIEU_NAISSANCE>
            <PRENOM>GEOFFROY</PRENOM><SEXE>M</SEXE>
            <INSEE_PAYS_NATIONALITE>171</INSEE_PAYS_NATIONALITE>
            <MATRIMONIAL>Célibataire</MATRIMONIAL><DATE_NAISSANCE>1913-08-24</DATE_NAISSANCE>
            <DATE_ENTREE_EN_FRANCE>{date}</DATE_ENTREE_EN_FRANCE>
            </ADULTE></INDIVIDU></INDIVIDUS>
            </DEMANDE></DEMANDES></ns1:getDonneePortail>
            </soapenv:Body></soapenv:Envelope>""".format(
                date=date.strftime("%Y-%m-%d"),
                date_rdv=add_days(date, 1).strftime("%Y-%m-%d"),
                site=site_structure_accueil.pk)

            assert not diff_xml(data, expected, whitelist=(), pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
            <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
            <SOAP-ENV:Header/><S:Body><ns2:getDonneePortailResponse
            xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
            <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
            <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
            <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
            </ns2:getDonneePortailResponse></S:Body>
            </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r
        callbacks = [callback_post_backend, callback_dna,
                     callback_get_backend, callback_get_recueil_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_dublin(self, user, da_en_cours_dublin, ref_pays):

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService" >
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA><TRANSFERT>
            <EXECUTION>true</EXECUTION><DATE_DECISION>2015-09-11</DATE_DECISION>
            <DATE_EXECUTION>2016-06-11</DATE_EXECUTION></TRANSFERT><IDENTIFICATION>
            <ID_USAGER_PORTAIL>{0}</ID_USAGER_PORTAIL><ID_AGDREF>{1}</ID_AGDREF>
            <ID_IND_DNA>{2}</ID_IND_DNA></IDENTIFICATION><TYPE_PERSONNE>Adulte</TYPE_PERSONNE>
            </MAJDA></ns1:majDonneesDA></soapenv:Body>
            </soapenv:Envelope>""".format(
                usager['id'],
                usager['identifiant_agdref'],
                usager['identifiant_dna'])

            diff_xml(data, expected, whitelist=(), pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        tester = BrokerBox(self.app, e.demande_asile.dublin_modifie.name, 'dna_majda')
        # Generate event
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.voir.name, p.demande_asile.modifier_dublin.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        route = '/demandes_asile/%s/dublin' % da_en_cours_dublin.pk
        payload = {
            'EM': str(ref_pays[0].pk),
            'date_demande_EM': '2015-06-11T03:22:43Z+00:00',
            'date_decision': '2015-09-11T03:22:43Z+00:00',
            'date_execution': '2016-06-11T03:22:43Z+00:00',
            'execution': True
        }
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_PROCEDURE_DUBLIN'
        assert 'dublin' in r.data
        route = '/usagers/%s' % r.data.get('usager', {}).get('id')
        r = user_req.get(route, data=payload)
        usager = r.data

        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_etat_civil_valide(self, user, ref_pays, exploite):

        def callback_backend_get_recueil(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/recueils_da' in url
            route = '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % usager.identifiant_agdref
            ret = user_req.get(route)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend_get_user(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % usager.id)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService">
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA>
            <ETATCIVIL><LIEU_NAISSANCE>Château-du-Loir, UKRAINE</LIEU_NAISSANCE>
            <INSEE_PAYS_NATIONALITE>und</INSEE_PAYS_NATIONALITE>
            <NOM_NAISSANCE>PLANTAGENET</NOM_NAISSANCE><SEXE>M</SEXE><PRENOM>GEOFFROY</PRENOM>
            <MATRIMONIAL>Concubin</MATRIMONIAL><DATE_NAISSANCE>1913-08-24</DATE_NAISSANCE>
            </ETATCIVIL><TYPE_PERSONNE>Adulte</TYPE_PERSONNE><IDENTIFICATION>
            <ID_AGDREF>{identifiant_agdref}</ID_AGDREF>
            <ID_USAGER_PORTAIL>{usager}</ID_USAGER_PORTAIL><ID_IND_DNA>233994</ID_IND_DNA>
            </IDENTIFICATION></MAJDA></ns1:majDonneesDA></soapenv:Body>
            </soapenv:Envelope>
            """.format(usager=usager.id, identifiant_agdref=usager.identifiant_agdref)
            assert not diff_xml(data, expected, pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.etat_civil.valider.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = exploite.usager_1.usager_existant
        da = exploite.usager_1.demande_asile_resultante
        # Sanity check
        assert da
        usager.identifiant_dna = "233994"
        usager.save()
        self.app.solr.commit(waitFlush=True)

        payload = ['nom', 'nom_usage', 'prenoms', 'sexe', 'date_naissance',
                   'date_naissance_approximative', 'pays_naissance', 'ville_naissance',
                   'nationalites', 'situation_familiale']
        payload = {key: usager[key] for key in payload}
        tester = BrokerBox(self.app, e.usager.etat_civil.valide.name, 'dna_majda')
        ret = user_req.post('/usagers/%s/etat_civil' % usager.id, data=payload)

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        assert ret.status_code == 200
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]
        callbacks = [callback_dna, callback_backend_get_recueil, callback_backend_get_user]
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_decision_definitive(self, user, da_decision_def):

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService" >
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA><DECISION>
            <DATE_NOTIF>{3}</DATE_NOTIF><ENTITE>CNDA</ENTITE><NATURE>CR</NATURE>
            <DATE_DECISION>{3}</DATE_DECISION></DECISION><IDENTIFICATION>
            <ID_IND_DNA>{2}</ID_IND_DNA><ID_USAGER_PORTAIL>{0}</ID_USAGER_PORTAIL>
            <ID_AGDREF>{1}</ID_AGDREF></IDENTIFICATION><TYPE_PERSONNE>Adulte</TYPE_PERSONNE>
            </MAJDA></ns1:majDonneesDA></soapenv:Body></soapenv:Envelope>""".format(
                usager['id'],
                usager['identifiant_agdref'],
                usager['identifiant_dna'],
                datetime.utcnow().strftime("%Y-%m-%d"))

            assert not diff_xml(data, expected, pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        tester = BrokerBox(self.app, e.demande_asile.decision_definitive.name, 'dna_majda')
        # Generate event
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.voir.name, p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        route = '/demandes_asile/%s/decisions_definitives' % da_decision_def.pk
        payload = {
            'nature': 'CR',
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'CNDA',
            'numero_skipper': 'Skiango'
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['decisions_definitives']) == 2
        route = '/usagers/%s' % r.data.get('usager', {}).get('id')
        r = user_req.get(route, data=payload)
        usager = r.data

        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_etat_civil(self, user, exploite, ref_nationalites):
        usager = exploite.usager_1.usager_existant
        usager.identifiant_dna = '123456'
        usager.save()

        def callback_backend_get_recueil(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/recueils_da' in url
            ret = user_req.get(
                '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % usager.identifiant_agdref)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService" >
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA>
            <TYPE_PERSONNE>Adulte</TYPE_PERSONNE><ETATCIVIL><NOM_NAISSANCE>CAESAIRE</NOM_NAISSANCE><INSEE_PAYS_NATIONALITE>und</INSEE_PAYS_NATIONALITE>
            </ETATCIVIL><IDENTIFICATION>
            <ID_AGDREF>{1}</ID_AGDREF><ID_USAGER_PORTAIL>{0}</ID_USAGER_PORTAIL>
            <ID_IND_DNA>{2}</ID_IND_DNA></IDENTIFICATION></MAJDA></ns1:majDonneesDA>
            </soapenv:Body></soapenv:Envelope>""".format(
                usager['id'],
                usager['identifiant_agdref'],
                usager['identifiant_dna'])

            assert not diff_xml(data, expected, pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        tester = BrokerBox(self.app, e.usager.etat_civil.modifie.name, 'dna_majda')
        # Generate event
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.usager.modifier.name, p.usager.etat_civil.modifier.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()

        nat = ref_nationalites[1]
        self.app.solr.commit(waitFlush=True)
        # Need permission to do it
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        payload = {'nom': 'Caesaire',
                   'nationalites': [{'code': str(nat.pk)}]}
        user_req.patch(route, data=payload)
        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend_get_recueil, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_no_identifiant_dna(self, user, exploite, ref_nationalites):

        def callback_backend_get_recueil(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/recueils_da' in url
            ret = user_req.get(
                '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % usager.identifiant_agdref)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert False

        tester = BrokerBox(self.app, e.usager.etat_civil.modifie.name, 'dna_majda')
        # Generate event
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.usager.modifier.name, p.usager.etat_civil.modifier.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = exploite.usager_1.usager_existant
        usager.identifiant_dna = None
        usager.save()
        nat = ref_nationalites[1]
        # Need permission to do it
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        payload = {'nom': 'Caesaire',
                   'nationalites': [{'code': str(nat.pk)}]}
        user_req.patch(route, data=payload)
        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend_get_recueil, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert msg.status_comment == 'Pas de mise à jour possible sans identifiant_dna'
        assert callbacks

    def test_dna_majda_usager_modifie_no_update(self, user, exploite, ref_nationalites):

        usager = exploite.usager_1.usager_existant

        def callback_backend_get_recueil(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/recueils_da' in url
            ret = user_req.get(
                '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % usager.identifiant_agdref)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert False

        tester = BrokerBox(self.app, e.usager.modifie.name, 'dna_majda')
        # Generate event
        usager.identifiant_dna = '123456'
        usager.save()
        self.app.solr.commit(waitFlush=True)
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        payload = {}
        # Need permission to do it
        route = '/usagers/{}'.format(usager.pk)
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.usager.modifier_agdref.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend_get_recueil, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert msg.status_comment == 'Le message transmis par la plateforme semble ne contenir aucune information de mise à jour'
        assert callbacks

    def test_dna_majda_usager_modifie(self, user, exploite, ref_nationalites):

        usager = exploite.usager_1.usager_existant

        def callback_backend_get_recueil(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.permissions = []
            user.save()
            assert method == 'GET'
            assert '/recueils_da' in url
            ret = user_req.get(
                '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % usager.identifiant_agdref)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.permissions = []
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService" >
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA>
            <FUITE><DATE_FUITE>{3}</DATE_FUITE></FUITE><IDENTIFICATION>
            <ID_IND_DNA>{2}</ID_IND_DNA><ID_USAGER_PORTAIL>{0}</ID_USAGER_PORTAIL>
            <ID_AGDREF>{1}</ID_AGDREF></IDENTIFICATION><TYPE_PERSONNE>Adulte</TYPE_PERSONNE><UPDATE></UPDATE></MAJDA>
            </ns1:majDonneesDA></soapenv:Body></soapenv:Envelope>""".format(
                usager['id'],
                usager['identifiant_agdref'],
                usager['identifiant_dna'],
                datetime.utcnow().strftime("%Y-%m-%d"))

            assert not diff_xml(data, expected, pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        tester = BrokerBox(self.app, e.usager.modifie.name, 'dna_majda')
        # Generate event
        usager.identifiant_dna = '123456'
        usager.save()
        self.app.solr.commit(waitFlush=True)
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        payload = {'eloignement': {'date_decision': datetime.utcnow()},
                   'date_fuite': datetime.utcnow()}
        # Need permission to do it
        route = '/usagers/{}'.format(usager.pk)
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.usager.modifier_agdref.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend_get_recueil, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_procedure_requalifiee(self, user, da_attente_ofpra):

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService" >
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA>
            <IDENTIFICATION><ID_IND_DNA>{2}</ID_IND_DNA>
            <ID_USAGER_PORTAIL>{0}</ID_USAGER_PORTAIL>
            <ID_AGDREF>{1}</ID_AGDREF></IDENTIFICATION>
            <TYPE_PERSONNE>Adulte</TYPE_PERSONNE>
            <PROCEDURE><DATE_NOTIF>2000-01-01</DATE_NOTIF>
            <DATE_PROCEDURE>{3}</DATE_PROCEDURE>
            <TYPE>En procédure prioritaire</TYPE>
            </PROCEDURE></MAJDA></ns1:majDonneesDA></soapenv:Body>
            </soapenv:Envelope>""".format(
                usager['id'],
                usager['identifiant_agdref'],
                usager['identifiant_dna'],
                datetime.utcnow().strftime("%Y-%m-%d"))

            assert not diff_xml(data, expected, pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        tester = BrokerBox(self.app, e.demande_asile.procedure_requalifiee.name, 'dna_majda')
        # Generate event
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.demande_asile.voir.name, p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = da_attente_ofpra.usager
        route = '/demandes_asile/%s/requalifications' % da_attente_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'OFPRA',
            'motif_qualification': 'FREM',
            'date_notification': '2015-09-20T00:00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_dna, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_droit_cree(self, user_with_site_affecte, da_prete_ea):

        def callback_backend_demande_asile(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/demandes_asile/' in url
            ret = user_req.get('/demandes_asile/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_dna(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            expected = """<?xml version="1.0" encoding="UTF-8"?>
            <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            xmlns:ns1="http://service.webservices.dna.anaem.social.fr/MajDonneesDAService" >
            <soapenv:Header/><soapenv:Body><ns1:majDonneesDA><MAJDA>
            <IDENTIFICATION><ID_IND_DNA>{2}</ID_IND_DNA>
            <ID_USAGER_PORTAIL>{0}</ID_USAGER_PORTAIL>
            <ID_AGDREF>{1}</ID_AGDREF></IDENTIFICATION>
            <TYPE_PERSONNE>Adulte</TYPE_PERSONNE>
            <TITRE></TITRE><UPDATE></UPDATE>
            </MAJDA></ns1:majDonneesDA></soapenv:Body>
            </soapenv:Envelope>""".format(
                usager['id'],
                usager['identifiant_agdref'],
                usager['identifiant_dna'],
                datetime.utcnow().strftime("%Y-%m-%d"))

            assert not diff_xml(data, expected, pop_count=3)
            r = Response(200, """<?xml version='1.0' encoding='UTF-8'?>
        <S:Envelope xmlns:S="http://schemas.xmlsoap.org/soap/envelope/"
        xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
        <SOAP-ENV:Header/><S:Body><ns2:majDonneesDAResponse
        xmlns:ns2="http://service.webservices.dna.anaem.social.fr/RecupererDonneesPortailService">
        <REPONSES><REPONSE><ID_RECUEIL_DEMANDE>{0}</ID_RECUEIL_DEMANDE>
        <ID_FAMILLE_DNA>{3}</ID_FAMILLE_DNA><CODE_ERREUR>{2}</CODE_ERREUR>
        <LIBELLE_ERREUR>{1}</LIBELLE_ERREUR></REPONSE></REPONSES>
        </ns2:majDonneesDAResponse></S:Body>
        </S:Envelope>""".format('1', 'OK', '00', '123'))
            return r

        user = user_with_site_affecte

        tester = BrokerBox(self.app, e.droit.cree.name, 'dna_majda')
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        da_prete_ea.procedure.type = 'NORMALE'
        da_prete_ea.procedure.motif_qualification = 'NECD'
        da_prete_ea.save()
        usager = da_prete_ea.usager
        usager.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea.pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00",
                   'date_decision_sur_attestation': "2015-09-22T00:00:03+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r

        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]
        callbacks = [callback_dna, callback_backend, callback_backend_demande_asile]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks

    def test_dna_majda_reexamen_skipped(self, user, da_attente_ofpra):

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            user.permissions = []
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        tester = BrokerBox(self.app, e.demande_asile.procedure_requalifiee.name, 'dna_majda')
        # Generate event
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.demande_asile.voir.name, p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        da_attente_ofpra.type_demande = 'REEXAMEN'
        da_attente_ofpra.numero_reexamen = 1
        da_attente_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_attente_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'OFPRA',
            'motif_qualification': 'FREM',
            'date_notification': '2015-09-20T00:00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]
        callbacks = [callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert msg.status == 'SKIPPED'


class TestDNAInputDisabled(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_DNA_REQUESTS': cls.mock_requests,
            'BACKEND_API_PREFIX': '/pref',
            'BACKEND_URL_DOMAIN': 'https://mydomain.com',
            'BACKEND_URL': 'https://mydomain.com/pref',
            'DISABLE_CONNECTOR_DNA_INPUT': True,
            'CONNECTOR_DNA_PREFIX': '/pref/dna'})

    def test_post(self, user):
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.test_set_accreditation(role='SYSTEME_DNA')
        user.permissions = []
        user.save()
        payload = """ZZZZ"""

        def callback(method, url, data=None, headers=None, json=None, **kwargs):
            assert False

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/dna/MajPortail', data=payload)
        assert r.status_code == 503
        assert '<tns:majPortailResponse><tns:CODE_ERREUR>77</tns:CODE_ERREUR><tns:LIBELLE_ERREUR>Connecteur DN@ entrant désactivé</tns:LIBELLE_ERREUR></tns:majPortailResponse>' in r.data.decode()
        r.data.decode()


class TestDNASkippedReexame(common.BaseSolrTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_DNA_REQUESTS': cls.mock_requests,
            'BACKEND_API_PREFIX': '/pref',
            'BACKEND_URL_DOMAIN': 'https://mydomain.com',
            'BACKEND_URL': 'https://mydomain.com/pref',
            'CONNECTOR_DNA_PREFIX': '/pref/dna',
            'DISABLE_EVENTS': False
        })

    def setup_method(self, method):
        # Clean broker data
        self.app.extensions['broker'].model.Message.objects.delete()
        self.app.extensions['broker'].model.QueueManifest.objects.delete()
        super().setup_method(method)

    def test_dna_majda_dublin_skipped(self, user, da_en_cours_dublin, ref_pays):

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        tester = BrokerBox(self.app, e.demande_asile.dublin_modifie.name, 'dna_majda')
        # Generate event
        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        user.permissions = [p.usager.voir.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.voir.name, p.demande_asile.modifier_dublin.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        da_en_cours_dublin.type_demande = "REEXAMEN"
        da_en_cours_dublin.numero_reexamen = 1
        da_en_cours_dublin.save()
        self.app.solr.commit(waitFlush=True)

        route = '/demandes_asile/%s/dublin' % da_en_cours_dublin.pk
        payload = {
            'EM': str(ref_pays[0].pk),
            'date_demande_EM': '2015-06-11T03:22:43Z+00:00',
            'date_decision': '2015-09-11T03:22:43Z+00:00',
            'date_execution': '2016-06-11T03:22:43Z+00:00',
            'execution': True
        }
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_PROCEDURE_DUBLIN'
        assert 'dublin' in r.data
        route = '/usagers/%s' % r.data.get('usager', {}).get('id')
        r = user_req.get(route, data=payload)
        usager = r.data

        # Check the presence&validity of the message
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert len(callbacks) == 1
        assert msg.status == 'SKIPPED'

    def test_dna_majda_usager_modifie_skipped(self, user, exploite, ref_nationalites):

        usager = exploite.usager_1.usager_existant
        exploite.usager_1.type_demande = 'REEXAMEN'
        exploite.usager_1.numero_reexamen = 1
        exploite.save()

        def callback_backend_get_recueil(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.permissions = []
            user.save()
            assert method == 'GET'
            assert '/recueils_da' in url
            ret = user_req.get(
                '/recueils_da?q=*:*&fq=usagers_identifiant_agdref:%s' % usager.identifiant_agdref)
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        def callback_backend(method, url, data=None, headers=None, **kwargs):
            user.test_set_accreditation(role='SYSTEME_DNA')
            user.permissions = []
            user.save()
            assert method == 'GET'
            assert '/usagers/' in url
            ret = user_req.get('/usagers/%s' % url.rsplit('/', 1)[1])
            assert ret.status_code == 200
            return Response(ret.status_code, json=ret.data)

        tester = BrokerBox(self.app, e.usager.modifie.name, 'dna_majda')
        # Generate event
        usager.identifiant_dna = '123456'
        usager.save()
        self.app.solr.commit(waitFlush=True)

        user_req = self.make_auth_request(user, user._raw_password, url_prefix='/pref/agent')
        payload = {'eloignement': {'date_decision': datetime.utcnow()},
                   'date_fuite': datetime.utcnow()}
        # Need permission to do it
        route = '/usagers/{}'.format(usager.pk)
        user.permissions = [p.usager.voir.name, p.usager.modifier.name,
                            p.usager.modifier_agdref.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]

        callbacks = [callback_backend_get_recueil, callback_backend]

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret
        self.mock_requests.callback_response = callback
        tester.event_handler.execute_legacy(msg)
        assert not callbacks
        assert msg.status == 'SKIPPED'
