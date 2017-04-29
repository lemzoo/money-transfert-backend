import pytest
from datetime import datetime, timedelta
import xmltodict

from tests import common
from tests.fixtures import *
from tests.connector.common import Response, BrokerBox, MockRequests, assert_xml_payloads
from connector.agdref.agdref_input import maj_agdref


class TestAGDREFConnector(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_AGDREF_REQUESTS': cls.mock_requests
        })

    def test_get_wsdl(self):
        r = self.client_app.get('/connectors/agdref/majAGDREF?wsdl')
        assert r.status_code == 200
        assert r.headers['Content-Type'] == 'text/xml; charset=utf-8'
        wsdl_domain = self.app.config['BACKEND_URL_DOMAIN'] + \
            self.app.config['CONNECTOR_AGDREF_PREFIX']
        assert wsdl_domain in r.data.decode()

    def test_editer_adresse(self, user, da_instruction_ofpra):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='SYSTEME_AGDREF')
        user.permissions = []
        user.save()
        da = da_instruction_ofpra
        usager = da.usager
        payload = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/majAGDREF">
   <soap:Header/>
   <soap:Body>
      <maj:miseAJourAdresseRequest>
         <maj:Tracability>
            <maj:typeFlux>04</maj:typeFlux>
            <maj:dateFlux>20150929</maj:dateFlux>
            <maj:heureFlux>155600</maj:heureFlux>
            <maj:numeroEtranger>{agdref_id}</maj:numeroEtranger>
            <maj:identifiantSIAsile>{si_id}</maj:identifiantSIAsile>
            <maj:numeroDemandeAsile>{demande_asile_id}</maj:numeroDemandeAsile>
         </maj:Tracability>
         <maj:Identifier>
            <!--Optional:-->
            <maj:chez>MOI</maj:chez>
            <!--Optional:-->
            <maj:numeroVoie>10</maj:numeroVoie>
            <!--Optional:-->
            <maj:typeVoie>BV</maj:typeVoie>
            <!--Optional:-->
            <maj:libelleVoie>DU PALAIS</maj:libelleVoie>
            <maj:codePostal>75004</maj:codePostal>
            <maj:libelleCommune>PARIS</maj:libelleCommune>
            <maj:dateMAJ>20150810</maj:dateMAJ>
         </maj:Identifier>
      </maj:miseAJourAdresseRequest>
   </soap:Body>
