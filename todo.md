# Engagement Courses ASPTT

Objectif: permettre aux utilisateurs du club de s'enregistrer sur les courses du calendrier à venir. L'admin consultera la liste pour réaliser les inscriptions des joueurs à la mano

# Fonctionnalités
### Utilisateurs
**Calendrier**
- ~~Parser les courses du calendrier FFC~~
- ~~Afficher les courses pertinentes dans le calendrier~~
- S'inscrire sur une course
- Voir les participants du clubs

**Mon profil**
- Update ses infos perso (toutes ?)
- Changer son mot de passe
- Supprimer son compte ?


### Administration
**Gestion des utilisateurs**
- ~~gérer les utilisateurs (créer, modifier, supprimer)~~
- Refresh les calendriers à intervalles régulier
- changement de mot de passe, envoyer un lien de réinitialisation de mot de passe ?

**Gestion des courses**
- valider l'inscription d'un coureur à une course
- visualiser toutes les inscriptions à faire
- marquer une inscription comme faite (et reverse le processus)

# Déploiement
- Caddy ou Nginx en frontal
- gunicorn pour servir l’app Flask
- **!backup de la DB!**

# Improvements
### V1
vide

### V2
- Parser les dates, distance, nb de tour
- Filtrer les courses par distance
- parser davantage de catégories
- notifications admin
- photo de profil utilisateur
- responsable de catégorie

### Urgent à résoudre

# Pour la prochaine fois
- inscription sur une course et visualisation des coureurs inscrits côté métier
- affichage des demande et validation des inscriptions