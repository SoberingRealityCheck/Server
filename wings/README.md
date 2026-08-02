# Wings configuration

`config.example.yml` is a template for the node config Wings reads from
`/etc/pterodactyl/config.yml` (mounted from `data/wings/etc/`). The real
file holds node credentials and is gitignored.

## Setup

1. Register the node in Panel (Admin -> Nodes -> Create Node).
2. Copy `config.example.yml` to `data/wings/etc/config.yml`.
3. Fill in `uuid`, `token_id`, and `token` from Panel's node
   Configuration tab.
4. `docker compose up -d --force-recreate wings`

Panel's Configuration tab also offers an auto-deploy `wings configure`
command. It writes the same file, but sets `remote` to the public Panel
URL -- see below. If used, run it as
`docker compose run --rm wings configure --panel-url http://127.0.0.1
--token <token> --node <id>`, since Wings only exists here as a container.

## Two deliberate deviations from Panel's generated config

**`remote: http://127.0.0.1`** rather than the public HTTPS URL. Panel
sits behind a proxied Cloudflare record, which returns 403 to non-browser
clients on `/api` routes -- Wings fails at boot with `failed to retrieve
server configurations ... (HTTP/403)`. Wings runs with `network_mode:
host`, so the loopback reaches Panel's published port 80 directly.

**`docker.network.interfaces.v4`** pinned to `172.21.0.0/16`. Wings
defaults to `172.18.0.0/16`, which Docker also hands out early to compose
networks; the collision surfaces as `invalid pool request: Pool overlaps
with other one on this address space`. The compose default network is
pinned to `172.30.0.0/16` for the same reason.

## Verifying

Panel API reachability from the host, bypassing Cloudflare:

```
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: <panel-domain>" \
  -H "Authorization: Bearer <application-api-key>" \
  -H "Accept: application/vnd.pterodactyl.v1+json" \
  http://127.0.0.1/api/application/nodes
```

`200` locally alongside `403` through the public hostname confirms the
proxy is the problem, not the credentials.
