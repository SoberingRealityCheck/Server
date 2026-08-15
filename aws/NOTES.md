# AWS

## Instance

| Setting | Value |
|---|---|
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | t3.large (2 vCPU / 8 GB) |
| Root volume | 25 GB gp3 |
| VPC/subnet | default |

**Sizing changed with the modpack.** The original t3.medium (4 GB) was
sized for a vanilla server plus the Pterodactyl stack. The current Fabric
profile is the binding constraint instead: Terralith and Tectonic hold
far more biome and worldgen state than vanilla, and Distant Horizons
generates and stores LOD data server-side. Retiring Pterodactyl freed
roughly 2 GB of overhead, but not enough to offset that.

Budget the JVM heap (`MC_MEMORY`) at about 1 GB below total RAM -- the
JVM needs metaspace, GC structures, and off-heap buffers beyond the
heap, and the kernel needs page cache for region file I/O.

| Instance | RAM | Workable heap | Verdict |
|---|---|---|---|
| t3.medium | 4 GB | 3G | Runs, but expect GC pauses under chunk generation |
| t3.large | 8 GB | 6G | Recommended for this modpack |

This has not been load-tested with players on. Start at t3.medium if you
want to confirm the pack works before paying for more; watch
`docker stats` and the server's tick time during first-time chunk
generation, which is the worst case.

Instance type can be changed later via stop/modify/start with brief
downtime. EBS volumes can grow live but not shrink in place, so avoid
over-provisioning storage up front.

x86_64 rather than Graviton/arm64: `itzg/minecraft-server` publishes
arm64 images, so arm64 is viable and cheaper -- but the mod jars pinned
in `pack.yaml` have not been checked for native components. Worth
testing if cost matters.

## Security group

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | restricted to admin IP(s) | management (or use SSM Session Manager instead -- no inbound rule needed) |
| Custom TCP | TCP | 25565 | 0.0.0.0/0 | Minecraft Java |

That is the whole list now. The Pterodactyl deployment additionally
needed 80/443 for the Panel, 8080 for the Wings daemon's WebSocket, and
2022 for its SFTP subsystem. None of those exist anymore: administration
is SSH plus `docker compose`, and file access is the filesystem.

RCON is enabled inside the container but its port is not published, so
it is reachable only via `docker compose exec`. Do not publish it --
RCON authenticates with a single shared password in cleartext.

## DNS

| Record | Type | Value | Proxy |
|---|---|---|---|
| `mc.<domain>` | A | instance IP | DNS only |
| `_minecraft._tcp.<subdomain>` | SRV | priority 0, weight 1, port 25565, target `mc.<domain>` | N/A (SRV can't be proxied) |

The A record must be DNS-only. Cloudflare only proxies TCP/UDP game
traffic through Spectrum, a paid feature; a proxied (orange-cloud)
record here will fail to connect. The SRV record is optional -- it lets
players connect without typing a port, and is Java Edition only.

The old `panel.<domain>` proxied record can be deleted along with the
panel.

### Historical note: Cloudflare proxying and APIs

The previous deployment hit a subtle failure worth remembering, because
it will recur with anything else placed behind an orange-cloud record: a
proxied hostname returns 403 to non-browser clients on `/api` routes
(Cloudflare bot protection), while the same URL works fine in a browser.
The tell is a 403 with no application JSON error body -- the block page
comes from Cloudflare, not the origin.

Fixes, if you ever put an HTTP service back here: point internal clients
at the loopback rather than the public hostname, and add a WAF skip rule
for `/api/*` for anything external.

Note also that in that setup TLS terminated at Cloudflare; the origin
served plain HTTP on 80 and nothing answered on 443. No HTTP service runs
on this host now.

## Elastic IP

If the instance is ever stopped and started, its public IP changes
unless an Elastic IP is attached -- and the DNS records above go stale
silently. Attach one, or expect to update DNS after any stop/start.
