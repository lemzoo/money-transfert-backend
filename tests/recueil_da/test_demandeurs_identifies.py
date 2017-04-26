import pytest
from datetime import datetime
import copy

from tests import common
from tests.fixtures import *

from sief.model.recueil_da import RecueilDA, RendezVousGu
from sief.model.demande_asile import DemandeAsile
from sief.model.usager import Usager
from sief.permissions import POLICIES as p


@pytest.fixture
def demandeurs_identifies(demandeurs_identifies_pret):
    demandeurs_identifies_pret.controller.identifier_demandeurs()
    demandeurs_identifies_pret.save()
    return demandeurs_identifies_pret


@pytest.fixture
def exploite_pret(demandeurs_identifies):
    recueil = demandeurs_identifies
    recueil.usager_1.type_procedure = 'NORMALE'
    recueil.usager_1.motif_qualification_procedure = 'NECD'
    recueil.usager_1.condition_entree_france = 'REGULIERE'
    recueil.usager_1.conditions_exceptionnelles_accueil = False
    recueil.usager_1.visa = 'C'
    recueil.usager_1.indicateur_visa_long_sejour = True
    recueil.usager_1.decision_sur_attestation = True
    recueil.usager_1.date_decision_sur_attestation = datetime.utcnow()
    recueil.usager_2.type_procedure = 'ACCELEREE'
    recueil.usager_2.motif_qualification_procedure = 'REEX'
    recueil.usager_2.condition_entree_france = 'IRREGULIERE'
    recueil.usager_2.conditions_exceptionnelles_accueil = True
    recueil.usager_2.motif_conditions_exceptionnelles_accueil = "RELOCALISATION"
    recueil.usager_2.visa = 'AUCUN'
    recueil.usager_2.indicateur_visa_long_sejour = False
    recueil.usager_2.decision_sur_attestation = False
    recueil.usager_2.date_decision_sur_attestation = datetime.utcnow()
    recueil.enfants[0].present_au_moment_de_la_demande = False
    recueil.enfants[1].present_au_moment_de_la_demande = True
    recueil.identifiant_famille_dna = 'dummy-id'
    recueil.save()
    return recueil

@pytest.fixture
def exploite_pret_reexamen(exploite_pret):
    recueil = exploite_pret
    recueil.usager_1.type_demande = 'REEXAMEN'
    recueil.usager_1.numero_reexamen = 1
    recueil.save()
    return recueil

def update_payload_pa_fini(payload, data, usager):
    payload['usager_1']['identifiant_agdref'] = \
    data['usager_1']['identifiant_agdref']
    payload['usager_1']['identifiant_portail_agdref'] = \
        data['usager_1']['identifiant_portail_agdref']
    payload['usager_1']['date_enregistrement_agdref'] = \
        data['usager_1']['date_enregistrement_agdref']
    payload['usager_1']['demandeur'] = True
    payload['usager_1']['type_procedure'] = 'DUBLIN'
    payload['usager_1']['motif_qualification_procedure'] = 'EAEA'
    payload['usager_1']['nom'] = 'Punch Plantagenêt'
    payload['usager_1']['date_naissance'] = "1985-02-02 23:00:00+00:00"
    # We even can totally replace an usager by another...
    payload['enfants'][0] = {'usager_existant': str(usager.pk),
                             'demandeur': True,
                             'present_au_moment_de_la_demande': True,
                             'date_depart': datetime(2015, 8, 18),
                             'date_depart_approximative': False,
                             'date_entree_en_france': datetime(2015, 8, 20),
                             'date_entree_en_france_approximative': False,
                             'identite_approchante_select': True,
                             'identifiant_eurodac': 'euro-56789'
                             }
    # ...as long as it has it agdref stuff valid
    usager.identifiant_agdref = '0123456789'
    usager.date_enregistrement_agdref = datetime.utcnow()
    usager.save()
    payload['usager_2']['demandeur'] = False
    # Remove fields not allowed for non demandeurs
    for field in ('pays_traverses', 'date_entree_en_france',
                  'date_entree_en_france_approximative',
                  'date_depart', 'date_depart_approximative',
                  'photo', 'photo_premier_accueil'):
        if field in payload['usager_2']:
            del payload['usager_2'][field]
    payload['enfants'][1]['demandeur'] = False

    return payload

