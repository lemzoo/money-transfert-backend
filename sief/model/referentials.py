from core.model_util import BaseSolrSearcher, SearchableDocument
from sief.model import fields


class ReferentialSearcher(BaseSolrSearcher):
    FIELDS = ('libelle', 'code')


class LangueIso6392(SearchableDocument):
    meta = {'collection': 'referentiels.langue_iso6392',
            'searcher_cls': ReferentialSearcher}
    code = fields.StringField(primary_key=True)
    libelle = fields.StringField()

    def to_embedded(self):
        return fields.ReferentialLangueIso6392EmbeddedDocument(
            code=self.code,
            libelle=self.libelle)


class LangueOfpra(SearchableDocument):
    meta = {'collection': 'referentiels.langue_OFPRA',
            'searcher_cls': ReferentialSearcher}
    code = fields.StringField(primary_key=True)
    libelle = fields.StringField()

    def to_embedded(self):
        return fields.ReferentialLangueOfpraEmbeddedDocument(
            code=self.code,
            libelle=self.libelle)


class Pays(SearchableDocument):
    meta = {'collection': 'referentiels.pays',
            'searcher_cls': ReferentialSearcher}
    code = fields.StringField(primary_key=True)
    libelle = fields.StringField()

    def to_embedded(self):
        return fields.ReferentialPaysEmbeddedDocument(
            code=self.code,
            libelle=self.libelle)


class Nationalite(SearchableDocument):
    meta = {'collection': 'referentiels.nationalite',
            'searcher_cls': ReferentialSearcher}
    code = fields.StringField(primary_key=True)
    libelle = fields.StringField()

    def to_embedded(self):
        return fields.ReferentialNationaliteEmbeddedDocument(
            code=self.code,
            libelle=self.libelle)


class CodeInseeAGDREF(SearchableDocument):
    meta = {'collection': 'referentiels.code_insee_agdref',
            'searcher_cls': ReferentialSearcher}
    code = fields.StringField(primary_key=True)
    libelle = fields.StringField()

    def to_embedded(self):
        return fields.ReferentialCodeInseeAGDREFEmbeddedDocument(
            code=self.code,
            libelle=self.libelle)
