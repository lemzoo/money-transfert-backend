import json

from connector.mail import mail_demande_asile_rejected

from tests import common
from tests.fixtures import *
from tests.broker.fixtures import *

from sief.tasks.email import mail

class TestMailAlert(common.BaseTest):

    def test_mail_demande_asile_rejected(self, message, site_prefecture):
        site_prefecture.email = 'test@test.com'
        site_prefecture.save()
        msg_ctx = {
            'demande_asile': {
                'decision_definitive_resultat': 'REJET',
                'decisions_definitives': [{'date': '2017-01-28T00:00:00+00:00',
                                           'date_notification': '2017-01-28T00:00:00+00:00',
                                           'nature': 'IND', 'numero_skipper': 'XXXX',
                                           'entite': 'CNDA'}],
                'id': '1',
                'prefecture_rattachee': {'id': str(site_prefecture.id)},
                'statut': 'DECISION_DEFINITIVE',
                'type_demandeur': 'PRINCIPAL',
                'usager': {'id': 1},
                'identifiant_inerec': 'ABCDEF',
            },
            'usager': {
                'date_naissance': '1970-02-14T02:37:32+00:00',
                'identifiant_agdref': '123456789',
                'identifiant_portail_agdref': '123456abcd',
                'nationalites': [{'code': 'YEM', 'libelle': 'yéménite'},
                                 {'code': 'BOL', 'libelle': 'bolivienne'}],
                'nom': 'LeNom',
                'pays_naissance': {'code': 'LBY', 'libelle': 'LIBYE'},
                'prenoms': ['LePrenom1', 'LePrenom2'],
                'sexe': 'M',
                'situation_familiale': 'CONCUBIN',
                'ville_naissance': 'Tripoli'
            }
        }

        message.json_context = json.dumps(msg_ctx)

        with mail.record_messages() as outbox:
            mail_demande_asile_rejected(handler=None, msg=message)
            assert len(outbox) == 1
            sent_email = outbox[0]
            assert sent_email.sender == 'ALERTE SI AEF <alerte-si-aef-dgef@interieur.gouv.fr>'
            assert sent_email.recipients == ['test@test.com']
            assert sent_email.subject == 'Décision\u00A0définitive de rejet de demande d\'asile - numéro étranger 123456789'
            assert sent_email.body == """
À l'attention du service éloignement de {libelle},

Une décision définitive de rejet de demande d'asile a été enregistrée dans le SI AEF pour l'usager ci-dessous :

Numéro étranger : 123456789
Nom : LeNom
Nom d'usage : -
Prénom(s) : LePrenom1, LePrenom2
Sexe : M
Date de naissance : 14/02/1970
Ville de naissance : Tripoli
Pays de naissance : LIBYE
Nationalité(s) : yéménite, bolivienne
Situation familiale : Concubin(e)

Détail de la décision :

Sens de la décision : Rejet
Nature : Irrecevable nouvelle demande
Date de la décision : 28/01/2017
Date de la notification : 28/01/2017
Entité : CNDA
Numéro SKIPPER : XXXX
Identifiant INEREC : ABCDEF
""".format(libelle=site_prefecture.libelle)
