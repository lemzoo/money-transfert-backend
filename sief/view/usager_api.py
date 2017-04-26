import re

from dateutil.parser import parse
from flask import request, url_for
from marshmallow import missing

from core import CoreResource, view_util
from core.auth import current_user
from core.tools import abort, get_search_urlargs, list_to_pagination, check_if_match, Export
from sief.permissions import POLICIES as p
from sief.events import EVENTS as e
from sief.model.usager import Usager
from sief.cache import cached_from_config
import services
from services.fpr import fpr_query, FprError, FprConnectionError, FprDisabledError
from sief.model.demande_asile import DemandeAsile

ETAT_CIVIL_FIELDS_VALIDATION_MANDATORY = (
    'nom', 'nom_usage', 'prenoms', 'sexe', 'date_naissance',
    'date_naissance_approximative', 'pays_naissance', 'ville_naissance',
    'nationalites', 'situation_familiale')
ETAT_CIVIL_FIELDS = ETAT_CIVIL_FIELDS_VALIDATION_MANDATORY + ('photo',)

Usager.set_link_builder_from_api('UsagerAPI')


class LocalisationSchema(view_util.UnknownCheckedSchema):
    class Meta:
        model = Usager.localisations.field.document_type_obj


class UsagerSchema(view_util.BaseModelSchema):
    localisation = view_util.fields.Method('get_localisation')

    def get_localisation(self, obj):
        portail_loc = [loc for loc in obj.localisations if loc.organisme_origine == 'PORTAIL']
        if not portail_loc:
            return missing
        return LocalisationSchema().dump(portail_loc[-1]).data

    def get_links(self, obj):
        route = url_for("UsagerAPI", item_id=obj.pk)
        locs_route = url_for('UsagerLocalisationsAPI', item_id=obj.pk)
        ec_route = url_for("UsagerEtatCivilAPI", item_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("UsagerListAPI"),
                 'localisations': locs_route}
        if obj.ecv_valide:
            if (p.usager.etat_civil.valider.can() and
                    p.usager.etat_civil.modifier.can()):
                links['etat_civil_update'] = ec_route
        else:
            if p.usager.etat_civil.valider.can():
                links['etat_civil_valider'] = ec_route
            if p.usager.etat_civil.modifier.can():
                links['etat_civil_update'] = ec_route
        if p.usager.modifier.can():
            links['update'] = route
            links['localisation_update'] = locs_route
        if p.historique.voir.can():
            links['history'] = url_for("UsagerHistoryListAPI",
                                       origin_id=obj.pk)
        if p.usager.prefecture_rattachee.modifier.can():
            links['prefecture_rattachee'] = url_for('UsagerPrefectureRattacheeAPI', item_id=obj.pk)
        return links

    class Meta:
        model = Usager
        model_fields_kwargs = {'localisations': {'dump_only': True, 'load_only': True},
                               'localisation': {'dump_only': True},
                               'prefecture_rattachee': {'dump_only': True},
                               'basic_auth': {'dump_only': True, 'load_only': True}}


class UsagerBaseSchema(UsagerSchema):
    class Meta:
        model = Usager
        exclude = ETAT_CIVIL_FIELDS + ('ecv_valide',)


class UsagerEtatCivilSchema(UsagerSchema):
    class Meta:
        model = Usager
        fields = ETAT_CIVIL_FIELDS


class UsagerEtatCivilValidationSchema(UsagerSchema):
    class Meta:
        model = Usager
        model_fields_kwargs = {f: {'required': True}
                               for f in ETAT_CIVIL_FIELDS_VALIDATION_MANDATORY}
        model_build_obj = False
        fields = ETAT_CIVIL_FIELDS


class UsagerPrefectureRattacheeSchema(view_util.BaseModelSchema):
    class Meta:
        model = Usager
        fields = ('prefecture_rattachee',)
        model_build_obj = False


