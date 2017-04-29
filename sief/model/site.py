from datetime import datetime, timedelta
from workdays import workday as add_days, networkdays as num_workdays
from mongoengine.fields import EmbeddedDocument

from core.model_util import (BaseController, BaseSolrSearcher,
                             BaseDocument)
from core.concurrency import ConcurrencyError
from sief.model import fields
from sief.model.utilisateur import Utilisateur


class CreneauReserverError(Exception):
    pass


def creneaux_multi_reserver(creneaux, document):

    reserved_creneaux = []

    def cleanup_and_abort():
        for creneau in reserved_creneaux:
            creneau.reload()
            if creneau.document_lie == document:
                creneau.controller.liberer()
                creneau.save()
        raise CreneauReserverError('Certains créneaux sont déjà reservés')

    try:
        for creneau in creneaux:
            creneau.controller.reserver(document)
            creneau.save()
            reserved_creneaux.append(creneau)
    except:
        # Something wrong happened, release the creneaux before leaving
        cleanup_and_abort()
        raise


class CreneauController(BaseController):

    def reserver(self, document):
        if self.document.reserve:
            raise CreneauReserverError('Le créneau est déjà reservé')

        self.document.reserve = True
        self.document.document_lie = document

    def liberer(self):
        if not self.document.reserve:
            raise CreneauReserverError('Le créneau est déjà libéré')
        self.document.reserve = False
        self.document.document_lie = None


class CreneauSearcher(BaseSolrSearcher):
    FIELDS = ('site', 'date_debut', 'date_fin', 'reserve', 'document_lie',
              'marge')


class Creneau(BaseDocument):
    site = fields.ReferenceField('Site', required=True)
    date_debut = fields.DateTimeField(required=True)
    date_fin = fields.DateTimeField(required=True)
    reserve = fields.BooleanField(required=True, default=False)
    document_lie = fields.GenericReferenceField(choices=("RecueilDA",), null=True)
    marge = fields.IntField(null=True)

    meta = {'controller_cls': CreneauController,
            'searcher_cls': CreneauSearcher}


class SiteController(BaseController):

    def close_site(self, date_fermeture=None):
        if not self.document.date_fermeture:
            self.document.date_fermeture = date_fermeture or datetime.utcnow()
            return True
        else:
            # Site already closed
            return False

#    def get_type(self):
#        return self.document._types[0].split('.')[-1]


class CreneauxBooking:

    def __init__(self, creneaux=None, do_check=True):
        self.creneaux = creneaux or ()
        self.do_check = do_check
        self.site = None
        self.document_lie = None
        self.today = None
        self.startday = None
        self.ok = None
        self.creneaux

    def book(self, site, document_lie, limite_rdv_jrs=3, family=False, today=None):
        self.site = site
        self.document_lie = document_lie
        # Start searching the day after
        today = (today or datetime.utcnow()).replace(hour=0, minute=0, second=0, microsecond=0)
        self.today = today
        # We start searching from the next day and skip the weekend days
        self.startday = add_days(start_date=today, days=1)
        get_creneaux_kwargs = {
            'date_debut__gte': self.startday,
            'reserve': False,
            'site': self.site
        }
        if limite_rdv_jrs:
            get_creneaux_kwargs['date_debut__lt'] = add_days(self.startday, limite_rdv_jrs)
        # Handle concurrency with this loop
        while True:
            try:
                self.creneaux = self._reserver_creneaux(
                    document_lie, get_creneaux_kwargs, family)
                break
            except ConcurrencyError:
                continue
        self.ok = bool(self.creneaux)
        if self.do_check:
            self._check_no_creneaux()
        return self

    def _reserver_creneaux(self, document, get_creneaux_kwargs, family):
        creneaux = Creneau.objects(**get_creneaux_kwargs).order_by('date_debut')

        # Two creneaux for family, one otherwise
        if not family:
            # Just take the next free creneau
            free = creneaux.first()
            if free:
                free.controller.reserver(document)
                free.save()
                return (free,)
        else:
            last = next(creneaux, None)
            for current in creneaux:
                # For each creneau, check if it has another following one
                if last.date_fin == current.date_debut:
                    # Current creneau follows the last one, this
                    # is the couple we are looking for !
                    last.controller.reserver(document)
                    current.controller.reserver(document)
                    last.save()
                    try:
                        current.save()
                    except ConcurrencyError:
                        # In case of concurrency, we must free the creneau
                        # previously reserved before leave
                        last.controller.liberer()
                        last.save()
                        raise
                    return (last, current)
                else:
                    if last.date_debut == current.date_debut:
                        # Current creneau is the same than last one, skip it
                        continue
                    else:
                        # Current creneau doesn't follow last one, hence
                        # drop last
                        last = current
        # Nothing found, sorry...
        return None

    def _check_no_creneaux(self):
        if not self.creneaux:
            return SiteActualite(type='ALERTE_GU_PLUS_CRENEAUX', site=self.site,
                                 contexte={'document_lie': self.document_lie}).save()

    def _check_site_days(self):
        if (self.creneaux and
                num_workdays(self.startday, self.creneaux[0].date_debut) > 3):
            return SiteActualite(type='ALERTE_GU_RDV_LIMITE_JRS', site=self.site,
                                 contexte={
                                     'document_lie': self.document_lie, 'creneaux': self.creneaux}
                                 ).save()

    def cancel(self):
        for creneau in self.creneaux:
            creneau.controller.liberer()
            creneau.save()

    def confirm(self):
        if self.do_check:
            self._check_site_days()


