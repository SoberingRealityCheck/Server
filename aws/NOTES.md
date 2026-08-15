# AWS

Provisioning guide for the EC2 host this repo runs on, plus the
reference tables behind the choices.

Work top to bottom for a new instance. `bootstrap.sh` in this directory
automates steps 4-6; everything before that is console work that a
script cannot do for you.

---

## 1. Launch the instance

| Setting | Value |
|---|---|
| Region | `us-east-2` (match the existing setup) |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | **t3.large** (2 vCPU / 8 GB) |
| Root volume | 25 GB gp3 |
| VPC/subnet | default |
| Key pair | existing, or create one and save the `.pem` |

Do not reuse the old instance. It carries a Docker install whose
embedded DNS stopped resolving between containers, and a MariaDB volume
for a database nothing uses now. A fresh host costs one afternoon less
than diagnosing inherited state.

**Why t3.large.** The old t3.medium was sized for a vanilla server plus
the Pterodactyl stack. The Fabric modpack is the binding constraint
instead: Terralith and Tectonic hold far more worldgen state than
vanilla, and Distant Horizons generates and stores LOD data server-side.
Dropping Pterodactyl freed roughly 2 GB, but not enough to cover it.

| Instance | RAM | `MC_MEMORY` | Verdict |
|---|---|---|---|
| t3.medium | 4 GB | 3G | Runs; expect GC pauses during chunk generation |
| t3.large | 8 GB | 6G | Recommended for this modpack |

Budget the heap about 1 GB below total RAM. The JVM needs metaspace, GC
structures, and off-heap buffers beyond the heap, and the kernel needs
page cache for region-file I/O. `bootstrap.sh` sets `MC_MEMORY`
automatically based on what it finds.

Instance type can be changed later via stop/modify/start with brief
downtime. EBS volumes grow live but cannot shrink in place, so do not
over-provision storage up front.

x86_64 rather than Graviton/arm64: `itzg/minecraft-server` publishes
arm64 images, so arm64 is viable and cheaper, but the mod jars pinned in
`pack.yaml` have not been checked for native components. Worth testing
if cost matters.

## 2. Attach an Elastic IP

Allocate one and associate it with the instance.

Without it, stopping and starting the instance changes its public IP and
the DNS records below go stale silently -- the server simply stops being
reachable with nothing in any log to say why. An Elastic IP attached to
a running instance is free.

## 3. Security group

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | your admin IP(s) only | management |
| Custom TCP | TCP | 25565 | 0.0.0.0/0 | Minecraft Java |

That is the entire list. Two ports.

If you are reusing the old security group, **delete the rules for 80,
443, 8080, and 2022** -- they existed for the Pterodactyl panel, its
Wings WebSocket, and its SFTP subsystem. Nothing listens on them now,
and an open port with nothing behind it is pure attack surface.

RCON runs inside the container but its port is deliberately not
published, so it is reachable only through `docker compose exec`. Do not
publish it: RCON authenticates with a single shared password in
cleartext.

SSM Session Manager is an alternative to the SSH rule if you would
rather have no inbound management port at all. It needs an IAM
instance profile with `AmazonSSMManagedInstanceCore`.

## 4. Bootstrap the host

SSH in, clone the repo, and run the script from inside it:

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/SoberingRealityCheck/Server.git
cd Server
bash aws/bootstrap.sh
```

Cloning first rather than curl-ing the script avoids two traps: the
default branch here is `master`, not `main`, so a `.../main/...` raw URL
404s; and `raw.githubusercontent.com` returns 404 (not 403) for private
repos, making "wrong branch" and "no access" look identical.

If the repo is private, use the SSH remote --
`git clone git@github.com:SoberingRealityCheck/Server.git` -- with a
[deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
on the instance.

It installs Docker Engine and the Compose plugin from Docker's own apt
repo (Ubuntu's `docker.io` package ships the unmaintained Compose v1),
installs uv, clones the repo, writes `.env`, builds the modpack, and
starts the server. It is safe to re-run -- every step checks whether it
already applies, so a bootstrap interrupted by a dropped SSH session is
fixed by running it again.

Read it before running it. It is short, and it is the only thing here
that touches your host unattended.

## 5. Configure access

`bootstrap.sh` creates `.env` with the whitelist **on** and empty, which
means nobody can join yet. That is deliberate -- an open server on a
public IP finds visitors quickly.

```bash
cd ~/Server
nano .env          # set MC_OPS and MC_WHITELIST
docker compose up -d --force-recreate minecraft
```

The whitelist is rewritten from `.env` on every start, so in-game
`/whitelist add` does not survive a restart. Edit `.env` instead.

## 6. Verify

```bash
docker compose ps                      # wait for "healthy"
docker compose logs -f minecraft       # watch first-boot worldgen
docker compose exec minecraft rcon-cli list
```

First boot downloads the mods and generates the world. With this modpack
that takes several minutes and pins the CPU -- it is not hung. The
healthcheck reports `healthy` only once the server answers status pings,
so `ps` is the honest answer to "is it up yet", not the container's
running state.

From your own machine, confirm the port is actually reachable:

```bash
nc -zv <elastic-ip> 25565
```

If that fails while `docker compose ps` says healthy, the problem is the
security group, not the server.

## 7. DNS

| Record | Type | Value | Proxy |
|---|---|---|---|
| `mc.<domain>` | A | Elastic IP | **DNS only** |
| `_minecraft._tcp.<subdomain>` | SRV | priority 0, weight 1, port 25565, target `mc.<domain>` | N/A |

The A record must be DNS-only (grey cloud). Cloudflare proxies TCP/UDP
game traffic only through Spectrum, a paid feature; an orange-cloud
record here will fail to connect.

The SRV record is optional -- it lets players connect without typing a
port, and is Java Edition only, not Bedrock.

**Delete the old `panel.<domain>` record.** Nothing serves it now.

## 8. Decommission the old instance

Once players have connected to the new host successfully:

1. Stop the old instance and leave it stopped for a few days. Stopped
   instances bill only for EBS, and this is cheap insurance against
   discovering you needed something on it.
2. Release its Elastic IP if it had one -- unassociated Elastic IPs bill
   hourly.
3. Terminate it, and delete the EBS volume if it does not go with it.

---

## Reference

### Backups

The world is a directory: `data/world`. Snapshot it with saves paused,
otherwise you can capture a half-written region file:

```bash
docker compose exec minecraft rcon-cli save-off
docker compose exec minecraft rcon-cli save-all
tar czf "backup-$(date +%F).tar.gz" data/world
docker compose exec minecraft rcon-cli save-on
```

Nothing schedules this yet. A cron entry or systemd timer plus `aws s3
cp` to a bucket is the natural next step, and is the one Pterodactyl
feature actually worth rebuilding.

### Historical: Cloudflare proxying and APIs

Worth remembering, because it will recur with anything HTTP placed
behind an orange-cloud record. A proxied hostname returns 403 to
non-browser clients on `/api` routes (Cloudflare bot protection) while
the same URL works fine in a browser. The tell is a 403 carrying no
application JSON error body -- the block page comes from Cloudflare, not
your origin.

Fixes, if you ever put an HTTP service back here: point internal clients
at the loopback rather than the public hostname, and add a WAF skip rule
for `/api/*` for anything external. Note also that in that setup TLS
terminated at Cloudflare and the origin served plain HTTP on port 80.

No HTTP service runs on this host now.
