from core.model_util import BaseSolrSearcher, BaseDocument
from sief.model import fields


class FichierSearcher(BaseSolrSearcher):
    FIELDS = ('name', 'author')


class Fichier(BaseDocument):
    name = fields.StringField(required=True)
    data = fields.FileField()
    author = fields.ReferenceField('Utilisateur')

    meta = {'searcher_cls': FichierSearcher}
