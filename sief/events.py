"""
Centralize the events
"""

from flask.ext.restful import Resource

from core.tools import Tree
from core.auth import current_user, login_required

from broker_dispatcher import BrokerDispatcher

from sief.permissions import POLICIES as p
from sief.event_handler import event_handlers_factory


class Event:

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<Event %s>' % self.name

    def __eq__(self, other):
        if isinstance(other, Event):
            return self.name == other.name
        else:
            return self.name == other

    def send(self, origin=None, **kwargs):
        origin = str(origin or current_user.pk)
        return broker_dispatcher.send(self.name, origin=origin, context=kwargs)


class EventTree(Tree):

    def build_leaf(self, route):
        return Event(route)


EVENTS = EventTree({
    'utilisateur': ('cree', 'modifie'),
    'site': ('cree', 'modifie', 'ferme', {'creneaux': ('cree', 'supprime')}),
    'recueil_da': ('modifie', 'pa_realise', 'demandeurs_identifies',
                   'exploite', 'exploite_by_step', 'annule', {'prefecture_rattachee': 'modifie'}),
    'droit': ('cree', 'retire', 'refus', 'modifie', {'prefecture_rattachee': 'modifie'},
              {'support': ('cree', 'modifie', 'annule')}),
    'demande_asile': ('cree', 'modifie', 'oriente', 'procedure_requalifiee',
                      'en_cours_procedure_dublin', 'en_attente_ofpra',
                      'attestation_edite', 'procedure_finie', 'introduit_ofpra', 'dublin_modifie',
                      'decision_definitive', 'decision_attestation',
                      'recevabilite_ofpra',
                      {'prefecture_rattachee': 'modifie'}),
    'usager': ('cree', 'modifie', {'etat_civil': ('modifie', 'valide')},
               {'localisation': 'modifie'}, {'prefecture_rattachee': 'modifie'}),
    'telemOfpra': ('cree'),
})


broker_dispatcher = BrokerDispatcher()


def init_events(app, **kwargs):

    app.json_encoder.register(Event, lambda x: x.name)

    class BaseBrokerResource(Resource):
        method_decorators = [p.broker.gerer.require(http_exception=403),
                             login_required]  # Reversed order

    app.config['BROKER_API_BASE_RESOURCE_CLS'] = BaseBrokerResource
    app.config['BROKER_AVAILABLE_EVENTS'] = [e.name for e in EVENTS]
    if 'event_handlers' not in kwargs:
        kwargs['event_handlers'] = event_handlers_factory(app)
    users = app.config['ALERT_MAIL_BROKER']
    if not users:
        from sief.model.utilisateur import Utilisateur
        users = Utilisateur.objects(accreditations__role='ADMINISTRATEUR_NATIONAL')
        app.config['ALERT_MAIL_BROKER'] = [u.email for u in users]

    disable_events = app.config['DISABLE_EVENTS']
    if disable_events:
        from unittest.mock import MagicMock
        broker_dispatcher.send = MagicMock()
    else:
        broker_dispatcher.init_app(app, **kwargs)

    return broker_dispatcher
