# EngagementCourse

Application pour faciliter les demanded d'engagement aux courses FFC a destination de club cyclistes.

## Configuration

Copier `.env.example` en `.env` et le compléter. `SECRET_KEY` et `EXTERNAL_URL` sont obligatoires, ainsi que `ADMIN_EMAIL` / `ADMIN_PASSWORD` au premier démarrage (création du compte admin). Les emails ne sont envoyés que si le SMTP est configuré.

## Lancer

```bash
docker compose --profile dev up --build       # dev: serveur Flask debug sur http://localhost:8000
docker compose --profile prod up -d --build   # prod: gunicorn + Caddy (HTTPS), voir DEPLOY.md
```

En production, le déploiement est automatique : un push sur `main` lance les tests, construit l'image et la déploie sur le serveur (voir DEPLOY.md).

Rafraîchir les courses depuis le calendrier FFC :

```bash
docker compose exec app flask seed-races
```

Envoyer les récaps hebdomadaires des admins dont l'heure est passée (à lancer toutes les heures, voir DEPLOY.md) :

```bash
docker compose exec app flask send-admin-recaps
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```
