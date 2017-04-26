#! /usr/bin/env python3

import csv
from flask import current_app
from flask.ext.script import Manager

from sief.model.referentials import LangueIso6392, LangueOfpra, Pays, Nationalite, CodeInseeAGDREF


referentials_manager = Manager(usage="Perform referential operations")


def _register_referential(name, document_cls, dot_every=100):
    manager = Manager(usage="Handle %s referential" % name)

    @manager.option('-d', '--delimiter', help='csv delimiter (default: ",")')
    @manager.option('input', help='csv file to load')
    def load(input, delimiter=","):
        """Load a new version of the referential"""
        with open(input, 'r', encoding='utf-8') as fd:
            reader = csv.reader(fd, delimiter=delimiter)
            headers = [h.strip() for h in next(reader)]
            unknown = [h for h in headers if h and not hasattr(document_cls, h)]
            if unknown:
                raise ValueError("document %s does't have fields %s" %
                                 (document_cls._class_name, unknown))
            # Clean mongodb and solr from potential old data
            document_cls.drop_collection()
            current_app.solr.delete('doc_type:%s' % document_cls._class_name)
            for i, line in enumerate(reader):
                # Ignore lines without header name
                line_dict = {h: c for h, c in zip(headers, line) if h and c}
                doc = document_cls(**line_dict)
                doc.save()
                if not i % dot_every:
                    print('.', end='', flush=True)
            print(' Done !')

    referentials_manager.add_command(name, manager)


_register_referential('langue_iso6392', LangueIso6392)
_register_referential('pays', Pays)
_register_referential('nationalites', Nationalite)
_register_referential('langue_OFPRA', LangueOfpra)
_register_referential('insee_agdref', CodeInseeAGDREF, 1000)


@referentials_manager.command
def load_default():
    "Load default referentials files in database"

    def _load(ref, **kwargs):
        referentials_manager._commands[ref]._commands['load'].run(**kwargs)

    print("Langues ISO-6392-2", end='', flush=True)
    _load('langue_iso6392', input='misc/referentiel_langues_iso639-2.csv', delimiter=';')
    print("Pays ISO-3166", end='', flush=True)
    _load('pays', input='misc/referentiel_pays_iso3166-1.csv', delimiter=';')
    print("Nationalités ISO-3166", end='', flush=True)
    _load('nationalites', input='misc/referentiel_nationalites.csv', delimiter=';')
    print("Langues OFPRA", end='', flush=True)
    _load('langue_OFPRA', input='misc/referentiel_langues_OFPRA.csv', delimiter=';')
    print("Codes INSEE AGDREF", end='', flush=True)
    _load('insee_agdref', input='misc/referentiel_code_insee_agdref.csv', delimiter=';')


if __name__ == "__main__":
    referentials_manager.run()
