import pytest

from tests import common
from tests.test_auth import user

from sief.permissions import POLICIES as p


class TestRole(common.BaseTest):

    @classmethod
    def setup_class(cls):
        # Monkey patch roles
        import sief.roles
        from sief.model.utilisateur import Accreditation
        cls.origin_roles = sief.roles.ROLES
        cls.origin_roles_choices = Accreditation._fields['role'].choices
        roles = {
            'role-1': [],  # Role with no permissions
            'role_on_user': p.utilisateur  # Role with a PolicyTree
        }
        sief.roles.ROLES = roles
        sief.roles.ROLE_TO_CAN_SET_ROLES['role_on_user'] = ('role_on_user', 'role-1')
        Accreditation._fields['role'].choices = list(roles.keys())
        super().setup_class()

    @classmethod
    def teardown_class(cls):
        # Undo the monkey patching
        import sief.roles
        from sief.model.utilisateur import Accreditation
        sief.roles.ROLES = cls.origin_roles
        del sief.roles.ROLE_TO_CAN_SET_ROLES['role_on_user']
        Accreditation._fields['role'].choices = cls.origin_roles_choices

    def test_change_self_role(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.patch('/moi', data={'role': 'role-1'})
        assert r.status_code == 400, r

    @pytest.mark.xfail
    def test_add_role(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Can't change role without proper permission
        route = '/utilisateurs/%s' % user.id
        r = user_req.patch(route, data={'role': 'role-1'})
        assert r.status_code == 403, r
        # Add right permission and retry
        user.permissions.append(p.utilisateur.modifier.name)
        user.save()
        r = user_req.patch(route, data={'role': 'role-1'})
        assert r.status_code == 200, r
        assert r.data.get('role', '<not_set>') == 'role-1'
        # Try to remove the role as well
        r = user_req.patch(route, data={'role': None})
        assert r.status_code == 200, r
        assert 'role' not in r.data

    def test_add_bad_role(self, user):
        user.permissions.append(p.utilisateur.modifier.name)
        user.save()
        user_req = self.make_auth_request(user, user._raw_password)
        for bad_role in ['not_a_role', '', 42]:
            r = user_req.patch('/utilisateurs/%s' % user.id, data={'role': bad_role})
            assert r.status_code == 400, r

    def test_role_give_permissions(self, user):
        user.test_set_accreditation(role="role_on_user")
        user.save()
        # Now the user have the permission through it role
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/utilisateurs/%s' % user.id
        r = user_req.patch(route, data={'nom': 'New-nom'})
        assert r.status_code == 200, r
