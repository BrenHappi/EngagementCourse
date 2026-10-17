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
~~4. Reset de mot de passe / envoyer un lien de réinitialisation de mot de passe~~

### V3
~~1. API Google map et calcul distance des courses depuis pos actuelle~~
~~2. Système de notification~~
3. Synchroniser avec google calendar
4. Ajout d'équipiers favoris pour savoir où on va

# Mise en prod

### Bloquants
- Secrets: rotation du mot de passe SMTP (déjà exposé), `SECRET_KEY` long et aléatoire, vrai mot de passe admin (à changer depuis le profil si la DB existe déjà, `ADMIN_PASSWORD` n'est lu qu'à la création du compte)
- Déployer la pré-prod en suivant `DEPLOY.md`, puis passer sur un vrai domaine pour la prod
- ~~Caddyfile: HTTPS automatique sur `DOMAIN`, ports 443, certificats persistés~~
- ~~Cookies `Secure` en HTTPS, ProxyFix derrière Caddy, workers configurables (`WEB_CONCURRENCY`)~~
- ~~Dockerfile: image de base pinnée (`python:3.12.15-slim-trixie` + digest)~~
- ~~Validation de la config au démarrage (`SECRET_KEY`, `EXTERNAL_URL`, admin)~~

### Très important
- Seed FFC: installer le cronjob documenté dans `DEPLOY.md` (`flask seed-races`) pour rafraîchir les courses → couvre "Refresh les calendriers à intervalles régulier" (au boot le seed ne tourne plus qu'une fois grâce à `gunicorn --preload`, et seulement si la DB est vide)
- Backups SQLite: installer le cronjob `scripts/backup_db.sh` (quotidien, 14 jours), prévoir la copie hors serveur et tester une restauration
- ~~Reset de mot de passe par email (lien signé, valable 1h, usage unique)~~
- ~~Démarrage gunicorn: 4 workers créaient l'admin en parallèle sur DB vide → crash au premier boot (corrigé par `--preload`)~~
- ~~Robustesse email: timeout SMTP, un échec d'envoi ne casse plus l'action (log + message à l'admin)~~
- ~~Création d'engagement en 500 si aucun responsable pour la catégorie~~
- ~~Lien d'inscription: token stocké en DB (partagé entre workers, survit aux redémarrages), régénérable depuis l'admin~~

### Important
- Logs: format structuré / centralisation si besoin une fois en prod
- Tests: étendre au calendrier (filtres), au profil et à l'admin utilisateurs
- ~~Healthcheck: route `/health` + `healthcheck` compose, Caddy attend que l'app soit healthy~~
- ~~Tests: suite pytest (config, inscription, engagements, reset mot de passe, parser FFC)~~
- ~~Logs: niveau configurable via `LOG_LEVEL`~~
- ~~`restart: unless-stopped`~~
- ~~Séparation dev/prod: profils compose (`--profile dev` / `--profile prod`), override supprimé~~
- ~~`data/` exclu de l'image Docker~~
