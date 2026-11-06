import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create the shared account once; never reset an existing password."

    def handle(self, *args, **options):
        username, password = os.getenv("APP_USERNAME", "department"), os.getenv("APP_PASSWORD", "")
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write("Shared account already exists; password unchanged.")
            return
        if not password:
            raise CommandError("APP_PASSWORD is required to create the account.")
        validate_password(password, user=User(username=username))
        User.objects.create_user(username=username, password=password)
        self.stdout.write(self.style.SUCCESS("Shared account created."))
