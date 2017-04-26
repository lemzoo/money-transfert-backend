import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class TestAGDREFConnectorMajEtatCivil(TestAGDREFConnectorSolr):

    def test_agdref_maj_etat_civil(self, user, da_orientation, ref_nationalites):
        usager = da_orientation.usager
        tester = BrokerBox(
            self.app, e.usager.etat_civil.modifie.name, 'agdref_demande_numero_ou_validation')
        # Generate event
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.usager.voir.name, p.usager.modifier.name,
                            p.usager.modifier.name, p.usager.etat_civil.modifier.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        nat = ref_nationalites[1]
        msgs = tester.get_messages()
        # Need permission to do it
        route = '/usagers/{}/etat_civil'.format(usager.pk)
        payload = {'nom': 'Caesaire',
                   'nationalites': [{'code': str(nat.pk)}]}
        user_req.patch(route, data=payload)
        # Check the presence&validity of the message
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
      <maj:demandeNumeroOuValidationRequest>
         <maj:typeFlux>03</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>170300</maj:heureEmissionFlux>
         <!--Optional:-->
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <maj:codeDepartement>331</maj:codeDepartement>
         <maj:nomRessortissantEtranger>CAESAIRE</maj:nomRessortissantEtranger>
         <maj:prenomRessortissantEtranger>GEOFFROY V</maj:prenomRessortissantEtranger>
         <maj:sexe>M</maj:sexe>
         <maj:nomUsage></maj:nomUsage>
         <maj:dateDeNaissance>19130824</maj:dateDeNaissance>
         <maj:paysDeNaissance>ZUK</maj:paysDeNaissance>
         <maj:villeDeNaissance>CHATEAU-DU-LOIR</maj:villeDeNaissance>
         <maj:situationMatrimoniale>C</maj:situationMatrimoniale>
         <maj:nationalite>INC</maj:nationalite>
         <maj:nomPere>V D'ANJOU</maj:nomPere>
         <maj:prenomPere>FOULQUE</maj:prenomPere>
         <maj:nomMere>EREMBOURGE</maj:nomMere>
         <maj:prenomMere>DU MAINE</maj:prenomMere>
         <maj:dateEntreeEnFrance>{date_maj}</maj:dateEntreeEnFrance>
         <maj:dateDepotDemande>{date_maj}</maj:dateDepotDemande>
         <maj:typeProcedure>N</maj:typeProcedure>
         <maj:motifQualification>NECD</maj:motifQualification>
         <maj:dateQualification>{date_maj}</maj:dateQualification>
         <maj:dateNotificationQualification></maj:dateNotificationQualification>
         <maj:conditionEntreeEnFrance>N</maj:conditionEntreeEnFrance>
         <maj:indicateurVisa>N</maj:indicateurVisa>
         <maj:decisionSurAttestation>N</maj:decisionSurAttestation>
         <!--Optional:-->
         <maj:dateDecisionAttestation></maj:dateDecisionAttestation>
         <!--Optional:-->
         <maj:dateNotificationRefus></maj:dateNotificationRefus>
         <!--Optional:-->
         <maj:motifRefus></maj:motifRefus>
         <maj:origineNom>E</maj:origineNom>
         <!--Optional:-->
         <maj:origineNomUsage></maj:origineNomUsage>
      </maj:demandeNumeroOuValidationRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           date_maj=DATE_MAJ)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:codeDepartement',
                'maj:nomRessortissantEtranger',
                'maj:prenomRessortissantEtranger',
                'maj:sexe',
                'maj:nomUsage',
                'maj:dateDeNaissance',
                'maj:paysDeNaissance',
                'maj:villeDeNaissance',
                'maj:situationMatrimoniale',
                'maj:nationalite',
                'maj:nomPere',
                'maj:prenomPere',
                'maj:nomMere',
                'maj:prenomMere',
                'maj:chez',
                'maj:typeDeVoie',
                'maj:numeroVoie',
                'maj:rue',
                'maj:codePostal',
                'maj:ville',
                'maj:dateEntreeEnFrance',
                'maj:dateDepotDemande',
                'maj:typeProcedure',
                'maj:motifQualification',
                'maj:dateQualification',
                'maj:dateNotificationQualification',
                'maj:conditionEntreeEnFrance',
                'maj:indicateurVisa',
                'maj:decisionSurAttestation',
                'maj:dateDecisionAttestation',
                'maj:dateNotificationRefus',
                'maj:motifRefus',
                'maj:origineNom',
                'maj:origineNomUsage',
            ), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <demandeNumeroOuValidationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>03</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>170300</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <dateEnregistrementAGDREF>20150929</dateEnregistrementAGDREF>
         <heureEnregistrementAGDREF>170210</heureEnregistrementAGDREF>
         <codeErreur>000</codeErreur>
      </demandeNumeroOuValidationResponse>
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
        assert not self.callbacks
