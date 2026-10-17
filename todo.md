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


# Mise en prod

### Bloquants
- Secrets: rotation du mot de passe SMTP (déjà exposé), `SECRET_KEY` long et aléatoire, vrai mot de passe admin (à changer depuis le profil si la DB existe déjà, `ADMIN_PASSWORD` n'est lu qu'à la création du compte)
- Caddyfile: domaine public + TLS (retirer `auto_https off`, ouvrir le port 443 dans le compose)
- `EXTERNAL_URL` = URL publique dans le `.env` du serveur
- Dockerfile: mettre à jour / pinner l'image de base (vulnérabilités signalées)
- ~~Validation de la config au démarrage (`SECRET_KEY`, `EXTERNAL_URL`, admin)~~

### Très important
- Seed FFC: retirer le seed du démarrage (lancé par chacun des 4 workers), passer par `flask seed-races` en cronjob → couvre aussi "Refresh les calendriers à intervalles régulier"
- Backups SQLite: cronjob `sqlite3 .backup` quotidien + rotation + copie hors serveur, tester une restauration
- Reset de mot de passe par email (V2 #4): indispensable avec l'inscription en libre-service
- ~~Robustesse email: timeout SMTP, un échec d'envoi ne casse plus l'action (log + message à l'admin)~~
- ~~Création d'engagement en 500 si aucun responsable pour la catégorie~~
- ~~Lien d'inscription: token stocké en DB (partagé entre workers, survit aux redémarrages), régénérable depuis l'admin~~

### Important
- Healthcheck: route `/health` + `healthcheck` sur `app` dans le compose
- Tests: aucun pour l'instant. Priorité: règles d'engagement (J-5, catégorie, droits) et parser FFC
- Logs: niveau configurable, format exploitable
- ~~`restart: unless-stopped`~~
- ~~Séparation dev/prod: profils compose (`--profile dev` / `--profile prod`), override supprimé~~
- ~~`data/` exclu de l'image Docker~~
