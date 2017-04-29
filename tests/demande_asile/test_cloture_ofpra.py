# uncomment this when the route foir floture_ofpra has been activated
# Reouverture FEB
# import pytest
# from datetime import datetime
# import copy
#
# from tests import common
# from tests.fixtures import *
#
# from sief.model.demande_asile import DemandeAsile
# from sief.permissions import POLICIES as p
#
# class TestDemandeAsileClotureOfpra(common.BaseTest):
#
#     def test_cloture(self, user_with_site_affecte, da_attente_ofpra):
#         user = user_with_site_affecte
#         user_req = self.make_auth_request(user, user._raw_password)
#         user.permissions = [p.demande_asile.cloture_ofpra.name,
#                             p.demande_asile.voir.name]
#         user.save()
#         route = '/demandes_asile/%s/cloture_ofpra' % da_attente_ofpra.pk
#         payload = {'date_notification': '2017-01-12'}
#         r = user_req.post(route, data=payload)
#         assert r.status_code == 201, r
#
#         route = '/demandes_asile/%s' % da_attente_ofpra.pk
#         r = user_req.get(route)
#         assert r.status_code == 200, r
#         assert r.data['statut'] == 'CLOTURE_OFPRA'
#         assert len(r.data['clotures_ofpra']) == 1
#
#     def test_cloture_no_date(self, user_with_site_affecte, da_attente_ofpra):
#         user = user_with_site_affecte
#         user_req = self.make_auth_request(user, user._raw_password)
#         user.permissions = [p.demande_asile.cloture_ofpra.name,
#                             p.demande_asile.voir.name]
#         user.save()
#         route = '/demandes_asile/%s/cloture_ofpra' % da_attente_ofpra.pk
#         payload = {'date_notification': ''}
#         r = user_req.post(route, data=payload)
#         assert r.status_code == 400, r
#
#     def test_cloture_no_demande_asile(self, user_with_site_affecte):
#         user = user_with_site_affecte
#         user_req = self.make_auth_request(user, user._raw_password)
#         user.permissions = [p.demande_asile.cloture_ofpra.name,
#                             p.demande_asile.voir.name]
#         user.save()
#         route = '/demandes_asile/0/cloture_ofpra'
#         payload = {'date_notification': ''}
#         r = user_req.post(route, data=payload)
#         assert r.status_code == 404, r
#
