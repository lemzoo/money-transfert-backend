from core.model_util import BaseDocument
from sief.model import fields


PARAMETRAGE_SINGLETON_ID = 'singleton'


class Parametrage(BaseDocument):
    """
    Singleton document to store the customisable configuration
    """

    id = fields.StringField(primary_key=True, default=PARAMETRAGE_SINGLETON_ID)
    test_variable = fields.StringField(default='default_value')
    duree_attestation = fields.DictField(null=True)

    @classmethod
    def get_singleton(cls):
        param = cls.objects(id=PARAMETRAGE_SINGLETON_ID).first()
        if not param:
            param = Parametrage()
        return param
