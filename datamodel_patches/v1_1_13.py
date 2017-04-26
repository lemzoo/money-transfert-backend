"""
Patch 1.1.12 => 1.1.13
Mise à jour de demande_asile.procedure.requalifications.date_notification
"""

import json
from datetime import datetime

from mongopatcher import Patch

patch_v1113 = Patch('1.1.12', '1.1.13', patchnote=__doc__)


@patch_v1113.fix
def _initialize_procedure_date_notification_when_missing(db):
    demandes_asile = db['demande_asile'].find({'procedure.date_notification':
                                               {'$exists': False}}, snapshot=True)
    for demande_asile in demandes_asile:
        date_decision_sur_attestation = demande_asile['date_decision_sur_attestation']
        db['demande_asile'].update_one(
            {'_id': demande_asile['_id']},
            {'$set': {'procedure.date_notification': date_decision_sur_attestation}}
        )


@patch_v1113.fix
def _update_procedure_requalifications_date_notification(db):
    demandes_asile = db['demande_asile'].find({'procedure.requalifications':
                                                {'$exists': True, '$ne': []}}, snapshot=True)

    def get_oldest_demande_asile_date_decision_sur_attestiation():
        initial_demande_asile = db['demande_asile.history'].find_one(
            {'origin': demande_asile['_id'], 'version': 2},
        )
        initial_date_decision_sur_attestation = json.loads(initial_demande_asile['content'])['date_decision_sur_attestation']['$date']
        return datetime.fromtimestamp(initial_date_decision_sur_attestation / 1000)

    def shift_procedure_requalifications_date_notification(demande_asile):
        new_requalifications = demande_asile['procedure']['requalifications'].copy()
        for curr_req, next_req in zip(new_requalifications[:-1], new_requalifications[1:]):
            curr_req['date_notification'] = next_req['date_notification']
        new_requalifications[-1]['date_notification'] = get_oldest_demande_asile_date_decision_sur_attestiation()

        db['demande_asile'].update_one(
            {'_id': demande_asile['_id']},
            {'$set': {'procedure.requalifications': new_requalifications}}
        )

    def use_most_recent_requalification_date_notifiation_for_procedure(demande_asile):
        most_recent_date_notification = demande_asile['procedure']['requalifications'][0]['date_notification']
        db['demande_asile'].update_one(
            {'_id': demande_asile['_id']},
            {'$set': {'procedure.date_notification': most_recent_date_notification}}
        )

    for demande_asile in demandes_asile:
        use_most_recent_requalification_date_notifiation_for_procedure(demande_asile)
        shift_procedure_requalifications_date_notification(demande_asile)
