# AWS

Provisioning guide for the two EC2 hosts this repo runs on, plus the
reference tables behind the choices.

There are two instances:

- **the game host** -- a t3.large that runs the Minecraft container and
  powers itself off when nobody is playing. Sections 1-8 below.
- **the front-door proxy** -- a tiny, always-on instance that answers the
  public address, keeps the server visible in the list while the game
  host is off, and wakes it on the first join. Its own section, "Front
  door (auto-wake proxy)", after section 8.

Work sections 1-8 top to bottom for the game host. `bootstrap.sh` in
this directory automates steps 4-6; everything before that is console
work that a script cannot do for you. Then do the proxy.

---

## 1. Launch the game host

| Setting | Value |
|---|---|
| Region | `us-east-2` (match the existing setup) |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | **t3.large** (2 vCPU / 8 GB) |
| Root volume | 25 GB gp3 |
| VPC/subnet | default |
| Key pair | existing, or create one and save the `.pem` |

Put both instances in the same VPC (the default VPC is fine). The proxy
reaches this host over its **private** IP, which only works inside a
shared VPC.

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

## 2. Networking: no Elastic IP on the game host

This host does **not** get an Elastic IP. The proxy holds the one stable
public address in the whole setup (see its section), and reaches this
host over its private IP.

- **Private IP.** In the default VPC an instance keeps its primary
  private IPv4 for its whole life, across every stop/start, released
  only on termination. That is what `server.address` in the proxy's
  `lazymc.toml` points at. Note it down after launch.
- **Public IP.** Leave auto-assign public IPv4 **on** (the default
  subnet does this). The host needs outbound access for the first-boot
  pack build (Modrinth) and image pulls (Docker Hub). The address
  changes on every stop/start, but nothing points at it, so that no
  longer matters.

An auto-assigned public IPv4 bills per hour only while the instance
runs, and is released when it stops -- which is most of the time here.
An Elastic IP bills even while its instance is stopped. So on a host
that is off most of the day, auto-assign is both simpler and cheaper.

## 3. Security groups

Two, one per instance. The proxy's is in its own section; the game
host's is:

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | your admin IP(s) only | management |
| Custom TCP | TCP | 25565 | **the proxy's security group** | Minecraft, from the proxy only |

Source 25565 from the proxy's security group id, not `0.0.0.0/0`. The
public game port lives on the proxy; players never connect here
directly. Locking it to the proxy removes the game port as public
attack surface on the expensive box.

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
instance profile with `AmazonSSMManagedInstanceCore`. The proxy also
works as a bastion, since it is the one box with a stable public
address.

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
means nobody can join yet. That is deliberate -- an open server finds
visitors quickly.

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

