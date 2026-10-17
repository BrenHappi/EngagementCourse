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

L'image n'est pas construite sur le serveur mais récupérée depuis GHCR (voir l'étape 8). Le dépôt étant privé, l'image l'est aussi : il faut donc autoriser le serveur à la tirer, avec un [token classique](https://github.com/settings/tokens) dont le seul scope est `read:packages`.

```bash
docker login ghcr.io -u <utilisateur GitHub>   # mot de passe = le token
```

Les identifiants sont enregistrés dans `/root/.docker/config.json` et n'ont pas à être renouvelés, sauf si le token expire.

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
docker compose up -d
docker compose ps                 # app doit passer "healthy", puis server démarre
docker compose logs -f server     # obtention du certificat Let's Encrypt
```

Si l'image n'a jamais été publiée sur GHCR (aucun push sur `main` depuis la mise en place du pipeline), la construire une fois sur place : `docker compose up -d --build`.

Ouvrir `https://<nom de domaine>`, se connecter avec le compte admin, puis récupérer le lien d'inscription dans Administration → Utilisateurs.

Au premier démarrage, la base est créée et les courses FFC importées.

## 6. Tâches planifiées

`crontab -e` (en root), en remplaçant `<APP_DIR>` :

```cron
# Import des courses FFC, chaque nuit
30 2 * * * cd <APP_DIR> && docker compose exec -T app flask seed-races >> /var/log/engagement-seed.log 2>&1
# Sauvegarde SQLite (data/backups/, 14 jours conservés)
0 3 * * * <APP_DIR>/scripts/backup_db.sh >> /var/log/engagement-backup.log 2>&1
# Récap hebdomadaire des admins : chaque admin choisit jour et heure (heure de Paris) dans son profil
5 * * * * cd <APP_DIR> && docker compose exec -T app flask send-admin-recaps >> /var/log/engagement-recap.log 2>&1
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

## 8. Déploiement continu (GitHub Actions)

À chaque push sur `main`, le workflow `.github/workflows/deploy.yml` enchaîne trois jobs :

| Job | Rôle |
|---|---|
| `test` | `pytest` — si les tests échouent, rien n'est déployé |
| `build` | construit l'image et la pousse sur `ghcr.io/brenhappi/engagementcourse`, en tags `latest` et `<sha du commit>` |
| `deploy` | se connecte en SSH au serveur et y lance `scripts/deploy.sh` |

L'image est construite chez GitHub et non sur le serveur : le droplet n'a que 512 Mo de RAM, et le cache de layers rend le build bien plus rapide.

`scripts/deploy.sh` met à jour le dépôt (donc aussi `docker-compose.yaml`, le `Caddyfile` et `deploy/`), tire la nouvelle image, redémarre la stack, puis attend que le healthcheck passe. **Si l'app ne devient pas `healthy` en 2 minutes, le script remet l'image précédente** et le job échoue — GitHub envoie alors un email.

L'app redémarre pendant le déploiement : le site est indisponible quelques secondes.

La mise à jour du dépôt est un `git reset --hard origin/main` : **toute modification faite à la main sur le serveur dans un fichier suivi par Git est écrasée**. Le `.env` et `data/` ne sont pas concernés, ils ne sont pas suivis.

### Clé SSH dédiée

Cette clé n'appartient ni à la machine de dev ni au serveur : c'est celle du runner GitHub Actions, qui la reçoit par un secret du dépôt. La générer **sur la machine de dev**, pour que la moitié privée ne séjourne jamais sur le serveur auquel elle donne accès :

```bash
ssh-keygen -t ed25519 -f ~/.ssh/engagement-deploy -N '' -C 'github-actions'
```

La clé privée (`engagement-deploy`) part dans le secret `DEPLOY_SSH_KEY`, la publique (`engagement-deploy.pub`) dans l'`authorized_keys` du serveur.

Sur le serveur, autoriser la clé publique **pour cette seule commande** : `command=` force l'exécution du script quoi que demande le client, et `restrict` coupe le forwarding et le pty. Même si la clé fuite, elle ne permet que de déclencher un déploiement.

```bash
# en root, sur le serveur, en remplaçant <APP_DIR> et la clé publique
printf 'restrict,command="<APP_DIR>/scripts/deploy.sh" %s\n' \
  'ssh-ed25519 AAAA... github-actions' >> /root/.ssh/authorized_keys
```

`<APP_DIR>` doit être un **chemin absolu** : sshd n'étend ni `~` ni les variables dans un `command=`.

Ce mode de déploiement se connecte en root, donc `sshd -T | grep permitrootlogin` ne doit pas répondre `no`. La valeur `forced-commands-only` suffit et reste la plus restrictive : elle autorise exactement les clés porteuses d'un `command=`, donc celle-ci et aucune autre.

### Secrets du dépôt

Dans GitHub → Settings → Secrets and variables → Actions :

| Secret | Valeur |
|---|---|
| `DEPLOY_HOST` | IP du serveur |
| `DEPLOY_SSH_KEY` | contenu de `~/.ssh/engagement-deploy` (la clé **privée**) |
| `DEPLOY_KNOWN_HOSTS` | sortie de `ssh-keyscan <IP>` |

### Ordre de la première mise en place

La commande forcée pointe vers `scripts/deploy.sh`, qui n'arrive sur le serveur que par `git pull`. Il faut donc l'y amener avant d'installer la clé :

1. Pousser le commit sur `main`. Les jobs `test` et `build` passent, `deploy` échoue — c'est attendu, les secrets et le script manquent encore.
2. Sur le serveur : `cd <APP_DIR> && git pull`, puis le `docker login ghcr.io` de l'étape 3 s'il n'a pas été fait.
3. Installer la clé publique dans `authorized_keys` (ci-dessus), maintenant que le chemin du script est valide.
4. Ajouter les trois secrets du dépôt.
5. Relancer le workflow : onglet **Actions** → `deploy` → *Run workflow*. Tout doit être vert.

Vérification depuis la machine de dev, une fois ces étapes faites : `ssh -i ~/.ssh/engagement-deploy root@<IP>` doit lancer le déploiement, et refuser toute autre commande.

## Mettre à jour

Rien à faire : pousser sur `main` suffit. Un déploiement peut aussi être relancé sans commit depuis l'onglet **Actions** du dépôt → `deploy` → *Run workflow*.

À la main sur le serveur, en cas de besoin :

```bash
cd <APP_DIR>
./scripts/deploy.sh
# si deploy/fail2ban a changé : recopier les fichiers, puis sudo systemctl reload fail2ban
```

### Revenir à une version précédente

Chaque commit déployé laisse un tag `<sha>` sur GHCR :

```bash
cd <APP_DIR>
echo 'APP_TAG=<sha du commit>' >> .env   # ou modifier la ligne existante
docker compose pull app && docker compose up -d
```

Tant que cette ligne est dans le `.env`, **les déploiements automatiques restent bloqués sur ce tag**. La retirer pour repasser sur `latest`.

## Changer de nom de domaine

1. Faire pointer le nouveau domaine (enregistrement DNS `A`) vers l'IP du serveur.
2. Mettre à jour `DOMAIN` et `EXTERNAL_URL` dans `.env`.
3. Lancer `docker compose up -d`. Caddy obtient le nouveau certificat tout seul.
4. Régénérer le lien d'inscription dans l'admin, puisque l'ancien pointe vers l'ancien domaine.

## Dépannage

- **Pas de certificat :** vérifier que les ports 80 et 443 sont ouverts, puis regarder `docker compose logs server`. Avec sslip.io, les quotas Let's Encrypt sont partagés entre tous ses utilisateurs : en cas d'erreur `rateLimited`, réessayer plus tard.
- **L'app ne démarre pas :** lancer `docker compose logs app`. Une variable obligatoire manquante est indiquée explicitement.