usager_schema = UsagerSchema()
usager_base_schema = UsagerBaseSchema()
usager_etat_civil_schema = UsagerEtatCivilSchema()
usager_etat_civil_validation_schema = UsagerEtatCivilValidationSchema()
localisation_schema = LocalisationSchema()
usager_prefecture_rattachee_schema = UsagerPrefectureRattacheeSchema()


def _check_prefecture_rattachee(prefecture_rattachee, overall=False):
    if not p.usager.prefecture_rattachee.sans_limite.can() and not overall:
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        if getattr(user_site, 'autorite_rattachement', user_site) != prefecture_rattachee:
            abort(403, "Prefecture de rattachement invalide")


def _prefecture_rattachee_lookup(solr=False, overall=False):
    if p.usager.prefecture_rattachee.sans_limite.can() or overall:
        if solr:
            return []
        else:
            return {}
    else:
        user_site = current_user.controller.get_current_site_affecte()
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        pref = getattr(user_site, 'autorite_rattachement', user_site)
        if solr:
            return ['prefecture_rattachee:%s' % str(pref.pk)]
        else:
            return {'prefecture_rattachee': pref}


def _check_modification_rights(usager, payload):
    errors = {}
    msg = 'permission `%s` nécessaire pour modifier ce champ'
    if not p.usager.modifier_agdref.can():
        error_msg = msg % p.usager.modifier_agdref.name
        for field in ('identifiant_agdref', 'date_enregistrement_agdref',
                      'date_naturalisation', 'eloignement', 'date_fuite'):
            if field in payload:
                errors[field] = error_msg
    if not p.usager.modifier_ofii.can():
        error_msg = msg % p.usager.modifier_ofii.name
        for field in ('identifiant_dna', 'date_dna', 'identifiant_famille_dna',
                      'vulnerabilite'):
            if field in payload:
                errors[field] = error_msg
    if not p.usager.modifier_ofpra.can():
        if 'enfant_de_refugie' in payload:
            errors['enfant_de_refugie'] = msg % p.usager.modifier_ofpra.name
    return errors


def _check_modification_etat_civil_rights(usager, payload):
    errors = {}
    msg = 'permission `%s` nécessaire pour modifier ce champ'
    if not p.usager.etat_civil.modifier_photo.can():
        if 'photo' in payload:
            errors['photo'] = msg % p.usager.etat_civil.modifier_photo.name
    return errors


class UsagerAPI(CoreResource):
    @p.usager.voir.require(http_exception=403)
    def get(self, item_id):
        overall = 'overall' in request.args
        if 'par_identifiant_agdref' in request.args:
            agdref_id = '{:0>10}'.format(item_id)
            usager = Usager.objects.get_or_404(identifiant_agdref=agdref_id)
        else:
            usager = Usager.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(usager.prefecture_rattachee, overall=overall)
        return usager_schema.dump(usager).data

    @p.usager.modifier.require(http_exception=403)
    def patch(self, item_id):
        usager = Usager.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(usager.prefecture_rattachee)
        if_match = check_if_match(usager)
        payload = request.get_json()
        errors = _check_modification_rights(usager, payload)
        if errors:
            abort(400, **errors)
        usager, errors = usager_base_schema.update(usager, payload)
        if errors:
            abort(400, **errors)
        errors = usager.controller.check_demandeur(('langues', 'langues_audition_OFPRA'))
        if errors:
            abort(400, **errors)
        usager.controller.save_or_abort(if_match=if_match)
        usager_dump = usager_schema.dump(usager).data

        e.usager.modifie.send(
            usager=usager_dump, payload=payload)
        return usager_dump