</soap:Envelope>""".format(demande_asile_id=da.id, si_id=usager.identifiant_portail_agdref, agdref_id=usager.identifiant_agdref)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 2

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
        assert r.status_code == 200
        response = r.data.decode()
        assert '<codeRetourSIAsile>000</codeRetourSIAsile>' in response, response
        assert not len(callbacks)
        usager.reload()
        da.reload()
        assert len(usager.localisations) == 2
        loc = usager.localisations[-1]
        assert loc.organisme_origine == 'AGDREF'
        assert loc.adresse.voie == 'BOULEVARD DU PALAIS'
        assert loc.adresse.numero_voie == '10'
        assert loc.adresse.code_postal == '75004'
        assert loc.adresse.code_insee == None
        assert loc.adresse.ville == 'PARIS'
        assert loc.adresse.chez == 'MOI'
        assert loc.adresse.complement == None
        assert loc.adresse.pays == None
        assert not loc.adresse.longlat

    def test_procedure_eloignement(self, user, da_instruction_ofpra):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='SYSTEME_AGDREF')
        user.permissions = []
        user.save()
        da = da_instruction_ofpra
        usager = da.usager
        payload = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/majAGDREF">
   <soap:Header/>
   <soap:Body>
      <maj:procedureEloignementRequest>
         <maj:Tracability>
            <maj:typeFlux>?</maj:typeFlux>
            <maj:dateFlux>20150929</maj:dateFlux>
            <maj:heureFlux>155600</maj:heureFlux>
            <maj:numeroEtranger>{agdref_id}</maj:numeroEtranger>
            <maj:identifiantSIAsile>{si_id}</maj:identifiantSIAsile>
            <maj:numeroDemandeAsile>{demande_asile_id}</maj:numeroDemandeAsile>
         </maj:Tracability>
         <maj:Identifier>
            <!--Optional:-->
            <maj:delaiDepartVolontaire>10</maj:delaiDepartVolontaire>
            <!--Optional:-->
            <maj:executionMesure>N</maj:executionMesure>
            <maj:dateDecisionEloignement>20151011</maj:dateDecisionEloignement>
            <!--Optional:-->
            <maj:dateExecutionEloignement>20151012</maj:dateExecutionEloignement>
            <!--Optional:-->
            <maj:contentieux>O</maj:contentieux>
            <!--Optional:-->
            <maj:decisionContentieux></maj:decisionContentieux>
         </maj:Identifier>
      </maj:procedureEloignementRequest>
   </soap:Body>
</soap:Envelope>""".format(demande_asile_id=da.id, si_id=usager.identifiant_portail_agdref, agdref_id=usager.identifiant_agdref)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 2

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
        assert r.status_code == 200
        response = r.data.decode()
        assert '<codeRetourSIAsile>000</codeRetourSIAsile>' in response, response
        assert not len(callbacks)
        usager.reload()
        da.reload()
        usager.eloignement.date_execution == datetime(2015, 10, 11)
        usager.eloignement.date_decision == datetime(2015, 10, 11)
        usager.eloignement.execution == False
        usager.eloignement.delai_depart_volontaire == 10
        usager.eloignement.contentieux == True
        usager.eloignement.decision_contentieux == None

    def test_bad_procedure_eloignement(self, user, da_instruction_ofpra):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='SYSTEME_AGDREF')
        user.permissions = []
        user.save()
        da = da_instruction_ofpra
        usager = da.usager
        template_payload = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/majAGDREF">
   <soap:Header/>
   <soap:Body>
      <maj:procedureEloignementRequest>
         <maj:Tracability>
            <maj:typeFlux>?</maj:typeFlux>
            <maj:dateFlux>20150929</maj:dateFlux>
            <maj:heureFlux>155600</maj:heureFlux>
            <maj:numeroEtranger>{agdref_id}</maj:numeroEtranger>
            <maj:identifiantSIAsile>{si_id}</maj:identifiantSIAsile>
            <maj:numeroDemandeAsile>{demande_asile_id}</maj:numeroDemandeAsile>
         </maj:Tracability>
         <maj:Identifier>
            <!--Optional:-->
            <maj:delaiDepartVolontaire>{{delai}}</maj:delaiDepartVolontaire>
            <!--Optional:-->
            <maj:executionMesure>{{execution}}</maj:executionMesure>
            <maj:dateDecisionEloignement>{{date_decision}}</maj:dateDecisionEloignement>
            <!--Optional:-->
            <maj:dateExecutionEloignement>{{date_execution}}</maj:dateExecutionEloignement>
            <!--Optional:-->
            <maj:contentieux>{{contentieux}}</maj:contentieux>
            <!--Optional:-->
            <maj:decisionContentieux>{{decision_contentieux}}</maj:decisionContentieux>
         </maj:Identifier>
      </maj:procedureEloignementRequest>
   </soap:Body>
