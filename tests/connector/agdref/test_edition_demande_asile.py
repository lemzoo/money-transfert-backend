import pytest

from tests import common
from tests.connector.common import Response, BrokerBox, assert_xml_payloads
from tests.fixtures import *
from tests.connector.agdref.common import *

from sief.events import EVENTS as e
from sief.permissions import POLICIES as p
from sief.model import RecueilDA
from sief.model.recueil_da import Refus


class TestAGDREFConnectorEditionDemandeAsile(TestAGDREFConnectorSolr):

    def test_edition_attestation_demande_asile(self, user, da_prete_ea, site_gu):
        tester = BrokerBox(
            self.app, e.droit.support.cree.name, 'agdref_edition_attestation_demande_asile')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.droit.support.creer.name,
                            p.droit.prefecture_rattachee.sans_limite.name]
        user.save()
        site_gu.autorite_rattachement.code_departement = '771'
        site_gu.autorite_rattachement.save()
        usager = da_prete_ea.usager
        da_prete_ea.procedure.type = 'NORMALE'
        da_prete_ea.procedure.motif_qualification = 'ND31'
        da_prete_ea.save()
        route = '/demandes_asile/%s/attestations' % da_prete_ea.pk
        payload = {
            'date_debut_validite': '2025-09-20T00:00:00',
            'date_fin_validite': '2025-12-19T00:00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        droit_id = r.data['droit']['id']
        r = user_req.post('/droits/%s/supports' % droit_id, data={
            'date_delivrance': '2015-09-23T00:00:00',
            'lieu_delivrance': str(site_gu.pk)})
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
      <maj:editionAttestionDemandeAsileRequest>
         <maj:typeFlux>05</maj:typeFlux>
         <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
         <maj:heureEmissionFlux>155300</maj:heureEmissionFlux>
         <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
         <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
         <maj:numeroDemandeAsile>01</maj:numeroDemandeAsile>
         <!--Optional:-->
         <maj:chez></maj:chez>
         <!--Optional:-->
         <maj:numeroVoie></maj:numeroVoie>
         <!--Optional:-->
         <maj:codeVoie></maj:codeVoie>
         <!--Optional:-->
         <maj:rue></maj:rue>
         <!--Optional:-->
         <maj:codePostal></maj:codePostal>
         <!--Optional:-->
         <maj:ville></maj:ville>
         <maj:typeDocument>ADA</maj:typeDocument>
         <maj:dureeValiditeDocument>0003</maj:dureeValiditeDocument>
         <maj:lieuDelivranceDocument>1</maj:lieuDelivranceDocument>
         <maj:autoriteDelivranceDocument>771</maj:autoriteDelivranceDocument>
         <maj:dateDelivranceDocument>20150923</maj:dateDelivranceDocument>
         <maj:dateDebutValidite>20250920</maj:dateDebutValidite>
         <maj:dateFinValidite>20251219</maj:dateFinValidite>
         <!--Optional:-->
         <maj:numeroDuplicata>00</maj:numeroDuplicata>
      </maj:editionAttestionDemandeAsileRequest>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:chez',
                'maj:numeroVoie',
                'maj:codeVoie',
                'maj:rue',
                'maj:codePostal',
                'maj:ville',
                'maj:typeDocument',
                'maj:dureeValiditeDocument',
                'maj:lieuDelivranceDocument',
                'maj:autoriteDelivranceDocument',
                'maj:dateDelivranceDocument',
                'maj:dateDebutValidite',
                'maj:dateFinValidite',
                'maj:numeroDuplicata'), pop_count=3)
            r = Response(200, """
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
   <soap:Body>
      <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
      xmlns:ns2="http://www.thalesgroup.com/sbna/">
         <typeFlux>05</typeFlux>
         <dateEmissionFlux>20150929</dateEmissionFlux>
         <heureEmissionFlux>155300</heureEmissionFlux>
         <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
         <identifiantSIAsile>{id}</identifiantSIAsile>
         <numeroDemandeAsile>01</numeroDemandeAsile>
         <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
         <heurePriseCompteAGDREF>162205</heurePriseCompteAGDREF>
         <codeErreur>000</codeErreur>
      </notificationResponse>
   </soap:Body>
</soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                           agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref, self.callback_get_backend,
                          self.callback_get_backend, self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)

    @pytest.mark.xfail
    def test_edition_attestation_demande_asile_reexamen(self, user, da_prete_ea, site_gu):
        tester = BrokerBox(
            self.app, e.droit.support.cree.name, 'agdref_edition_attestation_demande_asile')
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.site.voir.name, p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.droit.support.creer.name,
                            p.droit.prefecture_rattachee.sans_limite.name]
        user.save()
        site_gu.autorite_rattachement.code_departement = '771'
        site_gu.autorite_rattachement.save()
        usager = da_prete_ea.usager
        da_prete_ea.procedure.type = 'NORMALE'
        da_prete_ea.procedure.motif_qualification = 'ND31'
        da_prete_ea.type_demande = 'REEXAMEN'
        da_prete_ea.numero_reexamen = 1
        da_prete_ea.save()
        recueil = RecueilDA.objects(id=da_prete_ea.recueil_da_origine.id).first()
        recueil.usager_1.type_demande = 'REEXAMEN'
        recueil.usager_1.numero_reexamen = 1
        recueil.save()

        route = '/demandes_asile/%s/attestations' % da_prete_ea.pk
        payload = {
            'date_debut_validite': '2025-09-20T00:00:00',
            'date_fin_validite': '2025-12-19T00:00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        droit_id = r.data['droit']['id']
        r = user_req.post('/droits/%s/supports' % droit_id, data={
            'date_delivrance': '2015-09-23T00:00:00',
            'lieu_delivrance': str(site_gu.pk)})
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
          <maj:editionAttestionDemandeAsileRequest>
             <maj:typeFlux>05</maj:typeFlux>
             <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
             <maj:heureEmissionFlux>155300</maj:heureEmissionFlux>
             <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
             <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
             <maj:numeroDemandeAsile>02</maj:numeroDemandeAsile>
             <!--Optional:-->
             <maj:chez></maj:chez>
             <!--Optional:-->
             <maj:numeroVoie></maj:numeroVoie>
             <!--Optional:-->
             <maj:codeVoie></maj:codeVoie>
             <!--Optional:-->
             <maj:rue></maj:rue>
             <!--Optional:-->
             <maj:codePostal></maj:codePostal>
             <!--Optional:-->
             <maj:ville></maj:ville>
             <maj:typeDocument>ADA</maj:typeDocument>
             <maj:dureeValiditeDocument>0003</maj:dureeValiditeDocument>
             <maj:lieuDelivranceDocument>1</maj:lieuDelivranceDocument>
             <maj:autoriteDelivranceDocument>771</maj:autoriteDelivranceDocument>
             <maj:dateDelivranceDocument>20150923</maj:dateDelivranceDocument>
             <maj:dateDebutValidite>20250920</maj:dateDebutValidite>
             <maj:dateFinValidite>20251219</maj:dateFinValidite>
             <!--Optional:-->
             <maj:numeroDuplicata>00</maj:numeroDuplicata>
          </maj:editionAttestionDemandeAsileRequest>
       </soap:Body>
    </soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                               agdref_id=usager.identifiant_agdref)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:chez',
                'maj:numeroVoie',
                'maj:codeVoie',
                'maj:rue',
                'maj:codePostal',
                'maj:ville',
                'maj:typeDocument',
                'maj:dureeValiditeDocument',
                'maj:lieuDelivranceDocument',
                'maj:autoriteDelivranceDocument',
                'maj:dateDelivranceDocument',
                'maj:dateDebutValidite',
                'maj:dateFinValidite',
                'maj:numeroDuplicata'), pop_count=3)
            r = Response(200, """
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
       <soap:Body>
          <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
          xmlns:ns2="http://www.thalesgroup.com/sbna/">
             <typeFlux>05</typeFlux>
             <dateEmissionFlux>20150929</dateEmissionFlux>
             <heureEmissionFlux>155300</heureEmissionFlux>
             <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
             <identifiantSIAsile>{id}</identifiantSIAsile>
             <numeroDemandeAsile>01</numeroDemandeAsile>
             <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
             <heurePriseCompteAGDREF>162205</heurePriseCompteAGDREF>
             <codeErreur>000</codeErreur>
          </notificationResponse>
       </soap:Body>
    </soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                               agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref, self.callback_get_backend,
                          self.callback_get_backend, self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)

    @pytest.mark.xfail
    def test_edition_attestation_refus_demande_asile_reexamen(self, user_with_site_affecte, site, exploite_pret_reexamen):
        tester = BrokerBox(
            self.app, e.droit.refus.name, 'agdref_edition_attestation_demande_asile_refus')
        user = user_with_site_affecte

        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name,
                            p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.site.voir.name, p.demande_asile.voir.name,
                            p.demande_asile.editer_attestation.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.droit.support.creer.name,
                            p.droit.prefecture_rattachee.sans_limite.name]
        user.save()
        refus = Refus(motif="why not?")
        exploite_pret_reexamen.usager_1.refus = refus
        exploite_pret_reexamen.save()
        r = user_req.post('/recueils_da/%s/exploite' % exploite_pret_reexamen.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EXPLOITE'
        assert r.data['usager_1']['refus']['motif'] == "why not?"
        exploite_pret_reexamen.reload()
        usager = exploite_pret_reexamen.usager_1.usager_existant
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
          <maj:editionAttestionDemandeAsileRequest>
             <maj:typeFlux>05</maj:typeFlux>
             <maj:dateEmissionFlux>20150929</maj:dateEmissionFlux>
             <maj:heureEmissionFlux>155300</maj:heureEmissionFlux>
             <maj:numeroRessortissantEtranger>{agdref_id}</maj:numeroRessortissantEtranger>
             <maj:identifiantSIAsile>{id}</maj:identifiantSIAsile>
             <maj:numeroDemandeAsile>02</maj:numeroDemandeAsile>
             <maj:dateNotificationRefus>{date_refus:%Y%m%d}</maj:dateNotificationRefus>
             <maj:motifRefus>why not?</maj:motifRefus>
          </maj:editionAttestionDemandeAsileRequest>
       </soap:Body>
    </soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                               agdref_id=usager.identifiant_agdref,
                               date_refus=refus.date_notification)
            assert_xml_payloads(data, expected, fields=(
                'maj:typeFlux',
                'maj:numeroRessortissantEtranger',
                'maj:identifiantSIAsile',
                'maj:numeroDemandeAsile',
                'maj:dateNotificationRefus',
                'maj:motifRefus'
            ), pop_count=3)
            r = Response(200, """
    <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
       <soap:Body>
          <notificationResponse xmlns="http://interieur.gouv.fr/asile/maj"
          xmlns:ns2="http://www.thalesgroup.com/sbna/">
             <typeFlux>05</typeFlux>
             <dateEmissionFlux>20150929</dateEmissionFlux>
             <heureEmissionFlux>155300</heureEmissionFlux>
             <numeroRessortissantEtranger>{agdref_id}</numeroRessortissantEtranger>
             <identifiantSIAsile>{id}</identifiantSIAsile>
             <numeroDemandeAsile>01</numeroDemandeAsile>
             <datePriseCompteAGDREF>20150929</datePriseCompteAGDREF>
             <heurePriseCompteAGDREF>162205</heurePriseCompteAGDREF>
             <codeErreur>000</codeErreur>
          </notificationResponse>
       </soap:Body>
    </soap:Envelope>""".format(id=usager.identifiant_portail_agdref,
                               agdref_id=usager.identifiant_agdref))
            return r
        self.callbacks = [callback_agdref,
                          self.callback_get_usager_backend]

        self.mock_requests.callback_response = self.callback
        tester.event_handler.execute_legacy(msg)
