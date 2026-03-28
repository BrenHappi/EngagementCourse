# Engagement Courses ASPTT

Objectif: permettre aux utilisateurs du club de s'enregistrer sur les courses du calendrier à venir. L'admin consultera la liste pour réaliser les inscriptions des joueurs à la mano

# Fonctionnalités

### Utilisateurs
**Calendrier**
- ~~Parser les courses du calendrier FFC~~
- ~~Afficher les courses pertinentes dans le calendrier~~
- ~~S'inscrire sur une course~~
- définir une limite de temps pour la demande d'engagement (5 jours)
- Filtrer les courses sur les inscrits
- Voir les participants du clubs
- fetch les détails de la course (heure, nb de tours, kms, ...)
- filtrer sur MES engagements

**Mon profil**
- Update ses infos perso (toutes ?)
- Changer son mot de passe
- Supprimer son compte ?

En +: visualiser les courses sur lesquelles on est inscrit ? (ajouter un filtre?)


### Administration
**Gestion des utilisateurs**
- ~~gérer les utilisateurs (créer, modifier, supprimer)~~
- Refresh les calendriers à intervalles régulier
- changement de mot de passe, envoyer un lien de réinitialisation de mot de passe ?

**Gestion des courses**
- ~~valider l'inscription d'un coureur à une course~~
- ~~visualiser toutes les inscriptions à faire~~

# Déploiement
- Caddy ou Nginx en frontal
- gunicorn pour servir l’app Flask
- **!backup de la DB!**

# Improvements
### V1
- rendre home.html déclaratif, déplacer les règles de calcul dans Python, conserver le comportement actuel.

### V2
- Parser les dates, distance, nb de tour
- Filtrer les courses par distance
- parser davantage de catégories
- notifications admin
- photo de profil utilisateur
- responsable de catégorie

### Urgent à résoudre

# Pour la prochaine fois
