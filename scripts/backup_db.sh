#!/bin/sh
# Daily SQLite backup into data/backups/, keeps the last 14 days.
# Cron (as root): 0 3 * * * /opt/EngagementCourse/scripts/backup_db.sh >> /var/log/engagement-backup.log 2>&1
set -eu
cd "$(dirname "$0")/.."

# sqlite3 backup API: consistent copy even while the app is writing
docker compose exec -T app python3 -c "
import datetime, pathlib, sqlite3
backups = pathlib.Path('data/backups')
backups.mkdir(exist_ok=True)
target = backups / f'sqlite-{datetime.date.today():%Y%m%d}.db'
source = sqlite3.connect('data/sqlite.db')
copy = sqlite3.connect(target)
source.backup(copy)
copy.close()
source.close()
print(f'{datetime.datetime.now():%Y-%m-%d %H:%M} backup written to {target}')
"
find data/backups -name 'sqlite-*.db' -mtime +14 -delete
