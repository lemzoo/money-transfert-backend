from core import CoreResource, CoreApi
from core.view_util import history_api
from sief.view import (usager_api, utilisateur_api, site_api,
                       recueil_da_api, referentials_api, fichier_api,
                       demande_asile_api, droit_api, parametrage_api,
                       telemOfpra_api, impression_api, version_api,
                       paiements_api, timbre_api)
from sief.model import (utilisateur, site, recueil_da, usager, demande_asile,
                        droit)

from analytics.view import AnalyticsAPI
from services.monitoring import BrokerCheck, APICheck

api = CoreApi()


# utilisateurs
api.add_resource(utilisateur_api.UtilisateurAPI,
                 '/moi',
                 '/utilisateurs/<objectid:item_id>')
api.add_resource(utilisateur_api.AccreditationListAPI,
                 '/utilisateurs/<objectid:user_id>/accreditations', '/moi/accreditations')

api.add_resource(utilisateur_api.AccreditationAPI,
                 '/utilisateurs/<objectid:user_id>/accreditations/<int:accr_id>',
                 '/moi/accreditations/<int:accr_id>')
api.add_resource(utilisateur_api.UtilisateurListAPI, '/utilisateurs')

# sites
api.add_resource(site_api.SiteAPI, '/sites/<objectid:item_id>')
api.add_resource(site_api.SiteListAPI, '/sites')
api.add_resource(site_api.CreneauAPI,
                 '/sites/<objectid:site_id>/creneaux/<objectid:creneau_id>')
# TODO: remove this api ?
# api.add_resource(site_api.RendezVousAPI,
# '/sites/<objectid:site_id>/creneaux/<objectid:creneau_id>/rendez_vous')
api.add_resource(site_api.CreneauListAPI, '/sites/<objectid:site_id>/creneaux')
api.add_resource(site_api.SiteActualiteListAPI, '/sites/<objectid:site_id>/actualites')
api.add_resource(site_api.SiteActualiteAPI,
                 '/sites/<objectid:site_id>/actualites/<objectid:actualite_id>')
api.add_resource(site_api.SiteModelesAPI, '/sites/<objectid:site_id>/modeles')
api.add_resource(site_api.SiteExportAPI, '/sites/export')
# recueil_da
api.add_resource(recueil_da_api.RecueilDAAPI, '/recueils_da/<int:item_id>')
recueil_da.RecueilDA.set_link_builder_from_api(recueil_da_api.RecueilDAAPI)
api.add_resource(recueil_da_api.RecueilDAListAPI, '/recueils_da')
api.add_resource(recueil_da_api.RecueilDA_RendezVous_API,
                 '/recueils_da/<int:item_id>/rendez_vous')
api.add_resource(recueil_da_api.RecueilDA_PARealise_API,
                 '/recueils_da/<int:item_id>/pa_realise')
api.add_resource(recueil_da_api.RecueilDA_DemandeursIdentifies_API,
                 '/recueils_da/<int:item_id>/demandeurs_identifies')
api.add_resource(recueil_da_api.RecueilDA_Exploite_API,
                 '/recueils_da/<int:item_id>/exploite')
api.add_resource(recueil_da_api.RecueilDA_Annule_API,
                 '/recueils_da/<int:item_id>/annule')
api.add_resource(recueil_da_api.RecueilDA_Purge_API,
                 '/recueils_da/<int:item_id>/purge')
api.add_resource(recueil_da_api.RecueilDA_PrefectureRattachee_API,
                 '/recueils_da/<int:item_id>/prefecture_rattachee')
api.add_resource(recueil_da_api.RecueilDA_EnregistrementFamilleOfii_API,
                 '/recueils_da/<int:item_id>/enregistrement_famille_ofii')
api.add_resource(recueil_da_api.RecueilDA_ExportAPI,
                 '/recueils_da/export')
api.add_resource(recueil_da_api.RecueilDAGenererEurodacAPI,
                 '/recueils_da/<int:item_id>/generer_eurodac')

# demande_asile
api.add_resource(demande_asile_api.DemandeAsileAPI,
                 '/demandes_asile/<int:item_id>')
api.add_resource(demande_asile_api.DemandeAsile_orientation_API,
                 '/demandes_asile/<int:item_id>/orientation')
api.add_resource(demande_asile_api.DemandeAsile_editionAttestation_API,
                 '/demandes_asile/<int:item_id>/attestations')
api.add_resource(demande_asile_api.DemandeAsile_requalification_API,
                 '/demandes_asile/<int:item_id>/requalifications')
api.add_resource(demande_asile_api.DemandeAsile_finirProcedure_API,
                 '/demandes_asile/<int:item_id>/fin_procedure')
api.add_resource(demande_asile_api.DemandeAsile_dublin_API,
                 '/demandes_asile/<int:item_id>/dublin')
api.add_resource(demande_asile_api.DemandeAsile_introductionOfpra_API,
                 '/demandes_asile/<int:item_id>/introduction_ofpra')
api.add_resource(demande_asile_api.DemandeAsile_Recevabilite_API,
                 '/demandes_asile/<int:item_id>/recevabilite_ofpra')
api.add_resource(demande_asile_api.DemandeAsile_decisionDefinitive_API,
                 '/demandes_asile/<int:item_id>/decisions_definitives')