class UsagerEtatCivilAPI(CoreResource):
    @p.usager.etat_civil.modifier.require(http_exception=403)
    def patch(self, item_id):
        from sief.view.demande_asile_api import demande_asile_schema

        usager = Usager.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(usager.prefecture_rattachee)
        if usager.ecv_valide and not p.usager.etat_civil.valider.can():
            abort(403)
        if_match = check_if_match(usager)
        payload = request.get_json()
        errors = _check_modification_etat_civil_rights(usager, payload)
        if errors:
            abort(403, **errors)
        usager, errors = usager_etat_civil_schema.update(usager, payload)
        if errors:
            abort(400, **errors)
        errors = usager.controller.check_demandeur(('photo',))
        if errors:
            abort(400, **errors)
        usager.controller.save_or_abort(if_match=if_match)
        usager_dump = usager_schema.dump(usager).data
        demande_asile = DemandeAsile.objects(usager=usager).order_by('-doc_updated').first()
        demande_asile_dump = demande_asile_schema.dump(demande_asile).data
        e.usager.etat_civil.modifie.send(
            usager=usager_dump, demande_asile=demande_asile_dump, payload=payload)
        return usager_dump

    @p.usager.etat_civil.valider.require(http_exception=403)
    def post(self, item_id):
        usager = Usager.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(usager.prefecture_rattachee)
        if usager.ecv_valide:
            abort(400, "L'état civil est déjà validé")
        if_match = check_if_match(usager)
        payload = request.get_json()
        data, errors = usager_etat_civil_validation_schema.load(payload)
        if errors:
            abort(400, **errors)
        for key, value in data.items():
            setattr(usager, key, value)
        usager.ecv_valide = True
        usager.controller.save_or_abort(if_match=if_match)
        usager_dump = usager_schema.dump(usager).data
        e.usager.etat_civil.valide.send(usager=usager_dump, payload=payload)
        return usager_dump


class UsagerLocalisationsAPI(CoreResource):
    @p.usager.voir.require(http_exception=403)
    def get(self, item_id):
        usager = Usager.objects.get_or_404(id=item_id)
        overall = 'overall' in request.args
        _check_prefecture_rattachee(usager.prefecture_rattachee, overall=overall)
        links = {'usager': url_for('UsagerAPI', item_id=item_id)}
        locs = list_to_pagination(usager.localisations)
        return view_util.PaginationSerializer(
            localisation_schema,
            url_for('UsagerLocalisationsAPI', item_id=item_id)).dump(
            locs, links=links).data

    @p.usager.modifier.require(http_exception=403)
    def post(self, item_id):
        usager = Usager.objects.get_or_404(id=item_id)
        _check_prefecture_rattachee(usager.prefecture_rattachee)
        if_match = check_if_match(usager)

        payload = request.get_json()
        localisation, errors = localisation_schema.load(payload)
        if errors:
            abort(400, **errors)

        usager.controller.add_localisation(localisation)
        usager.controller.save_or_abort(if_match=if_match)

        usager_dump = usager_schema.dump(usager).data
        e.usager.localisation.modifie.send(usager=usager_dump, payload=payload)
        return usager_dump


