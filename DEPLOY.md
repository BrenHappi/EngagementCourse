# Déploiement

L'application tourne sur n'importe quel serveur Linux avec Docker. Caddy est en frontal avec le HTTPS automatique, et la base SQLite est stockée dans `data/`.

Dans ce guide, `<IP>` désigne l'IP publique du serveur (l'exemple utilisé est `203.0.113.10`), `<REPO_URL>` l'URL du dépôt Git, et `<APP_DIR>` le dossier d'installation (par exemple `/opt/engagement-course`).

## 1. Serveur

- Linux récent (par exemple Ubuntu LTS), accessible en SSH par clé.
- **512 Mo de RAM minimum**, avec de la swap (voir l'étape 3). 1 Go est plus confortable.
- 10 Go de disque suffisent.

## 2. Pare-feu

N'ouvrir que ces ports en entrée :

| Service | Port |
|---|---|
| SSH | 22 |
| HTTP | 80 (nécessaire pour obtenir le certificat) |
| HTTPS | 443 TCP + UDP |

Utiliser le pare-feu de l'hébergeur plutôt que `ufw` : Docker contourne les règles `ufw` pour les ports qu'il publie.

## 3. Installer Docker et récupérer le code

```bash
# Swap de 1 Go : évite que le build de l'image manque de mémoire sur un petit serveur
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

curl -fsSL https://get.docker.com | sh

git clone <REPO_URL> <APP_DIR>
cd <APP_DIR>
```

Si le dépôt est privé, utiliser une deploy key en lecture seule (`ssh-keygen -t ed25519`, puis ajouter la clé publique dans les paramètres du dépôt).

## 4. Configurer le `.env`

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # -> SECRET_KEY
```

```env
COMPOSE_PROFILES=prod
DOMAIN=<nom de domaine>
EXTERNAL_URL=https://<nom de domaine>
SECRET_KEY=<valeur générée>
ADMIN_EMAIL=<email de l'administrateur>
ADMIN_PASSWORD=<mot de passe fort>
SMTP_HOSTNAME=...
SMTP_USERNAME=...
SMTP_PASSWORD=...
```

- `DOMAIN` est le nom servi par Caddy, sans `https://`.
- `EXTERNAL_URL` est l'URL utilisée dans les emails et le lien d'inscription.
- `COMPOSE_PROFILES=prod` permet de lancer la prod avec `docker compose up -d`, sans `--profile`. Ne mettre cette ligne que dans le `.env` du serveur.

**Sans nom de domaine**, utiliser [sslip.io](https://sslip.io) : `203-0-113-10.sslip.io` pointe automatiquement vers `203.0.113.10`, et Caddy peut obtenir un vrai certificat pour ce nom. Il suffit donc de mettre `DOMAIN=<IP avec des tirets>.sslip.io`.

## 5. Lancer

```bash
docker compose up -d --build
docker compose ps                 # app doit passer "healthy", puis server démarre
docker compose logs -f server     # obtention du certificat Let's Encrypt
```

Ouvrir `https://<nom de domaine>`, se connecter avec le compte admin, puis récupérer le lien d'inscription dans Administration → Utilisateurs.

Au premier démarrage, la base est créée et les courses FFC importées.

## 6. Tâches planifiées

`crontab -e` (en root), en remplaçant `<APP_DIR>` :

```cron
# Import des courses FFC, chaque nuit
30 2 * * * cd <APP_DIR> && docker compose exec -T app flask seed-races >> /var/log/engagement-seed.log 2>&1
# Sauvegarde SQLite (data/backups/, 14 jours conservés)
0 3 * * * <APP_DIR>/scripts/backup_db.sh >> /var/log/engagement-backup.log 2>&1
```

Les sauvegardes restent sur le serveur. Pour en avoir une copie ailleurs, les rapatrier régulièrement :
`scp root@<IP>:<APP_DIR>/data/backups/sqlite-*.db ./backups/`

Restaurer une sauvegarde :

```bash
docker compose stop app
cp data/backups/sqlite-AAAAMMJJ.db data/sqlite.db
docker compose start app
```

## 7. fail2ban

Caddy écrit ses logs d'accès dans `/var/log/caddy/access.log` sur l'hôte. Deux prisons s'appuient dessus :

| Prison | Déclencheur | Bannissement |
|---|---|---|
| `caddy-login` | 5 échecs de connexion en 10 min | 1 h |
| `caddy-scan` | 3 requêtes de scanner en 10 min (`.php`, `.env`, `/.git`, `wp-`…) | 1 jour |

Les ports publiés par Docker ne passent pas par la chaîne `INPUT`. Les bannissements sont donc ajoutés dans la chaîne `DOCKER-USER`, et fail2ban doit démarrer après Docker.

```bash
sudo apt install fail2ban
sudo cp deploy/fail2ban/filter.d/*.conf /etc/fail2ban/filter.d/
sudo cp deploy/fail2ban/jail.d/*.conf /etc/fail2ban/jail.d/

sudo mkdir -p /etc/systemd/system/fail2ban.service.d
printf '[Unit]\nAfter=docker.service\nWants=docker.service\n' | sudo tee /etc/systemd/system/fail2ban.service.d/docker.conf
sudo systemctl daemon-reload
sudo systemctl restart fail2ban

sudo fail2ban-client status caddy-login
sudo fail2ban-client status caddy-scan
```

Commandes utiles :

```bash
sudo fail2ban-regex /var/log/caddy/access.log /etc/fail2ban/filter.d/caddy-scan.conf   # tester un filtre
sudo fail2ban-client set caddy-scan unbanip <IP>                                     # débannir une IP
```

## Mettre à jour

```bash
cd <APP_DIR>
git pull
docker compose up -d --build
# si deploy/fail2ban a changé : recopier les fichiers, puis sudo systemctl reload fail2ban
docker image prune -f   # libère l'espace des anciennes images
```

## Changer de nom de domaine

1. Faire pointer le nouveau domaine (enregistrement DNS `A`) vers l'IP du serveur.
2. Mettre à jour `DOMAIN` et `EXTERNAL_URL` dans `.env`.
3. Lancer `docker compose up -d`. Caddy obtient le nouveau certificat tout seul.
4. Régénérer le lien d'inscription dans l'admin, puisque l'ancien pointe vers l'ancien domaine.

## Dépannage

- **Pas de certificat :** vérifier que les ports 80 et 443 sont ouverts, puis regarder `docker compose logs server`. Avec sslip.io, les quotas Let's Encrypt sont partagés entre tous ses utilisateurs : en cas d'erreur `rateLimited`, réessayer plus tard.
- **L'app ne démarre pas :** lancer `docker compose logs app`. Une variable obligatoire manquante est indiquée explicitement.
