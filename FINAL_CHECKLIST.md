# EASYTECH THATTA — Final Production Checklist

Sign-off before going live. All items must be ✓.

---

## A. Security (7 items)

- [ ] `DEBUG = False` in production (verified in `settings_production.py`)
- [ ] `SECRET_KEY` generated fresh, 50+ chars, unique per deployment
- [ ] `ALLOWED_HOSTS` set to production domains only
- [ ] HTTPS enforced (`SECURE_SSL_REDIRECT=True`)
- [ ] SSL certificate valid (Let's Encrypt issued, auto-renew)
- [ ] `.env` NOT committed to git (check `git status`)
- [ ] `python manage.py check --deploy` → 0 warnings
- [ ] Default Django admin URL changed or restricted (`.env ADMIN_URL`)
- [ ] Rate limiting active (test 5 failed logins → 429)

## B. Data (4 items)

- [ ] MySQL backup runs daily (cron scheduled)
- [ ] Backup successfully tested (restore on staging)
- [ ] Backup retention working (30 days, old ones deleted)
- [ ] Off-server backup configured (S3/B2/rclone) — optional but recommended

## C. Functionality (10 items)

- [ ] Login page loads over HTTPS
- [ ] Staff login → staff dashboard
- [ ] Principal login → principal dashboard
- [ ] Create course + fee categories
- [ ] Create batch (end month auto-calculates)
- [ ] Admit student (ledger auto-generates)
- [ ] Record payment (partial + full)
- [ ] Apply waiver (Principal only, 403 for staff)
- [ ] Collection reports page + Excel download
- [ ] PDF download works
- [ ] Audit log shows entries
- [ ] Correction workflow end-to-end (submit → approve → reversal)
- [ ] Staff management (create, reset password, deactivate)

## D. Performance (3 items)

- [ ] Dashboard loads in < 2 seconds
- [ ] Dashboard subsequent loads < 500ms (cache working)
- [ ] Reports page < 1 second

## E. Monitoring (3 items)

- [ ] Error logs (`logs/error.log`) empty or expected
- [ ] Access logs (`logs/gunicorn_access.log`) rotating
- [ ] `systemctl status easystech` → active (running)

## F. Operational (3 items)

- [ ] RUNBOOK.md read by team
- [ ] Principal trained on:
  - Course/batch creation
  - Correction approval
  - Reports export
- [ ] Staff trained on:
  - Admission
  - Fee collection (quick collect)
  - Correction request

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Developer | _____________ | _____________ | ______ |
| Principal | _____________ | _____________ | ______ |
| Institute Owner | _____________ | _____________ | ______ |

---

**Once all items are checked, EASYTECH THATTA is live and production-ready.**