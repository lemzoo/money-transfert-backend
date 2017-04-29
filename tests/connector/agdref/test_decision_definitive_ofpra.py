import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, MockRequests, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class TestAGDREFConnectorDecisionDefinitiveOfpra(TestAGDREFConnectorSolr):

    def test_decision_definitive_ofpra(self, user, da_instruction_ofpra):
        tester = BrokerBox(
            self.app, e.demande_asile.decision_definitive.name, 'agdref_decision_definitive_ofpra')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = da_instruction_ofpra.usager
        route = '/demandes_asile/%s/decisions_definitives' % da_instruction_ofpra.pk
        payload = {
            'nature': "CR",
            'date': '2015-09-29T00:00:00',
            'date_premier_accord': '2015-09-29T00:00:00',
            'date_notification': '2015-09-20T00:00:00',
            'entite': 'OFPRA'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]
        self.app.solr.commit(waitFlush=True)

        def callback_agdref(method, url, data=None, headers=None, **kwargs):
            expected = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
 xmlns:maj="http://interieur.gouv.fr/asile/maj">
   <soap:Header/>
   <soap:Body>
      <maj:decisionDefinitiveOFPRACNDARequest>
         <maj:typeFlux>15</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>155300</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <maj:decision>O</maj:decision>
         <maj:typeProtectionAccordee>REF</maj:typeProtectionAccordee>
         <!--Optional:-->
         <maj:desistement></maj:desistement>
         <maj:dateDecision>20150929</maj:dateDecision>
         <maj:dateFinProtectionAccordee>20250929</maj:dateFinProtectionAccordee>
         <!--Optional:-->
         <maj:dateDesistement></maj:dateDesistement>
         <!--Optional:-->
         <maj:dateNotification>20150920</maj:dateNotification>
         <maj:entite>OFPRA</maj:entite>
         <!--Optional:-->
         <maj:numeroSKYPPER></maj:numeroSKYPPER>
         <!--Optional:-->
         <maj:paysExclu1></maj:paysExclu1>
         <!--Optional:-->
         <maj:paysExclu2></maj:paysExclu2>
         <!--Optional:-->
         <maj:paysExclu3></maj:paysExclu3>
      </maj:decisionDefinitiveOFPRACNDARequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:decision',
                'maj:typeProtectionAccordee',
                'maj:desistement',
                'maj:dateDecision',
                'maj:dateFinProtectionAccordee',
                'maj:dateDesistement',
                'maj:dateNotification',
                'maj:entite',
                'maj:numeroSKYPPER',
                'maj:paysExclu1',
                'maj:paysExclu2',
                'maj:paysExclu3',
            ), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>15</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>155300</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>161450</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref))
            return r

        self.callbacks = [callback_agdref, self.callback_get_usager_backend]
        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)
