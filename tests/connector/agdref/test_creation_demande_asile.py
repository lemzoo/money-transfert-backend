import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p
from sief.model import Usager


def _prepare_recueil(exploite_pret):
    del exploite_pret.usager_2
    del exploite_pret.enfants
    exploite_pret.usager_1.situation_familiale = 'CELIBATAIRE'
    exploite_pret.usager_1.adresse.chez = 'LUI'
    exploite_pret.usager_1.adresse.numero_voie = '25'
    exploite_pret.usager_1.adresse.voie = 'Rue Rabelais'
    exploite_pret.usager_1.adresse.code_insee = '78190'
    exploite_pret.usager_1.adresse.code_postal = '78000'
    exploite_pret.usager_1.adresse.ville = 'Chatou'
    exploite_pret.usager_1.nom_mere = None
    exploite_pret.usager_1.prenom_mere = None
    exploite_pret.usager_1.nationalites[0].code = 'CIV'
    exploite_pret.usager_1.motif_qualification_procedure = 'AECD'
    exploite_pret.usager_1.type_procedure = 'ACCELEREE'
    exploite_pret.usager_1.condition_entree_france = 'REGULIERE'
    exploite_pret.usager_1.conditions_exceptionnelles_accueil = True
    exploite_pret.usager_1.motif_conditions_exceptionnelles_accueil = 'RELOCALISATION'
    exploite_pret.save()


class TestAGDREFConnectorCreationDemandeAsile(TestAGDREFConnectorSolr):

    def test_creation_premiere_demande_asile(self, user, exploite_pret):
        tester = BrokerBox(
            self.app, e.demande_asile.cree.name, 'agdref_demande_numero_ou_validation')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        _prepare_recueil(exploite_pret)
        r = user_req.post('/recueils_da/%s/exploite' % exploite_pret.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EXPLOITE'
        msgs = tester.get_messages()
        assert len(msgs) == 1
        exploite_pret.structure_guichet_unique.autorite_rattachement.code_departement = '771'
        exploite_pret.structure_guichet_unique.autorite_rattachement.save()
        msg = msgs[0]
        usager = Usager.objects(id=msg.context['usager']['id']).first()
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
         <maj:codeDepartement>771</maj:codeDepartement>
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
         <maj:dateEntreeEnFrance>{date_maj}</maj:dateEntreeEnFrance>
         <maj:dateDepotDemande>{date_maj}</maj:dateDepotDemande>
         <maj:typeProcedure>A</maj:typeProcedure>
         <maj:motifQualification>AECD</maj:motifQualification>
         <maj:dateQualification>{date_maj}</maj:dateQualification>
         <maj:dateNotificationQualification></maj:dateNotificationQualification>
         <maj:conditionEntreeEnFrance>N</maj:conditionEntreeEnFrance>
         <maj:indicateurVisa>O</maj:indicateurVisa>
         <maj:decisionSurAttestation>O</maj:decisionSurAttestation>
         <!--Optional:-->
         <maj:dateDecisionAttestation>{date_maj}</maj:dateDecisionAttestation>
         <!--Optional:-->
         <maj:dateNotificationRefus></maj:dateNotificationRefus>
         <!--Optional:-->
         <maj:motifRefus></maj:motifRefus>
         <maj:origineNom>E</maj:origineNom>
         <!--Optional:-->
         <maj:origineNomUsage></maj:origineNomUsage>
         <maj:NumeroEurodac>{numero_eurodac}</maj:NumeroEurodac>
      </maj:demandeNumeroOuValidationRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           numero_eurodac=usager.identifiants_eurodac[-1],
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
#                'maj:NumeroEurodac'
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

    @pytest.mark.xfail
    def test_creation_reexamen(self, user, exploite_pret):
        tester = BrokerBox(
            self.app, e.demande_asile.cree.name, 'agdref_demande_numero_ou_validation')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        _prepare_recueil(exploite_pret)
        exploite_pret.usager_1.type_demande = 'REEXAMEN'
        exploite_pret.usager_1.numero_reexamen = 1
        exploite_pret.save()
        r = user_req.post('/recueils_da/%s/exploite' % exploite_pret.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EXPLOITE'
        msgs = tester.get_messages()
        assert len(msgs) == 1
        exploite_pret.structure_guichet_unique.autorite_rattachement.code_departement = '771'
        exploite_pret.structure_guichet_unique.autorite_rattachement.save()
        msg = msgs[0]
        usager = Usager.objects(id=msg.context['usager']['id']).first()
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
         <maj:numeroDemandeAsile>02</maj:numeroDemandeAsile>
         <maj:codeDepartement>771</maj:codeDepartement>
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
         <maj:dateEntreeEnFrance>{date_maj}</maj:dateEntreeEnFrance>
         <maj:dateDepotDemande>{date_maj}</maj:dateDepotDemande>
         <maj:typeProcedure>A</maj:typeProcedure>
         <maj:motifQualification>AECD</maj:motifQualification>
         <maj:dateQualification>{date_maj}</maj:dateQualification>
         <maj:dateNotificationQualification></maj:dateNotificationQualification>
         <maj:conditionEntreeEnFrance>N</maj:conditionEntreeEnFrance>
         <maj:indicateurVisa>O</maj:indicateurVisa>
         <maj:decisionSurAttestation>O</maj:decisionSurAttestation>
         <!--Optional:-->
         <maj:dateDecisionAttestation>{date_maj}</maj:dateDecisionAttestation>
         <!--Optional:-->
         <maj:dateNotificationRefus></maj:dateNotificationRefus>
         <!--Optional:-->
         <maj:motifRefus></maj:motifRefus>
         <maj:origineNom>E</maj:origineNom>
         <!--Optional:-->
         <maj:origineNomUsage></maj:origineNomUsage>
         <maj:TypeDemande>RX</maj:TypeDemande>
         <maj:NumeroReexamen>01</maj:NumeroReexamen>
         <maj:NumeroEurodac>{numero_eurodac}</maj:NumeroEurodac>

      </maj:demandeNumeroOuValidationRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref,
                           date_maj=DATE_MAJ,
                           numero_eurodac=usager.identifiants_eurodac[-1])
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
                'maj:TypeDemande',
                'maj:NumeroReexamen',
                'maj:NumeroEurodac'
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
         <numeroDemandeAsile>02</numeroDemandeAsile>
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
