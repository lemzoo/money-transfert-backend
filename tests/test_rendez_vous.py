import pytest
from datetime import datetime, timedelta
import mongoengine

from tests import common
from tests.test_site import site_prefecture

from sief.model.site import Creneau, SiteActualite
from core.model_util import fields, Document


# Don't actually use current day given it can alter the test
NOW = datetime(2015, 6, 22, 12, 44, 32)
TOMORROW = NOW + timedelta(days=1)
CRENEAU_TIME = timedelta(0, 45 * 60)


@pytest.fixture
def site_rdv(site_prefecture):
    return site_prefecture


class DummyDoc(Document):
    field = fields.StringField()
Creneau.document_lie.choices += ("DummyDoc",)


class NotAvailableDoc(Document):
    pass


def assert_reserved(booking, doc):
    assert booking.ok
    cr = booking.creneaux
    if isinstance(cr, tuple):
        assert len(cr) == 1
        cr = cr[0]
    assert cr is not None
    assert cr.reserve is True
    assert cr.document_lie == doc


def assert_reserved_family(booking, doc):
    assert booking.ok
    crs = booking.creneaux
    assert isinstance(crs, tuple)
    assert len(crs) == 2
    for cr in crs:
        assert cr is not None
        assert cr.reserve is True
        assert cr.document_lie == doc


def add_free_creneaux(count, site, start=None):
    from workdays import workday as add_days
    if not start:
        start = datetime.utcnow()
        start = add_days(start, 1)
    creneaux = []
    for _ in range(count):
        end = start + CRENEAU_TIME
        cr = Creneau(date_debut=start, date_fin=end,
                     site=site)
        cr.save()
        creneaux.append(cr)
        start = end
    return creneaux