api.add_resource(demande_asile_api.DemandeAsile_decisionAttestation_API,
                 '/demandes_asile/<int:item_id>/decisions_attestations')
api.add_resource(demande_asile_api.DemandeAsile_decisionDefinitiveINEREC_API,
                 '/demandes_asile/<string:item_id>/decisions_definitives_inerec')
api.add_resource(demande_asile_api.DemandeAsileListAPI, '/demandes_asile')
api.add_resource(demande_asile_api.DemandeAsile_PrefectureRattachee_API,
                 '/demandes_asile/<int:item_id>/prefecture_rattachee')
api.add_resource(demande_asile_api.DemandeAsile_ExportAPI,
                 '/demandes_asile/export')
api.add_resource(demande_asile_api.DemandeAsile_Condition_Exceptionnelle_ExportAPI,
                 '/demandes_asile/condition_exceptionnelle/export')
api.add_resource(demande_asile_api.DemandeAsile_EnAttenteIntroductionOfpra_ExportAPI,
                 '/demandes_asile/en_attente_introduction_ofpra/export')
# uncomment those two line to give the possibility to OPFRA to close
# an ASYLUM, #reouverture
# api.add_resource(demande_asile_api.DemandeAsile_decisionClotureOFPRA_API,
#                 '/demandes_asile/<int:item_id>/cloture_ofpra')


# Impression
api.add_resource(impression_api.ImpressionAPI, '/impression/id')

# droit
api.add_resource(droit_api.DroitListAPI, '/droits')
api.add_resource(droit_api.DroitAPI, '/droits/<objectid:item_id>')
api.add_resource(droit_api.DroitRetraitAPI,
                 '/droits/<objectid:item_id>/retrait')
api.add_resource(droit_api.DroitSupportsAPI,
                 '/droits/<objectid:item_id>/supports')
api.add_resource(droit_api.DroitAnnulerSupportAPI,
                 '/droits/<objectid:droit_id>/supports/<string:numero_serie>/annulation')
api.add_resource(droit_api.Droit_PrefectureRattachee_API,
                 '/droits/<objectid:item_id>/prefecture_rattachee')
api.add_resource(droit_api.Droit_ExportAPI, '/droits/export')

# usager
api.add_resource(usager_api.UsagerAPI, '/usagers/<int:item_id>')
api.add_resource(usager_api.UsagerEtatCivilAPI,
                 '/usagers/<int:item_id>/etat_civil')
api.add_resource(usager_api.UsagerLocalisationsAPI,
                 '/usagers/<int:item_id>/localisations')
api.add_resource(usager_api.UsagerPrefectureRattacheeAPI,
                 '/usagers/<int:item_id>/prefecture_rattachee')
api.add_resource(usager_api.UsagerEnfantsListAPI,
                 '/usagers/<int:item_id>/enfants')
api.add_resource(usager_api.UsagerListAPI, '/usagers')
api.add_resource(usager_api.UsagersCorrespondantsAPI, '/recherche_usagers_tiers/usager')
api.add_resource(usager_api.UsagersCorrespondantsListAPI, '/recherche_usagers_tiers')
api.add_resource(usager_api.UsagersFprAPI, '/recherche_fpr')
api.add_resource(usager_api.Usagers_ExportAPI, '/usagers/export')


# fichier
api.add_resource(fichier_api.FichierAPI, '/fichiers/<objectid:item_id>')
api.add_resource(fichier_api.FichierDataAPI,
                 '/fichiers/<objectid:item_id>/data')
api.add_resource(fichier_api.FichierListAPI, '/fichiers')

# parametrage
api.add_resource(parametrage_api.ParametrageApi, '/parametrage')

# telemOfpra
api.add_resource(telemOfpra_api.TelemOfpraListApi, '/telemOfpra')

# history
history_api.register_history(api, utilisateur.Utilisateur, 'utilisateurs')
history_api.register_history(api, usager.Usager, 'usagers')
history_api.register_history(api, site.Site, 'sites')
history_api.register_history(api, recueil_da.RecueilDA, 'recueils_da')
history_api.register_history(api, demande_asile.DemandeAsile, 'demandes_asile')
history_api.register_history(api, droit.Droit, 'droits')

# referentiel
referentials_api.register_referentials(api, '/referentiels')

# analytics
api.add_resource(AnalyticsAPI, '/analytics')

# Monitoring
api.add_resource(BrokerCheck, '/monitoring/broker')
api.add_resource(APICheck, '/monitoring/api')

# Backend version
api.add_resource(version_api.VersionAPI, '/version')

# Paiements
api.add_resource(paiements_api.PaiementsAPI, '/paiements')

# Timbre
api.add_resource(timbre_api.TimbreAPI, '/timbres/<string:numero_timbre>')


class RootAPI(CoreResource):

    """Root endpoint for api discovering"""

    def get(self):
        return {
            '_links': {
                'usager': '/usagers',
                'brokers': '/brokers',
                'messages': '/messages',
                'utilisateurs': '/utilisateurs',
                'sites': '/sites',
                'recueils_da': '/recueils_da',
                'droits': '/droits',
                'demandes_asile': '/demandes_asile',
                'referentiels': '/referentiels',
                'fichiers': '/fichiers',
                'version': '/version',
            }
        }
api.add_resource(RootAPI, '/')


__all__ = ('api',)
