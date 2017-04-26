from flask import current_app
from flask import request, url_for
from marshmallow import post_dump
from datetime import datetime

from core.tools import abort, get_search_urlargs, check_if_match
from core.auth import current_user, is_fresh_auth
from core import CoreResource, view_util
from sief.permissions import POLICIES as p
from sief.model.utilisateur import Utilisateur, Accreditation, AccreditationError
from sief.events import EVENTS as e
from sief.roles import (check_role_on_meta_utilisateur,
                        check_role_on_meta_utilisateur_per_accreditation,
                        check_can_see_user_by_role, is_system_accreditation,
                        get_can_see_user_by_role_lookup, ROLE_ADMIN)


Utilisateur.set_link_builder_from_api('UtilisateurAPI')


class UtilisateurSchema(view_util.BaseModelSchema):
    _links = view_util.fields.Method('get_links')

    def __init__(self, *args, full_access=False, show_preferences=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not full_access:
            for field in ('permissions', 'password'):
                self.fields[field].dump_only = True

        self.fields['preferences'].load_only = not show_preferences
        self.fields['preferences'].dump_only = not show_preferences

    def get_links(self, obj):
        route = url_for("UtilisateurAPI", item_id=obj.pk)
        links = {'self': route,
                 'parent': url_for("UtilisateurListAPI")}
        if p.utilisateur.modifier.can():
            links['update'] = route
        if p.historique.voir.can():
            links['history'] = url_for("UtilisateurHistoryListAPI",
                                       origin_id=obj.pk)
        return links

    class Meta:
        model = Utilisateur
        model_fields_kwargs = {
            'accreditations': {'dump_only': True},
            'basic_auth': {'load_only': True, 'dump_only': True},
            'fin_validite': {'dump_only': True}
        }


class AccreditationSchema(view_util.UnknownCheckedSchema):

    def __init__(self, *args, full_access=False, base_url=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not full_access:
            for field in ('role', 'site_affecte'):
                self.fields[field].dump_only = True
        self._base_url = base_url

    @post_dump(pass_original=True)
    def patch(self, data, original):
        if original.site_affecte:
            data['site_affecte']['libelle'] = original.site_affecte.libelle
        if original.site_rattache:
            data['site_rattache']['libelle'] = original.site_rattache.libelle
        url = '%s/%s' % (self._base_url, original.id)
        data['_links'] = {'self': url}
        can = p.utilisateur.accreditations.gerer.can()
        errors = check_role_on_meta_utilisateur_per_accreditation(original)
        if can and not errors:
            data['_links']['update'] = url

    class Meta:
        # marshmallow will return json instead of the object
        model_build_obj = False
        model = Accreditation
        #  Must set id to read-only manually given we don't inherit `BaseModelSchema`
        model_fields_kwargs = {'id': {'dump_only': True},
                               'site_rattache': {'dump_only': True}}


def _check_site_rattachee(utilisateur, overall=False):
    if not p.utilisateur.sans_limite_site_affecte.can() and not overall:
        curr_accr = current_user.controller.get_current_accreditation()
        if not curr_accr.site_affecte:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        for ua in utilisateur.accreditations:
            if (curr_accr.site_affecte == ua.site_rattache and
                    check_can_see_user_by_role(curr_accr.role, ua.role)):
                break
        else:
            abort(403, "Cet utilisateur est rattaché à un autre site et/ou"
                       " a un role que vous ne pouvez pas voir")


def _site_rattachee_lookup(solr=False, overall=False):
    if p.utilisateur.sans_limite_site_affecte.can() or overall:
        if solr:
            return []
        else:
            return {}
    else:
        user_accreditation = current_user.controller.get_current_accreditation()
        filt = get_can_see_user_by_role_lookup(user_accreditation.role, solr=solr)
        user_site = user_accreditation.site_affecte
        today = datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")
        if not user_site:
            abort(400, "L'utilisateur doit avoir un site_affecte")
        if solr:
            # Remove Utilisateur without active accreditations
            filt.append('-fin_validite: [* TO %s]' % today)
            filt.append('accreditations_site_rattache:%s' % user_site.pk)
        else:
            # Remove Utilisateur without active accreditations
            filt.update({'fin_validite__not__lte': today})
            filt.update({'accreditations__site_rattache': user_site})
        return filt


class UtilisateurAPI(CoreResource):

    def get(self, item_id=None):
        if not item_id:
            # Use current user by default
            user = current_user
            url = url_for('UtilisateurAPI')
            links = {'self': url, 'update': url, 'root': url_for('RootAPI')}
            show_preferences = True
        else:
            with p.utilisateur.voir.require(http_exception=403):
                user = Utilisateur.objects.get_or_404(id=item_id)
                links = None  # Use default links
                show_preferences = False
                overall = 'overall' in request.args
                _check_site_rattachee(user, overall=overall)
        schema = UtilisateurSchema(show_preferences=show_preferences)
        data = schema.dump(user).data

        if not item_id:
            accreditation = user.controller.get_current_accreditation()
            data['current_accreditation_id'] = accreditation.id
            data['_links'] = links
        return data

    def patch(self, item_id=None):
        if not item_id:
            schema = UtilisateurSchema(show_preferences=True)
            user = current_user
            links = {'self': '/moi', 'update': '/moi'}
        else:
            if not is_fresh_auth():
                abort(401, 'Token frais requis')
            with p.utilisateur.modifier.require(http_exception=403):
                schema = UtilisateurSchema(full_access=True)
                user = Utilisateur.objects.get_or_404(id=item_id)
                links = None
                overall = 'overall' in request.args
                _check_site_rattachee(user, overall=overall)
        if_match = check_if_match(user)
        payload = request.get_json()
        if 'password' in payload:
            password = payload.pop('password')
            if ((current_user.id != user.id) and
                    not p.utilisateur.changer_mot_de_passe_utilisateur.can()):
                abort(400, 'Impossible de modifier le mot de passe d\'un autre utilisateur.')
            if not user.controller.set_password(password):
                abort(400, 'Le mot de passe doit faire au moins 8 caractères '
                           'avec au moins une majuscule, une minuscule et un caractère spécial.')
        user, errors = schema.update(user, payload)
        if errors:
            abort(400, **errors)

        # TODO: DON'T AUTHORIZE USER_SYSTEM PATCH by ADMIN LOCAL
        # CHECK IF THE CURRENT USER IS ADMIN LOCAL => FORBIDDEN TO UPDATED THE
        # USER SYSTEM
        current_user_role = current_user.controller.get_current_role()
        if(current_user_role not in ROLE_ADMIN and user.system_account):
            abort(400, 'Un administrateur local ne peut pas modifer un compte systeme.')

        user.controller.save_or_abort(if_match=if_match)
        data = schema.dump(user).data
        e.utilisateur.modifie.send(utilisateur=data, payload=payload)
        if links:
            data['_links'] = links
        return data


class UtilisateurListAPI(CoreResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._serializer = view_util.PaginationSerializer(
            UtilisateurSchema(), url_for('UtilisateurListAPI'))

    @p.utilisateur.voir.require(http_exception=403)
    def get(self):
        urlargs = get_search_urlargs()
        overall = 'overall' in request.args
        if not urlargs['q'] and not urlargs['fq'] and not urlargs['sort']:
            lookup = _site_rattachee_lookup(overall=overall)
            # No need to use the searcher module
            users = Utilisateur.objects(**lookup).paginate(
                page=urlargs['page'], per_page=urlargs['per_page'])
        else:
            urlargs['fq'] += _site_rattachee_lookup(solr=True, overall=overall)
            users = Utilisateur.search_or_abort(**urlargs)
        links = {'root': url_for('RootAPI')}
        if p.utilisateur.creer.can():
            links['create'] = url_for('UtilisateurListAPI')
        return self._serializer.dump(users, links=links).data

    @p.utilisateur.creer.require(http_exception=403)
    def post(self):
        if not is_fresh_auth():
            abort(401, 'Token frais requis')
        payload = request.get_json()
        accreditations_payload = payload.pop('accreditations', [])
        schema = UtilisateurSchema(full_access=True)
        user, errors = schema.load(payload)

        # Special handling for accreditations with it own Schema
        if not isinstance(accreditations_payload, list):
            errors['accreditations'] = ['Not a list']
        accr_errors = {}
        if not errors:
            accr_errors = {}
            accr_schema = AccreditationSchema(full_access=True)
            for i, accr_payload in enumerate(accreditations_payload):
                # Check for required fields
                accr_data, err = accr_schema.load(accr_payload or {})
                if err:
                    accr_errors[str(i)] = err
                    continue
                # Site inheritance between created user and creator
                accr_data['site_rattache'] = current_user.controller.get_current_site_affecte()
                try:
                    user.controller.add_accreditation(**accr_data)
                except AccreditationError as exc:
                    accr_errors[str(i)] = str(exc)
                accr_errors.update(check_role_on_meta_utilisateur(user))
        if accr_errors:
            errors = {'accreditations': accr_errors}
        if errors:
            abort(400, **errors)

        if not current_app.config.get('FF_CONSOMMATION_TTE', False):
            accreditation_gestionnaires = [accreditation
                                           for accreditation in accreditations_payload
                                           if accreditation['role'] == 'GESTIONNAIRE_DE_TITRES']
            has_accreditation_gestionnaire = len(accreditation_gestionnaires) > 0
            if has_accreditation_gestionnaire:
                feature_deactivated_error = {
                    'code-erreur': 'feature-deactivated',
                    'description-erreur': 'You can not create a "Gestionnaire de titres".'
                }
                abort(400, errors=[feature_deactivated_error])

        user.controller.init_basic_auth()
        user.controller.generate_password()
        user.controller.email_password_link()
        # Check if the accreditation is system accreditation
        if is_system_accreditation(user.accreditations):
            user.system_account = True
        user.controller.save_or_abort()
        e.utilisateur.cree.send(utilisateur=schema.dump(user).data)
        return schema.dump(user).data, 201


class AccreditationListAPI(CoreResource):

    """
    API to manipulate user's accreditations
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get(self, user_id=None):
        if not user_id:
            user = current_user
            url = url_for('AccreditationListAPI')
            links = {'self': url}
        else:
            with p.utilisateur.voir.require(http_exception=403):
                user = Utilisateur.objects.get_or_404(id=user_id)
                url = url_for('AccreditationListAPI', user_id=user_id)
                links = {'self': url}
                if p.utilisateur.accreditations.gerer.can():
                    links['create'] = url
        schema = AccreditationSchema(base_url=url)
        items = [schema.dump(accr).data for accr in user.accreditations]
        data = {'_items': items, '_links': links}
        return data, 200

    @p.utilisateur.accreditations.gerer.require(http_exception=403)
    def post(self, user_id=None):
        # User cannot self add accreditation
        if user_id is None:
            abort(404)

        if not is_fresh_auth():
            abort(401, 'Token frais requis')

        payload = request.get_json()
        url = url_for('AccreditationListAPI', user_id=user_id)
        schema = AccreditationSchema(full_access=True, base_url=url)
        accreditation_data, errors = schema.load(payload)
        if errors:
            abort(400, **errors)

        user = Utilisateur.objects.get_or_404(id=user_id)
        # Site inheritance between created user and creator
        accreditation_data['site_rattache'] = \
            current_user.controller.get_current_site_affecte()

        try:
            accreditation = user.controller.add_accreditation(
                **accreditation_data)
        except AccreditationError as e:
            abort(400, _schema=str(e))
        errors = \
            check_role_on_meta_utilisateur_per_accreditation(accreditation)
        if errors:
            abort(400, **errors)
        # Check if the accreditation is system accreditation
        if is_system_accreditation(user.accreditations):
            user.system_account = True

        user.controller.save_or_abort()

        return schema.dump(accreditation).data, 201


def _get_accreditation_by_id_or_abort(user, accr_id):
    try:
        accreditation_gotten = user.accreditations[accr_id]
    except AccreditationError as e:
        abort(404, _schema=str(e))
    return accreditation_gotten


class AccreditationAPI(CoreResource):

    def get(self, user_id=None, accr_id=None):
        if not user_id:
            # Use current user by default
            user = current_user
            accreditation = _get_accreditation_by_id_or_abort(user, accr_id)
            url = url_for('AccreditationAPI', accr_id=accr_id)
        else:
            with p.utilisateur.accreditations.gerer.require(
                    http_exception=403):
                user = Utilisateur.objects.get_or_404(id=user_id)
                accreditation = _get_accreditation_by_id_or_abort(user, accr_id)
                url = '/utilisateurs/%s/accreditations' % user_id
        schema = AccreditationSchema(base_url=url, full_access=True)
        data = schema.dump(accreditation).data
        return data, 200

    def patch(self, user_id=None, accr_id=None):
        if not user_id:
            abort(405)
        elif current_user.id == user_id:
            abort(400, accreditations=["Vous n'avez pas le droit de modifier vos habilitations"])
        else:
            if not is_fresh_auth():
                abort(401, 'Token frais requis')
            with p.utilisateur.accreditations.gerer.require(http_exception=403):
                user = Utilisateur.objects.get_or_404(id=user_id)
                accreditation = _get_accreditation_by_id_or_abort(user, accr_id)
                _check_site_rattachee(user)
        if_match = check_if_match(user)
        payload = request.get_json()
        url = 'utilisateurs/%s/accreditations' % user_id
        schema = AccreditationSchema(base_url=url)
        updated_accreditation, errors = schema.update(
            accreditation, payload)
        errors = errors or check_role_on_meta_utilisateur_per_accreditation(accreditation)

        if errors:
            abort(400, **errors)

        user.controller.update_user_fin_validite()
        user.controller.save_or_abort(if_match=if_match)
        data = schema.dump(updated_accreditation).data
        return data, 200
