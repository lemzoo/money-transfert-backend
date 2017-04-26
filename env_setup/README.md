# L'environement de développement

## Why
Pour simplifier, maintenir et unifier les moyens d'installer un environnement.

## How
Le back sera installé et configurer dans une machine virtuelle (guest) sous vagrant.
Les fichiers du back sont accessibles par sa propre machine (host) par un dossier partagé avec la machine virtuelle vagrant.
Le front sera installé et configuré sur sa propre machine.

# Installation du Back

## Pré-requis:

Avoir vagrant pour le back :

- <https://www.vagrantup.com/downloads.html>

Et VirtualBox :

- <https://www.virtualbox.org/wiki/Downloads>

Putty sous windows :

- <http://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html>

Et bien évidement git ...

### Configuration de Git sur Windows

Sur Windows, il est important d'avoir des fins de ligne Unix (`LF`) et pas
Windows (`CRLF`) dans le fichier `provision.sh`, sinon la VM ne pourra pas
l'exécuter.


Cloner le dépôt back :

Pour ça, avant de git clone le projet back, configurer votre git :

```
$ git config --global core.autocrlf input
```

## Installation Back


Cloner le répo back (attention, pour le `git clone` sous Windows voir la conf préalable ci-dessus) :

    $ git clone git@github.com:Scille/sief-back.git

Créer et provisionner la VM :

    $ cd sief-back/env_setup
    $ vagrant up

- Aller prendre un café
- Note : Lorsque cela est terminé, python, solr, RabbitMQ et mongodb sont installé en tant que daemon. La base est _populate_. Et l'environement virtuel (virtualenv) est configuré dans le terminal par défaut à chaque session.

## Test post-installation

```
$ vagrant ssh
$ cd /vagrant/sief-back/
$ ./runtests.py tests
```

# Utilisation avec le Front

[Documentation pour installer le front](https://github.com/Scille/sief-front/blob/develop/README.md)

Attention : utiliser le front sur la bonne branche, celle qui correspond à votre branche back.

Ca marche tout seul en localhost sur le HOST, à condition de démarrer le back dans le GUEST comme suit :

    $ ./manage.py runserver --host=0.0.0.0

Ensuite, installer et démarrer le front depuis le host (voir README.md du front), et connectez-vous au front sur :

- <http://localhost:9000>

# Réferences

## SolR

- <https://cwiki.apache.org/confluence/display/solr/Installing+SolR>
- <https://cwiki.apache.org/confluence/display/solr/Taking+SolR+to+Production>

## Mongo

- <https://docs.mongodb.com/v3.0/tutorial/install-mongodb-on-debian/>

## virtualenv

- Ajout de la directive --always-copy pour la compatiblité vagrant/windows voir <https://github.com/gratipay/gratipay.com/issues/2327>

# Améliorations possibles

## SolR

Aujourd'hui, SolR est installé et configuré avec l'utilisateur `root` car on a
coincé sur les créations de cores avec l'utilisateur `vagrant`. Pour améliorer :

Créer un utilisateur `solr`,
Créer les cores en tant que l'utilisateur `solr` (`su solr -c '/opt/solr/bin/solr -c sief`).
