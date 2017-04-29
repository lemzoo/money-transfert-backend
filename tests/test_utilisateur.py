import pytest
import json
from datetime import datetime, timedelta

from flask import current_app

from tests import common
from tests.fixtures import *

from sief.model.utilisateur import Utilisateur, Accreditation
from sief.permissions import POLICIES as p
from sief.tasks.email import mail


class TestUtilisateur(common.BaseTest):

    def test_links_list(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'root'])
        user.permissions.append(p.utilisateur.creer.name)
        user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'create', 'root'])

    def test_links_single(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        route = '/utilisateurs/%s' % another_user.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions.append(p.utilisateur.modifier.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'update', 'parent'])
        user.permissions = [p.utilisateur.voir.name, p.historique.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent'])

    def test_links_self(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/moi')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'update', 'root'])

    def test_bad_field(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Invalid field
        r = user_req.patch('/moi', data={'nom': 'Doe',
                                         'prenom': 'John',
                                         'bad_field': 'eee'})
        assert r.status_code == 400, r
        # Invalid value
        r = user_req.patch('/moi', data={"nom": 4222, 'prenom': 'John'})
        assert r.status_code == 400, r

    def test_self_patch(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.patch('/moi', data={'nom': 'Doe', 'prenom': 'John'})
        assert r.status_code == 200, r
        assert r.data.get('nom', '<invalid>') == 'Doe'
        assert r.data.get('prenom', '<invalid>') == 'John'

    def test_change_self_password(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.patch('/moi', data={'password': 'h4ck'})
        assert r.status_code == 400, r.data

    def test_change_self_permissions(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.patch('/moi', data={'permissions': ['h4ck']})
        assert r.status_code == 400, r.data

    def test_update_user(self, user, another_user):
        user.permissions = [p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/utilisateurs/{}'.format(another_user.id)
        r = user_req.patch(route, data={'nom': 'Doe'})
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions.append(p.utilisateur.modifier.name)
        user.save()
        r = user_req.patch(route, data={'nom': 'Doe'})
        assert r.status_code == 200, r
        assert r.data.get('nom', '<invalid>') == 'Doe'

    def test_update_address(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.modifier.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        route = '/utilisateurs/{}'.format(user.id)
        address = {
            "identifiant_ban": "ADRNIVX_0000000287080409",
            "voie": "10 Allée Mickaël Lefebvre",
            "numero_voie": "10",
            "ville": "Asnières-sur-Seine",
            "code_postal": "92600",
            "code_insee": "92004"
        }
        r = user_req.patch(route, data={'adresse': address})
        assert r.status_code == 200, r
        assert r.data.get('adresse', '<invalid>') == address

    def test_bad_update_user(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.modifier.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Need permission to do it
        route = '/utilisateurs/{}'.format(another_user.id)
        for key, value in (('id', '554534801d41c8de989d038e'),
                           ('doc_version', 42), ('doc_version', '42'),
                           ('_version', '42'), ('_version', 42)):
            r = user_req.patch(route, data={key: value})
            assert r.status_code == 400, (key, value)

    def test_change_password(self, user, another_user, site_gu):
        user.permissions = [p.utilisateur.sans_limite_site_affecte.name]
        set_user_accreditation(user, site_affecte=site_gu, site_rattache=site_gu)
        user.save()
        set_user_accreditation(another_user, site_affecte=site_gu, site_rattache=site_gu)
        another_user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/utilisateurs/{}'.format(another_user.id)
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 403, r
        # Now provide the permission to modify antoher user. However we still
        # cannot change it password with explicit permission.
        user.permissions = [p.utilisateur.modifier.name]
        user.save()
        old_password = user.basic_auth.hashed_password
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 400, r
        # We but can change our own password.
        route = '/utilisateurs/{}'.format(user.id)
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 200, r
        assert 'password' not in r.data
        user.reload()
        assert user.basic_auth.hashed_password != old_password

    def test_change_password_admin(self, user, another_user, site_gu):
        user.permissions = [p.utilisateur.sans_limite_site_affecte.name]
        set_user_accreditation(user, site_affecte=site_gu, site_rattache=site_gu)
        user.save()
        set_user_accreditation(another_user, site_affecte=site_gu, site_rattache=site_gu)
        another_user.save()

        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/utilisateurs/{}'.format(another_user.id)
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 403, r
        # Now provide the permission to modify the user. However we still
        # cannot change it password with explicit permission.
        user.permissions = [p.utilisateur.modifier.name]
        user.save()
        old_password = another_user.basic_auth.hashed_password
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 400, r
        # Finally provide the right permission to modify password
        user.permissions.append(p.utilisateur.changer_mot_de_passe_utilisateur.name)
        user.save()
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 200, r
        assert 'password' not in r.data
        another_user.reload()
        assert another_user.basic_auth.hashed_password != old_password
        # Try to login with our brand new user
        payload = json.dumps({
            "login": another_user.email,
            "password": 'OtherP@ssw0rd'
        })
        r = self.client_app.post('/agent/login', data=payload,
                                 content_type='application/json',
                                 content_length=len(payload))
        assert r.status_code == 200, r

    def test_change_user_password_by_admin_dt_ofii(self, user, another_user, site_gu):
        # importer la liste complete des roles de siefs
        from sief.roles import ROLES

        # attache la prefecture rattache au gu a l'usager administrateur au
        # site_affecte et site_rattache
        user_role = 'ADMINISTRATEUR_DT_OFII'
        user_site_affecte = site_gu.autorite_rattachement
        user_site_rattache = site_gu.autorite_rattachement
        user.test_set_accreditation(role=user_role,
                                    site_affecte=user_site_affecte,
                                    site_rattache=user_site_rattache)
        user.save()
        another_user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/utilisateurs/{}'.format(another_user.id)
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 403, r
        # Now provide the permission
        # recuperation des permission liés au role de l'utilisateur
        role_policies = ROLES[user.controller.get_current_role()]
        # les permissions de l'utilisateurs sont des strings, et non des objets
        # on utilise ici la comprehension_list pour créer la liste de nom
        # correspondant a la liste des permissions de l'utilisateur
        role_policies = [policy.name for policy in role_policies]
        user.permissions = role_policies
        user.save()
        old_password = user.password
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        # another user role is not visible for an administrateur_dt_ofii
        assert r.status_code == 403, r
        # Mise a jour du role de l'autre utilisateur
        another_user_role = 'RESPONSABLE_GU_DT_OFII'
        # Mise a jour du site affecte
        another_user_site_affecte = site_gu
        # Mise a jour de l'autorite de rattachement
        another_user_site_rattache = user_site_affecte
        another_user.test_set_accreditation(
            role=another_user_role,
            site_affecte=another_user_site_affecte,
            site_rattache=another_user_site_rattache)
        another_user.save()
        r = user_req.patch(route, data={'password': 'OtherP@ssw0rd'})
        assert r.status_code == 200, r
        assert r.data.get('password', '<invalid>') != old_password
        # Try to login with our brand new user
        payload = json.dumps({
            "login": another_user.email,
            "password": 'OtherP@ssw0rd'
        })
        r = self.client_app.post('/agent/login', data=payload,
                                 content_type='application/json',
                                 content_length=len(payload))
        assert r.status_code == 200, r

    def test_change_bad_password(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        route = '/utilisateurs/{}'.format(user.id)
        r = user_req.patch(route, data={'password': 'new_pass'})
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions.append(p.utilisateur.modifier.name)
        user.save()
        r = user_req.patch(route, data={'password': 'new_pass'})
        assert r.status_code == 400, r

    def test_create_user(self, user):
        from re import match, DOTALL
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permission to do it
        r = user_req.post('/utilisateurs', data={
            "email": "new@user.com",
            "nom": "Doe",
            "prenom": "John"
        })
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions = [p.utilisateur.creer.name]
        user.save()
        with mail.record_messages() as outbox:
            r = user_req.post('/utilisateurs', data={
                "email": "new@user.com",
                "nom": "Doe",
                "prenom": "John"
            })
            assert r.status_code == 201, r
            assert r.data.get("email", '<invalid>') == "new@user.com"
            assert r.data.get("nom", '<invalid>') == "Doe"
            assert r.data.get("prenom", '<invalid>') == "John"
            assert len(outbox) == 1
            assert "new@user.com" in outbox[0].recipients
            email, token = match(
                r'.*https?://[^/]+/#/reset/([^/]+)/([0-9a-f]{64}).*', outbox[0].body, DOTALL).group(1, 2)
            assert email == 'new@user.com'
            assert match(r'[0-9a-f]{64}', token)
            r = user_req.post(('/agent/login/password_recovery/%s' % email),
                              data={'token': token, 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 200
        # Try to login with our brand new user
        payload = json.dumps({
            "login": "new@user.com",
            "password": 'newP@ssW0rd?!'
        })
        r = self.client_app.post('/agent/login', data=payload,
                                 content_type='application/json',
                                 content_length=len(payload))
        assert r.status_code == 200, r  # Cannot login anymore, sorry

    def test_phone_number(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        for num in [' ', 'not a number', '+33a01233', '123445+890',
                    ' 0123456789', '0123456789 ', '']:
            r = user_req.post('/utilisateurs', data={
                "email": "test_phone_number@user.com",
                "telephone": num,
                "nom": "Doe",
                "prenom": "John"
            })
            assert r.status_code == 400, num
        for i, num in enumerate(['0123456789', '01 23 45 67 89', '+33 123456789', None]):
            r = user_req.post('/utilisateurs', data={
                "email": "test_phone_number-%i@user.com" % i,
                "telephone": num,
                "nom": "Doe",
                "prenom": "John"
            })
            assert r.status_code == 201, num

    def test_bad_create_user(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]
        user.save()
        default_payload = {
            "email": "bad_create_user@user.com",
            "nom": "Doe",
            "prenom": "John"
        }
        for key, value in [("id", "554534801d41c8de989d038e"),  # id is read only
                           ("email", user.email),  # already taken
                           ("nom", None), ("prenom", None),
                           ("nom", ''), ("prenom", '')]:
            payload = default_payload.copy()
            if value is None:
                del payload[key]
            else:
                payload[key] = value
            r = user_req.post('/utilisateurs', data=payload)
            assert r.status_code == 400, r

    def test_get_users(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Need permission to do it
        r = user_req.get('/utilisateurs')
        assert r.status_code == 403, r
        r = user_req.get('/utilisateurs/{}'.format(user.id))
        assert r.status_code == 403, r
        # Now provide the permission
        user.permissions.append(p.utilisateur.voir.name)
        user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        r = user_req.get('/utilisateurs/{}'.format(user.id))
        assert r.status_code == 200, r

    # TODO: multirole FIXME !!!
    @pytest.mark.xfail(reason="multirole: accreditations change api is not defined yet")
    def test_site_affecte(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.modifier.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Cannot change my own site
        r = user_req.patch('/moi', data={'site_affecte': str(site.pk)})
        assert r.status_code == 400, r
        r = user_req.patch('/utilisateurs/%s' % user.pk,
                           data={'site_affecte': str(site.pk)})
        assert r.status_code == 200, r
        user.reload()
        assert user.site_affecte == site
        # Can remove a site_affecte as well
        r = user_req.patch('/utilisateurs/%s' % user.pk,
                           data={'site_affecte': None})
        assert r.status_code == 200, r
        user.reload()
        assert user.site_affecte is None

    def test_bad_site_affecte(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.modifier.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Cannot change my own site
        route = '/utilisateurs/%s' % user.pk
        for bad in [str(user.pk), '', 'not_an_id', {}, 42, 0]:
            r = user_req.patch(route, data={'site_affecte': bad})
            assert r.status_code == 400, bad


class TestPaginationUtilisateur(common.BaseTest):

    def test_paginate_users(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        # Start by creating a lot of users
        for i in range(49):
            new_user = Utilisateur(email='pag.%s@user.com' % i,
                                   nom='Pagination', prenom='Elem')
            new_user.controller.init_basic_auth()
            new_user.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/utilisateurs')


class TestUtilisateurConcurrency(common.BaseTest):

    def test_concurrency(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.modifier.name,
                            p.utilisateur.voir.name,
                            p.utilisateur.sans_limite_site_affecte.name]
        user.save()
        route = '/utilisateurs/{}'.format(user.id)
        bad_version = user.doc_version + 1
        # Test the presence of the ETAG header in the get
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.headers['etag'] == str(user.doc_version)
        # Try to modify the document with bad conditions
        r = user_req.patch(route, data={'nom': 'Doe'},
                           headers={'If-Match': bad_version})
        assert r.status_code == 412, r
        # Now use the correct condition two times
        good_version = user.doc_version
        r = user_req.patch(route, data={'nom': 'Doe'},
                           headers={'If-Match': good_version})
        assert r.status_code == 200, r
        # Now good_version is not good anymore...
        r = user_req.patch(route, data={'nom': 'Dooe'},
                           headers={'If-Match': good_version})
        assert r.status_code == 412, r
        # Test dummy If-Match values as well
        r = user_req.patch(route, data={'nom': 'Dooe'},
                           headers={'If-Match': 'NaN'})
        assert r.status_code == 412, r


class TestUtilisateurRole(common.BaseTest):

    def _prepare_accreditation_payload(self, **kwargs):
        payload = {
            "email": "new@user.com",
            "nom": "Doe",
            "prenom": "John",
            "accreditations": [kwargs]
        }
        return payload

    def _bad_create(self, user_req, **kwargs):
        payload = self._prepare_accreditation_payload(**kwargs)
        r = user_req.post('/utilisateurs', data=payload)
        assert r.status_code == 400, str(r.status_code)
        assert Utilisateur.objects(email="new@user.com").count() == 0
        return r

    def _good_create(self, user_req, **kwargs):
        payload = self._prepare_accreditation_payload(**kwargs)
        r = user_req.post('/utilisateurs', data=payload)
        assert r.status_code == 201, str(payload)
        Utilisateur.objects(id=r.data['id']).delete()

    def test_bad_role(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]

        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        self._bad_create(user_req, role='NOT_A_ROLE')

        user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        user.save()
        self._bad_create(user_req, role='ADMINISTRATEUR')
        self._bad_create(user_req, role='GESTIONNAIRE_PA')
        self._bad_create(user_req, role='RESPONSABLE_PA')
        self._bad_create(user_req, role='NOT_A_ROLE')

        user.test_set_accreditation(role='GESTIONNAIRE_PA')
        user.save()
        self._bad_create(user_req, role='ADMINISTRATEUR')
        self._bad_create(user_req, role='GESTIONNAIRE_NATIONAL')
        self._bad_create(user_req, role='GESTIONNAIRE_PA')
        self._bad_create(user_req, role='RESPONSABLE_PA')
        self._bad_create(user_req, role='NOT_A_ROLE')

        user.test_set_accreditation(role='GESTIONNAIRE_NATIONAL')
        user.save()
        self._bad_create(user_req, role='ADMINISTRATEUR')
        self._bad_create(user_req, role='GESTIONNAIRE_PA')
        self._bad_create(user_req, role='RESPONSABLE_PA')
        self._bad_create(user_req, role='NOT_A_ROLE')

    def test_good_role(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]

        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        site_id = site_structure_accueil.id
        self._good_create(user_req, role='ADMINISTRATEUR')
        self._good_create(user_req, role='RESPONSABLE_NATIONAL')
        self._good_create(user_req, role='GESTIONNAIRE_NATIONAL')
        self._good_create(user_req, role='ADMINISTRATEUR_PA', site_affecte=site_id)

        user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        user.save()
        self._good_create(user_req, role='GESTIONNAIRE_NATIONAL')

        user.test_set_accreditation(role='ADMINISTRATEUR_PA', site_affecte=site_structure_accueil)
        user.save()
        self._good_create(user_req, role='RESPONSABLE_PA', site_affecte=site_id)
        self._good_create(user_req, role='GESTIONNAIRE_PA', site_affecte=site_id)

    def test_inherit_site(self, user, site_structure_accueil, site_gu, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]

        user.test_set_accreditation(role='ADMINISTRATEUR_PA', site_affecte=site_structure_accueil)
        user.save()
        site_id = user.accreditations[0].site_affecte.id
        self._good_create(user_req, role='RESPONSABLE_PA', site_affecte=site_id)
        self._good_create(user_req, role='GESTIONNAIRE_PA', site_affecte=site_id)
        self._bad_create(user_req, role='RESPONSABLE_PA', site_affecte=site_gu.id)
        self._bad_create(user_req, role='RESPONSABLE_PA', site_affecte=None)

        user.test_set_accreditation(role='ADMINISTRATEUR_DT_OFII', site_affecte=site_prefecture)
        user.save()
        site_id = site_gu.id
        assert site_gu.autorite_rattachement == user.accreditations[0].site_affecte
        self._good_create(user_req, role='RESPONSABLE_GU_DT_OFII', site_affecte=site_id)
        self._good_create(user_req, role='GESTIONNAIRE_GU_DT_OFII', site_affecte=site_id)
        self._bad_create(
            user_req, role='RESPONSABLE_GU_DT_OFII', site_affecte=site_structure_accueil.id)
        self._bad_create(user_req, role='RESPONSABLE_GU_DT_OFII', site_affecte=None)

    def test_gu_assigne_site(self, user, site_prefecture, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]

        # Sanity check
        assert site_gu.autorite_rattachement == site_prefecture
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE', site_affecte=site_prefecture)
        user.save()
        site_id = site_gu.id
        self._good_create(user_req, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site_id)
        self._good_create(user_req, role='GESTIONNAIRE_GU_ASILE_PREFECTURE', site_affecte=site_id)
        self._bad_create(user_req, role='RESPONSABLE_GU_ASILE_PREFECTURE',
                         site_affecte=site_prefecture.id)
        self._bad_create(user_req, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=None)

    def test_zone_assigne_site(self, user, site_ensemble_zonal, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]

        # Sanity check
        assert site_prefecture in site_ensemble_zonal.prefectures
        user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        user.save()
        self._good_create(user_req, role='RESPONSABLE_ZONAL',
                          site_affecte=site_ensemble_zonal.id)
        self._bad_create(user_req, role='RESPONSABLE_ZONAL',
                         site_affecte=site_prefecture.id)
        self._bad_create(user_req, role='RESPONSABLE_ZONAL', site_affecte=None)

    # TODO: multirole FIXME !!!
    @pytest.mark.xfail(reason="multirole: cannot create user with accreditations yet")
    def test_change_role(self, user, site_structure_accueil):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name, p.utilisateur.modifier.name]
        user.role = 'ADMINISTRATEUR'
        user.save()

        # First create an user
        payload = {
            "email": "new@user.com",
            "password": "secret",
            "nom": "Doe",
            "prenom": "John",
            "role": 'GESTIONNAIRE_PA',
            "site_affecte": site_structure_accueil.id
        }
        r = user_req.post('/utilisateurs', data=payload)
        assert r.status_code == 201, str(r.data)
        route = '/utilisateurs/%s' % r.data['id']

        # Now change the role but forget to remove/change the site
        for role in ('ADMINISTRATEUR_NATIONAL', 'NOT_A_ROLE', 'GESTIONNAIRE_GU_DT_OFII'):
            r = user_req.patch(route, data={'role': role})
            assert r.status_code == 400, (r, role)

        # Change a role which doesn't involve site change
        r = user_req.patch(route, data={'role': 'RESPONSABLE_PA'})
        assert r.status_code == 200, r

        # Finally change the role and the site
        r = user_req.patch(route, data={'role': 'ADMINISTRATEUR_NATIONAL', 'site_affecte': None})
        assert r.status_code == 200, r

    # TODO: multirole FIXME !!!
    @pytest.mark.xfail(reason="multirole: cannot change user's accreditations yet")
    def test_site_affecte(self, user, site_prefecture, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.voir.name, p.utilisateur.creer.name]
        user.site_affecte = site_prefecture
        user.site_rattache = site_prefecture
        user.save()

        # First create an user
        payload = {
            "email": "site_affecte@user.com",
            "password": "secret",
            "nom": "Doe",
            "prenom": "John",
            "site_affecte": site_gu.id
        }
        r = user_req.post('/utilisateurs', data=payload)
        assert r.status_code == 201, r
        assert r.data['site_rattache']['id'] == str(user.site_affecte.id)

        route = '/utilisateurs/%s' % r.data['id']
        r = user_req.get(route)
        assert r.status_code == 200, r

        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 2

        # Now switch to another site_affecte, we shouldn't be able to see the created user anymore
        user.site_affecte = site_gu
        user.save()
        r = user_req.get(route)
        assert r.status_code == 403, r

        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0

    def test_create_a_gestionnaire_de_titres_if_feature_activated(self, user, site_prefecture):
        current_app.config.update(dict(FF_CONSOMMATION_TTE=True))
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE', site_affecte=site_prefecture)
        user.save()

        self._good_create(user_req, role='GESTIONNAIRE_DE_TITRES', site_affecte=site_prefecture.id)

    def test_not_create_a_gestionnaire_de_titres_if_feature_deactivated(self, user, site_prefecture):
        current_app.config.pop('FF_CONSOMMATION_TTE', None)
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE', site_affecte=site_prefecture)
        user.save()

        response = self._bad_create(user_req, role='GESTIONNAIRE_DE_TITRES', site_affecte=site_prefecture.id)

        expected_error = {'code-erreur': 'feature-deactivated',
                          'description-erreur': 'You can not create a "Gestionnaire de titres".'}
        assert response.data['errors'] == [expected_error]


class TestUtilisateurFilterViewRole(common.BaseTest):

    # TODO: multirole FIXME !!!
    @pytest.mark.xfail(reason="multirole: cannot change user's accreditations yet")
    def test_get_per_role_single(self, user, another_user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        user.role = 'ADMINISTRATEUR_PREFECTURE'
        user.site_affecte = site
        user.save()
        # Can see this kind of usertest
        another_user.save()
        route = '/utilisateurs/%s' % another_user.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        # Now change to a role we can't see
        another_user.role = 'ADMINISTRATEUR_PREFECTURE'
        another_user.save()
        r = user_req.get(route)
        assert r.status_code == 403, r

    def test_get_per_role_list(self, user, another_user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='ADMINISTRATEUR_PREFECTURE', site_affecte=site)
        user.save()
        # Can see this kind of user
        set_user_accreditation(
            another_user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_rattache=site)
        another_user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1
        # Now change to a role we can't see
        set_user_accreditation(another_user, role='ADMINISTRATEUR_PREFECTURE', site_rattache=site)
        another_user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0

    # TODO: multirole FIXME !!!
    @pytest.mark.xfail(reason="multirole: Utilisateur.objects(**lookup) makes false positive")
    def test_bad_get_per_role_list(self, user, another_user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='ADMINISTRATEUR_PREFECTURE', site_affecte=site)
        user.save()
        # Other user has two accreditations, each of them cannot be seen by
        # main user. However the combinaison of both can produce a
        # false positive, that's what we want to test...
        another_user.accreditations = [
            Accreditation(role='RESPONSABLE_GU_ASILE_PREFECTURE'),
            Accreditation(role='ADMINISTRATEUR_PREFECTURE', site_rattache=site)
        ]
        another_user.save()
        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0


class TestUtilisateurFilterViewRoleSolr(common.BaseSolrTest):

    def test_solr_get_per_role_list(self, user, another_user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = []
        set_user_accreditation(user, role='ADMINISTRATEUR_PREFECTURE', site_affecte=site)
        user.save()
        # Can see this kind of user
        set_user_accreditation(
            another_user, role='RESPONSABLE_GU_ASILE_PREFECTURE', site_rattache=site)
        another_user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        route = '/utilisateurs?q=nom:%s' % another_user.nom
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1
        # Now change to a role we can't see
        set_user_accreditation(another_user, role='ADMINISTRATEUR_PREFECTURE', site_rattache=site)
        another_user.save()
        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 0


class TestUtilisateurPermission(common.BaseTest):

    def _call_request(self, user, permissions):
        from flask.ext.principal import Identity, UserNeed
        from sief.permissions import POLICIES as p
        from sief.roles import ROLES as r

        identity = Identity(str(user.id))
        identity.provides.add(UserNeed(user.id))
        role = user.accreditations[0].role
        if role:
            role_policies = r.get(role)
            for policy in role_policies:
                identity.provides.add(policy.action_need)

        # Utilisateur Permissions
        assert identity.can(p.utilisateur.creer.permission) is bool(
            "utilisateur_creer" in permissions)
        assert identity.can(p.utilisateur.modifier.permission) is bool(
            "utilisateur_modifier" in permissions)
        assert identity.can(p.utilisateur.voir.permission) is bool(
            "utilisateur_voir" in permissions)
        assert identity.can(p.utilisateur.sans_limite_site_affecte.permission) is bool(
            "utilisateur_sans_limite_site_affecte" in permissions)
        assert identity.can(p.utilisateur.changer_mot_de_passe_utilisateur.permission) is bool(
            "utilisateur_changer_mot_de_passe_utilisateur" in permissions)

        # Site Permissions
        assert identity.can(p.site.creer.permission) is bool("site_creer" in permissions)
        assert identity.can(p.site.modifier.permission) is bool("site_modifier" in permissions)
        assert identity.can(p.site.voir.permission) is bool("site_voir" in permissions)
        assert identity.can(p.site.export.permission) is bool("site_export" in permissions)
        assert identity.can(p.site.fermer.permission) is bool("site_fermer" in permissions)
        assert identity.can(p.site.sans_limite_site_affecte.permission) is bool(
            "site_sans_limite_site_affecte" in permissions)
        assert identity.can(p.site.rendez_vous.gerer.permission) is bool(
            "site_rendez_vous_gerer" in permissions)
        assert identity.can(p.site.creneaux.gerer.permission) is bool(
            "site_creneaux_gerer" in permissions)
        assert identity.can(p.site.actualite.gerer.permission) is bool(
            "site_actualite_gerer" in permissions)

        # Recueil Permissions
        assert identity.can(p.recueil_da.creer_pa_realise.permission) is bool(
            "recueil_da_creer_pa_realise" in permissions)
        assert identity.can(p.recueil_da.creer_brouillon.permission) is bool(
            "recueil_da_creer_brouillon" in permissions)
        assert identity.can(p.recueil_da.modifier_brouillon.permission) is bool(
            "recueil_da_modifier_brouillon" in permissions)
        assert identity.can(p.recueil_da.modifier_pa_realise.permission) is bool(
            "recueil_da_modifier_pa_realise" in permissions)
        assert identity.can(p.recueil_da.modifier_demandeurs_identifies.permission) is bool(
            "recueil_da_modifier_demandeurs_identifies" in permissions)
        assert identity.can(p.recueil_da.modifier_exploite.permission) is bool(
            "recueil_da_modifier_exploite" in permissions)
        assert identity.can(p.recueil_da.voir.permission) is bool("recueil_da_voir" in permissions)
        assert identity.can(p.recueil_da.export.permission) is bool(
            "recueil_da_export" in permissions)
        assert identity.can(p.recueil_da.purger.permission) is bool(
            "recueil_da_purger" in permissions)
        assert identity.can(p.recueil_da.rendez_vous.gerer.permission) is bool(
            "recueil_da_rendez_vous_gerer" in permissions)
        assert identity.can(p.recueil_da.prefecture_rattachee.modifier.permission) is bool(
            "recueil_da_prefecture_rattachee_modifier" in permissions)
        assert identity.can(p.recueil_da.prefecture_rattachee.sans_limite.permission) is bool(
            "recueil_da_prefecture_rattachee_sans_limite" in permissions)
        assert identity.can(p.recueil_da.enregistrer_famille_ofii.permission) is bool(
            "recueil_da_enregistrer_famille_ofii" in permissions)

        # DA Permissions
        assert identity.can(p.demande_asile.creer.permission) is bool(
            "demande_asile_creer" in permissions)
        assert identity.can(p.demande_asile.voir.permission) is bool(
            "demande_asile_voir" in permissions)
        assert identity.can(p.demande_asile.modifier.permission) is bool(
            "demande_asile_modifier" in permissions)
        assert identity.can(p.demande_asile.export.permission) is bool(
            "demande_asile_export" in permissions)
        assert identity.can(p.demande_asile.orienter.permission) is bool(
            "demande_asile_orienter" in permissions)
        assert identity.can(p.demande_asile.modifier_dublin.permission) is bool(
            "demande_asile_modifier_dublin" in permissions)
        assert identity.can(p.demande_asile.editer_attestation.permission) is bool(
            "demande_asile_editer_attestation" in permissions)
        assert identity.can(p.demande_asile.requalifier_procedure.permission) is bool(
            "demande_asile_requalifier_procedure" in permissions)
        assert identity.can(p.demande_asile.modifier_ofpra.permission) is bool(
            "demande_asile_modifier_ofpra" in permissions)
        assert identity.can(p.demande_asile.finir_procedure.permission) is bool(
            "demande_asile_finir_procedure" in permissions)
        assert identity.can(p.demande_asile.modifier_stock_dna.permission) is bool(
            "demande_asile_modifier_stock_dna" in permissions)
        assert identity.can(p.demande_asile.prefecture_rattachee.sans_limite.permission) is bool(
            "demande_asile_prefecture_rattachee_sans_limite" in permissions)

        # Droit Permissions
        assert identity.can(p.droit.creer.permission) is bool("droit_creer" in permissions)
        assert identity.can(p.droit.retirer.permission) is bool("droit_retirer" in permissions)
        assert identity.can(p.droit.voir.permission) is bool("droit_voir" in permissions)
        assert identity.can(p.droit.support.creer.permission) is bool(
            "droit_support_creer" in permissions)
        assert identity.can(p.droit.support.annuler.permission) is bool(
            "droit_support_annuler" in permissions)
        assert identity.can(p.droit.prefecture_rattachee.sans_limite.permission) is bool(
            "droit_prefecture_rattachee_sans_limite" in permissions)

        # Usager Permissions
        assert identity.can(p.usager.creer.permission) is bool("usager_creer" in permissions)
        assert identity.can(p.usager.voir.permission) is bool("usager_voir" in permissions)
        assert identity.can(p.usager.modifier.permission) is bool("usager_modifier" in permissions)
        assert identity.can(p.usager.export.permission) is bool("usager_export" in permissions)
        assert identity.can(p.usager.consulter_fpr.permission) is bool(
            "usager_consulter_fpr" in permissions)
        assert identity.can(p.usager.etat_civil.valider.permission) is bool(
            "usager_etat_civil_valider" in permissions)
        assert identity.can(p.usager.etat_civil.modifier.permission) is bool(
            "usager_etat_civil_modifier" in permissions)
        assert identity.can(p.usager.etat_civil.modifier_photo.permission) is bool(
            "usager_etat_civil_modifier_photo" in permissions)
        assert identity.can(p.usager.modifier_ofpra.permission) is bool(
            "usager_modifier_ofpra" in permissions)
        assert identity.can(p.usager.modifier_ofii.permission) is bool(
            "usager_modifier_ofii" in permissions)
        assert identity.can(p.usager.modifier_agdref.permission) is bool(
            "usager_modifier_agdref" in permissions)
        assert identity.can(p.usager.prefecture_rattachee.modifier.permission) is bool(
            "usager_prefecture_rattachee_modifier" in permissions)
        assert identity.can(p.usager.prefecture_rattachee.sans_limite.permission) is bool(
            "usager_prefecture_rattachee_sans_limite" in permissions)

        # Others
        assert identity.can(p.historique.voir.permission) is bool("historique_voir" in permissions)
        assert identity.can(p.fichier.voir.permission) is bool("fichier_voir" in permissions)
        assert identity.can(p.fichier.gerer.permission) is bool("fichier_gerer" in permissions)
        assert identity.can(p.parametrage.gerer.permission) is bool(
            "parametrage_gerer" in permissions)
        assert identity.can(p.telemOfpra.creer.permission) is bool(
            "telemOfpra_creer" in permissions)
        assert identity.can(p.telemOfpra.voir.permission) is bool("telemOfpra_voir" in permissions)
        assert identity.can(p.broker.gerer.permission) is bool("broker_gerer" in permissions)
        assert identity.can(p.analytics.voir.permission) is bool("analytics_voir" in permissions)
        assert identity.can(p.timbre.voir.permission) is bool("timbre_voir" in permissions)
        assert identity.can(p.timbre.consommer.permission) is bool(
            "timbre_consommer" in permissions)

    def test_permission(self, user, site_prefecture, site_gu, site_structure_accueil,
                        site_ensemble_zonal):
        kwargs = {
            "nom": "Doe",
            "prenom": "John"
        }

        other_user = Utilisateur(email="other@test.com", **kwargs)
        other_user.controller.init_basic_auth()
        set_user_accreditation(other_user, role='ADMINISTRATEUR')
        other_user.save()

        # SYSTEME_INEREC
        user = Utilisateur(email="inerec@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='SYSTEME_INEREC')
        user.save()
        permissions = ["demande_asile_voir", "demande_asile_modifier",
                       "demande_asile_requalifier_procedure", "demande_asile_modifier_ofpra",
                       "demande_asile_finir_procedure", "demande_asile_modifier_stock_dna",
                       "demande_asile_prefecture_rattachee_sans_limite", "droit_voir",
                       "droit_prefecture_rattachee_sans_limite", "usager_voir",
                       "usager_prefecture_rattachee_sans_limite", "usager_modifier",
                       "usager_etat_civil_valider", "usager_etat_civil_modifier", "usager_modifier_ofpra"]
        self._call_request(user, permissions)

        # SYSTEME_DNA
        user = Utilisateur(email="dna@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='SYSTEME_DNA')
        user.save()
        permissions = ["demande_asile_voir", "demande_asile_modifier", "demande_asile_orienter",
                       "demande_asile_prefecture_rattachee_sans_limite", "site_voir",
                       "site_sans_limite_site_affecte", "recueil_da_voir",
                       "recueil_da_prefecture_rattachee_sans_limite", "droit_voir",
                       "droit_prefecture_rattachee_sans_limite", "usager_voir",
                       "usager_prefecture_rattachee_sans_limite", "usager_modifier",
                       "usager_etat_civil_modifier", "recueil_da_enregistrer_famille_ofii",
                       "usager_modifier_ofii"]
        self._call_request(user, permissions)

        # SYSTEME_AGDREF
        user = Utilisateur(email="agdref@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='SYSTEME_AGDREF')
        user.save()
        permissions = ["demande_asile_voir", "demande_asile_modifier",
                       "demande_asile_modifier_dublin", "demande_asile_requalifier_procedure",
                       "demande_asile_finir_procedure", "demande_asile_prefecture_rattachee_sans_limite",
                       "site_voir", "site_sans_limite_site_affecte", "droit_voir",
                       "droit_prefecture_rattachee_sans_limite", "usager_voir", "usager_modifier",
                       "usager_modifier_agdref", "usager_etat_civil_modifier",
                       "usager_prefecture_rattachee_sans_limite", "recueil_da_voir",
                       "recueil_da_prefecture_rattachee_sans_limite"]
        self._call_request(user, permissions)

        # ADMINISTRATEUR_NATIONAL
        user = Utilisateur(email="admin_nat@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='ADMINISTRATEUR_NATIONAL')
        user.save()
        permissions = ["utilisateur_creer", "utilisateur_changer_mot_de_passe_utilisateur",
                       "utilisateur_modifier", "utilisateur_voir", "utilisateur_sans_limite_site_affecte",
                       "site_voir", "site_creer", "site_modifier", "site_fermer",
                       "site_sans_limite_site_affecte", "broker_gerer", "parametrage_gerer", "telemOfpra_voir"]
        self._call_request(user, permissions)

        # RESPONSABLE_NATIONAL
        user = Utilisateur(email="respo_nat@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='RESPONSABLE_NATIONAL')
        user.save()
        permissions = ["site_export", "recueil_da_export", "demande_asile_export", "usager_export",
                       "site_voir", "site_sans_limite_site_affecte", "analytics_voir"]
        self._call_request(user, permissions)

        # SUPPORT_NATIONAL
        user = Utilisateur(email="sup_nat@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='SUPPORT_NATIONAL')
        user.save()
        permissions = ["utilisateur_voir", "utilisateur_sans_limite_site_affecte", "site_voir",
                       "site_sans_limite_site_affecte", "site_actualite_gerer", "site_export",
                       "recueil_da_voir", "recueil_da_prefecture_rattachee_sans_limite", "recueil_da_export",
                       "demande_asile_voir", "demande_asile_prefecture_rattachee_sans_limite",
                       "demande_asile_export", "droit_voir", "droit_prefecture_rattachee_sans_limite",
                       "usager_voir", "usager_prefecture_rattachee_sans_limite", "usager_export",
                       "fichier_voir", "telemOfpra_voir"]
        self._call_request(user, permissions)

        # RESPONSABLE_ZONAL
        user = Utilisateur(email="respo_zonal@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='RESPONSABLE_ZONAL',
                               site_rattache=site_ensemble_zonal.id,
                               site_affecte=site_ensemble_zonal.id
                               )
        user.save()
        permissions = ["site_export", "site_voir", "recueil_da_export",
                       "recueil_da_prefecture_rattachee_sans_limite", "recueil_da_voir", "analytics_voir"]
        self._call_request(user, permissions)

        # SUPERVISEUR_ECHANGES
        user = Utilisateur(email="sup_echanges@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='SUPERVISEUR_ECHANGES')
        user.save()
        permissions = ["broker_gerer"]
        self._call_request(user, permissions)

        # ADMINISTRATEUR_PA
        user = Utilisateur(email="admin_pa@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='ADMINISTRATEUR_PA',
                               site_rattache=site_structure_accueil.id,
                               site_affecte=site_structure_accueil.id
                               )
        user.save()
        permissions = ["utilisateur_creer", "utilisateur_modifier", "utilisateur_voir",
                       "utilisateur_changer_mot_de_passe_utilisateur", "site_voir"]
        self._call_request(user, permissions)

        # RESPONSABLE_PA
        user = Utilisateur(email="respo_pa@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='RESPONSABLE_PA',
                               site_rattache=site_structure_accueil.id,
                               site_affecte=site_structure_accueil.id
                               )
        user.save()
        permissions = ["site_voir", "recueil_da_voir", "recueil_da_creer_brouillon",
                       "recueil_da_modifier_brouillon"]
        self._call_request(user, permissions)

        # GESTIONNAIRE_PA
        user = Utilisateur(email="gest_pa@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='GESTIONNAIRE_PA',
                               site_rattache=site_structure_accueil.id,
                               site_affecte=site_structure_accueil.id
                               )
        user.save()
        permissions = ["site_voir", "recueil_da_voir", "recueil_da_creer_brouillon",
                       "recueil_da_modifier_brouillon"]
        self._call_request(user, permissions)

        # ADMINISTRATEUR_PREFECTURE
        user = Utilisateur(email="admin_pref@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='ADMINISTRATEUR_PREFECTURE',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_prefecture.id
                               )
        user.save()
        permissions = ["utilisateur_creer", "utilisateur_modifier", "utilisateur_voir",
                       "utilisateur_changer_mot_de_passe_utilisateur", "site_voir"]
        self._call_request(user, permissions)

        # GESTIONNAIRE_NATIONAL
        user = Utilisateur(email="gest_nat@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user, role='GESTIONNAIRE_NATIONAL')
        user.save()
        permissions = ["recueil_da_voir", "recueil_da_prefecture_rattachee_sans_limite",
                       "demande_asile_voir", "demande_asile_prefecture_rattachee_sans_limite", "droit_voir",
                       "droit_prefecture_rattachee_sans_limite", "site_voir", "site_sans_limite_site_affecte",
                       "usager_voir", "usager_prefecture_rattachee_sans_limite", "analytics_voir"]
        self._call_request(user, permissions)

        # RESPONSABLE_GU_ASILE_PREFECTURE
        user = Utilisateur(email="respo_gu@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='RESPONSABLE_GU_ASILE_PREFECTURE',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_gu.id
                               )
        user.save()
        permissions = ["utilisateur_voir", "utilisateur_creer", "site_voir", "site_modifier",
                       "site_creneaux_gerer", "site_rendez_vous_gerer", "site_actualite_gerer",
                       "recueil_da_voir", "recueil_da_creer_pa_realise", "recueil_da_modifier_pa_realise",
                       "recueil_da_modifier_demandeurs_identifies", "recueil_da_rendez_vous_gerer",
                       "demande_asile_voir", "demande_asile_orienter", "demande_asile_editer_attestation",
                       "demande_asile_modifier", "demande_asile_requalifier_procedure",
                       "demande_asile_finir_procedure", "usager_voir", "usager_consulter_fpr",
                       "usager_modifier", "usager_etat_civil_modifier", "usager_prefecture_rattachee_modifier",
                       "usager_etat_civil_modifier_photo", "droit_creer", "droit_voir", "droit_support_creer",
                       "droit_support_annuler", "telemOfpra_creer", "historique_voir", "analytics_voir"]
        self._call_request(user, permissions)

        # GESTIONNAIRE_GU_ASILE_PREFECTURE
        user = Utilisateur(email="gest_gu@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='GESTIONNAIRE_GU_ASILE_PREFECTURE',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_gu.id
                               )
        user.save()
        permissions = ["utilisateur_voir", "site_voir", "site_rendez_vous_gerer", "recueil_da_voir",
                       "recueil_da_creer_pa_realise", "recueil_da_modifier_pa_realise",
                       "recueil_da_modifier_demandeurs_identifies", "recueil_da_rendez_vous_gerer",
                       "demande_asile_voir", "demande_asile_orienter", "demande_asile_editer_attestation",
                       "demande_asile_modifier", "demande_asile_requalifier_procedure",
                       "demande_asile_finir_procedure", "usager_voir", "usager_consulter_fpr",
                       "usager_modifier", "usager_etat_civil_modifier", "usager_prefecture_rattachee_modifier",
                       "usager_etat_civil_modifier_photo", "droit_creer", "droit_voir", "droit_support_creer",
                       "droit_support_annuler", "telemOfpra_creer"]
        self._call_request(user, permissions)

        # GESTIONNAIRE_ASILE_PREFECTURE
        user = Utilisateur(email="gest_apref@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='GESTIONNAIRE_ASILE_PREFECTURE',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_prefecture.id
                               )
        user.save()
        permissions = ["site_voir", "demande_asile_voir", "demande_asile_orienter",
                       "demande_asile_editer_attestation", "demande_asile_modifier",
                       "demande_asile_requalifier_procedure", "demande_asile_finir_procedure",
                       "droit_creer", "droit_voir", "droit_support_creer", "droit_support_annuler",
                       "usager_voir", "usager_consulter_fpr",
                       "usager_modifier", "usager_etat_civil_modifier_photo", "usager_etat_civil_modifier",
                       "usager_prefecture_rattachee_modifier", "telemOfpra_creer", "analytics_voir"]
        self._call_request(user, permissions)

        # GESTIONNAIRE DE TITRES
        user = Utilisateur(email="gest_titres_pref@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
            role='GESTIONNAIRE_DE_TITRES',
            site_rattache=site_prefecture.id,
            site_affecte=site_prefecture.id,
        )
        user.save()
        permissions = ["site_voir", "timbre_voir", "usager_voir", "usager_prefecture_rattachee_sans_limite", "timbre_consommer"]
        self._call_request(user, permissions)

        # ADMINISTRATEUR_DT_OFII
        user = Utilisateur(email="admin_dt_ofii@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='ADMINISTRATEUR_DT_OFII',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_prefecture.id
                               )
        user.save()
        permissions = ["utilisateur_creer", "utilisateur_modifier", "utilisateur_voir",
                       "site_voir", "utilisateur_changer_mot_de_passe_utilisateur"]
        self._call_request(user, permissions)

        # RESPONSABLE_GU_DT_OFII
        user = Utilisateur(email="respo_gu_dt_ofii@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='RESPONSABLE_GU_DT_OFII',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_gu.id
                               )
        user.save()
        permissions = ["site_voir", "site_modifier", "site_creneaux_gerer",
                       "site_rendez_vous_gerer", "site_actualite_gerer", "recueil_da_voir", "analytics_voir"]
        self._call_request(user, permissions)

        # GESTIONNAIRE_GU_DT_OFII
        user = Utilisateur(email="gest_gu_dt_ofii@test.com", **kwargs)
        user.controller.init_basic_auth()
        set_user_accreditation(user,
                               role='GESTIONNAIRE_GU_DT_OFII',
                               site_rattache=site_prefecture.id,
                               site_affecte=site_gu.id
                               )
        user.save()
        permissions = ["site_voir", "site_actualite_gerer", "recueil_da_voir"]
        self._call_request(user, permissions)