class UsagerListAPI(CoreResource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = view_util.PaginationSerializer(
            usager_schema, url_for('UsagerListAPI'))

    @p.usager.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        overall = 'overall' in request.args
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            lookup = _prefecture_rattachee_lookup(overall=overall)
            # No need to use the searcher module
            users = Usager.objects(**lookup).paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            urlargs['fq'] += _prefecture_rattachee_lookup(solr=True, overall=overall)
            users = Usager.search_or_abort(**urlargs)
        links = {'root': url_for('RootAPI')}
        if p.usager.creer.can():
            links['create'] = url_for('UsagerListAPI')
        return self._serializer.dump(users, links=links).data

    @p.usager.creer.require(http_exception=403)
    def post(self):
        payload = request.get_json()
        usager, errors = usager_schema.load(payload)
        if errors:
            abort(400, **errors)
        usager.controller.save_or_abort()
        usager_dump = usager_schema.dump(usager).data
        e.usager.cree.send(usager=usager_dump)
        return usager_dump, 201


class UsagerPrefectureRattacheeAPI(CoreResource):
    @p.usager.voir.require(http_exception=403)
    def get(self, item_id):
        usager = Usager.objects.get_or_404(id=item_id)
        return usager_prefecture_rattachee_schema.dump(usager).data

    @p.usager.prefecture_rattachee.modifier.require(http_exception=403)
    def patch(self, item_id):
        usager = Usager.objects.get_or_404(id=item_id)
        if not usager:
            abort(400, {'usager': 'Usager inexistant'})
        if not usager.transferable:
            abort(400, {'usager': 'Usager non transférable'})
        payload = request.get_json()
        data, errors = usager_prefecture_rattachee_schema.load(payload)
        if errors:
            abort(400, **errors)
        pref = data['prefecture_rattachee']
        pref_origin = usager.prefecture_rattachee
        usager.prefecture_rattachee = pref
        usager.save()
        for da in DemandeAsile.objects(usager=usager):
            da.prefecture_rattachee = pref
            da.save()
        from sief.model.droit import Droit
        for droit in Droit.objects(usager=usager):
            droit.prefecture_rattachee = pref
            droit.save()
        usager_dump = usager_schema.dump(usager).data
        e.usager.prefecture_rattachee.modifie.send(
            usager=usager_dump, payload=payload, pref_origin=pref_origin)
        return usager_dump


class UsagerEnfantsListAPI(CoreResource):
    @p.usager.voir.require(http_exception=403)
    def get(self, item_id):
        usagers = {}
        usagers['enfants'] = []

        def _getChildren(page, usagers):
            fq = []
            fq.append('identifiant_pere:%s OR identifiant_mere_r:%s' % (item_id, item_id))
            children = Usager.search_or_abort(fq=fq, page=page)
            for usager in children.items():
                usagers['enfants'].append(usager_schema.dump(usager).data.get('id', None))

            if len(children.items) != 0:
                _getChildren(page + 1, usagers)

        _getChildren(1, usagers)

        return usagers


class UsagersCorrespondantsListAPI(CoreResource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = view_util.PaginationSerializer(
            usager_schema, url_for('UsagersCorrespondantsListAPI'))

    @p.usager.voir.require(http_exception=403)
    @cached_from_config('FNE_CACHE_TIMEOUT')
    def get(self):
        usagers = {}
        check_all = not (request.args.get('fne') or request.args.get('usagers'))
        nom = request.args.get('nom')
        prenom = request.args.get('prenom')
        date_naissance = request.args.get('date_naissance')
        sexe = request.args.get('sexe')
        identifiant_agdref = request.args.get('identifiant_agdref')
        identifiants_eurodac = request.args.get('identifiants_eurodac')

        if check_all or request.args.get('usagers'):
            fq = []
            usagers['PLATEFORME'] = []

            if nom:
                fq.append('nom_phon:%s' % nom)
            if prenom:
                fq.append('prenoms_phons:%s' % prenom)
            if date_naissance:
                # Assume that date_naissance has format YYYY-MM-DD
                fq.append('date_naissance:[%sT00:00:00Z TO %sT23:59:59Z]' %
                          (date_naissance, date_naissance))
            if sexe:
                fq.append('sexe:%s' % sexe)

            if identifiant_agdref:
                fq.append('identifiant_agdref:%s' % identifiant_agdref)

            if identifiants_eurodac:
                fq.append('identifiants_eurodac:%s' % identifiants_eurodac)

            def _get_usager_plateforme(page, usagers_plateforme):
                pf_usagers = Usager.search_or_abort(fq=fq, page=page)
                for usager in pf_usagers.items():
                    das = DemandeAsile.objects(usager=usager)
                    indicateur_presence_demande_asile = False
                    for da in das:
                        if da.statut not in ["DECISION_DEFINITIVE", "FIN_PROCEDURE_DUBLIN", "FIN_PROCEDURE"]:
                            indicateur_presence_demande_asile = True
                            break
                    usager_data = usager_schema.dump(usager).data
                    usager_data[
                        'indicateurPresenceDemandeAsile'] = indicateur_presence_demande_asile
                    usagers['PLATEFORME'].append(usager_data)

                if len(pf_usagers.items) != 0:
                    _get_usager_plateforme(page + 1, usagers_plateforme)

            _get_usager_plateforme(1, usagers['PLATEFORME'])

        if check_all or request.args.get('fne'):
            try:
                usagers['FNE'] = {}
                usagers['FNE']['errors'] = []
                fne_users = services.fne.lookup_fne(nom=nom, prenom=prenom,
                                                    date_naissance=date_naissance,
                                                    sexe=sexe)
                if fne_users:
                    usagers['FNE']['usagers'] = fne_users
                else:
                    usagers['FNE'] = []
            except services.fne.FNEDisabledError:
                usagers['FNE']['errors'].append(
                    {"code": 503, "libelle": 'Connecteur FNE desactive'})
            except services.fne.FNEConnectionError:
                usagers['FNE']['errors'].append(
                    {"code": 503, "libelle": 'Le service n\'a pas reussi a se connecter au FNE'})
            except services.fne.FNETooManyResponse:
                usagers['FNE']['errors'].append(
                    {"code": 416, "libelle": 'Trop de réponses, veuillez affiner la recherche.'})

            except services.fne.FNEBadRequestError as e:
                usagers['FNE']['errors'].append({"code": 400, "libelle": str(e)})
        return usagers


class UsagersCorrespondantsAPI(CoreResource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = view_util.PaginationSerializer(
            usager_schema, url_for('UsagersCorrespondantsAPI'))

    @p.usager.voir.require(http_exception=403)
    @cached_from_config('FNE_CACHE_TIMEOUT')
    def get(self):
        if request.args.get('identifiant_agdref'):
            try:
                return services.fne.lookup_fne(identifiant_agdref=request.args.get('identifiant_agdref'))
            except services.fne.FNEDisabledError:
                abort(503, 'Connecteur FNE desactive')
            except services.fne.FNEConnectionError:
                abort(503, 'Le service n\'a pas reussi a se connecter au FNE')
            except services.fne.FNEBadRequestError as e:
                abort(400, str(e))
        return {}


class UsagersFprAPI(CoreResource):
    @p.usager.consulter_fpr.require(http_exception=403)
    @cached_from_config('FPR_CACHE_TIMEOUT')
    def get(self):
        if not request.args.get('nom'):
            abort(400, nom="Paramètre manquant")
        nom = request.args['nom']
        prenom = request.args.get('prenom', '')
        date_naissance = request.args.get('date_naissance')
        if not date_naissance:
            abort(400, date_naissance="Paramètre manquant")
        if not re.match(r'[0-9 ]{8}', date_naissance):
            # If date not in AGDREF format, try to parse into a datetime
            try:
                date_naissance = parse(request.args['date_naissance'])
            except ValueError:
                abort(400, date_naissance="Date invalide")
        try:
            res = fpr_query(firstname=prenom, lastname=nom, birthday=date_naissance)
        except FprDisabledError:
            abort(503, 'Connecteur FPR desactive')
        except FprConnectionError:
            abort(503, 'Le service n\'a pas reussi a se connecter au FPR')
        except FprError as exc:
            abort(400, str(exc))
        return {
            'nom': nom,
            'date_naissance': date_naissance,
            'resultat': res
        }


class Usagers_ExportAPI(CoreResource):
    @p.usager.export.require(http_exception=403)
    def get(self):
        exporter = Export(Usager)
        return exporter.csv_format(['id', 'doc_version', 'doc_updated', 'doc_created',
                                    'identifiant_agdref', 'date_enregistrement_agdref',
                                    'ecv_valide', 'sexe', 'date_naissance', 'pays_naissance',
                                    'ville_naissance', 'nationalites', 'situation_familiale',
                                    'localisations', 'langues', 'langues_audition_OFPRA',
                                    'sites_suiveurs', 'date_deces', 'eloignement',
                                    'prefecture_rattachee', 'identifiant_portail_agdref',
                                    'identifiant_dna', 'date_dna',
                                    'identifiant_famille_dna', 'date_naissance_approximative',
                                    'date_naturalisation', 'date_fuite', 'identifiant_pere',
                                    'identifiant_mere', 'enfant_de_refugie', 'conjoint'],
                                   get_search_urlargs(),
                                   url_for('Usagers_ExportAPI')), 200
