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

Wings' own management API (default port 8080) has no security group rule
-- Panel and Wings communicate over `localhost` on a single-host setup.

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