</soap:Envelope>""".format(demande_asile_id=da.id, si_id=usager.identifiant_portail_agdref, agdref_id=usager.identifiant_agdref)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        default_values = {
            'delai': 10,
            'execution': 'N',
            'date_decision': '20151011',
            'date_execution': '20151012',
            'contentieux': 'O',
            'decision_contentieux': '20151013'
        }

        for key, value, error_code in (
                ('delai', 'NaN', 4),
                ('execution', 'true', 5),
                ('execution', 'Maybe', 5),
                ('date_decision', 'Not a date', 6)):
            values = default_values.copy()
            values[key] = value
            payload = template_payload.format(**values)
            callbacks = [callback_get_backend]

            def callback(*args, **kwargs):
                assert callbacks, (key, value)
                current_callback = callbacks.pop()
                ret = current_callback(*args, **kwargs)
                return ret

            self.mock_requests.callback_response = callback
            r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
            assert r.status_code == 200
            response = r.data.decode()
            assert '<codeRetourSIAsile>{:0>3}</codeRetourSIAsile>'.format(
                error_code) in response, response
            assert not len(callbacks)

    def test_procedure_naturalisation(self, user, da_instruction_ofpra):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='SYSTEME_AGDREF')
        user.permissions = []
        user.save()
        da = da_instruction_ofpra
        usager = da.usager
        payload = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/majAGDREF">
   <soap:Header/>
   <soap:Body>
      <maj:enregistrementNaturalisationRequest>
         <maj:Tracability>
            <maj:typeFlux>?</maj:typeFlux>
            <maj:dateFlux>20150929</maj:dateFlux>
            <maj:heureFlux>155600</maj:heureFlux>
            <maj:numeroEtranger>{agdref_id}</maj:numeroEtranger>
            <maj:identifiantSIAsile>{si_id}</maj:identifiantSIAsile>
            <maj:numeroDemandeAsile>{demande_asile_id}</maj:numeroDemandeAsile>
         </maj:Tracability>
         <maj:Identifier>
            <maj:dateNaturalisation>20150922</maj:dateNaturalisation>
         </maj:Identifier>
      </maj:enregistrementNaturalisationRequest>
   </soap:Body>
</soap:Envelope>""".format(demande_asile_id=da.id, si_id=usager.identifiant_portail_agdref, agdref_id=usager.identifiant_agdref)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 2

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
        assert r.status_code == 200
        response = r.data.decode()
        assert '<codeRetourSIAsile>000</codeRetourSIAsile>' in response, response
        assert not len(callbacks)
        usager.reload()
        da.reload()
        usager.date_naturalisation == datetime(2015, 9, 22)

    def test_procedure_readmission(self, user, da_en_cours_dublin):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='SYSTEME_AGDREF')
        user.permissions = []
        user.save()
        da = da_en_cours_dublin
        usager = da.usager
        payload = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/majAGDREF">
   <soap:Header/>
   <soap:Body>
      <maj:procedureReadmissionRequest>
         <maj:Tracability>
            <maj:typeFlux>?</maj:typeFlux>
            <maj:dateFlux>20150929</maj:dateFlux>
            <maj:heureFlux>155600</maj:heureFlux>
            <maj:numeroEtranger>{agdref_id}</maj:numeroEtranger>
            <maj:identifiantSIAsile>{si_id}</maj:identifiantSIAsile>
            <maj:numeroDemandeAsile>{demande_asile_id}</maj:numeroDemandeAsile>
         </maj:Tracability>
         <maj:Identifier>
            <maj:dateDemandealEtatMembre>20150908</maj:dateDemandealEtatMembre>
            <maj:etatMembre>EIR</maj:etatMembre>
            <!--Optional:-->
            <maj:dateReponseEtatMembre>20150909</maj:dateReponseEtatMembre>
            <!--Optional:-->
            <maj:reponseEtatMembre>Not sure holmes...</maj:reponseEtatMembre>
            <!--Optional:-->
            <maj:dateDecisionOuTransfert>20150910</maj:dateDecisionOuTransfert>
            <!--Optional:-->
            <maj:dateExecutionTransfert>20150911</maj:dateExecutionTransfert>
            <!--Optional:-->
            <maj:executionMesure>N</maj:executionMesure>
            <!--Optional:-->
            <maj:delaiDepartVolontaire>10</maj:delaiDepartVolontaire>
            <!--Optional:-->
            <maj:contentieux>O</maj:contentieux>
            <!--Optional:-->
            <maj:decisionContentieux>TODO</maj:decisionContentieux>
         </maj:Identifier>
      </maj:procedureReadmissionRequest>
   </soap:Body>
