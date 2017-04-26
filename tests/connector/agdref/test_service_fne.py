import pytest
from datetime import datetime, timedelta
import xmltodict

from tests import common
from tests.fixtures import *
from tests.connector.common import Response, BrokerBox, MockRequests, assert_xml_payloads
from services.agdref import enregistrement_agdref
from tests.connector.agdref.common import usager_agdref, DATE_MAJ
from sief.events import EVENTS as e
from sief.permissions import POLICIES as p


class TestAGDREFService(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'AGDREF_NUM_REQUESTS': cls.mock_requests,
            'AGDREF_NUM_TESTING_STUB': False,
            'AGDREF_NUM_URL': 'http://agdref.fr/num'
        })

    def test_demande_request(self, demandeurs_identifies_pret):
        code_departement = '771'
        usager = demandeurs_identifies_pret.usager_1
        usager.identifiant_portail_agdref = 'stub'
        del demandeurs_identifies_pret.usager_2
        del demandeurs_identifies_pret.enfants
        demandeurs_identifies_pret.usager_1.situation_familiale = 'CELIBATAIRE'
        demandeurs_identifies_pret.usager_1.adresse.chez = 'LUI'
        demandeurs_identifies_pret.usager_1.adresse.numero_voie = '25'
        demandeurs_identifies_pret.usager_1.adresse.voie = 'Rue Rabelais'
        demandeurs_identifies_pret.usager_1.adresse.code_insee = '78190'
        demandeurs_identifies_pret.usager_1.adresse.code_postal = '78000'
        demandeurs_identifies_pret.usager_1.adresse.ville = 'Chatou'
        demandeurs_identifies_pret.usager_1.nom_mere = None
        demandeurs_identifies_pret.usager_1.prenom_mere = None
        demandeurs_identifies_pret.usager_1.nationalites[0].code = 'CIV'
        demandeurs_identifies_pret.usager_1.motif_qualification_procedure = 'FRIF'
        demandeurs_identifies_pret.usager_1.type_procedure = 'NORMALE'
        demandeurs_identifies_pret.save()
        identifiant_portail_agdref = None

        def callback(method, url, data=None, headers=None, **kwargs):
            nonlocal identifiant_portail_agdref
            expected = """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" xmlns:maj="http://interieur.gouv.fr/asile/maj">
   <soap:Header/>
   <soap:Body>
      <maj:demandeNumeroOuValidationRequest>
         <maj:typeFlux>03</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>170300</maj:heureEmissionFlux>
         <!--Optional:-->
         <maj:numeroRessortissantEtranger></maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>cannot check me here</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>00</maj:numeroDemandeAsile>
         <maj:codeDepartement>{code_departement}</maj:codeDepartement>
         <maj:nomRessortissantEtranger>PLANTAGENET</maj:nomRessortissantEtranger>
         <maj:prenomRessortissantEtranger>GEOFFROY V</maj:prenomRessortissantEtranger>
         <maj:sexe>M</maj:sexe>
         <maj:nomUsage></maj:nomUsage>
         <maj:dateDeNaissance>19130824</maj:dateDeNaissance>
         <maj:paysDeNaissance>ZUK</maj:paysDeNaissance>
         <maj:villeDeNaissance>CHATEAU-DU-LOIR</maj:villeDeNaissance>
         <maj:situationMatrimoniale>C</maj:situationMatrimoniale>
         <maj:nationalite>CI </maj:nationalite>
         <maj:nomPere>V D'ANJOU</maj:nomPere>
         <maj:prenomPere>FOULQUE</maj:prenomPere>
         <maj:nomMere>INC</maj:nomMere>
         <maj:prenomMere>INC</maj:prenomMere>
         <!--Optional:-->
         <maj:chez>LUI</maj:chez>
         <!--Optional:-->
         <maj:typeDeVoie>RUE</maj:typeDeVoie>
         <!--Optional:-->
         <maj:numeroVoie>25</maj:numeroVoie>
         <!--Optional:-->
         <maj:rue>RABELAIS</maj:rue>
         <!--Optional:-->
         <maj:codePostal>78000</maj:codePostal>
         <!--Optional:-->
         <maj:ville>CROISSY S SEINE</maj:ville>
         <maj:dateEntreeEnFrance>{maj}</maj:dateEntreeEnFrance>
         <maj:dateDepotDemande></maj:dateDepotDemande>
         <maj:typeProcedure></maj:typeProcedure>
         <maj:motifQualification></maj:motifQualification>
         <maj:dateQualification></maj:dateQualification>
         <maj:dateNotificationQualification></maj:dateNotificationQualification>
         <maj:conditionEntreeEnFrance></maj:conditionEntreeEnFrance>
         <maj:indicateurVisa></maj:indicateurVisa>
         <maj:decisionSurAttestation></maj:decisionSurAttestation>
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
</soap:Envelope>""".format(id=identifiant_portail_agdref,
                           code_departement=code_departement, maj=DATE_MAJ)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
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
            identifiant_portail_agdref = data.split(
                '<maj:identifiantSIAsile>', 1)[1].split('<', 1)[0]
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <demandeNumeroOuValidationResponse xmlns="http://interieur.gouv.fr/asile/maj" xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>03</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>170300</heureEmissionFlux>
         <numeroRessortissantEtranger>7777777777</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <dateEnregistrementAGDREF>20150929</dateEnregistrementAGDREF>
         <heureEnregistrementAGDREF>170210</heureEnregistrementAGDREF>
         <codeErreur>000</codeErreur>
      </demandeNumeroOuValidationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=identifiant_portail_agdref))
            return r

        self.mock_requests.callback_response = callback
        agdref_info = enregistrement_agdref(usager, code_departement)
        assert agdref_info.identifiant_agdref == '7777777777'
        assert agdref_info.identifiant_portail_agdref == identifiant_portail_agdref
        assert agdref_info.date_enregistrement_agdref == datetime(2015, 9, 29, 17, 2, 10)

    def test_demande_request(self, ref_insee_agdref):
        from services.fne import FNELookup
        assert FNELookup()._get_code_insee(ref_insee_agdref[0].libelle) == ref_insee_agdref[0].code
        assert FNELookup()._get_code_insee('PARIS17', '75017') == '75117'
        assert FNELookup()._get_code_insee('PARIS17') == '75117'
        assert FNELookup()._get_code_insee('PARIS', '75017') == '75117'
        assert FNELookup()._get_code_insee('PARIS') == '00000'


class TestAGDREFServicePartial(common.BaseLegacyBrokerTest):

    @classmethod
    def setup_class(cls):
        cls.mock_requests = MockRequests()
        super().setup_class(config={
            'AGDREF_NUM_REQUESTS': cls.mock_requests,
            'AGDREF_NUM_TESTING_STUB': False,
            'CONNECTOR_AGDREF_PARTIAL': True,
            'AGDREF_NUM_URL': 'http://127.0.0.1/',
        })

    def test_skipped_message(self, user, usager_agdref, ref_pays, ref_nationalites):
        usager = usager_agdref
        tester = BrokerBox(self.app, e.usager.etat_civil.valide.name,
                           'agdref_reconstitution_etat_civil_OFPRA',
                           True)
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
            'ville_naissance': 'Braslou',
            'photo': None,
            'pays_naissance': 'CIV',
            "date_naissance": '1990-12-12T00:00:00',
            'date_naissance_approximative': False
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        msgs = tester.get_messages()
        assert len(msgs) == 1
        msg = msgs[0]
        tester.broker_dispatcher.event_handler.execute_legacy(msg)
        assert msg.status == 'SKIPPED'
