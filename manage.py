#! /usr/bin/env python3

import pymongo
import importlib
from flask import current_app
from flask.ext.script import Manager, Server, Shell
from mongopatcher.extensions.flask import init_patcher, patcher_manager

from broker import broker_manager
from broker_rabbit import broker_manager_rabbit
from analytics import analytics_manager
from core.managers import solr_manager, ask_or_abort
from sief import bootstrap_app
from sief.main import create_app
from sief.managers import (referentials_manager, user_manager, import_manager, dna_stock_manager,
                           message_manager, ofpra_manager, demande_asile_manager, monitoring_manager,
                           agdref_manager)

from sief.managers.populate.populate_manager import populate_manager


app = create_app()


class BoostrapperManager(Manager):
    """
    Given datamodel manager aims at upgrading a database currently not compatible
    with the application, we have to avoid the app bootstrap in such a case.
    """

    def handle(self, prog, args=None):
        sub_manager = args[0] if len(args) else None
        if sub_manager in ('datamodel', 'init'):
            db = pymongo.MongoClient(host=app.config['MONGODB_HOST']).get_default_database()
            init_patcher(app, db)
        if sub_manager != 'datamodel':
            bootstrap_app(app)

        return super().handle(prog, args=args)


manager = BoostrapperManager(app)


class BootstrappedShell(Shell):

    def __init__(self, *args, **kwargs):

        def make_context():
            context = {'db': current_app.db, 'solr': current_app.solr}
            model_module = importlib.import_module('sief.model')
            for elem in ('Utilisateur', 'Fichier', 'RecueilDA',
                         'LangueIso6392', 'LangueOfpra', 'Pays', 'Nationalite',
                         'Site', 'GU', 'Prefecture', 'StructureAccueil',
                         'DemandeAsile', 'Usager'):
                try:
                    context[elem] = getattr(model_module, elem)
                except AttributeError:
                    print('Can not import {} from sief.model'.format(elem))
            print('Context vars: %s' % ', '.join(context.keys()))
            return context
        super().__init__(*args, make_context=make_context, **kwargs)


@manager.option('-y', '--yes', help="Don't ask for confirmation",
                action='store_true', default=False)
def init(yes):
    "Initialize the database and create initial admin"

    def _action():
        print(" *** Initialize datamodel version ***")
        manager._commands['datamodel']._commands['init'].run(
            version=None, force=False)
        print(" *** Loading referentials ***")
        manager._commands['referentials']._commands['load_default'].run()
        print(" *** Creating first admin ***")
        manager._commands['user']._commands['add_admin'].run()
        print(" *** Creating 3rd party accounts ***")
        manager._commands['user']._commands['create_3rd_party'].run()

    ask_or_abort(_action, yes=yes)


manager.add_command("runserver", Server())
manager.add_command("shell", BootstrappedShell())
manager.add_command("referentials", referentials_manager)
manager.add_command("solr", solr_manager)
manager.add_command("user", user_manager)
manager.add_command("broker", broker_manager)
manager.add_command("rabbit", broker_manager_rabbit)
manager.add_command("import", import_manager)
manager.add_command("dna_stock", dna_stock_manager)
manager.add_command("message", message_manager)
manager.add_command("populate", populate_manager)
manager.add_command("analytics", analytics_manager)
manager.add_command("demande_asile", demande_asile_manager)
manager.add_command("ofpra", ofpra_manager)
manager.add_command("monitoring", monitoring_manager)
manager.add_command("agdref", agdref_manager)


manager.add_command("datamodel", patcher_manager)


if __name__ == "__main__":
    manager.run()