</soap:Envelope>""".format(demande_asile_id=da.id, si_id=usager.identifiant_portail_agdref, agdref_id=usager.identifiant_agdref)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            assert ret.status_code == 200
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 2

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
        assert r.status_code == 200
        response = r.data.decode()
        assert '<codeRetourSIAsile>000</codeRetourSIAsile>' in response, response
        assert not len(callbacks)
        usager.reload()
        da.reload()
        da.dublin.date_demande_EM == datetime(2015, 9, 8)
        da.dublin.date_reponse_EM == datetime(2015, 9, 9)
        da.dublin.EM.code == ''
        da.dublin.reponse_EM == 'Not sure holmes...'
        da.dublin.date_decision == datetime(2015, 9, 10)
        da.dublin.execution == False
        da.dublin.date_execution == datetime(2015, 9, 11)
        da.dublin.delai_depart_volontaire == 10
        da.dublin.contentieux == True
        da.dublin.decision_contentieux == 'TODO'
        da.dublin.date_signalement_fuite == None

    @pytest.mark.xfail
    def test_delivrance_document_sejour(self, user, da_en_cours_dublin):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='SYSTEME_AGDREF')
        user.permissions = []
        user.save()
        da = da_en_cours_dublin
        usager = da.usager
        payload = """<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/majAGDREF">
   <soap:Header/>
   <soap:Body>
      <maj:delivranceDocumentSejourRequest>
         <maj:Tracability>
            <maj:typeFlux>?</maj:typeFlux>
            <maj:dateFlux>20150929</maj:dateFlux>
            <maj:heureFlux>155600</maj:heureFlux>
            <maj:numeroEtranger>{agdref_id}</maj:numeroEtranger>
            <maj:identifiantSIAsile>{si_id}</maj:identifiantSIAsile>
            <maj:numeroDemandeAsile>{demande_asile_id}</maj:numeroDemandeAsile>
         </maj:Tracability>
         <maj:Identifier>
            <maj:typeDocument>?</maj:typeDocument>
            <maj:dureeValiditeDocument>1</maj:dureeValiditeDocument>
            <maj:referenceReglementaire>?</maj:referenceReglementaire>
            <maj:lieuDelivrance>?</maj:lieuDelivrance>
            <maj:dateDelivrance>?</maj:dateDelivrance>
            <maj:dateDebutValidite>?</maj:dateDebutValidite>
            <maj:dateFinValidite>?</maj:dateFinValidite>
            <!--Optional:-->
            <maj:dateRetraitDocument>?</maj:dateRetraitDocument>
         </maj:Identifier>
      </maj:delivranceDocumentSejourRequest>
   </soap:Body>
</soap:Envelope>""".format(demande_asile_id=da.id, si_id=usager.identifiant_portail_agdref, agdref_id=usager.identifiant_agdref)

        def callback_get_backend(method, url, data=None, headers=None, json=None, **kwargs):
            headers = headers or {}
            if json:
                headers['Content-Type'] = 'application/json'
                data = json
            assert url.startswith(self.app.config['BACKEND_URL'])
            route = url[len(self.app.config['BACKEND_URL']):]
            ret = user_req.request(method, route, data=data, headers=headers)
            assert ret.status_code == 200
            return Response(status_code=ret.status_code, json=ret.data)

        callbacks = [callback_get_backend] * 2

        def callback(*args, **kwargs):
            current_callback = callbacks.pop()
            ret = current_callback(*args, **kwargs)
            return ret

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
        assert r.status_code == 200
        response = r.data.decode()
        assert '<codeRetourSIAsile>000</codeRetourSIAsile>' in response, response
        assert not len(callbacks)
        usager.reload()
        da.reload()


class TestAGDREFConnectorInputDisabled(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'CONNECTOR_AGDREF_REQUESTS': cls.mock_requests,
            'DISABLE_CONNECTOR_AGDREF_INPUT': True
        })

    def test_get_wsdl(self):
        r = self.client_app.get('/connectors/agdref/majAGDREF?wsdl')
        assert r.status_code == 200
        assert r.headers['Content-Type'] == 'text/xml; charset=utf-8'
        wsdl_domain = self.app.config['BACKEND_URL_DOMAIN'] + \
            self.app.config['CONNECTOR_AGDREF_PREFIX']
        assert wsdl_domain in r.data.decode()

    def test_post(self, user):
        payload = """Ce message est invalide"""

        def callback(method, url, data=None, headers=None, json=None, **kwargs):
            assert False

        self.mock_requests.callback_response = callback
        r = self.client_app.post('/connectors/agdref/majAGDREF', data=payload)
        assert r.status_code == 503
        assert 'Connecteur AGDREF entrant désactivé' in r.data.decode()
