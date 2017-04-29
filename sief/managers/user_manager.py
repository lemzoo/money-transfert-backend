#! /usr/bin/env python3
from flask.ext.script import Manager, prompt, prompt_pass
from sief.model.utilisateur import Utilisateur


user_manager = Manager(usage="Perform users operations")


@user_manager.option('-p', '--prenom', help="First name of the admin")
@user_manager.option('-n', '--nom', help="Last name of the admin")
@user_manager.option('-e', '--email', help="email of the admin")
@user_manager.option('-P', '--password', help="Password of the admin")
def add_admin(prenom=None, nom=None, email=None, password=None):
    """Create an admin user"""
    nom = nom or prompt('nom')
    prenom = prenom or prompt('prenom')
    email = email or prompt('email')
    while not password:
        password = prompt_pass('password')
        pass_confirm = prompt_pass('confirm password')
        if password != pass_confirm:
            print('Password mismatched')
            password = None
        else:
            break
    user = Utilisateur(email=email, nom=nom, prenom=prenom)
    user.controller.add_accreditation(role="ADMINISTRATEUR")
    user.controller.init_basic_auth()
    user.controller.set_password(password)
    user.save()
    print('Created admin user %s (%s)' % (user.id, user.email))


@user_manager.command
def create_3rd_party():
    """Create AGDREF, INEREC and DN@ accounts"""
    from core.auth import generate_password

    def _create(name, role):
        email = '%s@connector.com' % name.lower()
        existing = Utilisateur.objects(email=email).first()
        if existing:
            print("Utilisateur %s already create as %s" % (name, existing.id))
            return
        user = Utilisateur(email=email, nom='Connector', prenom=name.capitalize(), system_account=True)
        user.controller.add_accreditation(role=role)
        password = generate_password()
        user.controller.init_basic_auth()
        user.controller.set_password(password)
        user.save()
        print('Created %s (password: %s)' % (email, password))
    _create('agdref', 'SYSTEME_AGDREF')
    _create('inerec', 'SYSTEME_INEREC')
    _create('dna', 'SYSTEME_DNA')


if __name__ == "__main__":
    user_manager.run()
