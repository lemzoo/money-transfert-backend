
## Nos règles pour coder ensemble


### Gestion de version (Git)

- Messages de commit en anglais et surtout voulant dire quelque chose (pas de
  `updated un_truc.py` ou `small cleanup`)
- Commits bien décomposés par fonctionnalité (pas de commit fourre-tout à la fin de la journée)
- Dans le cas d'un ticket, le nom de la branche est préfixée par le numéro du ticket
  (`t1234-feature-description`)
- Pas de code non lié au ticket / à la feature
- Atomicité de la PR (doit pouvoir être utilisée indépendamment -> possibilité de revert le
  merge)
- Toute nouvelle fonctionnalité doit pouvoir être activée / désactivé par configuration (sans
  redéploiement). Voir
    - [FeatureToggle](https://martinfowler.com/bliki/FeatureToggle.html)
    - [Feature Toggles](https://martinfowler.com/articles/feature-toggles.html)
    - [Feature Flipping](http://blog.octo.com/feature-flipping/)


### Tests

- Tests obligatoires pour tout ajout / modification
    - Nouvelle fonctionnalité: présence et pertinence des tests
    - Modification de code: modification des tests? non? pourquoi?


### Conception

- [KISS](http://wiki.c2.com/?KeepItSimple)
- [YAGNI](http://wiki.c2.com/?YouArentGonnaNeedIt)
- Partager les choix d'implémentation qui ont un impact fonctionnel (par Slack à minima)


### Style

- [PEP8](https://www.python.org/dev/peps/pep-0008/)
    - En acceptant les lignes jusqu'à 100 caractères (cas prévu par la PEP8) car souvent la
      limite à 80 caractères encourage l'utilisation de noms de méthodes moins explicites
- [Zen of Python](https://www.python.org/dev/peps/pep-0020/)
- Pas de trailing whitespace
- Retour à la ligne en fin de fichier
- Idiomatique du langage (itération, splicing, context managers, ...)
- Tout ce qui est en lien avec le métier (message d'erreur dans l'api, champ dans un model
  etc.) en français, tout le reste en anglais


### Clean Code

- Attention à l'abus de commentaires : Python est très expressif et un bon code avec de
  méthodes explicites se comprend de lui même la plupart du temps
- Prendre le temps de tout nommer correctement (choisir les noms à plusieurs par ex.)
- Pas de except global ou de except Exception (actuellement dans tout le projet son usage est
  justifié à un seul endroit dans le broker)
- Pas de fonction trop longue (je fais ça au jugé, mais environ une vingtaine de lignes max)
- Éviter les classes avec trop de responsabilités
- Éviter d'avoir trop de couplage (une classe ne doit pas avoir trop de collaborateurs)
- [Tell, don't ask](https://martinfowler.com/bliki/TellDontAsk.html) : les détails d'implémentation d'une classe ne sont pas exposés aux autres
  classes
- [La loi de Demeter](https://en.wikipedia.org/wiki/Law_of_Demeter)
- Plus généralement la liste des [CodeSmells](http://wiki.c2.com/?CodeSmell)
- [S.O.L.I.D.](https://en.wikipedia.org/wiki/SOLID_(object-oriented_design))


### Gestion des erreurs

- Tous les chemins sont gérés
- Entrées utilisateur vérifiées


### Sécurité

- Se conforter au [12 factor app de Heroku](https://12factor.net/)
    - (par exemple concernant les logs, l'application se contente de les sortir sur stdout et de la responsabilité de
      l'infrastructure sous-jacente de les collecter)
    - Jamais aucun secret (Clé API par ex.) dans le code source.


### API

- L'ajout d'une route doit être validé (Core Back)
- Suivre les [recos WOAPI](http://blog.octo.com/designer-une-api-rest/)
- Nouvelle: réutilisation/factorisation
- Casse: penser aux impacts de la casse (majuscule / minuscule) dans l'API (routes et ressources)
- Utiliser le header HTTP `If-Match` dans les requêtes du front vers le back (mécanisme de Compare And
  Set)
- Changement d'API => mise à jour de Confluence
- Suivre [le nouveau format d'erreur](https://scille.atlassian.net/wiki/pages/viewpage.action?pageId=70932051)


### Documentation

- Docstring
- Commentaires utiles **si le code n'est pas self-documented** (voir Clean Code)


### Performances

- Impacts IO, mémoire, CPU (attention, pas d'optimisations sans mesure)
