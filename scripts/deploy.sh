#!/bin/sh
# Pulls the image built by CI and restarts the stack. Rolls back if the new
# image does not become healthy.
# Run over SSH by .github/workflows/deploy.yml, or by hand on the server.
#
# Everything sits in functions on purpose: `git reset --hard` below can rewrite
# this very file, and the shell must not read the rest of it from disk after that.
set -eu

HEALTH_TIMEOUT=120

# The prod profile is explicit, so the script does not depend on COMPOSE_PROFILES
compose() {
    docker compose --profile prod "$@"
}

app_container() {
    compose ps --quiet app
}

health() {
    container=$(app_container)
    [ -n "$container" ] || { echo missing; return 0; }
    docker inspect --format '{{.State.Health.Status}}' "$container" 2>/dev/null || echo missing
}

wait_healthy() {
    waited=0
    while [ "$waited" -lt "$HEALTH_TIMEOUT" ]; do
        case "$(health)" in
            healthy) return 0 ;;
            unhealthy) return 1 ;;
        esac
        sleep 2
        waited=$((waited + 2))
    done
    return 1
}

# `up -d` does not restart Caddy when only its Caddyfile changed: reload it.
# Caddy may still be starting if `up -d` just recreated it, hence the retries.
# An invalid Caddyfile is refused and the running config is kept.
reload_caddy() {
    tries=0
    until compose exec -T server caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile; do
        tries=$((tries + 1))
        if [ "$tries" -ge 5 ]; then
            echo "Caddy refused the new Caddyfile, it keeps running the previous config" >&2
            return 1
        fi
        sleep 3
    done
}

main() {
    cd "$(dirname "$0")/.."

    # Config too, not just code: docker-compose.yaml, deploy/ (Caddyfile, fail2ban)
    git fetch --quiet origin main
    git reset --hard --quiet origin/main

    image=$(compose config --format json \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["services"]["app"]["image"])')
    # Image id of the running container, to roll back to if the new one fails
    previous=$(app_container | xargs -r docker inspect --format '{{.Image}}')

    compose pull --quiet app
    compose up -d

    if wait_healthy; then
        reload_caddy
        docker image prune -f >/dev/null
        echo "deployed $(git rev-parse --short HEAD) from $image"
        return 0
    fi

    echo "app did not become healthy, rolling back" >&2
    compose logs --tail 50 --no-color app >&2
    if [ -n "$previous" ]; then
        docker tag "$previous" "$image"
        compose up -d app
        wait_healthy && echo "rolled back to the previous image" >&2
    fi
    return 1
}

main "$@"