class TestRecueilDA_DemandeursIdentifies(common.BaseTest):

    def test_get_recueil_da(self, user, demandeurs_identifies):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/recueils_da')
        assert r.status_code == 403, r
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        r = user_req.get(route)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name]
        user.save()
        r = user_req.get('/recueils_da')
        assert r.status_code == 200, r
        r = user_req.get(route)
        assert r.status_code == 200, r

    def test_get_links(self, user, demandeurs_identifies):
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent'))
        user.permissions.append(p.recueil_da.modifier_demandeurs_identifies.name)
        user.permissions.append(p.historique.voir.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'parent', 'replace',
                                'exploiter', 'annuler', 'history'))

    def test_cant_delete(self, user, demandeurs_identifies):
        # Only brouillons can be deleted
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        user.permissions = [p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        r = user_req.delete(route)
        assert r.status_code == 400, r

    def test_switch_to_exploite(self, user, exploite_pret, ref_pays, ref_nationalites, ref_langues_ofpra, ref_langues_iso):
        # Slight modification : usager_2 already exists in the database
        from sief.model.usager import Usager
        from sief.model.recueil_da import UsagerSecondaireRecueil
        from sief.model.fichier import Fichier
        from sief.model.demande_asile import PaysTraverse
        photo = Fichier(name='photo.png').save()
        u2_usager = Usager(
            nom=exploite_pret.usager_2.nom,
            origine_nom='EUROPE',
            prenoms=exploite_pret.usager_2.prenoms,
            sexe=exploite_pret.usager_2.sexe,
            pays_naissance=ref_pays[0].to_embedded(),
            date_naissance=datetime(1950, 8, 22),
            nationalites=[ref_nationalites[0].to_embedded()],
            ville_naissance="Pondichery",
            situation_familiale='MARIE',
            photo=str(photo.pk),
            langues=(ref_langues_iso[0].to_embedded(),),
            langues_audition_OFPRA=(ref_langues_ofpra[0].to_embedded(),),
            identifiant_agdref=exploite_pret.usager_2.identifiant_agdref,
            identifiant_portail_agdref=exploite_pret.usager_2.identifiant_portail_agdref,
            date_enregistrement_agdref=exploite_pret.usager_2.date_enregistrement_agdref
        ).save()
        exploite_pret.usager_2 = UsagerSecondaireRecueil(
            usager_existant=u2_usager,
            identifiant_eurodac=exploite_pret.usager_2.identifiant_eurodac,

            type_procedure=exploite_pret.usager_2.type_procedure,
            motif_qualification_procedure=exploite_pret.usager_2.motif_qualification_procedure,
            condition_entree_france=exploite_pret.usager_2.condition_entree_france,
            conditions_exceptionnelles_accueil=exploite_pret.usager_2.conditions_exceptionnelles_accueil,
            motif_conditions_exceptionnelles_accueil=exploite_pret.usager_2.motif_conditions_exceptionnelles_accueil,
            visa=exploite_pret.usager_2.visa,
            indicateur_visa_long_sejour=exploite_pret.usager_2.indicateur_visa_long_sejour,
            decision_sur_attestation=exploite_pret.usager_2.decision_sur_attestation,
            date_decision_sur_attestation=exploite_pret.usager_2.date_decision_sur_attestation,
            present_au_moment_de_la_demande=True,
            demandeur=True,
            date_entree_en_france=datetime(1152, 1, 1),
            date_depart=datetime(1152, 1, 1),
            date_depart_approximative=False,
            date_entree_en_france_approximative=False,
            pays_traverses=[PaysTraverse(
                pays=ref_pays[0].to_embedded(),
                date_entree=datetime(2015, 8, 15),
                date_entree_approximative=False,
                date_sortie=datetime(2015, 8, 20),
                date_sortie_approximative=True,
                moyen_transport="Pied"
            )],
            identite_approchante_select=True
        )
        exploite_pret.save()
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.prefecture_rattachee.sans_limite.name,
                            p.demande_asile.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        r = user_req.post('/recueils_da/%s/exploite' % exploite_pret.pk)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EXPLOITE'
        # Check for Usager/DemandeAsile creations
        u1 = r.data['usager_1']
        u2 = r.data['usager_2']
        user.permissions.append(p.usager.voir.name)
        user.permissions.append(p.demande_asile.voir.name)
        user.save()
        recueil_data = r.data
        assert recueil_data.get('identifiant_famille_dna')
        # Check the new Usager has been created

        def check_usager(u):
            r = user_req.get(u['usager_existant']['_links']['self'])
            assert r.data['identifiant_famille_dna'] == recueil_data['identifiant_famille_dna']
            assert r.data['nom'] == u['nom']
            assert r.data['prenoms'] == u['prenoms']
            if u.get('demandeur'):
                assert r.data['origine_nom'] == u['origine_nom']
                assert r.data['identifiant_agdref'] == u['identifiant_agdref']
                assert r.data['identifiant_portail_agdref'] == u['identifiant_portail_agdref']
                assert r.data['date_enregistrement_agdref'] == u['date_enregistrement_agdref']
        check_usager(u1)
        for child in recueil_data['enfants']:
            check_usager(child)
            assert 'demande_asile_resultante' not in child
        # Usager2 already existed, should not have changed
        assert u2['usager_existant']['id'] == u2_usager.pk
        # Same thing for DemandeAsile
        r = user_req.get(u1['demande_asile_resultante']['_links']['self'])
        r.data['usager']['_links']['self'] == recueil_data[
            'usager_1']['usager_existant']['_links']['self']
        assert r.data['type_demandeur'] == 'PRINCIPAL'
        assert r.data['date_entree_en_france'] == u1['date_entree_en_france']
        assert r.data['date_depart'] == u1['date_depart']
        assert r.data['date_depart_approximative'] == u1['date_depart_approximative']
        assert r.data['date_entree_en_france_approximative'] ==  \
            u1['date_entree_en_france_approximative']
        # All the children present_au_moment_de_la_demande are linked to the PRINCIPAL
        linked_children = []
        for child in recueil_data['enfants']:
            if child.get('present_au_moment_de_la_demande'):
                linked_children.append(child)
        enfants_presents = r.data.get('enfants_presents_au_moment_de_la_demande', [])
        assert len(enfants_presents) == len(linked_children)
        for enfant in enfants_presents:
            for linked_child in linked_children:
                if (linked_child['usager_existant']['_links']['self'] ==
                        enfant['_links']['self']):
                    break
            assert linked_child, 'Not found %s' % enfant
        r = user_req.get(u2['demande_asile_resultante']['_links']['self'])
        r.data['usager']['_links']['self'] == recueil_data[
            'usager_2']['usager_existant']['_links']['self']
        assert r.data['type_demandeur'] == 'CONJOINT'
        # No children linked to the CONJOINT
        assert 'enfants_presents_au_moment_de_la_demande' not in r.data

    def test_invalid_switches(self, user, exploite_pret):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.creer_brouillon.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_brouillon.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.recueil_da.modifier_exploite.name,
                            p.recueil_da.purger.name]
        user.save()
        route = '/recueils_da/%s' % exploite_pret.pk
        from tests.test_rendez_vous import add_free_creneaux
        creneaux = add_free_creneaux(4, exploite_pret.structure_accueil.guichets_uniques[0])

        r = user_req.put(
            route + '/pa_realise', data={'creneaux': [creneaux[0]['id'], creneaux[1]['id']]})
        assert r.status_code == 400, r
        for action in ['demandeurs_identifies', 'purge']:
            r = user_req.post(route + '/' + action)
            assert r.status_code == 400, r

    def test_good_update_usager(self, user, demandeurs_identifies,
                                payload_pa_fini, usager):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.test_set_accreditation(site_affecte=demandeurs_identifies.structure_accueil)
        user.save()
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        # As long as the agdref informations stay filled, we can modify
        # everything in the recueil_da's usagers
        r = user_req.get(route)
        assert r.status_code == 200, r

        payload = update_payload_pa_fini(payload_pa_fini, r.data, usager)
        r = user_req.put(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['usager_1']['nom'] == 'Punch Plantagenêt'
        assert 'nom' not in r.data['enfants'][0]
        assert 'prenoms' not in r.data['enfants'][0]
        assert r.data['enfants'][0]['usager_existant']['id'] == usager.pk

    def test_update_usager_with_refus(self, user, demandeurs_identifies,
                                payload_pa_fini, usager):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.test_set_accreditation(site_affecte=demandeurs_identifies.structure_accueil)
        user.save()
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        # As long as the agdref informations stay filled, we can modify
        # everything in the recueil_da's usagers
        r = user_req.get(route)
        assert r.status_code == 200, r
        payload = update_payload_pa_fini(payload_pa_fini, r.data, usager)
        payload['usager_1']['refus'] = {'motif' : "DEPOT_DEUXIEME_DEMANDE_REEXAMEN"}
        r = user_req.put(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['usager_1']['refus']['motif'] == "DEPOT_DEUXIEME_DEMANDE_REEXAMEN"
        payload['usager_1']['refus'] = {'motif' : "DEPOT_TROISIEME_DEMANDE_REEXAMEN", 'date_notification' : "2016-11-16T00:00:00Z"}
        r = user_req.put(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['usager_1']['refus']['motif'] == "DEPOT_TROISIEME_DEMANDE_REEXAMEN"

    def test_bad_update_usager(self, user, demandeurs_identifies,
                               payload_pa_fini, usager):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.test_set_accreditation(site_affecte=demandeurs_identifies.structure_accueil)
        user.save()
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        # Cannot modify some usager's information
        r = user_req.get(route)
        assert r.status_code == 200, r
        payload_pa_fini['usager_2']['demandeur'] = False
        payload_pa_fini['usager_2']['present_au_moment_de_la_demande'] = True
        payload_pa_fini['usager_1']['demandeur'] = True
        payload_pa_fini['usager_1']['present_au_moment_de_la_demande'] = True
        payload_pa_fini['usager_1']['identifiant_agdref'] = 'id-agdref-1'
        payload_pa_fini['usager_1']['date_enregistrement_agdref'] = \
            datetime.utcnow()
        payload_pa_fini['enfants'][0]['identifiant_agdref'] = 'id-agdref-e1'
        payload_pa_fini['enfants'][0]['date_enregistrement_agdref'] = \
            datetime.utcnow()
        payload_pa_fini['enfants'][0]['demandeur'] = True
        payload_pa_fini['enfants'][0]['present_au_moment_de_la_demande'] = True
        payload_pa_fini['enfants'][1]['demandeur'] = False
        usager.identifiant_agdref = None
        usager.date_enregistrement_agdref = None
        usager.save()
        for key, value in (
            ('usager_1', {'usager_existant': str(usager.pk),
                          'demandeur': True}),
            ('usager_1.present_au_moment_de_la_demande', common.NOT_SET),
            ('usager_1.present_au_moment_de_la_demande', False),
            ('enfants.0.identifiant_agdref', common.NOT_SET),
            ('enfants.0.present_au_moment_de_la_demande', common.NOT_SET),
            ('enfants.0.present_au_moment_de_la_demande', False),
            ('enfants.0.date_enregistrement_agdref', common.NOT_SET),
        ):
            payload = copy.deepcopy(payload_pa_fini)
            common.update_payload(payload, key, value)
            r = user_req.put(route, data=payload)
            assert r.status_code == 400, (key, value)

    def test_bad_update(self, user, demandeurs_identifies, payload_pa_fini):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.voir.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.test_set_accreditation(site_affecte=demandeurs_identifies.structure_accueil)
        user.save()
        route = '/recueils_da/%s' % demandeurs_identifies.pk
        for key, value in (('usager_1', None), ('usager_1', common.NOT_SET),
                           ('usager_1', {}), ('usager_2', common.NOT_SET)):
            payload = copy.deepcopy(payload_pa_fini)
            common.update_payload(payload, key, value)
            r = user_req.put(route, data=payload)
            assert r.status_code == 400, r


class TestRecueilDA_DemandeursIdentifies_BadSwitch(common.BaseTest):

    def test_bad_switch_to_exploite(self, user, demandeurs_identifies):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_demandeurs_identifies.name]
        user.save()
        recueil_da = demandeurs_identifies
        # Try to switch when nothing is ready...
        r = user_req.post('/recueils_da/%s/exploite' % recueil_da.pk)
        assert r.status_code == 400, r
        recueil_da.reload()
        assert recueil_da.statut == 'DEMANDEURS_IDENTIFIES'
        # Make sure nothing has been created
        assert Usager.objects.count() == 0
        assert DemandeAsile.objects.count() == 0
        recueil_da = exploite_pret(recueil_da)
        saved_dna_id = recueil_da.identifiant_famille_dna
        recueil_da.save()
        # Next try, everything is ok except a little thing
        recueil_da.identifiant_famille_dna = saved_dna_id
        saved_name = recueil_da.enfants[0].nom
        recueil_da.enfants[0].nom = None
        recueil_da.save(clean=False)
        r = user_req.post('/recueils_da/%s/exploite' % recueil_da.pk)
        assert r.status_code == 400, r
        recueil_da.reload()
        assert recueil_da.statut == 'DEMANDEURS_IDENTIFIES'
        # Again nothing should have been created (even all the valid usagers)
        assert Usager.objects.count() == 0
        assert DemandeAsile.objects.count() == 0
        # motif_qualification is mandatory
        motif_saved = recueil_da.usager_1.motif_qualification_procedure
        recueil_da.enfants[0].nom = saved_name
        recueil_da.usager_1.motif_qualification_procedure = None
        recueil_da.save()
        r = user_req.post('/recueils_da/%s/exploite' % recueil_da.pk)
        assert r.status_code == 400, r
        recueil_da.reload()
        assert recueil_da.statut == 'DEMANDEURS_IDENTIFIES'
        # Again nothing should have been created (even all the valid usagers)
        assert Usager.objects.count() == 0
        assert DemandeAsile.objects.count() == 0
        # Finally make sure default case succeed
        recueil_da.usager_1.motif_qualification_procedure = motif_saved
        recueil_da.save()
        r = user_req.post('/recueils_da/%s/exploite' % recueil_da.pk)
        assert r.status_code == 200, r
        recueil_da.reload()
        assert recueil_da.statut == 'EXPLOITE'
        # Again nothing should have been created (even all the valid usagers)
        assert Usager.objects.count() == 4
        assert DemandeAsile.objects.count() == 2

