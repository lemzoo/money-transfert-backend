import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class TestAGDREFConnectorRequalificationProcedure(TestAGDREFConnectorSolr):

    def test_enregistrement_demandeur_inerec(self, user, da_attente_ofpra):
        tester = BrokerBox(self.app,
                           e.demande_asile.introduit_ofpra.name,
                           'agdref_enregistrement_demandeur_inerec')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        usager = da_attente_ofpra.usager
        route = '/demandes_asile/%s/introduction_ofpra' % da_attente_ofpra.pk
        r = user_req.post(route, data={'identifiant_inerec': 'inerec_12',
                                       'date_introduction_ofpra': '2015-09-22T00:00:00'})
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
      <maj:enregistrementDemandeurINERECRequest>
         <maj:typeFlux>12</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>153000</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <maj:numeroINEREC>inerec_12</maj:numeroINEREC>
         <maj:dateEnregistrement>20150922</maj:dateEnregistrement>
      </maj:enregistrementDemandeurINERECRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           inerec_id=da_attente_ofpra.identifiant_inerec)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:numeroINEREC',
                'maj:dateEnregistrement'), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>12</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>153000</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>162413</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref, self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)

    @pytest.mark.xfail(reason="agdref is ready to receive the information on REEXAMEN ?")
    def test_enregistrement_demandeur_inerec_reexamen(self, user, da_attente_ofpra):
        tester = BrokerBox(self.app,
                           e.demande_asile.introduit_ofpra.name,
                           'agdref_enregistrement_demandeur_inerec')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name, p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name]
        user.save()
        da_attente_ofpra.type_demande = 'REEXAMEN'
        da_attente_ofpra.numero_reexamen = 1
        da_attente_ofpra.save()
        usager = da_attente_ofpra.usager
        route = '/demandes_asile/%s/introduction_ofpra' % da_attente_ofpra.pk
        r = user_req.post(route, data={'identifiant_inerec': 'inerec_12',
                                       'date_introduction_ofpra': '2015-09-22T01:12:00'})
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
      <maj:enregistrementDemandeurINERECRequest>
         <maj:typeFlux>12</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>153000</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>{number_da}</maj:numeroDemandeAsile>
         <maj:numeroINEREC>inerec_12</maj:numeroINEREC>
         <maj:dateEnregistrement>20150922</maj:dateEnregistrement>
         <maj:heureEnregistrement>01</maj:heureEnregistrement>
         <maj:minureEnregistrement>12</maj:minureEnregistrement>
      </maj:enregistrementDemandeurINERECRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           inerec_id=da_attente_ofpra.identifiant_inerec,
                           number_da=get_da_number(usager))
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:numeroINEREC',
                'maj:dateEnregistrement',
                'maj:heureEnregistrement',
                'maj:minureEnregistrement'), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>12</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>153000</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>{number_da}</numeroDemandeAsile>
         <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>162413</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           number_da=get_da_number(usager)))
            return r
        self.callbacks = [callback_agdref, self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)
