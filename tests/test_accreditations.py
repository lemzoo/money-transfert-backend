import pytest
from datetime import datetime, timedelta

from tests import common
from tests.fixtures import *
from sief.permissions import POLICIES as p

from sief.tasks.email import mail

VALID_DIGITS = 20


class TestUtilisateurAccreditation(common.BaseTest):

    def test_empty_list_of_accreditation(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions.append(p.utilisateur.voir.name)
        user.save()

        route = '/utilisateurs/{}/accreditations' .format(user.pk)
        response = user_req.get(route)

        assert response.status_code == 200
        assert response.data['_items'] == []

    def test_show_accreditations_is_denied_without_permissions(self, user):
        user_req = self.make_auth_request(user, user._raw_password)

        route = '/utilisateurs/{}/accreditations' .format(user.pk)
        response = user_req.get(route)

        assert response.status_code == 403

    def test_non_empty_list_of_accreditation(self, user_with_accreditations):
        user = user_with_accreditations
        user_req = self.make_auth_request(user, user._raw_password)

        route = '/utilisateurs/{}/accreditations' .format(user.pk)
        response = user_req.get(route)

        assert response.status_code == 200
        number_of_accreditations = len(user_with_accreditations.accreditations)
        assert len(response.data['_items']) == number_of_accreditations

    def test_create_user_without_role_and_site_affecte(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        user.save()
        accreditation = {}

        payload = {
            'email': 'utilisateur.sans.role.sans.site@user.com',
            'nom': 'Gestionnaire',
            'prenom': 'Dtofii'
        }

        ret = user_req.post('/utilisateurs', data=payload)
        assert ret.status_code == 201, ret

        user_created_id = ret.data['id']

        route = '/utilisateurs/%s/accreditations' % user_created_id
        ret = user_req.post(route, data=accreditation)
        assert ret.status_code == 400, ret
        assert ret.data['_schema'] == 'Un role ou un site affecté est requis'

        ret = user_req.get(route)
        assert len(ret.data.get('_items')) == 0

    def test_create_user_with_duplicate_accreditation(self, user,
                                                      site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE',
                                    site_affecte=site_prefecture)
        user.save()
        accreditation = {'role': 'GESTIONNAIRE_ASILE_PREFECTURE',
                         'site_affecte': site_prefecture.id}

        payload = {
            'email': 'gestionnaire.asile.prefecture@user.com',
            'nom': 'Gestionnaire',
            'prenom': 'Dtofii'
        }

        ret = user_req.post('/utilisateurs', data=payload)
        assert ret.status_code == 201, ret

        user_created_id = ret.data['id']

        route = '/utilisateurs/%s/accreditations' % user_created_id
        ret = user_req.post(route, data=accreditation)
        assert ret.status_code == 201, ret

        ret = user_req.get(route)
        assert len(ret.data.get('_items')) == 1

        ret = user_req.post(route, data=accreditation)
        assert ret.status_code == 400, ret

        ret = user_req.get(route)
        assert len(ret.data.get('_items')) == 1

    def test_create_user_mono_role(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        accreditation = {'role': 'ADMINISTRATEUR_NATIONAL'}

        route = '/utilisateurs/%s/accreditations' % another_user.id
        ret = user_req.post(route, data=accreditation)
        assert ret.status_code == 201, ret

        ret = user_req.get(route)
        assert len(ret.data.get('_items')) == 1

    def test_create_user_multi_role(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        payload = {
            'email': 'utilisateur-multi-role@user.com',
            'nom': 'Gestionnaire',
            'prenom': 'Dtofii',
            'accreditations': [
                {'role': 'ADMINISTRATEUR_NATIONAL'},
                {
                    'role': 'ADMINISTRATEUR_PREFECTURE',
                    'site_affecte': site.id
                },
                {
                    'role': 'ADMINISTRATEUR',
                    'fin_validite': '2016-01-01'
                }
            ]
        }
        ret = user_req.post('/utilisateurs', data=payload)
        assert ret.status_code == 201
        ret = user_req.get('/utilisateurs/%s/accreditations' % ret.data['id'])
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 3
        common.assert_response_contains_links(ret, ['self', 'create'])
        accreditations = ret.data['_items']
        for accreditation in accreditations:
            assert set(accreditation['_links'].keys()) == {'self', 'update'}

    def test_create_user_site_rattache(self, user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE', site_affecte=site_gu.autorite_rattachement)
        user.save()
        payload = {
            'email': 'utilisateur-site-rattache@user.com',
            'nom': 'Doe',
            'prenom': 'John',
            'accreditations': [{'role': 'GESTIONNAIRE_GU_ASILE_PREFECTURE', 'site_affecte': site_gu.id}]
        }
        ret = user_req.post('/utilisateurs', data=payload)
        assert ret.status_code == 201
        assert len(ret.data['accreditations']) == 1
        accr = ret.data['accreditations'][0]
        assert accr['role'] == 'GESTIONNAIRE_GU_ASILE_PREFECTURE'
        assert accr['site_affecte']['id'] == str(site_gu.id)
        assert accr['site_rattache']['id'] == str(site_gu.autorite_rattachement.id)

    def test_bad_create_user_multi_role(self, user, site):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.utilisateur.creer.name]
        user.save()
        payload = {
            'email': 'utilisateur-bad-multi-role@user.com',
            'nom': 'Gestionnaire',
            'prenom': 'Dtofii',
        }
        GOOD_ACCR = {'role': 'ADMINISTRATEUR'}
        for bad in (None, 42, 'not a list', {0: GOOD_ACCR}, [1, 2], [GOOD_ACCR, None],
                    [GOOD_ACCR, {}], [{'role': 'ADMINISTRATEUR', 'dummy': 'foo'}],
                    [{'fin_validite': '2016-01-01'}], [{'role': 'ADMINISTRATEUR_PREFECTURE'}]):
            payload['accreditations'] = bad
            ret = user_req.post('/utilisateurs', data=payload)
            assert ret.status_code == 400
            assert set(ret.data.keys()) == {'accreditations'}

    def test_add_accreditation(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        accreditation = {'role': 'ADMINISTRATEUR_NATIONAL'}

        route = '/utilisateurs/%s/accreditations' % another_user.id
        ret = user_req.post(route, data=accreditation)
        assert ret.status_code == 201, ret

        ret = user_req.get(route)
        assert len(ret.data.get('_items')) == 1

    def test_bad_add_accreditation(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()

        # Should not be able to add accreditation by updating user
        ret = user_req.patch('/utilisateurs/%s' % another_user.id,
                             data={'accreditations': [{'role': 'ADMINISTRATEUR'}]})
        assert ret.status_code == 400, ret
        assert ret.data == {'_schema': ['Unknown field name accreditations']}

        route = '/utilisateurs/%s/accreditations' % another_user.id
        for bad_payload in (None, 42, 'not a dict', {}, {'role': 'dummy'}, {'role': 'ADMINISTRATEUR', 'dummy': 'field'}):
            ret = user_req.post(route, data=bad_payload)
            assert ret.status_code == 400

    def test_add_accreditation_site_rattache(self, user, another_user, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE', site_affecte=site_gu.autorite_rattachement)
        user.save()
        accreditation = {'role': 'GESTIONNAIRE_GU_ASILE_PREFECTURE', 'site_affecte': site_gu.id}

        route = '/utilisateurs/%s/accreditations' % another_user.id
        ret = user_req.post(route, data=accreditation)
        assert ret.status_code == 201, ret
        assert ret.data['role'] == 'GESTIONNAIRE_GU_ASILE_PREFECTURE'
        assert ret.data['site_affecte']['id'] == str(site_gu.id)
        assert ret.data['site_rattache']['id'] == str(site_gu.autorite_rattachement.id)

    def test_update_user_multi_role(self, user, another_user, site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        accreditations = [{'role': 'ADMINISTRATEUR_NATIONAL'},
                          {'role': 'ADMINISTRATEUR_PREFECTURE',
                           'site_affecte': site_prefecture.id}]

        route = '/utilisateurs/%s/accreditations' % another_user.id
        for accreditation in accreditations:
            ret = user_req.post(route, data=accreditation)
            assert ret.status_code == 201, ret

        ret = user_req.get(route)
        assert len(ret.data.get('_items')) == 2

    def test_get_valid_accreditations(self, user, user_with_accreditations):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE')
        user.save()
        route = '/utilisateurs/%s/accreditations' % user_with_accreditations.pk
        for accreditation in user_with_accreditations.accreditations:
            accr_route = route + '/%s' % accreditation.id
            ret = user_req.get(accr_route)
            items = ret.data.get('_items')
            assert ret.status_code == 200
            assert 'role' or 'site_affecte' in items

    def test_get_invalid_accreditation(self, user, user_with_accreditations):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE')
        user.save()
        route = '/utilisateurs/%s/accreditations' % user_with_accreditations.pk
        id_invalid_accr = len(user_with_accreditations.accreditations)
        route += '/%s' % id_invalid_accr

        # Cannot get the accreditation which not exist on the list
        with pytest.raises(IndexError):
            user_req.get(route)

    def test_updating_single_accreditation(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        another_user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        another_user.save()

        tomorrow = (datetime.utcnow() + timedelta(1)).isoformat()
        payload = {'fin_validite': tomorrow}
        id_accreditation_to_update = another_user.accreditations[0].id
        route = '/utilisateurs/{0}/accreditations/{1}'\
            .format(another_user.id, id_accreditation_to_update)
        ret = user_req.patch(route, data=payload)
        assert ret.status_code == 200, ret

        ret = user_req.get(route)
        fin_validite = ret.data['fin_validite']

        assert fin_validite[:VALID_DIGITS] == tomorrow[:VALID_DIGITS]

    def test_cannot_update_my_own_accreditations(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()

        tomorrow = (datetime.utcnow() + timedelta(1)).isoformat()
        payload = {'fin_validite': tomorrow}
        id_accreditation_to_update = user.accreditations[0].id

        # Try to use the route /moi
        route = '/moi/accreditations/%s' % id_accreditation_to_update
        ret = user_req.patch(route, data=payload)
        assert ret.status_code == 405, ret

        # Try to use the route /utilisateur
        route = '/utilisateurs/{0}/accreditations/{1}'\
            .format(user.id, id_accreditation_to_update)
        ret = user_req.patch(route, data=payload)
        assert ret.status_code == 400, ret
        msg_error = ["Vous n'avez pas le droit de modifier vos habilitations"]
        assert ret.data['accreditations'] == msg_error

    def test_cannot_update_an_accreditation_role(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        another_user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        another_user.save()

        payload = {'role': 'GESTIONNAIRE_NATIONAL'}
        id_accreditation_to_update = another_user.accreditations[0].id
        route = '/utilisateurs/{0}/accreditations/{1}'\
            .format(another_user.id, id_accreditation_to_update)
        ret = user_req.patch(route, data=payload)
        assert ret.status_code == 400, ret
        # TODO: avoir un message en français
        assert '_schema' in ret.data

    def test_updating_all_accreditations(self, user,
                                         another_user,
                                         site_prefecture):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        another_user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        another_user.test_set_accreditation(role='GESTIONNAIRE_NATIONAL')
        another_user.test_set_accreditation(role='ADMINISTRATEUR_PREFECTURE',
                                            site_affecte=site_prefecture)
        another_user.save()

        tomorrow = (datetime.utcnow() + timedelta(days=1)).isoformat()
        payload = {'fin_validite': tomorrow}
        for accreditation in another_user.accreditations:
            route = '/utilisateurs/{0}/accreditations/{1}'\
                .format(another_user.id, accreditation.id)
            ret = user_req.patch(route, data=payload)
            assert ret.status_code == 200, ret

            ret = user_req.get(route)
            assert ret.status_code == 200, ret
            fin_validite = ret.data.get('fin_validite')

            assert fin_validite[:VALID_DIGITS] == tomorrow[:VALID_DIGITS]

        # User is automatically disabled once all it accreditations are
        ret = user_req.get('/utilisateurs/%s' % another_user.id)
        assert ret.status_code == 200
        assert ret.data['fin_validite'][:VALID_DIGITS] == tomorrow[:VALID_DIGITS]

    def test_enable_single_accreditation(self, user, another_user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()
        another_user_req = self.make_auth_request(another_user,
                                                  another_user._raw_password)
        another_user.test_set_accreditation(role='ADMINISTRATEUR_NATIONAL')
        another_user.save()
        another_user.reload()

        # Disable the accreditation first
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        payload = {'fin_validite': yesterday}
        id_accreditation_to_update = another_user.accreditations[0].id
        route = '/utilisateurs/{0}/accreditations/{1}'\
            .format(another_user.id, id_accreditation_to_update)
        ret = user_req.patch(route, data=payload)
        assert ret.status_code == 200

        # User is now disabled
        ret = another_user_req.get('/moi')
        assert ret.status_code == 401

        # When the admin reactivates the accreditation
        payload = {'fin_validite': None}
        id_accreditation_to_update = another_user.accreditations[0].id
        route = '/utilisateurs/{0}/accreditations/{1}'\
            .format(another_user.id, id_accreditation_to_update)
        ret = user_req.patch(route, data=payload)
        assert ret.status_code == 200

        # Then another user can use this accreditation
        ret = another_user_req.get('/moi')
        assert ret.status_code == 200
        assert 'fin_validite' not in ret.data

    def test_user_system(self, administrateur, another_user):
        user_req = self.make_auth_request(administrateur,
                                          administrateur._raw_password)
        accreditations = [{'role': 'SYSTEME_INEREC'},
                          {'role': 'SYSTEME_DNA'}]

        route = '/utilisateurs/%s/accreditations' % another_user.id
        for accreditation in accreditations:
            ret = user_req.post(route, data=accreditation)
            assert ret.status_code == 201, ret

        ret = user_req.get(route)
        accreditations = ret.data['_items']
        assert len(accreditations) == 2

        # Get the user and check system_account
        route_to_get_user = '/utilisateurs/%s' % another_user.id
        ret = user_req.get(route_to_get_user)
        assert ret.data['system_account'] is True

        accreditations = ret.data.get('accreditations')

        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        payload = {'fin_validite': yesterday}
        api_route = route = '/utilisateurs/{0}/accreditations'\
            .format(another_user.id)

        # Disable first accreditation system and check if the account valid
        route = api_route + '/%s' % accreditations[0]['id']
        ret = user_req.patch(route, data=payload)
        fin_validite = ret.data['fin_validite']
        assert fin_validite[:VALID_DIGITS] == yesterday[:VALID_DIGITS]

        # Check if system account is True and fin_validite is None
        ret = user_req.get(route_to_get_user)
        assert ret.data['system_account'] is True
        assert 'fin_validite' not in ret.data

        # Disable last accreditation system and check if the user is invalid
        route = api_route + '/%s' % accreditations[1]['id']
        ret = user_req.patch(route, data=payload)
        fin_validite = ret.data['fin_validite']
        assert fin_validite[:VALID_DIGITS] == yesterday[:VALID_DIGITS]

        # Check if fin_validite is setted to the same date
        ret = user_req.get(route_to_get_user)
        assert 'fin_validite' in ret.data
        fin_validite = ret.data['fin_validite']
        assert fin_validite[:VALID_DIGITS] == yesterday[:VALID_DIGITS]

    def test_update_user_system_by_admin_local(self, administrateur_national,
                                               administrateur_prefecture,
                                               another_user):
        admin_nat_req = self.make_auth_request(administrateur_national,
                                          administrateur_national._raw_password)
        accreditations = [{'role': 'SYSTEME_INEREC'},
                          {'role': 'SYSTEME_DNA'}]

        route = '/utilisateurs/%s/accreditations' % another_user.id
        for accreditation in accreditations:
            ret = admin_nat_req.post(route, data=accreditation)
            assert ret.status_code == 201, ret

        # Check if the admin can always update user system
        route = '/utilisateurs/%s?overall' % another_user.pk
        payload = {'nom': 'System'}
        ret = admin_nat_req.patch(route, data=payload)
        assert ret.status_code == 200

        # user administrateur_prefecture to updated the user system data
        admin_pref_req = self.make_auth_request(administrateur_prefecture,
                                          administrateur_prefecture._raw_password)
        payload = {'nom': 'New-System'}
        ret = admin_pref_req.patch(route, data=payload)
        assert ret.status_code == 400
        errors = '_errors'
        msg_error = 'Un administrateur local ne peut pas modifer un compte systeme.'
        assert errors in ret.data
        assert ret.data[errors][0] == msg_error


class TestUtilisateurPreference(common.BaseTest):

    def test_show_my_preferences(self, user_with_accreditations):
        user_req = self.make_auth_request(user_with_accreditations,
                                          user_with_accreditations._raw_password)

        # Preferences are not taken into account by the backend
        user_with_accreditations.preferences.current_accreditation_id = 42
        user_with_accreditations.save()

        # Check the preferences documents
        ret = user_req.get('/moi')
        assert ret.status_code == 200, ret
        assert 'preferences' in ret.data
        assert ret.data['preferences'] == {'current_accreditation_id': 42}

    def test_admin_cannot_see_users_preferences(self, administrateur_national,
                                                user_with_accreditations):
        admin_nat_req = self.make_auth_request(administrateur_national,
                                          administrateur_national._raw_password)
        route = '/utilisateurs/%s' % user_with_accreditations.pk
        ret = admin_nat_req.get(route)
        assert ret.status_code == 200, ret
        assert 'preferences' not in ret.data

    def test_admin_cannot_see_users_preferences_in_list(self, administrateur_national,
                                                        user_with_accreditations):
        admin_nat_req = self.make_auth_request(administrateur_national,
                                          administrateur_national._raw_password)

        # Check old api route
        ret = admin_nat_req.get('/utilisateurs')
        assert ret.status_code == 200, ret
        # User can see himself and all others users
        assert len(ret.data['_items']) == 2
        # Should not be able to see preferences from there
        assert not any(u for u in ret.data['_items'] if 'preferences' in u)

        # Same thing with overall
        ret = admin_nat_req.get('/utilisateurs?overall')
        assert ret.status_code == 200, ret
        assert len(ret.data['_items']) == 2
        assert not any(u for u in ret.data['_items'] if 'preferences' in u)


class TestAddingCustomHeaderForAccreditation(common.BaseTest):

    def test_use_first_accreditation_valid(self, administrateur_national):
        admin_nat = administrateur_national
        admin_req = self.make_auth_request(admin_nat, admin_nat._raw_password)

        # Check preferences not in the response
        ret = admin_req.get('/moi')
        assert ret.status_code == 200
        assert 'preferences' not in ret.data

        # Use the first accreditation
        first_accr_id = ret.data['accreditations'][0]['id']
        preferences = {'current_accreditation_id': first_accr_id}
        payload = {'preferences': preferences}

        ret = admin_req.patch('/moi', data=payload)
        assert ret.status_code == 200
        assert 'preferences' in ret.data
        preferences = ret.data['preferences']
        id_accr_pref = preferences['current_accreditation_id']
        assert id_accr_pref == first_accr_id

        # Check the current role by using the id in the preference
        expected_role = administrateur_national.accreditations[0].role
        used_role = ret.data['accreditations'][id_accr_pref]['role']
        assert used_role == expected_role

    def test_user_with_accreditations(self, administrateur_national, another_user, user_with_accreditations):
        user_req = self.make_auth_request(another_user, another_user._raw_password)
        admin_req = self.make_auth_request(administrateur_national, administrateur_national._raw_password)

        # 0. check if preference is not available on user
        # 1. add accreditations
        # 2. use the first one
        # 3. switch to the second
        # 4. disable the first accreditation
        # 5. use patch request to get data by using the second accr
        # 6. use the disabled accreditation header


        # 0. Check preferences not in the user response
        ret = user_req.get('/moi')
        assert ret.status_code == 200
        assert 'preferences' not in ret.data

        # 1. add accreditations
        accreditations = [{'role': 'ADMINISTRATEUR_NATIONAL'},
                          {'role': 'SUPPORT_NATIONAL'}]
        route = '/utilisateurs/%s/accreditations' % another_user.id
        for accreditation in accreditations:
            ret = admin_req.post(route, data=accreditation)
            assert ret.status_code == 201

        # 2. Use the first accreditation
        ret = user_req.get('/moi')
        assert ret.status_code == 200
        first_accr_id = ret.data['accreditations'][0]['id']
        preferences = {'current_accreditation_id': first_accr_id}
        payload = {'preferences': preferences}

        ret = user_req.patch('/moi', data=payload)
        assert ret.status_code == 200
        assert 'preferences' in ret.data
        preferences = ret.data['preferences']
        id_accr_pref = preferences['current_accreditation_id']
        assert id_accr_pref == first_accr_id

        # 3. Use the second accreditation
        second_accr_id = ret.data['accreditations'][1]['id']
        preferences = {'current_accreditation_id': second_accr_id}
        payload = {'preferences': preferences}

        ret = user_req.patch('/moi', data=payload)
        assert ret.status_code == 200
        preferences = ret.data['preferences']
        id_accr_pref = preferences['current_accreditation_id']
        assert id_accr_pref == second_accr_id

        # 4. disable the first accreditation
        route = '/utilisateurs/%s/accreditations/%s' % (another_user.id, first_accr_id)
        now = datetime.utcnow().isoformat()
        payload = {'fin_validite': now}
        ret = admin_req.patch(route, data=payload)
        assert ret.status_code == 200

        # 5. use patch request to get data by using the second accr
        route = '/utilisateurs'
        # Force use the second accreditation
        ret = user_req.get(route, headers={'X-Use-Accreditation': second_accr_id})
        assert ret.status_code == 200

        # 6 Force use the first accreditation which is disabled
        ret = user_req.get(route, headers={'X-Use-Accreditation': first_accr_id})
        assert ret.status_code == 401

    def test_user_with_none_accreditation_id(self,
                                             administrateur_national,
                                             user_with_accreditations,
                                             another_user, site_prefecture,
                                             gestionnaire_gu_asile_prefecture):

        admin_nat_req = self.make_auth_request(administrateur_national,
                                               administrateur_national._raw_password)

        user_req = self.make_auth_request(another_user,
                                          another_user._raw_password)

        total_user = 4
        # 1. add accreditation to user
        # 2. Check if the accreditation was added correctly as expected
        # 3. make request in '/utilisateurs' url which provides the headers
        # 4, 5, 6. make request in '/utilisateurs' url whithout providing the headers

        # 1. add accreditation ADMINISTRATEUR_NATIONAL, 'SUPPORT_NATIONAL'
        # and 'ADMINISTRATEUR_PREFECTURE to user
        accreditations = [{'role': 'ADMINISTRATEUR_NATIONAL'},
                          {'role': 'SUPPORT_NATIONAL'},
                          {'role': 'ADMINISTRATEUR_PREFECTURE',
                           'site_affecte': site_prefecture.id}]
        route = '/utilisateurs/%s/accreditations' % another_user.id
        for accreditation in accreditations:
            ret = admin_nat_req.post(route, data=accreditation)
            assert ret.status_code == 201

        # 2. check if the accreditation was added in the user
        ret = user_req.get('/moi')
        assert ret.status_code == 200
        returned_accreditations = ret.data['accreditations']
        another_user.reload()
        expected_accreditations = another_user.accreditations
        assert len(returned_accreditations) == len(expected_accreditations)

        # 3. make request in '/utilisateurs' url which not provide a specific
        # id of the accreditation.  By default, it will use the first available
        route = '/utilisateurs'
        ret = user_req.get(route)
        assert ret.status_code == 200
        users = ret.data['_items']
        assert len(users) == total_user

        # 4. make request in '/utilisateurs' url which provides a specific
        # id of the accreditation to use in the header 'ADMINISTRATEUR_NATIONAL'
        id_accr_admin_nat = expected_accreditations[0].id
        ret = user_req.get(route, headers={'X-Use-Accreditation': id_accr_admin_nat})
        assert ret.status_code == 200
        users = ret.data['_items']
        assert len(users) == total_user

        # 5. make request in '/utilisateurs' url which provides a specific
        # id of the accreditation to use in the header 'SUPPORT_NATIONAL'
        id_accr_support_nat = expected_accreditations[1].id
        ret = user_req.get(route, headers={'X-Use-Accreditation': id_accr_support_nat})
        assert ret.status_code == 200
        users = ret.data['_items']
        assert len(users) == total_user

        # 6. make request in '/utilisateurs' url which provides a specific
        # id of the accreditation to use in the header 'ADMINISTRATEUR_PREFECTURE'
        id_accr_admin_pref = expected_accreditations[2].id
        ret = user_req.get(route, headers={'X-Use-Accreditation': id_accr_admin_pref})
        assert ret.status_code == 200
        users = ret.data['_items']
        assert len(users) == 1
