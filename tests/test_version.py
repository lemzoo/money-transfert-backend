import re

from tests import common
from tests.test_auth import user


class TestVersion(common.BaseTest):
    def test_get_version(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        r = user_req.get('/version')
        assert r.status_code == 200
        assert 'version' in r.data
        assert re.match('\d{1,2}\.\d{1,2}\.\d{1,3}', r.data['version'])