class TestCreneauxRendezVous(common.BaseTest):

    def setup(self):
        DummyDoc.drop_collection()
        Creneau.drop_collection()

    def test_empty_rendez_vous(self, site_rdv):
        doc = DummyDoc()
        doc.save()
        # No creneau available
        booking = site_rdv.controller.reserver_creneaux(doc)
        assert not booking.ok
        assert not booking.creneaux

    def test_multi_reserve(self, site_rdv):
        add_free_creneaux(4, site_rdv, TOMORROW)
        # Reserve the creneaux
        for _ in range(4):
            doc = DummyDoc()
            doc.save()
            booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
            assert_reserved(booking, doc)
        # No more creneaux for this one
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert not booking.ok

    def test_reserve_family(self, site_rdv):
        add_free_creneaux(5, site_rdv, TOMORROW)
        # Should be able to reserve creneaux for 2 family
        for _ in range(2):
            doc = DummyDoc()
            doc.save()
            booking = site_rdv.controller.reserver_creneaux(
                doc, family=True, today=NOW)
            assert_reserved_family(booking, doc)
        # No more creneaux for this family
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, family=True, today=NOW)
        assert not booking.ok

    def test_family_and_holes(self, site_rdv):
        creneaux = add_free_creneaux(4, site_rdv, TOMORROW)
        creneaux[1].reserve = True
        creneaux[1].save()
        # There is still room for one family
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, family=True, today=NOW)
        assert_reserved_family(booking, doc)
        # Then one more person fits
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert_reserved(booking, doc)
        # Only one
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert not booking.ok

    def test_multi_desk(self, site_rdv):
        add_free_creneaux(1, site_rdv, TOMORROW)
        add_free_creneaux(1, site_rdv, TOMORROW)
        # 2 free creneaux, but at the same time are not ok for a family
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, family=True, today=NOW)
        assert not booking.ok
        # But is pretty fine for two persons alone
        for _ in range(2):
            doc = DummyDoc()
            doc.save()
            booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
            assert_reserved(booking, doc)

    def test_get_linked(self, site_rdv):
        # Create a creneau and reserve it
        add_free_creneaux(1, site_rdv, TOMORROW)
        doc = DummyDoc(field='test')
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert_reserved(booking, doc)
        # Now we can get back and interogate the linked document from the cr
        assert booking.creneaux[0].document_lie == doc

    def test_bad_document_register(self, site_rdv):
        # A free creneau is available...
        add_free_creneaux(1, site_rdv, TOMORROW)
        # ...but the document is not allowed to be registered
        bad_doc = NotAvailableDoc()
        bad_doc.save()
        with pytest.raises(mongoengine.errors.ValidationError):
            site_rdv.controller.reserver_creneaux(bad_doc, today=NOW)
        # The creneau is still available
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert_reserved(booking, doc)

    def test_skip_weekend(self, site_rdv):
        # Now let say today is thursday, +3days means the last day we can
        # have a rdv is tuesday
        today = datetime(2015, 6, 25, 12, 44, 23)
        last_day_creneau = datetime(2015, 6, 29, 18, 00, 00)
        add_free_creneaux(1, site_rdv, last_day_creneau)
        # Reserve the creneaux
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=today)
        assert_reserved(booking, doc)

    def test_saturday_skip(self, site_rdv):
        # Special case for saturday: skip only sunday, so last day to
        # consider will be wednesday
        today = datetime(2015, 6, 20, 12, 44, 23)
        last_day_creneau = datetime(2015, 6, 24, 18, 00, 00)
        out_of_3days_creneau = datetime(2015, 6, 25, 18, 00, 00)
        add_free_creneaux(1, site_rdv, out_of_3days_creneau)
        # No good creneau to reserve
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=today)
        assert not booking.ok
        # Now add a good creneau and retry
        add_free_creneaux(1, site_rdv, last_day_creneau)
        booking = site_rdv.controller.reserver_creneaux(doc, today=today)
        assert_reserved(booking, doc)

    def test_friday_skip(self, site_rdv):
        # Special case for friday: skip the weekend to start on monday
        today = datetime(2015, 6, 19, 12, 44, 23)
        last_day_creneau = datetime(2015, 6, 24, 18, 00, 00)
        out_of_3days_creneau = datetime(2015, 6, 25, 18, 00, 00)
        add_free_creneaux(1, site_rdv, out_of_3days_creneau)
        # No good creneau to reserve
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=today)
        assert not booking.ok
        # Now add a good creneau and retry
        add_free_creneaux(1, site_rdv, last_day_creneau)
        booking = site_rdv.controller.reserver_creneaux(doc, today=today)
        assert_reserved(booking, doc)

    def test_3days_max(self, site_rdv):
        # Next creneau is in 4days, should not be able to reserve it
        out_of_3days_creneau = TOMORROW + timedelta(4)
        add_free_creneaux(1, site_rdv, out_of_3days_creneau)
        # Fail to reserve the creneau
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert not booking.ok

    def test_infinite_reserve_mode(self, site_rdv):
        # We can disable max +3days mode, then reserve any creneaux
        # in the future
        out_of_3days_creneau = TOMORROW + timedelta(4)
        add_free_creneaux(1, site_rdv, out_of_3days_creneau)
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(
            doc, limite_rdv_jrs=4, today=NOW)
        assert_reserved(booking, doc)

    def test_no_reserve_today(self, site_rdv):
        # No matter what, we can't reserve today's creneaux
        add_free_creneaux(4, site_rdv, NOW)
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert not booking.ok
        # Even without limit
        booking = site_rdv.controller.reserver_creneaux(
            doc, limite_rdv_jrs=2, today=NOW)
        assert not booking.ok

    def test_alerte_reserve_no_creneaux(self, site_rdv):
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW)
        assert not booking.ok
        actualites = SiteActualite.objects(site=site_rdv)
        assert actualites.count() == 1
        assert actualites[0].type == 'ALERTE_GU_PLUS_CRENEAUX'
        assert actualites[0].contexte == {'document_lie': doc}

    def test_alerte_reserve_more_than_site_days(self, site_rdv):
        # Book a creneau in more than 3 days
        out_of_3days_creneau = TOMORROW + timedelta(4)
        add_free_creneaux(1, site_rdv, out_of_3days_creneau)
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW, limite_rdv_jrs=4)
        assert_reserved(booking, doc)
        actualites = SiteActualite.objects(site=site_rdv)
        # 3 day actualities are send only after booking confirmation
        assert actualites.count() == 0
        booking.confirm()
        assert actualites.count() == 1
        assert actualites[0].type == 'ALERTE_GU_RDV_LIMITE_JRS'
        assert actualites[0].contexte == {'document_lie': doc, 'creneaux': list(booking.creneaux)}

    def test_no_alerte_on_abort(self, site_rdv):
        # Book a creneau in more than 3 days
        out_of_3days_creneau = TOMORROW + timedelta(4)
        add_free_creneaux(1, site_rdv, out_of_3days_creneau)
        doc = DummyDoc()
        doc.save()
        booking = site_rdv.controller.reserver_creneaux(doc, today=NOW, limite_rdv_jrs=4)
        assert_reserved(booking, doc)
        actualites = SiteActualite.objects(site=site_rdv)
        # Cancel the booking, no actuality should be send and creneaux
        # should be free again
        booking.cancel()
        assert actualites.count() == 0
        for cr in booking.creneaux:
            cr.reload()
            assert cr.reserve is False
            assert cr.document_lie is None
