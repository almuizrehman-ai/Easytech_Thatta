"""App configuration for the batches application."""
from django.apps import AppConfig


class BatchesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'batches'
    verbose_name = 'Batches'