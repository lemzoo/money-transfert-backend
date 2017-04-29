import re
import datetime

from mongoengine import EmbeddedDocument
from functools import partial
from mongoengine import ValidationError as MongoValidationError

from core.model_util.fields import *  # noqa
from core.model_util.searcher import solr_register_field_converter, AsbFieldSolrConverter

from marshmallow_mongoengine import register_field_builder
from marshmallow_mongoengine.conversion.fields import EmbeddedDocumentBuilder
from marshmallow_mongoengine.fields import Nested
from core.view_util import UnknownCheckedSchema
# Add functional fields


class PatronymeField(StringField):
    ALLOWED_UNICODE_LOWER = "abcdefghijklmnopqrstuvwxyzáàâäåãæçéèêëíìîïñóòôöõøœšúùûüýÿž"
    ALLOWED_UNICODE_UPPER = ALLOWED_UNICODE_LOWER.upper()

    def __init__(self, *args, **kwargs):
        regex = r"^([{up}]|([{up}][{up}{low}{spe}]*[{up}{low}]))$".format(
            up=self.ALLOWED_UNICODE_UPPER, low=self.ALLOWED_UNICODE_LOWER, spe=r" \-'")
        kwargs.setdefault('regex', regex)
        super().__init__(*args, **kwargs)
# PatronymeField should have phonetic search functionalities


class PatronymeFieldSolrConverter(AsbFieldSolrConverter):
    FIELD_CLS = PatronymeField
    FIELD_SOLR_EXTENSION = '_txt_fr'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._solr_field_name_phon = self._field_name + '_phon'
        self._phon_aliases = [a + '_phon' for a in self._aliases or ()]
        if self._multi:
            # User can search for "field_phon" but field is "field_phons"
            self._phon_aliases.append(self._solr_field_name_phon)
            self._solr_field_name_phon += 's'

    def replace_aliases(self, query):
        query = super().replace_aliases(query)
        for alias in self._phon_aliases:
            query = re.sub(r"\b%s\b" % alias, self._solr_field_name_phon, query)
        return query

    def _serialize(self, value):
        # Default serializer
        return {self._solr_field_name_phon: value,
                self._solr_field_name: value}
solr_register_field_converter(PatronymeFieldSolrConverter)


OrigineNom = partial(StringField, choices=(
    'EUROPE', 'ARABE', 'CHINOISE', 'TURQUE/AFRIQ'))
FamilyStatusField = partial(StringField, choices=(
    "CELIBATAIRE", "DIVORCE", "MARIE", "CONCUBIN", "SEPARE", "VEUF", "PACSE"))
PhoneField = partial(StringField, regex=r"^[+]?[0-9][0-9 ]+[0-9]$", max_length=22)
SexeField = partial(StringField, choices=('M', 'F'))
AgdrefIdField = partial(StringField, max_length=10, min_length=10)
EurodacIdField = partial(StringField, max_length=10, min_length=10)


class DateTimeBoundedField(DateTimeField):

    def __init__(self, max_date=None, min_date=None, **kwargs):
        self.max_date = max_date
        self.min_date = min_date
        super().__init__(**kwargs)

    def validate(self, value):
        if self.max_date is not None and value > self.max_date:
            self.error('La date ne doit pas être plus récente que %s' %
                       self.max_date.strftime("%d/%m/%Y"))

        if self.min_date is not None and value < self.min_date:
            self.error('La date ne doit pas être antérieure au %s' %
                       self.min_date.strftime("%d/%m/%Y"))

DateNaissanceField = partial(DateTimeBoundedField, min_date=datetime.datetime(1881, 1, 1))


class ReferentialEmbeddedDocument(EmbeddedDocument):
    meta = {'abstract': True}
    code = StringField(required=True)
    libelle = StringField()

    def clean(self):
        from mongoengine.base import get_document
        # TODO: allow code_<3rd_party> field search ?
        ref_name = self._meta['referential_document_cls']
        doc_cls = get_document(ref_name)
        doc = doc_cls.objects(code=self.code).first()
        if not doc:
            raise MongoValidationError(
                "le code %s n'existe pas dans le referentiel %s" %
                (self.code, ref_name))
        self.libelle = doc.libelle


class ReferentialLangueIso6392EmbeddedDocument(ReferentialEmbeddedDocument):
    meta = {'referential_document_cls': 'LangueIso6392'}


