"""App configuration for the audit application."""
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = 'Audit Logs'

    def ready(self):
        # Import signals so they register on app startup
        from . import signals  # noqa: F401