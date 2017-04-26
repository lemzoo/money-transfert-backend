from datetime import datetime

from tests import common
from tests.fixtures import *

from sief.permissions import POLICIES as p


class TestRecueilDAReexamenExploite(common.BaseLegacyBrokerTest):

    def test_reexamen_reouverture(self, user, usager, site_gu, photo,
                                  ref_pays, ref_langues_ofpra,
                                  ref_langues_iso, ref_nationalites):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_gu)
        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.demande_asile.voir.name]
        user.save()
        payload = {
            'usager_1': {
                'date_entree_en_france': datetime(1952, 1, 1),
                'date_depart': datetime(1952, 1, 1),
                'date_depart_approximative': False,
                'date_entree_en_france_approximative': False,
                'nom': 'Plantagenêt', 'prenoms': ['Geoffroy', 'V'], 'sexe': 'M',
                'origine_nom': 'EUROPE',
                'photo': str(photo.id),
                'acceptation_opc': False,
                'date_naissance': datetime(1913, 8, 24),
                "pays_naissance": str(ref_pays[0].id),
                "ville_naissance": "Château-du-Loir",
                "nom_pere": "Foulque",
                "prenom_pere": "V",
                "nom_mere": "Erembourge",
                "prenom_mere": "Du Maine",
                "situation_familiale": "CELIBATAIRE",
                "condition_entree_france": "REGULIERE",
                "conditions_exceptionnelles_accueil": False,
                "present_au_moment_de_la_demande": True,
                "demandeur": True,
                "photo_premier_accueil": str(photo.id),
                "langues_audition_OFPRA": (str(ref_langues_ofpra[0].id), ),
                "langues": (str(ref_langues_iso[0].id), ),
                "nationalites": (str(ref_nationalites[0].id), ),
                "adresse": {"adresse_inconnue": True},
                'date_decision_sur_attestation': True,
                'type_procedure': 'DUBLIN',
                'decision_sur_attestation': True,
                'date_decision_sur_attestation': datetime(2015, 8, 24),
                'motif_qualification_procedure': 'EAEA',
                'visa': 'C',
                'indicateur_visa_long_sejour': True,
                'identifiant_eurodac': 'euro-12345',
                'identite_approchante_select': True,
                'type_demande': "REEXAMEN"
            },
            "statut": "PA_REALISE",
            "profil_demande": "ADULTE_ISOLE"
        }
        # Reexamen
        payload['usager_1']['type_demande'] = "REEXAMEN"
        r = user_req.post('/recueils_da', data=payload)
        # on error numero_reexamen should have a value if type_demande == REEXAMEN
        assert r.status_code == 400, r
        payload['usager_1']['numero_reexamen'] = 0
        r = user_req.post('/recueils_da', data=payload)
        # on error numero_reexamen should start at 1
        assert r.status_code == 400, r
        payload['usager_1']['numero_reexamen'] = 1
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        # going through the different step of the life cycle of a recueil
        r = user_req.post(route + '/demandeurs_identifies')
        assert r.status_code == 200, r
        r = user_req.post(route + '/exploite')
        assert r.status_code == 200, r
        # Check broker messages as well
        Message = self.app.extensions['broker'].model.Message
        msg = Message.objects(handler='inerec-demande_asile.en_attente_ofpra')
        assert msg.count() == 0
        # check if the asylum issue from the recueil has the good attribute
        r = user_req.get('/demandes_asile')
        assert r.data['_items'][0]['type_demande'] == "REEXAMEN"
        assert r.data['_items'][0]['numero_reexamen'] == 1
        # Reouverture
        payload['usager_1']['type_demande'] = "REOUVERTURE_DOSSIER"
        r = user_req.post('/recueils_da', data=payload)
        # no need for numero_reexamen since it is a REOUVERTURE_DOSSIER
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.post(route + '/demandeurs_identifies')
        assert r.status_code == 200, r
        r = user_req.post(route + '/exploite')
        assert r.status_code == 200, r
        r = user_req.get('/demandes_asile')
        assert r.data['_items'][1]['type_demande'] == "REOUVERTURE_DOSSIER"

    def test_reexamen_refus(self, user, usager, site_gu, photo,
                            ref_pays, ref_langues_ofpra,
                            ref_langues_iso, ref_nationalites):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_gu)
        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.demande_asile.voir.name]
        user.save()
        payload = {
            'usager_1': {
                'date_entree_en_france': datetime(1952, 1, 1),
                'date_depart': datetime(1952, 1, 1),
                'date_depart_approximative': False,
                'date_entree_en_france_approximative': False,
                'nom': 'Plantagenêt', 'prenoms': ['Geoffroy', 'V'], 'sexe': 'M',
                'origine_nom': 'EUROPE',
                'photo': str(photo.id),
                'acceptation_opc': False,
                'date_naissance': datetime(1913, 8, 24),
                "pays_naissance": str(ref_pays[0].id),
                "ville_naissance": "Château-du-Loir",
                "nom_pere": "Foulque",
                "prenom_pere": "V",
                "nom_mere": "Erembourge",
                "prenom_mere": "Du Maine",
                "situation_familiale": "CELIBATAIRE",
                "condition_entree_france": "REGULIERE",
                "conditions_exceptionnelles_accueil": False,
                "present_au_moment_de_la_demande": True,
                "demandeur": True,
                "photo_premier_accueil": str(photo.id),
                "langues_audition_OFPRA": (str(ref_langues_ofpra[0].id), ),
                "langues": (str(ref_langues_iso[0].id), ),
                "nationalites": (str(ref_nationalites[0].id), ),
                "adresse": {"adresse_inconnue": True},
                'date_decision_sur_attestation': True,
                'type_procedure': 'NORMALE',
                'decision_sur_attestation': True,
                'date_decision_sur_attestation': datetime(2015, 8, 24),
                'motif_qualification_procedure': 'PNOR',
                'visa': 'C',
                'indicateur_visa_long_sejour': True,
                'identifiant_eurodac': 'euro-12345',
                'identite_approchante_select': True,
                'type_demande': "REEXAMEN",
                'numero_reexamen': 2,
                'refus': {'motif': 'seconde demande'}
            },
            "statut": "PA_REALISE",
            "profil_demande": "ADULTE_ISOLE"
        }
        # Reexamen
        payload['usager_1']['type_demande'] = "REEXAMEN"
        r = user_req.post('/recueils_da', data=payload)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        # going through the different step of the life cycle of a recueil
        r = user_req.post(route + '/demandeurs_identifies')
        assert r.status_code == 200, r
        r = user_req.post(route + '/exploite')
        assert r.status_code == 200, r
        # Check broker messages as well
        Message = self.app.extensions['broker'].model.Message
        msg = Message.objects(handler='inerec-demande_asile.en_attente_ofpra')
        assert msg.count() == 1
        # check if the asylum issue from the recueil has the good attribute
        r = user_req.get('/demandes_asile')
        assert r.data['_items'][0]['type_demande'] == "REEXAMEN"
        assert r.data['_items'][0]['numero_reexamen'] == 2

    def test_reexamen_on_second_demande_asile(self, user, usager, site_gu, photo,
                                              ref_pays, ref_langues_ofpra,
                                              ref_langues_iso, ref_nationalites):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(site_affecte=site_gu)
        user.permissions = [p.recueil_da.creer_pa_realise.name,
                            p.recueil_da.voir.name,
                            p.recueil_da.prefecture_rattachee.sans_limite.name,
                            p.recueil_da.modifier_pa_realise.name,
                            p.recueil_da.modifier_demandeurs_identifies.name,
                            p.demande_asile.voir.name,
                            p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.editer_attestation.name,
                            p.demande_asile.finir_procedure.name]
        user.save()
        payload_recueil = {
            'usager_1': {
                'date_entree_en_france': datetime(1952, 1, 1),
                'date_depart': datetime(1952, 1, 1),
                'date_depart_approximative': False,
                'date_entree_en_france_approximative': False,
                'nom': 'Plantagenêt', 'prenoms': ['Geoffroy', 'V'], 'sexe': 'M',
                'origine_nom': 'EUROPE',
                'photo': str(photo.id),
                'acceptation_opc': False,
                'date_naissance': datetime(1913, 8, 24),
                "pays_naissance": str(ref_pays[0].id),
                "ville_naissance": "Château-du-Loir",
                "nom_pere": "Foulque",
                "prenom_pere": "V",
                "nom_mere": "Erembourge",
                "prenom_mere": "Du Maine",
                "situation_familiale": "CELIBATAIRE",
                "condition_entree_france": "REGULIERE",
                "conditions_exceptionnelles_accueil": False,
                "present_au_moment_de_la_demande": True,
                "demandeur": True,
                "photo_premier_accueil": str(photo.id),
                "langues_audition_OFPRA": (str(ref_langues_ofpra[0].id), ),
                "langues": (str(ref_langues_iso[0].id), ),
                "nationalites": (str(ref_nationalites[0].id), ),
                "adresse": {"adresse_inconnue": True},
                'date_decision_sur_attestation': True,
                'type_procedure': 'NORMALE',
                'decision_sur_attestation': True,
                'date_decision_sur_attestation': datetime(2015, 8, 24),
                'motif_qualification_procedure': 'PNOR',
                'visa': 'C',
                'indicateur_visa_long_sejour': True,
                'identifiant_eurodac': 'euro-12345',
                'identite_approchante_select': True,
                'type_demande': "PREMIERE_DEMANDE_ASILE"
            },
            "statut": "PA_REALISE",
            "profil_demande": "ADULTE_ISOLE"
        }
        r = user_req.post('/recueils_da', data=payload_recueil)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        # going through the different step of the life cycle of a recueil
        r = user_req.post(route + '/demandeurs_identifies')
        assert r.status_code == 200, r
        r = user_req.post(route + '/exploite')
        assert r.status_code == 200, r
        recueil_id = r.data['id']
        # check if the asylum issue from the recueil has the good attribute
        r = user_req.get('/demandes_asile')
        assert r.status_code == 200
        assert r.data['_items'][0]['recueil_da_origine']['id'] == int(recueil_id)
        da_pk = r.data['_items'][0]['id']
        route = '/demandes_asile/%s/attestations' % da_pk
        payload = {'date_debut_validite': "2015-09-22T00:00:01+00:00",
                   'date_fin_validite': "2015-09-22T00:00:02+00:00",
                   'date_decision_sur_attestation': "2015-09-22T00:00:03+00:00"}
        r = user_req.post(route, data=payload)
        assert r.status_code == 201
        payload = {
            'motif_refus': 'motif'
        }
        route = '/demandes_asile/%s/fin_procedure' % da_pk
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        payload_recueil['usager_1'] = {'usager_existant': r.data['usager']['id'],
                                       'demandeur': True,
                                       'present_au_moment_de_la_demande': True,
                                       'date_depart': datetime(2015, 8, 18),
                                       'date_depart_approximative': False,
                                       'date_entree_en_france': datetime(2015, 8, 20),
                                       'date_entree_en_france_approximative': False,
                                       'identite_approchante_select': True,
                                       'identifiant_eurodac': 'euro-12345',
                                       'type_demande': "REEXAMEN",
                                       'numero_reexamen': 1,
                                       'type_procedure': 'NORMALE',
                                       'visa': 'C',
                                       'indicateur_visa_long_sejour': True,
                                       'decision_sur_attestation': True,
                                       "condition_entree_france": "REGULIERE",
                                       'motif_qualification_procedure': 'PNOR',
                                       'date_decision_sur_attestation': datetime(2015, 8, 24),
                                       'conditions_exceptionnelles_accueil': False,
                                       }
        r = user_req.post('/recueils_da', data=payload_recueil)
        assert r.status_code == 201, r
        route = '/recueils_da/%s' % r.data['id']
        r = user_req.post(route + '/demandeurs_identifies')
        assert r.status_code == 200, r
        r = user_req.post(route + '/exploite')
        assert r.status_code == 200, r
