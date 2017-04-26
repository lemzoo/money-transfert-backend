## Money - Transfert backend

Ce projet comme son nom l'intitule, il s'agit d'un système de transfert d'argent. Ces types de systèmes sont très énormes et sont souvent complexe. 

## Contexte

Le contexte est hyper simple : J'ai deux oncles qui sont en France et un oncle en Mauritanie et qui s'occupe de faire du transfert d'argent en Afrique et plus particulièrement Mauritanie. 
Ici en France, mes oncles recoivent des appels de leurs clients souhaitant envoyé de l'argent à des personnes qui sont en Afrique. 
Les clients communiquent le montant qu'ils souhaitent envoyer en euros ou en ouguiya et ces derniers s'occupent de faire la conversion en se rensignant sur le taux d'échange en cours. Ensuite, mes oncles récupèrent les informations d'identifications des clients et des personnes qui doivent récupérer le montant en Mauritanie. 

A la fin de chaque journée, mes deux oncles se synchronisent sur le total de l'argent envoyé. Eensuite, un mail est redigé à destination de mon oncle qui se trouvent en Mauritanie dans lequel une liste des personnes qui recoivent cette argent est décrites. Cette liste contient le nom, prénom de la personne, son numéro de téléphone, le montant du transfert et le nom de la personne qui lui à envoyé l'argent. Ces informations sont obligatoires pour sécuriser la remise du montant au niveau de la Mauritanie. 

Ensuite mes deux oncles ici en France s'occupe de récupérer le montant transférés en euros et font le compte du business. Lorsqu'il réunisse la somme, ils enverront au correspondant qui est en Mauritanie pour convertir ce dernier en monnaie local. Et ils se basent sur ce montant pour savoir qu'il leur restent de l'argent et donc ils peuvent faire le transfert en cas de besoin d'un client. 

## La problèmatique

Aujourd'hui, ils ont une bonne clientèle dont nombreuse sont des fidèles. Au début de chaque mois, il y'a beaucoup de client qui envoie de manière régulière l'argent à leurs familles en Mauritanie. Et à la récupération, les destinataires se pleignent beaucoup du manque de réactivité de mon oncle qui leur remet la somme transférée. Parfois mêmes, les clients peuvent rester au bout d'une semaine avant de recevoir leurs argents. La réponse que fournit souvent mon oncle en Mauritanie c'est qu'il n'a pas recu le mail contenant les noms des personnes alors que ce mail là a bien été envoyé au moment il le fallait. Et des coups de files de la France en Mauritanie se multiplie. Les clients appellent mes oncles pour dire que les destinataires n'ont pas recus leurs sommes. Et mes deux oncles se synchronisent pour appeler l'oncle qui est en Mauritanie. 

## Objectif

Développer un système d'information servant de support pour un groupe (Mes deux oncles ici en France et mon concle en Mauritanie) de travailler dans un bon cadre afin de synchroniser tout le monde via le SI. Ce type de business est nombreux ici en France. Donc, ça serait très géniale de pouvoir le vendre à ces groupes de personnes afin de leurs faciliter la vie. 

## Liste des fonctionnalités

### Pouvoir se connecter au portail Money-Transfert de manière sécurisé.
> Il existera trois mode de connexion à l'application : 
	1 . Le mode de connexion par défaut sera une authentification basic avec un login et mot de passe de connexion.
	2. L'authentification par token avec une durée de validité de 24 heures. 
	3. Une authentification de type Auth2. Auth2 est un mode d'authentification permettant de se connecter à une application partenaire à partir des informations de connexion d'une autre application. Exemple : Se connecter sur Github en utilisant son compte Google. 

