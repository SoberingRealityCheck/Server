# AWS

## Instance

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | t3.medium (2 vCPU / 4 GB) |
| Root volume | 25 GB gp3 |
| VPC/subnet | default |

Sized for a small vanilla Minecraft server (1-4 players) plus the
Panel/Wings/database/cache stack (~2 GB overhead). Instance type can be
changed later via stop/modify/start with brief downtime; EBS volumes can
be grown live but not shrunk in place, so avoid over-provisioning storage
up front.

x86_64 rather than Graviton/arm64: official Pterodactyl Panel and Wings
images are published for amd64 only.

## Security group

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | restricted to admin IP(s) | management (or use SSM Session Manager instead -- no inbound rule needed) |
| HTTP/HTTPS | TCP | 80, 443 | 0.0.0.0/0 | Panel |
| Custom TCP | TCP | 25565 | 0.0.0.0/0 | Minecraft Java |
| Custom TCP | TCP | 2022 | restricted to admin IP(s) | Wings SFTP |
| Custom TCP | TCP | 8080 | restricted to admin IP(s) | Wings daemon -- browser console/file manager connect here directly (WebSocket), not through Panel's backend |

Panel's PHP backend does talk to Wings over `localhost`, but that's not
the whole picture: the in-browser console and file manager open a
WebSocket straight from your browser to Wings, which needs real network
access to port 8080 -- restricted to admin IPs, same threat model as SSH
and SFTP, since this isn't player-facing.

## DNS

| Record | Type | Value | Proxy |
|---|---|---|---|
| `panel.<domain>` | A | instance IP | Proxied |
| `mc.<domain>` | A | instance IP | DNS only |
| `_minecraft._tcp.<subdomain>` | SRV | priority 0, weight 1, port 25565, target `mc.<domain>` | N/A (SRV can't be proxied) |

The Minecraft A record must be DNS-only -- Cloudflare only proxies
TCP/UDP game traffic through Spectrum, a paid feature. A proxied record
here will fail to connect. SRV record is optional (Java Edition only;
not supported by Bedrock clients).

### Proxied panel record and Pterodactyl's API

A proxied `panel.<domain>` record returns 403 to non-browser clients on
`/api` routes (Cloudflare bot protection), while the dashboard itself
works normally in a browser. Symptoms: Wings fails at boot with `failed
to retrieve server configurations ... (HTTP/403)`, and `wings configure`
reports invalid credentials -- both with valid tokens. The giveaway is a
403 carrying no Pterodactyl JSON error body, since the block page comes
from Cloudflare rather than Panel.

Two fixes, not mutually exclusive:

- Point Wings at Panel over the loopback (`remote: http://127.0.0.1`) --
  see `../wings/README.md`. Sufficient for Wings, and avoids the round
  trip out to Cloudflare for a service on the same host.
- Disable Bot Fight Mode, or add a WAF skip rule for `/api/*`. Needed
  regardless if anything outside the host calls the API.

Note also that TLS terminates at Cloudflare in this setup; Panel's nginx
serves plain HTTP on 80 and nothing answers on 443 at the origin.
