import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class TestAGDREFConnector(TestAGDREFConnectorSolr):

    def test_reconstitution_etat_civil_OFPRA(self, user, usager_agdref, ref_pays, ref_nationalites):
        usager = usager_agdref
        tester = BrokerBox(
            self.app, e.usager.etat_civil.valide.name, 'agdref_reconstitution_etat_civil_OFPRA')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.etat_civil.valider.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        payload = {
            'nom': 'Assimbe',
            'nom_usage': 'Roux',
            'prenoms': ["Louise", "Céline"],
            'nationalites': ['CIV'],
            'situation_familiale': 'VEUF',
            'sexe': 'F',
            'ville_naissance': 'Basse-Pointe',
            'photo': None,
            'pays_naissance': 'CIV',
            "date_naissance": '1990-12-12T00:00:00',
            'date_naissance_approximative': False,
            'ville_naissance': 'Braslou'
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
      <maj:reconstitutionEtatCivilOFPRARequest>
         <maj:typeFlux>16</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>161000</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <maj:etatCivilValide>O</maj:etatCivilValide>
         <maj:nomEpouse>ROUX</maj:nomEpouse>
         <maj:prenoms>LOUISE CELINE</maj:prenoms>
         <maj:sexe>F</maj:sexe>
         <maj:nomNaissance>ASSIMBE</maj:nomNaissance>
         <maj:dateNaissance>19901212</maj:dateNaissance>
         <maj:paysNaissance>CI</maj:paysNaissance>
         <!--Optional:-->
         <maj:villeNaissance>BRASLOU</maj:villeNaissance>
         <maj:nationalite>CI </maj:nationalite>
         <!--Optional:-->
         <maj:enfantDeRefugie>N</maj:enfantDeRefugie>
      </maj:reconstitutionEtatCivilOFPRARequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:etatCivilValide',
                'maj:nomEpouse',
                'maj:prenoms',
                'maj:sexe',
                'maj:nomNaissance',
                'maj:dateNaissance',
                'maj:paysNaissance',
                'maj:villeNaissance',
                'maj:nationalite',
                'maj:enfantDeRefugie',
            ), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
       xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>16</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>161000</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile></numeroDemandeAsile>
         <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>164739</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref, self.callback_get_usager_backend]
        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)
