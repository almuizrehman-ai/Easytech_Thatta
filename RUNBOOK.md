# EASYTECH THATTA — Operations Runbook

Day-to-day operational guide for administrators.

---

## 1. First-Time Setup (after deployment)

### Create Principal account
```bash
cd /var/www/easystech
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_production
python manage.py createsuperuser
# Username: principal01
# Password: (12+ chars, strong)
```
Role auto-sets to `principal`. Login works immediately.

### Create initial staff account
Login as Principal → Sidebar → **Staff Management** → **New Staff**
- Username: `staff01`
- Password: give to staff member

### Set up courses + batches
1. Principal → **Courses** → **New Course**
   - DIT: code `DIT`, duration `12`
   - CIT: code `CIT`, duration `6`
   - Add fee categories per course (Admission, Registration, Semester, etc.)
2. Principal → **Batches** → **New Batch**
   - Select course, enter start month (e.g. `2027-03`)
   - Set monthly fee (e.g. 1500)
   - End month auto-calculates

### First student admission
Staff login → **New Admission** → fill form → save
Fee ledger auto-generates with all backdated months + admission fee as pending.

---

## 2. Password Recovery

### Staff forgot password
Principal → **Staff Management** → click staff row → **Reset Password** (key icon)
- Set new password
- Share with staff securely

### Principal forgot password
Cannot reset from UI (no self-service).
Server command:
```bash
cd /var/www/easystech
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_production
python manage.py changepassword principal01
```

### All principals locked out
```bash
python manage.py createsuperuser
# Create a second principal to regain access
```

---

## 3. Backup & Restore

### Manual backup (Linux)
```bash
cd /var/www/easystech
./scripts/backup.sh
# Backs to: backup/YYYY-MM-DD_HH-MM-SS/
```

### Manual backup (Windows)
```cmd
cd C:\easystech
scripts\backup.bat
```

### Restore from backup (Linux)
```bash
cd /var/www/easystech
./scripts/restore.sh 2026-11-05_02-00-00
# Prompts for confirmation
# Then restart service:
sudo systemctl restart easystech
```

### Off-server backup (recommended)
Add to backup.sh after successful run:
```bash
# Upload to S3/B2 (requires rclone config)
rclone sync "$BACKUP_DIR" remote:easystech-backup/latest/
```

---

## 4. Common Issues

### Site slow
1. Check `sudo tail -100 /var/www/easystech/logs/app.log`
2. Clear dashboard cache: `python manage.py clear_dashboard_cache`
3. Check DB: `SHOW PROCESSLIST` in MySQL
4. Restart: `sudo systemctl restart easystech`

### 500 error
1. Check logs:
   - `sudo tail -100 /var/www/easystech/logs/error.log`
   - `sudo journalctl -u easystech -n 100`
2. Common causes:
   - Missing `.env` variable → fix and restart
   - DB connection failure → `sudo systemctl status mysql`
   - Disk full → `df -h`

### Login blocked (rate limit)
Wait 5 minutes OR:
```bash
python manage.py shell
>>> from django.core.cache import cache
>>> cache.delete_pattern('rl:login:*')  # Redis
>>> # For LocMem: cache.clear()
```

### Migrations pending after update
```bash
source venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_production
python manage.py migrate
sudo systemctl restart easystech
```

### Disk full
```bash
# Check usage
df -h
du -sh /var/www/easystech/*
du -sh /var/www/easystech/logs/*
du -sh /var/www/easystech/backup/*

# Clean old logs
find /var/www/easystech/logs -name "*.log" -mtime +30 -delete

# Old backups (retention should handle, verify)
ls /var/www/easystech/backup/ | head
```

---

## 5. Daily Operations

### Morning routine
1. Open dashboard → verify yesterday's collections reconciled
2. Check "Pending Fees" count — any spikes?
3. Check "Overdue Fees" — any large amounts?
4. Review recent admissions

### End of day
1. Staff: confirm all payments recorded today
2. Principal: check "Today's Collection" matches cash box
3. Any corrections pending? Review + approve/reject

### Weekly
1. Review audit logs (any suspicious actions?)
2. Check backup folder sizes (should be growing slowly)
3. Update courses/batches if needed

### Monthly
1. Review pending summary by course/batch
2. Follow up on 90+ day overdue accounts
3. Verify backup retention (30 days)
4. Check disk usage (logs + media + backup)

---

## 6. Financial Integrity

### Never modify payment history directly
All corrections must go through the correction workflow:
- Staff submits request → Principal approves → reversal + replacement

### Audit trail
Every action logged in `AuditLog`:
- Principal → **Audit Logs** → filter by user/action/module
- Immutable (cannot be edited or deleted)

### Waivers
- Principal-only
- Requires reason (mandatory)
- Logged with approver name + timestamp

---

## 7. Adding New Staff Mid-Session

1. Principal → Staff Management → New Staff
2. Create with temporary password
3. Staff logs in → change password (recommended) via edit
4. Assign permissions (role='staff' fixed, no admin access)

---

## 8. Quarterly Maintenance

```bash
# 1. Test restore on staging (never on production directly)
# 2. Update dependencies
source venv/bin/activate
pip list --outdated
pip install --upgrade <package-name>

# 3. Security check
python manage.py check --deploy
sudo apt update && sudo apt upgrade

# 4. SSL expiry check
sudo certbot certificates

# 5. Backup verification
ls -la /var/www/easystech/backup/ | tail -5
# Verify backups are recent (within 24 hours)
```

---

## 9. Emergency Contacts

- **Server provider:** [Add provider support]
- **Domain registrar:** [Add registrar]
- **Principal phone:** [Add]
- **Developer:** [Add]

---

## 10. Adding a Second Server (Scaling)

When single server becomes insufficient:
1. Move MySQL to dedicated DB server
2. Add Redis for cache + sessions
3. Add second app server behind load balancer
4. Move media to S3/NFS
5. Update Nginx upstream to load-balance both servers

For now, single-server is sufficient for typical institute (< 2000 students).