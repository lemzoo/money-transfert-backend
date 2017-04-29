from flask_mail import Mail, Message


default_mail = """Bonjour {0} {1},
Veuillez trouver ci-dessous un lien permettant de configurer votre mot de passe (Internet):
    {2}/#/reset/{3}/{4}

Ou (Intranet) :
    {5}/#/reset/{3}/{4}

Attention : Ces liens ne sont valides que pendant 24 heures.

Cordialement,
-- Mailer Daemon"""

default_mail_reset = """Bonjour {0} {1},
Veuillez trouver ci-dessous un lien permettant de réinitialiser votre mot de passe :
    {2}/#/reset/{3}/{4}

Ou (Intranet) :
    {5}/#/reset/{3}/{4}

Attention : Ces liens ne sont valides que pendant 24 heures.

Cordialement,
-- Mailer Daemon"""

default_subject = "Votre mot de passe ASILE"
default_subject_reset = "Reinitialisation de votre mot de passe ASILE"


class MailHandler:

    def init_app(self, app):
        app.config.setdefault('DISABLE_MAIL', False)
        app.config.setdefault('MAIL_DEBUG', False)  # VERY DANGEROUS
        app.config.setdefault('FRONTEND_DOMAIN', 'https://asile.dgef.interieur.gouv.fr')
        app.config.setdefault('FRONTEND_DOMAIN_INTRANET', 'https://asile.dgef.minint.fr')
        self.front_url = app.config['FRONTEND_DOMAIN']
        self.debug = app.config['MAIL_DEBUG']
        self.secret = app.config['SECRET_KEY']
        self.disabled = app.config['DISABLE_MAIL']
        self.front_url_intranet = app.config['FRONTEND_DOMAIN_INTRANET']
        if not app.config['DISABLE_MAIL']:
            self.mail = Mail(app)
        else:
            self.mail = None

    def send(self, body=None, recipient=None, subject=None, recipients=None):
        recipients = recipients or []
        if recipient:
            recipients.append(recipient)
        if self.mail:
            msg = Message(subject=subject, body=body)
            for recipient in recipients:
                msg.add_recipient(recipient)
            return self.mail.send(msg)

    def send_message(self, msg):
        return self.mail.send(msg)

    def record_messages(self, *args, **kwargs):
        if self.mail:
            return self.mail.record_messages(*args, **kwargs)

mail = MailHandler()
