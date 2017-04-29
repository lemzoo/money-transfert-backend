#! /usr/bin/env python3

from dateutil.parser import parse as dateparse
from flask import current_app
from flask.ext.script import Manager, prompt_bool, prompt_choices
from functools import partial

from sief import model

# TODO: use more dynamic way to do this
default_solr_collections = (
    'Utilisateur',
    'Fichier',
    'RecueilDA',
    'LangueIso6392',
    'LangueOfpra',
    'Pays',
    'Nationalite',
    'Site',
    'DemandeAsile',
    'Usager',
    'Droit',
    'Creneau',
    'TelemOfpra'
)
solr_manager = Manager(usage="Handle Solr operations")


def ask_or_abort(fn, yes=False, msg=None):
    if not msg:
        msg = "Are you sure you want to alter {green}{name}{endc}".format(
            green='\033[92m', name=current_app.config['SOLR_URL'], endc='\033[0m')
    if yes or prompt_bool(msg):
        return fn()
    else:
        raise SystemExit('You changed your mind, exiting...')


@solr_manager.option('-y', '--yes', help="Don't ask for confirmation",
                     action='store_true')
@solr_manager.option('-s', '--since',
                     help="Update only element updated since this date")
def clear(yes=False, since=None):
    """Drop the solr database"""
    if since:
        since = dateparse(since)
        q = 'doc_updated_dt:[%sZ TO NOW]' % since.isoformat()
    else:
        q = '*:*'
    ask_or_abort(partial(current_app.solr.delete, q=q), yes=yes)


@solr_manager.option('-y', '--yes', help="Don't ask for confirmation",
                     action='store_true')
@solr_manager.option('-s', '--since',
                     help="Update only element updated since this date")
@solr_manager.option('--no_timeout', help="Returned cursor will never timeout",
                     action='store_true')
def build(yes=False, since=None, no_timeout=False, solr_collections=default_solr_collections):
    """Build the solr database"""
    if since:
        since = dateparse(since)

    def _build():
        for col_cls_name in solr_collections:
            col_cls = getattr(model, col_cls_name)
            if since:
                if not hasattr(col_cls, 'doc_updated'):
                    print('%s skipped (no doc_updated field)' % col_cls.__name__)
                    continue
                objs = col_cls.objects(doc_updated__gte=since).no_cache().timeout(not no_timeout)
            else:
                objs = col_cls.objects().no_cache().timeout(not no_timeout)
            print('%s (%s elements)' % (col_cls.__name__, objs.count()),
                  flush=True, end='')
            document_rebuild = []
            solr_args = {'commit': False, 'waitFlush': False}
            for i, obj in enumerate(objs):
                document_rebuild.append(
                    obj.searcher.build_document(obj, return_not_add_to_solr=True))
                if not i % 1000:
                    print('.', flush=True, end='')
                    current_app.solr.add(document_rebuild, **solr_args)
                    document_rebuild.clear()
            current_app.solr.add(document_rebuild, **solr_args)
            print()

    ask_or_abort(_build, yes=yes)


@solr_manager.option('-y', '--yes', help="Don't ask for confirmation",
                     action='store_true')
@solr_manager.option('-s', '--since',
                     help="Update only element updated since this date")
@solr_manager.option('-c', '--collections', nargs='+', choices=['All',
                                                                'Creneau',
                                                                'DemandeAsile',
                                                                'Droit',
                                                                'Fichier',
                                                                'LangueIso6392',
                                                                'LangueOfpra',
                                                                'Nationalite',
                                                                'Pays',
                                                                'RecueilDA',
                                                                'Site',
                                                                'TelemOfpra',
                                                                'Utilisateur',
                                                                'Usager'],
                     default=['All'],
                     help='Collections to rebuild')
@solr_manager.option('--no_timeout', help="Returned cursor will never timeout",
                     action='store_true')
def rebuild(yes=False, since=None, no_timeout=False, collections=()):
    """Rebuild the entire solr index"""
    def _rebuild():
        map_collection = {'All': default_solr_collections,
                          'Creneau': ['Creneau', 'RecueilDA'],
                          'DemandeAsile': ['DemandeAsile', 'RecueilDA', 'TelemOfpra'],
                          'Droit': ['Droit', 'DemandeAsile'],
                          'Fichier': ['Fichier', 'Usager', 'RecueilDA', 'DemandeAsile'],
                          'LangueIso6392': ['LangueIso6392', 'RecueilDA', 'Usager'],
                          'LangueOfpra': ['LangueOfpra', 'RecueilDA', 'Usager'],
                          'Nationalite': ['Nationalite', 'Usager', 'RecueilDA'],
                          'Pays': ['Pays', 'Site', 'DemandeAsile', 'Usager', 'RecueilDA', 'Utilisateur', 'Creneau'],
                          'RecueilDA': ['RecueilDA', 'DemandeAsile'],
                          'Site': ['Site', 'DemandeAsile', 'RecueilDA', 'Usager', 'Utilisateur', 'Droit', 'Creneau'],
                          'TelemOfpra': ['TelemOfpra'],
                          'Utilisateur': ['Utilisateur', 'Fichier', 'Droit', 'TelemOfpra', 'DemandeAsile', 'RecueilDA',
                                          'Usager'],
                          'Usager': ['Usager', 'DemandeAsile', 'Droit', 'RecueilDA']}

        solr_collections = set()
        for collection in collections:
            solr_collections |= set(map_collection[collection])
        build(yes=True, since=since, no_timeout=no_timeout, solr_collections=solr_collections)

    ask_or_abort(_rebuild, yes=yes)


if __name__ == "__main__":
    solr_manager.run()