class SiteWithCreneauxController(SiteController):

    def add_creneaux(self, plage_start: datetime, plage_end: datetime,
                     duration: timedelta, desks: int,
                     marge: int, marge_initiale: bool):
        creneaux = []
        creneaux_start = plage_start

        # Maximum creneau duration is 86400 seconds (a day)
        MAX_CRENEAU_DURATION = 86400
        # Minimum creneau duration is 600 seconds (10 minutes)
        MIN_CRENEAU_DURATION = 600
        # Start and end of a creneau can be only 7 days apart at most
        MAX_DAYS_BETWEEN_START_AND_END = 7
        # Maximum number of creneaux that can be created in one request
        MAX_CRENEAU_CREATED = 200

        if duration.days < 0:
            raise ValueError('Negative duration')
        if duration.days > 0 or duration.seconds > MAX_CRENEAU_DURATION:
            raise ValueError('Duration too large')
        if duration.days <= 0 and duration.seconds < MIN_CRENEAU_DURATION:
            raise ValueError('Duration too small')
        if (plage_end - plage_start).days > MAX_DAYS_BETWEEN_START_AND_END:
            raise ValueError('Start and end are more than seven days apart')
        if desks <= 0:
            raise ValueError('Invalid number of agents')
        if desks > Utilisateur.objects(accreditations__site_affecte=self.document.id).count():
            raise ValueError('Desks is superior to the number of available agents')

        while True:
            creneaux_end = creneaux_start + duration
            if creneaux_end > plage_end:
                break
            kwargs = {'date_debut': creneaux_start, 'date_fin': creneaux_end,
                      'site': self.document}
            if marge and (plage_start != creneaux_start or marge_initiale):
                kwargs['marge'] = marge
            for _ in range(desks):
                c = Creneau(**kwargs)
                creneaux.append(c)
                # Limiting the number of creneaux created in one request to avoid DDosing the server
                # and the database
                if len(creneaux) > MAX_CRENEAU_CREATED:
                    raise ValueError('Too many creneaux created in one request')
            creneaux_start = creneaux_end
        # Creneaux are only saved at the end, to avoid having "ghost creneaux" if an error happens
        # in the loop
        for creneau in creneaux:
            creneau.save()
        return creneaux

    def get_creneaux(self, **kwargs):
        return Creneau.objects(site=self.document.pk, date_debut__gte=datetime.utcnow(), **kwargs).order_by('date_debut')

    def reserver_creneaux(self, document, **kwargs):
        """Find consecutive creneaux an register them the given recueils_da"""
        return CreneauxBooking().book(self.document, document, **kwargs)


class SiteSearcher(BaseSolrSearcher):
    FIELDS = ('libelle', 'telephone', 'email', 'date_fermeture',
              'autorite_rattachement', 'adresse')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build_and_register_converter(
            'guichets_uniques', StructureAccueil.guichets_uniques,
            aliases=('guichet_unique',)
        )
        self.build_and_register_converter('type', fields.StringField(),
                                          extractor=lambda doc: doc._class_name.split('.')[-1])


class Plage(EmbeddedDocument):
    plage_debut = fields.DateTimeField(required=True)
    plage_fin = fields.DateTimeField(required=True)
    plage_guichets = fields.IntField(null=True)
    duree_creneau = fields.IntField(null=True)
    marge = fields.IntField(null=True)
    marge_initiale = fields.BooleanField(required=True, default=False)


class Modele(EmbeddedDocument):
    libelle = fields.StringField(max_length=255, required=True)
    type = fields.StringField(choices=('QUOTIDIEN', 'HEBDOMADAIRE'), required=True)
    plages = fields.ListField(fields.EmbeddedDocumentField(Plage), default=list)


class Site(BaseDocument):
    libelle = fields.StringField(min_length=1, max_length=255, required=True, unique=True)
    adresse = fields.AddressField(required=True)
    telephone = fields.PhoneField(null=True)
    email = fields.EmailField(max_length=255, null=True)
    date_fermeture = fields.DateTimeField(null=True)

    meta = {'allow_inheritance': True, 'controller_cls': SiteController,
            'searcher_cls': SiteSearcher}


class StructureAccueil(Site):
    guichets_uniques = fields.ListField(fields.ReferenceField('GU'), required=True)


class GU(Site):
    autorite_rattachement = fields.ReferenceField('Prefecture', required=True)
    limite_rdv_jrs = fields.IntField(default=3, required=True)
    modeles = fields.ListField(fields.EmbeddedDocumentField(Modele), default=list)

    meta = {'controller_cls': SiteWithCreneauxController}


class Prefecture(Site):
    limite_rdv_jrs = fields.IntField(default=3, required=True)
    code_departement = fields.StringField(regex=r"^[0-9a-zA-Z]{3}$", required=True)

    meta = {'controller_cls': SiteWithCreneauxController}


class EnsembleZonal(Site):
    prefectures = fields.ListField(fields.ReferenceField('Prefecture'), required=True)


class SiteActualite(BaseDocument):
    type = fields.StringField(
        choices=('ALERTE_GU_RDV_LIMITE_JRS', 'ALERTE_GU_PLUS_CRENEAUX'), required=True)
    site = fields.ReferenceField('Site', required=True)
    contexte = fields.DictField()
    cloturee = fields.DateTimeField()

    indexes = ('cloturee', 'site', 'type')
