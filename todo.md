# Engagement Courses ASPTT

Objectif: permettre aux utilisateurs du club de s'enregistrer sur les courses du calendrier à venir. L'admin consultera la liste pour réaliser les inscriptions des joueurs à la mano

# Fonctionnalités

### Utilisateurs
**Calendrier**
- ~~Parser les courses du calendrier FFC~~
- ~~Afficher les courses pertinentes dans le calendrier~~
- ~~S'inscrire sur une course~~
- ~~définir une limite de temps pour la demande d'engagement (5 jours)~~
- ajouter une course manuellement
~~- pagination courses / découpage semaine, 1 mois, 3 mois~~


**Mon profil**
~~- Update ses infos perso (toutes ?)~~
~~- Changer son mot de passe~~
~~- Supprimer son compte ?~~

~~En +: visualiser les courses sur lesquelles on est inscrit ? (ajouter un filtre?)~~


### Administration
**Gestion des utilisateurs**
- ~~gérer les utilisateurs (créer, modifier, supprimer)~~
- Refresh les calendriers à intervalles régulier
~~- responsable de catégorie~~

**Gestion des courses**
- ~~valider l'inscription d'un coureur à une course~~
- ~~visualiser toutes les inscriptions à faire~~
~~- responsable de catégorie~~
- supprimer une course

# Déploiement
- Caddy ou Nginx en frontal
- gunicorn pour servir l’app Flask
- **!backup de la DB!**

# Improvements
### V1
- rendre home.html déclaratif, déplacer les règles de calcul dans Python, conserver le comportement actuel.

### V2
~~1. Profil utilisateur~~
2. Parser le détail des courses
~~3. Add filters: Filtrer les courses sur les inscrits, filtrer sur mes courses~~
4. Reset de mot de passe / envoyer un lien de réinitialisation de mot de passe

### V3
~~1. API Google map et calcul distance des courses depuis pos actuelle~~
~~2. Système de notification~~
3. Synchroniser avec google calendar
4. Ajout d'équipiers favoris pour savoir où on va

Le système de filtre actuel n'est pas très performant et pas très pratique. à la place:
- faire une vue mois par mois
<!-- - filtre par distance à notre domicile/temps de route -->
- affichage beaucoup plus compact, quasi sous forme de tableau pour voir toute les courses 


# Bloquants

Secrets exposés/fragiles:
docker-compose.yaml lit bien les variables, mais .env contient encore des credentials réels (SMTP, admin, secret key). Rotation immédiate des secrets déjà exposés auparavant, surtout SMTP.
ADMIN_PASSWORD=admin dans .env est inacceptable en prod.
Reverse proxy non prod:
Caddyfile est limité à localhost/127.0.0.1 et auto_https off. Pour prod il faut un domaine public + TLS activé.
URL externe non prod:
EXTERNAL_URL=http://localhost dans .env. En prod, URL réelle obligatoire pour liens email corrects.
Image avec vulnérabilités:
scan signalé sur Dockerfile (base image). Il faut mettre à jour/pinner une image corrigée.


# Très important

Robustesse envoi email:
mail.py n’a pas de timeout ni gestion d’erreurs SMTP. Un échec SMTP ne doit pas casser le flux principal.
Démarrage applicatif avec effets de bord:
app.py seed au startup. En prod, éviter les jobs réseau au boot; passer en job planifié/commande dédiée.
Sauvegardes:
DB SQLite montée sur volume dans docker-compose.yaml, mais pas de stratégie de backup/restauration automatisée.


# Important

Observabilité minimale:

Logs applicatifs structurés, niveau configurable, corrélation requête, rotation/centralisation.
Santé des services:
Ajouter healthcheck et politique de redémarrage (restart: unless-stopped) dans docker-compose.yaml.
Séparation envs:
Garder docker-compose.override.yaml pour dev, et un fichier compose prod dédié ou pipeline explicite pour éviter les erreurs de lancement.