from tests import common
from tests.fixtures import *
from sief.permissions import POLICIES as p
from sief.managers.referentials_manager import load_default
from sief.managers.populate.populate_manager import database
from sief.model import Usager


import os


class TestPopulate(common.BaseSolrTest):

    def test_manager_populate(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name, p.site.voir.name, p.utilisateur.voir.name]
        user.test_set_accreditation(role='ADMINISTRATEUR')
        user.save()

        # Empty database
        r = user_req.get('/usagers')
        assert r.status_code == 200, r
        assert r.data['_meta']['total'] == 0, r

        if os.path.isfile('./populate_sites.csv'):
            os.remove('./populate_sites.csv')
        if os.path.isfile('./populate_utilisateurs.csv'):
            os.remove('./populate_utilisateurs.csv')

        # Now initialize the populate
        load_default()
        self.app.config['POPULATE_DB'] = True
        database(password='Azerty', usagers='100', fake=True, log=True)

        # Check CSV
        assert os.path.isfile('./populate_sites.csv')
        assert os.path.isfile('./populate_utilisateurs.csv')
        num_sites = sum(1 for line in open('./populate_sites.csv'))
        num_users = sum(1 for line in open('./populate_utilisateurs.csv'))
        assert num_sites > 1
        assert num_users > 1
        os.remove('./populate_sites.csv')
        os.remove('./populate_utilisateurs.csv')

        # Check Database
        r = user_req.get('/sites')
        assert r.status_code == 200, r
        # total = nb_line - title_csv
        assert r.data['_meta']['total'] == num_sites - 1, r

        r = user_req.get('/utilisateurs')
        assert r.status_code == 200, r
        # total = nb_line - title_csv + admin
        assert r.data['_meta']['total'] == num_users, r

        r = user_req.get('/usagers')
        assert r.status_code == 200, r
        assert r.data['_meta']['total'] >= 100, r

        usagers_with_auth = Usager.objects(basic_auth__exists=True)
        assert usagers_with_auth is not None
        assert len(usagers_with_auth) > 0