class ReferentialLangueOfpraEmbeddedDocument(ReferentialEmbeddedDocument):
    meta = {'referential_document_cls': 'LangueOfpra'}


class ReferentialPaysEmbeddedDocument(ReferentialEmbeddedDocument):
    meta = {'referential_document_cls': 'Pays'}


class ReferentialNationaliteEmbeddedDocument(ReferentialEmbeddedDocument):
    meta = {'referential_document_cls': 'Nationalite'}


class ReferentialCodeInseeAGDREFEmbeddedDocument(ReferentialEmbeddedDocument):
    meta = {'referential_document_cls': 'CodeInseeAGDREF'}


# Subclass field to allow marshmallow to handle this type of field specifically
class ReferentialField(EmbeddedDocumentField):
    pass


class ReferentialFieldSolrConverter(AsbFieldSolrConverter):
    FIELD_CLS = ReferentialField
    FIELD_SOLR_EXTENSION = '_s'

    def _serialize(self, value):
        return {self._solr_field_name: value.code}
solr_register_field_converter(ReferentialFieldSolrConverter)


NationaliteField = partial(ReferentialField,
                           ReferentialNationaliteEmbeddedDocument)
PaysField = partial(ReferentialField,
                    ReferentialPaysEmbeddedDocument)
LangueIso6392Field = partial(ReferentialField,
                             ReferentialLangueIso6392EmbeddedDocument)
LangueOfpraField = partial(ReferentialField,
                           ReferentialLangueOfpraEmbeddedDocument)


# Register the ReferentialField in marshmallow_mongoengine
# for automatic load/dumps


class ReferentialBuilder(EmbeddedDocumentBuilder):
    BASE_NESTED_SCHEMA_CLS = UnknownCheckedSchema

    class MARSHMALLOW_FIELD_CLS(Nested):

        def _deserialize(self, value, attr, data):
            if not isinstance(value, dict):
                value = {'code': value}
            return super()._deserialize(value, attr, data)

register_field_builder(ReferentialField, ReferentialBuilder)


class AddressEmbeddedDocument(EmbeddedDocument):

    def clean(self):
        if isinstance(self.code_insee, str):
            self.code_insee = self.code_insee.upper()

    chez = StringField(null=True)
    complement = StringField(null=True)
    identifiant_ban = StringField(null=True)
    adresse_inconnue = BooleanField(null=True)
    numero_voie = StringField(null=True)
    voie = StringField(null=True)
    code_insee = StringField(regex=r"[0-9A-Z]{5}", null=True)
    code_postal = StringField(regex=r"[0-9]{5}", null=True)
    ville = StringField(null=True)
    longlat = ListField(FloatField(), null=True)
    pays = PaysField(null=True)

    def to_solr(self):
        args = []
        if self.chez:
            args.append('Chez %s' % self.chez)
        if self.complement:
            args.append(self.complement)
        if self.voie:
            args.append('%s %s' % (self.numero_voie or '', self.voie))
        if self.code_postal:
            args.append(self.code_postal)
        if self.ville:
            args.append(self.ville)
        if self.pays:
            args.append(self.pays.libelle)
        return '\n'.join(args)

    def __str__(self):
        if self.adresse_inconnue:
            return "Adresse inconnue"
        format_adresse = ""
        if self.chez:
            format_adresse = "Chez {}".format(self.chez)
        fields = ['numero_voie', 'voie', 'code_postal', 'ville']
        values = [self[field] for field in fields if self[field]]
        format_adresse.join(values)
        if self.pays:
            format_adresse = "{} Pays: {}".format(format_adresse, self.pays.libelle)
        if self.identifiant_ban:
            format_adresse = "{} (identifiant BAN: {})".format(format_adresse, self.identifiant_ban)
        if self.code_insee:
            format_adresse = "{} (code INSEE: {})".format(format_adresse, self.code_insee)
        if self.longlat:
            format_adresse = "{} (Longlat: {})".format(format_adresse, self.longlat)
        return format_adresse


class AddressField(EmbeddedDocumentField):

    def __init__(self, *args, **kwargs):
        super().__init__(AddressEmbeddedDocument, *args, **kwargs)


class AddressFieldSolrConverter(AsbFieldSolrConverter):
    FIELD_CLS = AddressField
    FIELD_SOLR_EXTENSION = '_txt_fr'

    def _serialize(self, value):
        return {self._solr_field_name: value.to_solr()}
solr_register_field_converter(AddressFieldSolrConverter)
