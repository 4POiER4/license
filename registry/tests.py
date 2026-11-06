import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Contract, License, months_before

TODAY = date(2026, 11, 6)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RegistryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="department", password="test-secret-password-42")
        cls.contract = Contract.objects.create(number="ПО-01", signed_on=date(2026, 1, 10), total_amount="1500.00", currency="BYN")

    def setUp(self):
        self.client.force_login(self.user)
        self.clock = patch("django.utils.timezone.localdate", return_value=TODAY)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def license(self, **kwargs):
        data = dict(contract=self.contract, software="Программа", quantity=10, cost="1000.10", starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 6))
        data.update(kwargs)
        return License.objects.create(**data)

    def contract_payload(self, **kwargs):
        data = {"number": "НОВЫЙ-26", "signed_on": "2026-11-06", "vendor": "Поставщик", "currency": "USD", "total_amount": "123.45", "notes": "",
            "positions-TOTAL_FORMS": "2", "positions-INITIAL_FORMS": "0", "positions-MIN_NUM_FORMS": "1", "positions-MAX_NUM_FORMS": "200",
            "positions-0-software": "Программа A", "positions-0-quantity": "5", "positions-0-cost": "100.10", "positions-0-starts_on": "2026-11-06", "positions-0-ends_on": "2027-01-06",
            "positions-1-software": "Программа B", "positions-1-quantity": "2", "positions-1-cost": "20.20", "positions-1-starts_on": "2026-11-06", "positions-1-ends_on": "", "positions-1-perpetual": "on"}
        data.update(kwargs)
        return data

    def test_calendar_months_clamp(self):
        self.assertEqual(months_before(date(2027, 4, 30)), date(2027, 2, 28))
        self.assertEqual(months_before(date(2028, 4, 30)), date(2028, 2, 29))
        self.assertEqual(months_before(date(2027, 1, 31)), date(2026, 11, 30))

    def test_reminder_begins_exactly_two_calendar_months_before(self):
        item = self.license()
        self.assertFalse(item.needs_reminder_on(TODAY - timedelta(days=1)))
        self.assertTrue(item.needs_reminder_on(TODAY))
        self.assertEqual(item.status_on(TODAY), "expiring")
        self.assertTrue(item.is_red)

    def test_reminder_remains_on_last_day_and_fifth_day(self):
        item = self.license(ends_on=TODAY)
        self.assertEqual(item.status_on(TODAY), "expiring")
        self.assertTrue(item.needs_reminder_on(TODAY))
        self.assertTrue(item.needs_reminder_on(TODAY + timedelta(days=5)))
        self.assertFalse(item.needs_reminder_on(TODAY + timedelta(days=6)))
        self.assertEqual(item.status_on(TODAY + timedelta(days=6)), "expired")

    def test_old_expiration_stays_red_without_reminder(self):
        item = self.license(ends_on=TODAY - timedelta(days=6))
        response = self.client.get(reverse("dashboard"))
        self.assertTrue(item.is_red)
        self.assertEqual(response.context["reminder_count"], 0)
        self.assertContains(response, "Срок истёк")
        self.assertContains(response, "row-alert")

    def test_perpetual_never_reminds(self):
        item = self.license(perpetual=True, ends_on=None)
        self.assertEqual(item.status_on(TODAY), "perpetual")
        self.assertFalse(item.needs_reminder_on(TODAY))
        self.assertFalse(item.is_red)

    def test_future_period_status_and_approaching_end(self):
        item = self.license(starts_on=TODAY + timedelta(days=1), ends_on=TODAY + timedelta(days=20))
        self.assertEqual(item.status_on(TODAY), "future")
        self.assertTrue(item.needs_reminder_on(TODAY))

    def test_dates_and_cost_are_validated_by_model(self):
        item = self.license()
        item.ends_on = date(2025, 1, 1)
        with self.assertRaises(ValidationError):
            item.full_clean()
        item.ends_on = TODAY
        item.quantity = 0
        item.cost = Decimal("-1")
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_database_rejects_invalid_period(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.license(ends_on=date(2025, 1, 1))

    def test_all_private_pages_require_login(self):
        self.client.logout()
        item = self.license()
        paths = ["/", "/contracts/", "/contracts/new/", f"/contracts/{self.contract.pk}/", f"/contracts/{self.contract.pk}/edit/",
            "/licenses/new/", f"/licenses/{item.pk}/", f"/licenses/{item.pk}/edit/", "/notifications/", "/renewals/", "/export/", "/account/password/"]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)

    def test_health_without_login(self):
        self.client.logout()
        self.assertEqual(self.client.get("/health/").json(), {"status": "ok"})

    def test_login_reminds_again_on_each_login(self):
        self.license()
        for _ in range(2):
            self.client.logout()
            response = self.client.post("/login/", {"username": "department", "password": "test-secret-password-42"}, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["show_reminders"])
            self.assertContains(response, 'data-force="true"')
            self.assertFalse(self.client.get("/").context["show_reminders"])

    def test_notifications_include_only_appropriate_periods(self):
        expected = self.license(software="Порог")
        grace = self.license(software="Пятый день", ends_on=TODAY - timedelta(days=5))
        self.license(software="Шестой день", ends_on=TODAY - timedelta(days=6))
        self.license(software="Без срока", perpetual=True, ends_on=None)
        self.license(software="Позже порога", ends_on=date(2027, 1, 7))
        response = self.client.get("/notifications/")
        self.assertEqual({x.pk for x in response.context["nav_reminders"]}, {expected.pk, grace.pk})

    def test_login_to_deep_link_also_shows_reminder(self):
        self.license()
        self.client.logout()
        response = self.client.post("/login/", {"username": "department", "password": "test-secret-password-42", "next": "/contracts/"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["show_reminders"])
        self.assertContains(response, 'id="reminder-dialog"')

    def test_create_contract_with_multiple_positions(self):
        response = self.client.post("/contracts/new/", self.contract_payload())
        self.assertEqual(response.status_code, 302)
        contract = Contract.objects.get(number="НОВЫЙ-26")
        self.assertEqual(contract.currency, "USD")
        self.assertEqual(contract.licenses.count(), 2)
        self.assertEqual(contract.positions_total, Decimal("120.30"))
        self.assertEqual(contract.difference, Decimal("3.15"))
        self.assertEqual(contract.licenses.get(software="Программа A").cost, Decimal("100.10"))
        self.assertIsNone(contract.licenses.get(software="Программа B").ends_on)

    def test_invalid_position_does_not_partially_create_contract(self):
        response = self.client.post("/contracts/new/", self.contract_payload(**{"positions-0-ends_on": "2025-01-01"}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contract.objects.filter(number="НОВЫЙ-26").exists())
        self.assertEqual(License.objects.count(), 0)
        self.assertContains(response, "Дата окончания не может быть раньше")

    def test_empty_post_displays_validation_errors(self):
        for url in ["/contracts/new/", "/licenses/new/"]:
            with self.subTest(url=url):
                response = self.client.post(url, {})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(License.objects.count(), 0)

    def test_duplicate_contract_is_rejected(self):
        self.client.post("/contracts/new/", self.contract_payload())
        response = self.client.post("/contracts/new/", self.contract_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Contract.objects.filter(number="НОВЫЙ-26").count(), 1)

    def test_deleted_extra_position_is_ignored(self):
        response = self.client.post("/contracts/new/", self.contract_payload(**{"positions-1-DELETE": "on", "positions-1-cost": "invalid"}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contract.objects.get(number="НОВЫЙ-26").licenses.count(), 1)

    def test_cannot_create_contract_without_any_positions(self):
        response = self.client.post("/contracts/new/", self.contract_payload(**{"positions-0-DELETE": "on", "positions-1-DELETE": "on"}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Contract.objects.filter(number="НОВЫЙ-26").exists())

    def test_rub_currency_and_price_not_multiplied(self):
        response = self.client.post("/contracts/new/", self.contract_payload(currency="RUB"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Contract.objects.get(number="НОВЫЙ-26").positions_total, Decimal("120.30"))

    def test_currency_cannot_change_for_existing_contract(self):
        response = self.client.post(reverse("contract_edit", args=[self.contract.pk]), {"number": "ПО-01", "signed_on": "2026-01-10", "total_amount": "1600.00", "currency": "USD", "vendor": "", "notes": ""})
        self.assertEqual(response.status_code, 302)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.currency, "BYN")
        self.assertEqual(self.contract.total_amount, Decimal("1600.00"))

    def renewal_payload(self, **kwargs):
        data = {"contract": self.contract.pk, "software": "Программа", "quantity": 12, "cost": "1100.00", "starts_on": "2027-01-07", "ends_on": "2028-01-06", "notes": "Продление"}
        data.update(kwargs)
        return data

    def test_renewal_keeps_previous_period_unchanged(self):
        previous = self.license()
        original = (previous.starts_on, previous.ends_on, Decimal(previous.cost), previous.quantity, previous.contract_id)
        response = self.client.post(f"/licenses/new/?renew={previous.pk}", self.renewal_payload())
        self.assertEqual(response.status_code, 302)
        previous.refresh_from_db()
        self.assertEqual(original, (previous.starts_on, previous.ends_on, previous.cost, previous.quantity, previous.contract_id))
        self.assertEqual(previous.renewal.previous_id, previous.pk)
        self.assertEqual([x.pk for x in previous.renewal.history()], [previous.pk, previous.renewal.pk])

    def test_second_renewal_follows_chain(self):
        first = self.license()
        second = self.license(previous=first, starts_on=date(2027, 1, 7), ends_on=date(2028, 1, 6))
        third = self.license(previous=second, starts_on=date(2028, 1, 7), ends_on=None, perpetual=True)
        self.assertEqual([x.pk for x in second.history()], [first.pk, second.pk, third.pk])

    def test_cannot_renew_same_period_twice(self):
        previous = self.license()
        for _ in range(2):
            response = self.client.post(f"/licenses/new/?renew={previous.pk}", self.renewal_payload())
            self.assertEqual(response.status_code, 302)
        self.assertEqual(License.objects.filter(previous=previous).count(), 1)

    def test_renewal_must_start_after_previous_start(self):
        previous = self.license()
        response = self.client.post(f"/licenses/new/?renew={previous.pk}", self.renewal_payload(starts_on="2025-01-01"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(License.objects.filter(previous=previous).exists())
        self.assertContains(response, "Новый период должен начинаться позже")

    def test_renewal_with_new_contract_in_one_save(self):
        previous = self.license()
        response = self.client.post(f"/contracts/new/?renew={previous.pk}", self.contract_payload(**{"positions-0-starts_on": "2027-01-07", "positions-0-ends_on": "2028-01-06"}))
        self.assertEqual(response.status_code, 302)
        next_item = License.objects.get(previous=previous)
        self.assertNotEqual(next_item.contract_id, previous.contract_id)
        self.assertEqual(next_item.contract.currency, "USD")
        self.assertEqual(next_item.contract.licenses.count(), 2)

    def test_editing_old_start_cannot_invert_history(self):
        first = self.license()
        self.license(previous=first, starts_on=date(2027, 1, 7), ends_on=date(2028, 1, 6))
        response = self.client.post(reverse("license_edit", args=[first.pk]), self.renewal_payload(starts_on="2027-01-08"))
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        self.assertEqual(first.starts_on, date(2026, 1, 1))

    def test_search_and_currency_and_expired_filters(self):
        expected = self.license(software="nanoCAD", ends_on=TODAY - timedelta(days=9))
        self.license(software="Другая программа", perpetual=True, ends_on=None)
        response = self.client.get("/", {"q": "nanocad", "currency": "BYN", "status": "expired"})
        self.assertEqual([x.pk for x in response.context["page_obj"]], [expected.pk])
        self.assertEqual(self.client.get("/", {"currency": "USD"}).context["filtered_count"], 0)

    def test_export_filters_and_formula_injection(self):
        self.license(software='=HYPERLINK("http://example.com")')
        self.license(software="Обычная программа", perpetual=True, ends_on=None)
        response = self.client.get("/export/", {"status": "attention"})
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1][0].startswith("'="))
        self.assertEqual(rows[1][2], "1000.10")
        self.assertEqual(rows[1][3], "BYN")

    def test_xss_is_escaped(self):
        self.license(software='<script>alert("x")</script>')
        response = self.client.get("/")
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_csrf_protection_and_logout_post_only(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post("/contracts/new/", self.contract_payload()).status_code, 403)
        self.assertEqual(client.get("/logout/").status_code, 405)

    def test_pages_render_with_records(self):
        first = self.license()
        second = self.license(previous=first, starts_on=date(2027, 1, 7), ends_on=date(2028, 1, 6))
        for path in ["/", "/contracts/", "/contracts/new/", f"/contracts/{self.contract.pk}/", f"/contracts/{self.contract.pk}/edit/",
            "/licenses/new/", f"/licenses/new/?renew={second.pk}", f"/licenses/{first.pk}/", f"/licenses/{first.pk}/edit/", "/notifications/", "/renewals/", "/account/password/"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_bootstrap_never_resets_changed_password(self):
        with patch.dict("os.environ", {"APP_USERNAME": "department", "APP_PASSWORD": "another-password-12345"}):
            call_command("bootstrap", stdout=io.StringIO())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("test-secret-password-42"))

    def test_contract_cannot_be_deleted_with_licenses(self):
        self.license()
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.contract.delete()
