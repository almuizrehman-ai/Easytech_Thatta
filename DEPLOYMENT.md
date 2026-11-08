# EASYTECH THATTA — Deployment Guide

Complete step-by-step guide for deploying to production.

---

## Part 1: Linux Server (Ubuntu 22.04 LTS) — Recommended

### Prerequisites
- Ubuntu 22.04 LTS VPS (min 2 GB RAM, 2 CPU, 20 GB SSD)
- Root or sudo access
- Domain pointing to server IP (`easystech.pk`)
- MySQL 8.x, Nginx, Gunicorn

### Step 1: System setup

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3.11 python3.11-venv python3-pip \
    mysql-server nginx certbot python3-certbot-nginx \
    git build-essential libmysqlclient-dev pkg-config \
    ufw

# Create dedicated user
sudo adduser easystech
sudo usermod -aG www-data easystech

# Firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Step 2: MySQL setup

```bash
sudo mysql -u root

-- In MySQL shell:
CREATE DATABASE easystech_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'easystech_user'@'localhost' IDENTIFIED BY 'STRONG-PASSWORD-HERE';
GRANT ALL PRIVILEGES ON easystech_db.* TO 'easystech_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### Step 3: Deploy project

```bash
# Clone/copy project
sudo mkdir -p /var/www/easystech
sudo chown easystech:www-data /var/www/easystech

sudo -u easystech bash
cd /var/www/easystech

# If using git:
git clone https://github.com/yourorg/easystech.git .

# Create virtualenv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn whitenoise

# Create directories
mkdir -p logs media staticfiles backup

# Copy env file
cp .env.production.example .env
nano .env  # Edit with real values!

# Generate SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
# Copy output to .env SECRET_KEY
```

### Step 4: Migrate + collect static

```bash
# Still as easystech user, venv activated
export DJANGO_SETTINGS_MODULE=config.settings_production

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser  # Principal account
```

### Step 5: Gunicorn service

```bash
exit  # Back to sudo user

# Socket directory
sudo mkdir -p /run/gunicorn
sudo chown easystech:www-data /run/gunicorn

# Copy service file
sudo cp /var/www/easystech/deployment/gunicorn.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable easystech
sudo systemctl start easystech
sudo systemctl status easystech
```

### Step 6: Nginx

```bash
# Get SSL first (Nginx not yet active)
sudo certbot certonly --standalone -d easystech.pk -d www.easystech.pk

# Copy Nginx config
sudo cp /var/www/easystech/deployment/nginx.conf /etc/nginx/sites-available/easystech
sudo ln -s /etc/nginx/sites-available/easystech /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default

# Test + reload
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7: Backup cron

```bash
sudo chmod +x /var/www/easystech/scripts/backup.sh
sudo chmod +x /var/www/easystech/scripts/restore.sh

sudo cp /var/www/easystech/deployment/easystech-backup.cron /etc/cron.d/easystech-backup
sudo chmod 644 /etc/cron.d/easystech-backup
```

### Step 8: SSL auto-renewal

```bash
# Certbot renewal is automatic via systemd timer
sudo systemctl status certbot.timer

# Test renewal
sudo certbot renew --dry-run
```

### Step 9: Verify

- Open `https://easystech.pk/` → should show login page
- Login with superuser → should land on Principal dashboard
- Check `sudo journalctl -u easystech -n 50` for errors
- Check `sudo tail -f /var/log/nginx/easystech_error.log`

---

## Part 2: Windows Server 2019

### Prerequisites
- Windows Server 2019 (or Windows 10/11 Pro for small deployments)
- Python 3.11+, MySQL 8.x, Waitress (WSGI server)
- IIS or Nginx for Windows (reverse proxy)

### Step 1: Install software

- Python 3.11 from python.org (add to PATH)
- MySQL 8.0 installer (note root password)
- Nginx for Windows (or IIS with HttpPlatformHandler)
- 7-Zip (for backup scripts)

### Step 2: Setup project

```cmd
cd C:\
mkdir easystech
cd easystech

# Copy project files
# Create virtualenv
python -m venv venv
venv\Scripts\activate

pip install --upgrade pip
pip install -r requirements.txt
pip install waitress whitenoise

# Config
copy .env.production.example .env
notepad .env  # Edit
```

### Step 3: Migrate

```cmd
set DJANGO_SETTINGS_MODULE=config.settings_production

python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### Step 4: Windows Service (Waitress)

Use **NSSM** (Non-Sucking Service Manager):

1. Download NSSM from https://nssm.cc/download
2. Extract to `C:\nssm\`
3. Open admin CMD:
```cmd
C:\nssm\win64\nssm.exe install EASYTECH "C:\easystech\venv\Scripts\waitress-serve.exe" "--listen=127.0.0.1:8001" "config.wsgi:application"
C:\nssm\win64\nssm.exe set EASYTECH AppDirectory "C:\easystech"
C:\nssm\win64\nssm.exe set EASYTECH AppEnvironmentExtra DJANGO_SETTINGS_MODULE=config.settings_production
C:\nssm\win64\nssm.exe set EASYTECH Start SERVICE_AUTO_START
C:\nssm\win64\nssm.exe start EASYTECH
```

### Step 5: IIS or Nginx reverse proxy

- Point reverse proxy to `http://127.0.0.1:8001`
- Configure static files from `C:\easystech\staticfiles\`
- Configure media files from `C:\easystech\media\`

### Step 6: Backups

- Open Task Scheduler
- Create Basic Task → Daily at 2:00 AM
- Action: Start program → `C:\easystech\scripts\backup.bat`
- Run with highest privileges

---

## Post-Deployment Checklist

- [ ] `python manage.py check --deploy` → 0 warnings
- [ ] `https://easystech.pk/` loads
- [ ] Login works (staff + principal)
- [ ] Dashboards render (charts visible)
- [ ] Admit a test student → ledger auto-generates
- [ ] Record a test payment → receipt appears
- [ ] Reports page → Excel + PDF download
- [ ] Audit log shows actions
- [ ] Backup script runs manually (first time)
- [ ] Backup cron scheduled
- [ ] SSL certificate valid (browser padlock)
- [ ] `http://` redirects to `https://`
- [ ] Rate limiting works (5 failed logins → 429)
- [ ] `.env` NOT in git
- [ ] Server logs clean (no errors)