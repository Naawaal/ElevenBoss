# ElevenBoss VPS operations (Bisup / Ubuntu)

Quick reference for running the Discord bot on a Linux VPS with **systemd**.  
Replace `YOUR_VPS_IP` with your server IP. **Never commit `.env` or tokens.**

---

## SSH

```powershell
# From Windows PowerShell
ssh root@YOUR_VPS_IP
```

Paste password: `Ctrl+V` or right-click (nothing shows while typing — normal).

Bot runs as user `elevenboss`; app path: `/home/elevenboss/ElevenBoss`.

---

## First-time setup (summary)

```bash
apt update && apt upgrade -y
apt install -y git python3 python3-venv python3-pip build-essential libjpeg-dev zlib1g-dev

adduser --disabled-password --gecos "" elevenboss
su - elevenboss
cd ~
git clone https://github.com/Naawaal/ElevenBoss.git
cd ElevenBoss

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip

# Ubuntu 22.04 = Python 3.10 — skip audioop-lts (Python 3.13+ only)
grep -v audioop-lts requirements.txt > requirements-vps.txt
pip install -r requirements-vps.txt

nano .env   # DISCORD_TOKEN, SUPABASE_URL, SUPABASE_KEY, ENVIRONMENT=production
```

**`.env` on VPS — do not set `PORT` or `RENDER`** (Render-only).

---

## systemd service

Service file: `/etc/systemd/system/elevenboss.service`

```ini
[Unit]
Description=ElevenBoss Discord Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=elevenboss
WorkingDirectory=/home/elevenboss/ElevenBoss
EnvironmentFile=/home/elevenboss/ElevenBoss/.env
ExecStart=/home/elevenboss/ElevenBoss/.venv/bin/python -m apps.discord_bot.main
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable elevenboss
systemctl start elevenboss
systemctl status elevenboss
```

---

## Day-to-day commands

```bash
# Start / stop / restart
systemctl start elevenboss
systemctl stop elevenboss
systemctl restart elevenboss

# Is it running?
systemctl status elevenboss

# Live logs
journalctl -u elevenboss -f

# Last 50 lines
journalctl -u elevenboss -n 50 --no-pager

# Logs since 10 minutes ago
journalctl -u elevenboss --since "10 min ago" --no-pager

# Confirm login name (production vs dev)
journalctl -u elevenboss -n 30 --no-pager | grep "Logged in"
```

---

## Update production token or `.env`

```bash
chown elevenboss:elevenboss /home/elevenboss/ElevenBoss/.env
chmod 600 /home/elevenboss/ElevenBoss/.env
nano /home/elevenboss/ElevenBoss/.env
```

Format (no quotes, no spaces around `=`):

```env
DISCORD_TOKEN=your_production_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key
ENVIRONMENT=production
```

Optional — instant slash-command sync on one test server:

```env
GUILD_ID=your_discord_server_id
```

```bash
systemctl restart elevenboss
journalctl -u elevenboss -n 20 --no-pager
```

Verify token is loaded (as `elevenboss`):

```bash
su - elevenboss -c 'cd ~/ElevenBoss && .venv/bin/python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(bool(os.getenv(\"DISCORD_TOKEN\")))"'
```

Should print `True`.

---

## Deploy code updates

```bash
su - elevenboss
cd ~/ElevenBoss
git pull
source .venv/bin/activate
pip install -r requirements-vps.txt
exit

systemctl restart elevenboss
journalctl -u elevenboss -f
```

Regenerate `requirements-vps.txt` after `requirements.txt` changes:

```bash
grep -v audioop-lts requirements.txt > requirements-vps.txt
```

---

## Manual test (bypass systemd)

```bash
su - elevenboss
cd ~/ElevenBoss
source .venv/bin/activate
python -m apps.discord_bot.main
# Ctrl+C to stop — use systemd for 24/7
```

---

## Production vs dev bot

| Bot              | Log line                         | Token in `.env`      |
|------------------|----------------------------------|----------------------|
| Production       | `Logged in as ElevenBoss`        | Production app token |
| Dev              | `Logged in as ElevenBoss - Dev`  | Dev app token        |

**One token = one running instance.** Stop Render and any local `python -m apps.discord_bot.main` using the same token before starting on VPS.

Invite link (replace `CLIENT_ID`):

```text
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `DISCORD_TOKEN is missing` | `.env` empty, wrong path, or `chown elevenboss:elevenboss .env` |
| `ModuleNotFoundError: discord` | `pip install -r requirements-vps.txt` inside `.venv` |
| `audioop-lts` pip error | Use `requirements-vps.txt` (grep -v audioop-lts) on Python 3.10 |
| Bot offline in Discord | Wrong token (dev vs prod), bot not invited to server, or second instance on Render/PC |
| Login loops / 429 | Stop duplicate hosts; VPS dedicated IP usually avoids Render shared-IP issues |

```bash
# .env permissions
ls -la /home/elevenboss/ElevenBoss/.env

# Service definition
systemctl cat elevenboss

# Memory
free -h
```

---

## Optional hardening

```bash
passwd                          # change root password
ufw allow OpenSSH
ufw enable
```

Use SSH keys instead of password login when convenient.
