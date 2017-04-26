from flask import current_app
import flask_mail
import dateutil

from sief.model.site import Prefecture
from sief.model.demande_asile import DECISIONS_DEFINITIVES, DECISIONS_DEFINITIVES_DESCRIPTIONS

from sief.tasks.email import mail


DA_REJECTED_MAIL_TEMPLATE = """
À l'attention du service éloignement de {libelle_prefecture},

Une décision définitive de rejet de demande d'asile a été enregistrée dans le SI AEF pour l'usager ci-dessous :

Numéro étranger : {number}
Nom : {name}
Nom d'usage : {name_usage}
Prénom(s) : {first_names}
Sexe : {sex}
Date de naissance : {birth_date:%d/%m/%Y}
Ville de naissance : {birth_city}
Pays de naissance : {birth_country}
Nationalité(s) : {nationalities}
Situation familiale : {family_situation}

Détail de la décision :

Sens de la décision : Rejet
Nature : {nature}
Date de la décision : {decision_date:%d/%m/%Y}
Date de la notification : {notification_date:%d/%m/%Y}
Entité : {entity}
Numéro SKIPPER : {skipper}
Identifiant INEREC : {inerec_id}
"""

FAMILY_SITUATION_CONVERT = {
    'CELIBATAIRE': 'Célibataire',
    'DIVORCE': 'Divorcé(e)',
    'MARIE': 'Marié(e)',
    'CONCUBIN': 'Concubin(e)',
    'SEPARE': 'Séparé(e)',
    'VEUF': 'Veuf(ve)',
    'PACSE': 'Pacsé(e)'
}


def _format_demande_asile_rejected_message(prefecture, usager, demande_asile, decision):
    msg = flask_mail.Message(
        sender=current_app.config.get('MAIL_ALERT_SENDER',
                                      'ALERTE SI AEF <alerte-si-aef-dgef@interieur.gouv.fr>'),
        # \u00A0 is unicode code for non-breaking space. This is necessary due to a bug in flask-mail
        # with Python3.4 (fixed on
        # https://github.com/monterosa/flask-mail/commit/135c53665b58b5d73252aa13addff76195407527)
        # but sadly, this is not the official repository.
        subject='Décision\u00A0définitive de rejet de demande d\'asile - numéro étranger {}'.format(
            usager.get('identifiant_agdref', 'inconnu')
        ),
        recipients=[prefecture.email])

    entity = decision.get('entite', '-')
    nature = DECISIONS_DEFINITIVES_DESCRIPTIONS.get(entity, {}).get(decision['nature'], '-')

    msg.body = DA_REJECTED_MAIL_TEMPLATE.format(
        libelle_prefecture=prefecture.libelle,
        number=usager.get('identifiant_agdref', '-'),
        name=usager['nom'],
        name_usage=usager.get('nom_usage', '-'),
        first_names=', '.join(usager['prenoms']),
        sex=usager['sexe'],
        birth_date=dateutil.parser.parse(usager['date_naissance']),
        birth_city=usager['ville_naissance'],
        birth_country=usager['pays_naissance']['libelle'],
        nationalities=', '.join([n['libelle'] for n in usager['nationalites']]),
        family_situation=FAMILY_SITUATION_CONVERT[usager['situation_familiale']],
        nature=nature,
        decision_date=dateutil.parser.parse(decision['date']),
        notification_date=dateutil.parser.parse(decision['date_notification']),
        entity=entity,
        skipper=decision.get('numero_skipper', '-'),
        inerec_id=demande_asile.get('identifiant_inerec', '-')
    )
    return msg


def mail_demande_asile_rejected(handler, msg):
    ctx = msg.context
    demande_asile = ctx['demande_asile']
    decision = demande_asile['decisions_definitives'][-1] if demande_asile['decisions_definitives'] else None

    if not decision or DECISIONS_DEFINITIVES[decision['nature']] != 'REJET':
        return
    prefecture = Prefecture.objects.get(id=demande_asile['prefecture_rattachee']['id'])
    if not prefecture.email:
        return
    prefecture_ids = [pref_id for pref_id in current_app.config.get('FF_MAIL_ALERT_PREFECTURE_IDS')
                      if pref_id]
    if prefecture_ids and str(prefecture.id) not in prefecture_ids:
        return

    msg = _format_demande_asile_rejected_message(prefecture, ctx['usager'], demande_asile, decision)

    mail.send_message(msg)