This host has no public game port -- there is nothing to test from your
own machine. Reachability is checked later, from the proxy box, once it
exists (see the front-door section's step 4). If that check fails while
`docker compose ps` here says healthy, the cause is the game host's
security group (does it allow 25565 from the proxy's group?) or the two
instances not being in the same VPC.

## 7. DNS

| Record | Type | Value | Proxy |
|---|---|---|---|
| `mc.<domain>` | A | **the proxy instance's Elastic IP** | **DNS only** |
| `_minecraft._tcp.<subdomain>` | SRV | priority 0, weight 1, port 25565, target `mc.<domain>` | N/A |

The A record points at the proxy, not the game host. It must be DNS-only
(grey cloud): Cloudflare proxies TCP/UDP game traffic only through
Spectrum, a paid feature; an orange-cloud record here will fail to
connect.

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

## Cost and idle shutdown

A t3.large left running is about **$61/month** compute plus ~$2 EBS --
around $2/day for a box that is idle most of the time.

This setup instead powers the game host off when nobody is playing. The
always-on proxy wakes it automatically on the next join. At a few hours
of play a day this lands around **$15-20/month** all in, the proxy
included.

| Approach | Rough monthly | Notes |
|---|---|---|
| Game host always on | $63 | What you get by default |
| Auto-stop + proxy wake (this setup) | $15-20 | Adds a ~$4 always-on proxy; cold join costs players ~3-5 min |
| Fixed schedule (EventBridge) | ~$20 | Simpler, but unavailable off-hours |
| 1-year Savings Plan | ~$40 | No behaviour change; stacks with the above |
| Graviton t4g.large game host | ~$49 | ~19% cheaper, arm64 mod support unverified |

The proxy's Elastic IP is the one public IPv4 in the setup, so the
~$3.65/month IPv4 floor stays regardless -- but it is now a floor you
were paying anyway, moved from the game host to a box that is always up
to use it. The game host itself has no Elastic IP (see section 2).

### How it works

Three pieces, because no single one is sufficient:

1. **`ENABLE_AUTOSTOP`** in the container stops the Minecraft server
   after `AUTOSTOP_TIMEOUT_EST` seconds with no players. This frees CPU
   but saves nothing on its own -- EC2 bills for a running instance
   regardless of what it is running.
2. **`mc-idle-shutdown.timer`** on the host checks every minute whether
   the container is gone and powers the instance off. This is the part
   that actually stops the meter.
3. **lazymc on the proxy** issues `ec2:StartInstances` on the first join
   attempt from a whitelisted client after the game host has stopped
   (non-whitelisted joins and login-spam are kicked without a wake --
   see "Whitelist sync"). It cannot live on the game host, for obvious
   reasons -- hence the second instance.

The container's restart policy is `"no"` -- required, since a restart
policy would immediately revive the container and the host would never
go idle. `minecraft.service` starts the stack at boot instead.

### Guards

Idle shutdown refuses to fire when:

- the host has been up less than 20 minutes (`BOOT_GRACE_SECONDS`;
  otherwise a woken instance could power off before the server finished
  starting -- an unwakeable loop, and one nobody is watching now that
  waking is automatic)
- anyone is logged in over SSH
- `/etc/mc-no-shutdown` exists
- `data/.skip-stop` exists (which also suspends the container's own
  auto-stop)

Use the inhibit file for anything long-running with no players
connected. **Chunky pre-generation is exactly this** -- it runs for
hours and looks completely idle:

```bash
sudo touch /etc/mc-no-shutdown     # before starting a chunky run
sudo rm /etc/mc-no-shutdown        # after it finishes
```

### Turning it off

```bash
# One session (on the game host)
sudo touch /etc/mc-no-shutdown

# Permanently: stop the game host powering off
sudo systemctl disable --now mc-idle-shutdown.timer
# and set MC_ENABLE_AUTOSTOP=false in .env, then recreate the container

# Stop players being able to wake it at all (on the proxy)
sudo systemctl disable --now lazymc
```

---

## Front door (auto-wake proxy)

The game host powers itself off when empty (above), which is what makes
the whole thing cheap. Something then has to turn it back on, and it
cannot be the game host. That something is a second, deliberately tiny
instance running [lazymc](https://github.com/timvisee/lazymc): it
answers the address players actually use, holds a correct server-list
entry while the game host is off, and calls `ec2:StartInstances` the
first time someone tries to join.

Config lives in `aws/proxy/`:

| File | Role |
|---|---|
| `lazymc.toml` | proxy config -- two placeholders to fill, plus optional version hints |
| `lazymc.service` | systemd unit |
| `setup.sh` | installs the lazymc binary, the AWS CLI, the unit, and the whitelist receiver |
| `lazymc-recv-whitelist` | forced command that lands a whitelist push into `/etc/lazymc` |
| `iam-policy.json` | the instance profile policy -- start one instance, nothing else |

The game host keeps this proxy's whitelist current by pushing to it on
change -- see "Whitelist sync" below. The units for that live in
`aws/systemd/` and are installed by `bootstrap.sh` on the game host.

### 1. Launch the proxy instance

| Setting | Value |
|---|---|
| Region | `us-east-2` (same as the game host) |
| AMI | Ubuntu Server 24.04 LTS (x86_64) |
| Instance type | **t3.nano** (or t3.micro) -- lazymc is idle almost all the time |
| Root volume | 8 GB gp3 |
| VPC/subnet | **same VPC as the game host** |
| Elastic IP | allocate and associate one -- this is the address DNS points at |

This is the box that must stay reachable at a fixed address, so it is
the one that gets the Elastic IP.

### 2. Security group (proxy)

| Type | Protocol | Port | Source | Purpose |
|---|---|---|---|---|
| SSH | TCP | 22 | your admin IP(s) only | management |
| SSH | TCP | 22 | the **game host's** security group id | whitelist push (see "Whitelist sync") |
| Custom TCP | TCP | 25565 | `0.0.0.0/0` | Minecraft Java -- the real public game port |

Then, on the **game host's** security group, allow 25565 from *this*
security group's id (section 3).

### 3. IAM instance profile

Create a role, attach `aws/proxy/iam-policy.json` to it with your
account ID and the game host's instance ID substituted, and attach the
role to the proxy instance as its instance profile.

The policy grants `ec2:StartInstances` on that one instance and
`ec2:DescribeInstances` (read-only, for `aws ec2 describe-instances` by
hand). No stop, no terminate, no modify. lazymc never needs more than
start; the game host decides its own stops.

### 4. Install

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/SoberingRealityCheck/Server.git
cd Server
bash aws/proxy/setup.sh
```

`setup.sh` installs the pinned lazymc binary, the AWS CLI v2 (the `aws`
CLI is what the wake command calls; Ubuntu's packaged `awscli` is the
unmaintained v1), the systemd unit, and the whitelist receiver. It
seeds `/etc/lazymc/server.properties` (`white-list=true`) and an empty
`/etc/lazymc/whitelist.json`, so the proxy **fails closed** -- it wakes
nothing -- until the game host has pushed the real list. It does **not**
start the service. Fill the placeholders first:

```bash
sudo nano /etc/lazymc/lazymc.toml
```

- `server.address` -- the game host's **private** IP, port 25565
- `server.command` -- the game host's instance ID

Optionally also uncomment and set `public.version` / `public.protocol`
to the running Minecraft version and its wire-protocol number, so the
sleeping server-list entry shows the right version rather than lazymc's
built-in default. This only affects how the entry looks before the game
host has been woken once; connecting works either way. See the comments
in `lazymc.toml` for how to get the protocol number.

Authorise the game host's whitelist push: append its sync public key
(printed at the end of `bootstrap.sh` on the game host) to
`/home/ubuntu/.ssh/authorized_keys` here, forced to the receiver:

```
command="/usr/local/bin/lazymc-recv-whitelist",restrict ssh-ed25519 AAAA... game-host-whitelist-sync
```

Confirm this box can reach the game host privately (start the game host
first if it is stopped):

```bash
nc -zv <game-host-private-ip> 25565
```

A failure here is the game host's security group (does it allow 25565
from this instance's security group?) or the two instances not sharing a
VPC.

Then check the filled config parses and start it:

```bash
lazymc config test --config /etc/lazymc/lazymc.toml
sudo systemctl start lazymc
journalctl -u lazymc -f
```

Point the `mc.<domain>` A record at this instance's Elastic IP
(section 7). Then, on the **game host**, do the whitelist-sync steps
below and run one push. Finally test a real join with a whitelisted
account.

### What a join looks like

- **Game host up:** lazymc forwards transparently. Players cannot tell
  it is there.
- **Game host off, player pings:** lazymc answers the status request
  itself from its cached/hinted version. The server shows in the list
  with the "asleep" MOTD. Nothing is woken.
- **Game host off, non-whitelisted client joins:** lazymc reads the
  login-start username, finds it in neither `whitelist.json` nor
  `ops.json`, and kicks with "You are not white-listed on this server!"
  **before** it runs `start-instances`. Nothing is woken. Logged as
  `User '<name>' tried to wake server but is not whitelisted`.
- **Game host off, whitelisted client joins:** lazymc runs
  `start-instances`, shows the "starting" MOTD, and holds the connection
  for up to 25s before kicking with a "reconnect in a few minutes"
  message. Meanwhile the game host boots, `minecraft.service` brings the
  stack up (rebuilding the pack if the jar cache is cold), and lazymc
  polls the private address until it answers. Cold path is ~3-5 minutes.

### Threat model

Only a whitelisted username can wake the game host. lazymc answers
status pings itself, so scanners and server-list crawlers never wake
anything; and it checks the login-start username against the synced
`whitelist.json` / `ops.json` before calling `start-instances`, so
commodity login-spam -- well-formed login packets with random usernames
-- is kicked at the proxy for free.

Two residual ways to trigger a wake, both economically pointless:

- A stranger who knows a real whitelisted name. They wake it but cannot
  join -- the game host verifies the account for real on connect.
- A hand-crafted login packet whose username lazymc cannot parse: in
  0.2.11 an undecodable username skips the whitelist check
  (`src/status.rs`). This needs deliberately malformed packets, not a
  normal client or a stock spam bot.

Either way the whole payoff is one server that idle-shutdown stops again
within ~20 minutes, with no way to play in between.

If the synced whitelist is missing or empty while
`/etc/lazymc/server.properties` says `white-list=true`, lazymc wakes
**nobody**. That is the intended failure direction: a broken sync costs
you access, never money. The one misconfiguration that fails *open* is
`wake_whitelist = true` with no `white-list=true` in
`/etc/lazymc/server.properties` -- lazymc then treats everyone as
allowed. `setup.sh` writes that file; do not delete it.

Username matching is exact and case-sensitive against the `name` fields.
The UUIDs in the file are ignored by lazymc. Offline-mode name spoofing
is not a concern here: a spoofer can wake the server but the game host
rejects them at login, same as a stranger with a real name.

### Whitelist sync

The proxy enforces the whitelist (above), so it needs a current copy of
it. lazymc cannot read the game host's `data/` directory, so the game
host pushes the files to the proxy whenever they change. Push, not pull:
the game host is up exactly when the whitelist can change (you edit
`.env` and recreate the container), and the more-trusted box should be
the one initiating to the internet-facing one.

**Pieces**, all in `aws/systemd/`, installed on the **game host** by
`bootstrap.sh`:

| Unit / file | Role |
|---|---|
| `mc-whitelist-sync.path` | watches `data/whitelist.json` and `data/ops.json` |
| `mc-whitelist-sync.service` | oneshot, runs the script |
| `mc-whitelist-sync.sh` | tars the two files plus a `white-list=<flag>` line and sends them over SSH |
| `~/.ssh/mc-whitelist-sync` | dedicated key, generated by `bootstrap.sh` |
| `/etc/mc-whitelist-sync.target` | one line: `ubuntu@<proxy-private-ip>` |

On the **proxy**, `lazymc-recv-whitelist` is the forced command for that
key -- it drops the three files into `/etc/lazymc/`, and lazymc's file
watcher reloads them within ~2s. The key can do nothing else on the
proxy.

**One-time wiring** (both ends). Until the first push lands, the proxy
fails closed -- nobody can wake the game host by joining -- so the game
host has to be up by other means for these steps:

1. Start the game host from the EC2 console (this first time only; after
   the sync works, a whitelisted join is enough).
2. On the game host, run `bootstrap.sh` (or re-run it -- it is
   idempotent). It generates the key and prints the exact
   `authorized_keys` line.
3. On the proxy, paste that line into `/home/ubuntu/.ssh/authorized_keys`.
4. On the game host, set the target and push once:

   ```bash
   echo 'ubuntu@<proxy-private-ip>' | sudo tee /etc/mc-whitelist-sync.target
   /usr/local/bin/mc-whitelist-sync.sh
   ```

After that it is automatic. `itzg/minecraft-server` rewrites
`whitelist.json` from `MC_WHITELIST` on every container start, so the
normal "edit `.env`, `docker compose up -d --force-recreate`" cycle
fires a push with no extra step. Check it landed with
`journalctl -u mc-whitelist-sync` on the game host, or look at
`/etc/lazymc/whitelist.json` on the proxy.

**Open server.** If you run with `MC_ENABLE_WHITELIST=false`, the sync
sends `white-list=false` and lazymc stops enforcing -- the proxy then
wakes for anyone, matching the game host. The wake-spam protection is
gone in that mode, by definition.

### Stopping is not the proxy's job

lazymc's own sleep timer is disabled (`sleep_after` set to a year). The
game host's idle-shutdown decides when to stop, with guards the proxy
cannot see -- an active SSH session, the Chunky inhibit file. When the
game host stops, lazymc's status probe returns nothing and it moves
Started -> Stopped ("Server is now sleeping"), then waits for the next
join.

That is not a crash. In lazymc 0.2.11 (`src/server.rs`) the crash path
fires only when the process lazymc *itself spawned* via `command` exits
nonzero while already in the Started state. Here `command` is a one-shot
`aws ec2 start-instances` that exits 0 during Starting, so `wake_on_crash`
cannot fire regardless of its value -- it is left off for clarity.

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

No HTTP service runs on either host now.
