# Déploiement (pré-prod / prod)

Serveur cible : un droplet DigitalOcean, avec Docker, Caddy en frontal (HTTPS automatique) et SQLite sur un volume.

## 1. Créer le droplet

- Image **Ubuntu 24.04 LTS**, offre **Basic 512 Mo** (4 $/mois). Elle suffit pour le club, à condition d'ajouter de la swap (étape 3).
- Authentification : **clé SSH** (pas de mot de passe).
- Option recommandée : **Backups** DigitalOcean (instantané hebdomadaire de tout le serveur, +20 %).
- Noter l'IP publique, par exemple `164.90.12.34`.

## 2. Pare-feu

Dans DigitalOcean → Networking → **Firewalls**, créer un pare-feu attaché au droplet :

| Entrant | Port |
|---|---|
| SSH | 22 |
| HTTP | 80 (nécessaire pour obtenir le certificat) |
| HTTPS | 443 TCP + UDP |

Utiliser le pare-feu DigitalOcean plutôt que `ufw` : Docker contourne les règles `ufw` pour les ports qu'il publie.

## 3. Installer Docker et récupérer le code

```bash
ssh root@164.90.12.34

# 1 Go de swap : évite que le build de l'image manque de mémoire sur 512 Mo
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

curl -fsSL https://get.docker.com | sh

# Clé de déploiement en lecture seule : ssh-keygen -t ed25519, puis ajouter la clé publique
# dans GitHub → repo → Settings → Deploy keys
git clone git@github.com:BrenHappi/EngagementCourse.git /opt/EngagementCourse
cd /opt/EngagementCourse
```

## 4. Configurer le `.env`

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # -> SECRET_KEY
nano .env
```

Sans nom de domaine, utiliser **sslip.io** : `164-90-12-34.sslip.io` pointe automatiquement vers `164.90.12.34`.

```env
COMPOSE_PROFILES=prod
DOMAIN=164-90-12-34.sslip.io
EXTERNAL_URL=https://164-90-12-34.sslip.io
SECRET_KEY=<valeur générée>
ADMIN_EMAIL=<ton email>
ADMIN_PASSWORD=<mot de passe fort>
SMTP_...=<identifiants SMTP, mot de passe d'application régénéré>
```

`DOMAIN` est le nom servi par Caddy, sans `https://`. `EXTERNAL_URL` est l'URL utilisée dans les emails et le lien d'inscription. Avec `COMPOSE_PROFILES=prod`, `docker compose up -d` lance la prod sans `--profile`. Ne mettre cette ligne que dans le `.env` du serveur.

## 5. Lancer

```bash
docker compose up -d --build
docker compose ps                 # app doit passer "healthy", puis server démarre
docker compose logs -f server     # obtention du certificat Let's Encrypt
```

Ouvrir `https://164-90-12-34.sslip.io`, se connecter avec le compte admin, puis récupérer le lien d'inscription dans Administration → Utilisateurs.

Au premier démarrage, la base est créée et les courses FFC importées.

## 6. Tâches planifiées

`crontab -e` (en root) :

```cron
# Import des courses FFC, chaque nuit
30 2 * * * cd /opt/EngagementCourse && docker compose exec -T app flask seed-races >> /var/log/engagement-seed.log 2>&1
# Sauvegarde SQLite (data/backups/, 14 jours conservés)
0 3 * * * /opt/EngagementCourse/scripts/backup_db.sh >> /var/log/engagement-backup.log 2>&1
```

Les sauvegardes restent sur le serveur. Pour en avoir une copie ailleurs, les rapatrier de temps en temps :
`scp root@164.90.12.34:/opt/EngagementCourse/data/backups/sqlite-*.db ./backups/`

Restaurer une sauvegarde :

```bash
docker compose stop app
cp data/backups/sqlite-AAAAMMJJ.db data/sqlite.db
docker compose start app
```

## Mettre à jour

```bash
cd /opt/EngagementCourse
git pull
docker compose up -d --build
docker image prune -f   # libère l'espace des anciennes images (disque de 10 Go)
```

## Passer à un vrai domaine

1. Créer un enregistrement DNS `A` qui pointe vers l'IP du droplet.
2. Dans `.env`, mettre `DOMAIN=mon-domaine.fr` et `EXTERNAL_URL=https://mon-domaine.fr`.
3. Lancer `docker compose up -d`. Caddy obtient le nouveau certificat tout seul.
4. Régénérer le lien d'inscription dans l'admin, puisque l'ancien pointe vers sslip.io.

## Dépannage

- **Pas de certificat :** vérifier que les ports 80 et 443 sont ouverts dans le pare-feu, et regarder `docker compose logs server`. Avec sslip.io, les quotas Let's Encrypt sont partagés entre tous ses utilisateurs : en cas d'erreur `rateLimited`, réessayer plus tard.
- **L'app ne démarre pas :** lancer `docker compose logs app`. Une variable obligatoire manquante est indiquée explicitement.
