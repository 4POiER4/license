import os
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from registry.models import Contract, License


class Command(BaseCommand):
    help = "Create synthetic examples in an empty, explicitly enabled QA database."

    @transaction.atomic
    def handle(self, *args, **options):
        if os.getenv("ALLOW_DEMO_DATA") != "1":
            raise CommandError("Demo seeding is disabled. Use the isolated compose.qa.yaml project.")
        if Contract.objects.exists() or License.objects.exists():
            raise CommandError("Database is not empty; nothing was changed.")
        today = timezone.localdate()
        data = [
            ("ДЕМО-026/ПО", "Демонстрационный поставщик А", "BYN", "24500.00", 180, [
                ("nanoCAD СПДС", 12, "12000.00", 44), ("Антивирус для рабочих станций", 30, "8400.00", 350), ("PDF-редактор", 5, "3600.00", None)]),
            ("ДЕМО-018/ИТ", "Демонстрационный поставщик Б", "RUB", "185000.00", 350, [
                ("Система резервного копирования", 1, "125000.00", -3), ("Графический редактор", 3, "60000.00", 200)]),
            ("ДЕМО-009/SW", "Демонстрационный поставщик В", "USD", "2700.00", 365, [
                ("Корпоративная почта", 25, "1500.00", 15), ("Архиватор", 20, "400.00", None), ("Инструменты разработчика", 4, "800.00", -10)]),
        ]
        for number, vendor, currency, amount, days_ago, items in data:
            contract = Contract.objects.create(number=number, vendor=vendor, currency=currency, total_amount=amount,
                signed_on=today - timedelta(days=days_ago), notes="Демонстрационные данные. Не является реальным договором.")
            for software, quantity, cost, remaining in items:
                License.objects.create(contract=contract, software=software, quantity=quantity, cost=cost,
                    starts_on=contract.signed_on, ends_on=today + timedelta(days=remaining) if remaining is not None else None,
                    perpetual=remaining is None, notes="Демонстрационная запись для проверки интерфейса.")
        self.stdout.write(self.style.SUCCESS("Created 3 synthetic contracts and 8 software positions."))
