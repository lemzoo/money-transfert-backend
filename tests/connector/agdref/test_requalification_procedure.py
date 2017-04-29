import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class TestAGDREFConnectorRequalificationProcedure(TestAGDREFConnectorSolr):

    def test_requalification_procedure(self, user, da_attente_ofpra):
        tester = BrokerBox(self.app,
                           e.demande_asile.procedure_requalifiee.name,
                           'agdref_requalification_procedure')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = da_attente_ofpra.usager
        route = '/demandes_asile/%s/requalifications' % da_attente_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'OFPRA',
            'motif_qualification': 'FREM',
            'date_notification': '2000-01-01T00:00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
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
      <maj:requalificationProcedureRequest>
         <maj:typeFlux>14</maj:typeFlux>
         <maj:dateEmissionFlux>20000101</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>170000</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <maj:typeProcedure>A</maj:typeProcedure>
         <maj:dateRequalification>{date_maj}</maj:dateRequalification>
         <maj:dateNotification>20000101</maj:dateNotification>
         <maj:motifRequalification>FREM</maj:motifRequalification>
      </maj:requalificationProcedureRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           date_maj=DATE_MAJ)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:typeProcedure',
                'maj:dateRequalification',
                'maj:dateNotification',
                'maj:motifRequalification',
            ), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>14</typeFlux>
         <dateEmissionFlux>20000101</dateEmissionFlux>
         <heureEmissionFlux>170000</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <datePriseCompteAGDREF>20000101</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>164927</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref, self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)

    def test_requalification_procedure_prefecture(self, user, da_attente_ofpra):
        tester = BrokerBox(self.app,
                           e.demande_asile.procedure_requalifiee.name,
                           'agdref_requalification_procedure')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = da_attente_ofpra.usager
        route = '/demandes_asile/%s/requalifications' % da_attente_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'PREFECTURE',
            'motif_qualification': 'FREM',
            'date_notification': '2015-09-20T00:00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
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
      <maj:requalificationProcedureRequest>
         <maj:typeFlux>03</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>170000</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <maj:typeProcedure>A</maj:typeProcedure>
      </maj:requalificationProcedureRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:typeProcedure',
            ), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>14</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>170000</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>164927</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref,
                          self.callback_get_demandes_asile,
                          self.callback_get_backend,
                          self.callback_get_backend,
                          self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)
