from django.apps import AppConfig


class WwwappConfig(AppConfig):
    name = 'wwwapp'

    def ready(self):
        import wwwapp.sheets.signals  # noqa: F401