### Définir son équipe de travail. 
> Il s'agira d'une interface d'administration qui permet à l'utilisateur disposant le Role ADMINISTRATEUR` de configurer son équipe de travail. Cette interface lui permettra également de consulter l'historique des actions de son équipe. 

### Définir une interface pour la saisie du demande de transfert
> Le but étant d'avoir une interface sur lequel l'utilisateur pourra saisir la demande de transfert composée du nom du client, le montant du transfert, le destinataire, le taux de conversion, la date de remise du montant avec deux status binaire montant remis en euros et montant remis en ouguiya.

### Définir une interface sur lequel l'utilisateur pourra consulter la liste des demandes de transfert par date d'envoie. 
> C'est une liste de transfert réunissant un résumé des demandes de transfert du jour avec les informations sur le nom du client et le montant en euros et en ouguiya. 
Cette liste est affichée par rôles. Si c'est un utilisateur disposant du rôle `SENDER`, il ne verra sur la liste que le nom du client, montant en euros et le status `argent remis`. Un utilisateur ayant comme rôle `RECEIVER` verra une liste de destinataire dans lequel il y'aura le nom du destinataire, le montant en ouguiya et le status `remis au destinataire`. 

### Définir une interface de modification d'une demande de transfert
> L'interface servant de présenter la demande de transfert doit également servir d'interface de mise à jour de la demande : D'un coté le `SENDER` peut mettre à jour la demande sauf le status `argent remis au destinataire`. De l'autre coté le`RECEIVER`ne pourra mettre à jour que le champ `argent remis au destinataire`et le champ `argent du client remis` n'est pas affiché à ce dernier. 

### Définir une recherche sur l'ensemble des champs de la demande de transfert
> Les utilisateurs pourront utiliser une liste de filtre qui leurs permettent de chercher des informations sur la demande.
1. Les différents champs de recherche
	- Nom du client
	- Nom du destinataire
	- Montant en euros
	- Date de transfert
	- Date de remise
	- status de la remise d'argent par le client
	- status de la remise d'argent au destinataire
2. Les autres champs seront à définir dans une nouvelle version 
	- Champs à définir

### Fournir une interface d'administration du business qui contien la liste des utilisateurs ayant fait le transfert et la totale de la somme envoyé par jour. 
> Cette interface doit également contenir le montant total des `SENDER` (avoir par sender).
Il doit également présenter la différence de leur montant qui leur reste à consommé. 
Il doit également présenter le montant en ouguiya disponible au niveau du `RECEIVER`

### Envoyer un mail récapitulatif des demandes de transfert
> Un mail quotidien est envoyé au `RECEIVER` et les `SENDER` en copie de mail contenant une recpaitulatif de l'ensemble des demandes de transfert. 
 Le but étant qu'à chaque nouvelle demande de saisie d'un transfert d'argent doit générer un évenement qui enverra un message au `broker` pour ensuite gérer l'envoie de mail contenant le recapitulatif de la liste des demandes de transfert à la fin de la journée. Ce message broker sera basé sur `RabbitMQ`. Un `CRON` sera chargé de générer un événement qui déclenchera un worker s'occupant de lister l'ensemble des messages et d'envoyer le mail aux destinataires.

### Mettre à jour e status `argent remis au destinataire` par le `RECEIVER`.
> Lorsque le `RECEIVER` met à jour le status de la demande de transfert, un événement est également généré pour être envoyé dans le message broker. Un `CRON`également génère un évenement pour ensuite traiter les demandes de transfert mis à jour. 
Une fois que ces demandes de transfert sont mis jour avec un status `argent remis au destinataire` sont archivés et ne seront consultables que sur la liste des demandes archivés. 

### Consulter la liste des demandes de transfert par status 
> `argent cient remis` pour les `SENDER`

> `argent remis au destinataire` pour les `RECEIVER`. 

## Spécification de l'application

Un backend avec une haute disponibilité concu avec API RESTfull.
Un frontend concu en Angular JS en étant design responsive. 
Une application android pour la présentation des données sur un support mobile.
Une application ios pour la présentation des données sur un support mobile d'apple.

## Les différents rôles sur l'application 

> `ROOT` : comme indique son nom, c'est l'administrateur.

> `ADMINISTRATEUR` : comme indique son nom, c'est l'administrateur du business.

> `SENDER` : C'est le rôle d'un des utilisateurs envoyant l'argent depuis la France.

> `RECEIVER`: C'est le rôle de la personne qui s'occupe de remettre le transfert aux destinataires. 


## Technologies utilisés

- [Flask ] (http://flask.pocoo.org/) as the framework in Python 3.6
- [MongoDB] (https://www.mongodb.com/fr) as the database.
- [SolR] (http://lucene.apache.org/solr/) as a search plateform.
- [RabbitMQ] (https://www.rabbitmq.com/) as the message broker
- [Angular 1](https://angular.io/) as the framework, with [Coffeescript](http://coffeescript.org/).
- [pytest] (https://docs.pytest.org) as the framework for test.
- [Karma](https://karma-runner.github.io) as unit tests runner.
- [Protractor](http://www.protractortest.org/) as end-to-end tests runner.
- [Cucumber](https://cucumber.io/) as [BDD](https://en.wikipedia.org/wiki/Behavior-driven_development) framework for end-to-end tests
- [Angular CLI](https://github.com/angular/angular-cli) as CLI tool to generate, serve and build files

## Get Started

Install [node and grunt](https://nodejs.org/en/download/).

> Note: the project works with node v7.5.0 and npm v4.2.0. If you have troubles with installation or commands, check these versions.

Install dependencies with `npm install`.

If not already done, install `angular-cli` globally with `npm install -g @angular/cli`.