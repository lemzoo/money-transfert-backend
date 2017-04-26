"""
This module centralize all the action-needs/permissions used for the
access rights policy
"""

from flask.ext.principal import Permission, ActionNeed

from core.tools import Tree


class Policy:

    def __init__(self, name):
        self.name = name
        self._action_need = ActionNeed(name)
        self._permission = Permission(self._action_need)

    def __str__(self):
        return self.name

    def __repr__(self):
        return '<Policy %s>' % self.name

    def can(self):
        return self._permission.can()

    def require(self, *args, **kwargs):
        return self._permission.require(*args, **kwargs)

    @property
    def permission(self):
        return self._permission

    @property
    def action_need(self):
        return self._action_need


class PolicyTree(Tree):

    def build_leaf(self, route):
        return Policy(route)


POLICIES = PolicyTree({
    'utilisateur': ('creer', 'modifier', 'voir', 'sans_limite_site_affecte', 'changer_mot_de_passe_utilisateur', {'accreditations': 'gerer'}),
    'site': ('creer', 'modifier', 'voir', 'export', 'fermer', 'sans_limite_site_affecte',
             {'rendez_vous': 'gerer'}, {'creneaux': 'gerer'},
             {'actualite': 'gerer'}, {'modele': 'gerer'}),
    'recueil_da': ('creer_pa_realise', 'creer_brouillon', 'modifier_brouillon', 'modifier_pa_realise',
                   'modifier_demandeurs_identifies', 'modifier_exploite', 'generer_eurodac',
                   'voir', 'export', 'purger', {'rendez_vous': 'gerer'},
                   {'prefecture_rattachee': ('modifier', 'sans_limite')},
                   'enregistrer_famille_ofii'),
    'demande_asile': ('creer', 'voir', 'modifier', 'export', 'orienter',
                      'modifier_dublin', 'editer_attestation',
                      'requalifier_procedure', 'modifier_ofpra', 'cloture_ofpra',
                      'finir_procedure', 'modifier_stock_dna',
                      {'prefecture_rattachee': 'sans_limite'}, {'condition_exceptionnelle': ('export')},
                      {'en_attente_introduction_ofpra': ('export')}),
    'droit': ('creer', 'retirer', 'voir',
              {'support': ('creer', 'annuler')},
              {'prefecture_rattachee': 'sans_limite'}, 'export'),
    'usager': ('creer', 'modifier', 'voir', 'export', 'consulter_fpr',
               {'etat_civil': ('valider', 'modifier', 'modifier_photo')},
               'modifier_ofpra', 'modifier_ofii', 'modifier_agdref',
               {'prefecture_rattachee': ('modifier', 'sans_limite')}),
    'historique': 'voir',
    'fichier': ('voir', 'gerer'),
    'parametrage': 'gerer',
    'telemOfpra': ('creer', 'voir'),
    'broker': 'gerer',
    'analytics': 'voir',
    'monitoring': 'voir',
    'timbre': ('voir', 'consommer'),
})
