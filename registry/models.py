import calendar
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


def months_before(value, count=2):
    """Calendar months, clamped to the last day when the target month is shorter."""
    month_index = value.year * 12 + value.month - 1 - count
    year, month = divmod(month_index, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


class Contract(models.Model):
    class Currency(models.TextChoices):
        BYN = "BYN", "BYN · Белорусский рубль"
        RUB = "RUB", "RUB · Российский рубль"
        USD = "USD", "USD · Доллар США"

    number = models.CharField("Номер договора", max_length=100)
    signed_on = models.DateField("Дата заключения")
    vendor = models.CharField("Контрагент", max_length=200, blank=True)
    currency = models.CharField("Валюта договора", max_length=3, choices=Currency.choices, default=Currency.BYN)
    total_amount = models.DecimalField("Общая сумма договора", max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    notes = models.TextField("Примечание", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-signed_on", "-id"]
        constraints = [models.UniqueConstraint(fields=["number", "signed_on"], name="unique_contract_number_date"),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="contract_amount_nonnegative")]

    def __str__(self):
        return f"№ {self.number} от {self.signed_on:%d.%m.%Y} · {self.currency}"

    @property
    def positions_total(self):
        return sum((item.cost for item in self.licenses.all()), Decimal("0.00"))

    @property
    def difference(self):
        return self.total_amount - self.positions_total


class License(models.Model):
    contract = models.ForeignKey(Contract, on_delete=models.PROTECT, related_name="licenses", verbose_name="Договор")
    software = models.CharField("Название ПО", max_length=200)
    quantity = models.PositiveIntegerField("Количество лицензий", validators=[MinValueValidator(1)])
    cost = models.DecimalField("Стоимость всей позиции", max_digits=16, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    starts_on = models.DateField("Начало действия")
    perpetual = models.BooleanField("Бессрочная лицензия", default=False)
    ends_on = models.DateField("Окончание действия", null=True, blank=True)
    previous = models.OneToOneField("self", on_delete=models.PROTECT, null=True, blank=True, related_name="renewal", verbose_name="Предыдущая лицензия")
    notes = models.TextField("Примечание", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["software", "-starts_on", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="license_quantity_positive"),
            models.CheckConstraint(condition=Q(cost__gte=0), name="license_cost_nonnegative"),
            models.CheckConstraint(condition=(Q(perpetual=True, ends_on__isnull=True) | Q(perpetual=False, ends_on__isnull=False, ends_on__gte=models.F("starts_on"))), name="license_valid_period"),
        ]

    def __str__(self):
        return self.software

    def clean(self):
        super().clean()
        errors = {}
        if self.perpetual:
            self.ends_on = None
        elif not self.ends_on:
            errors["ends_on"] = "Укажите дату окончания или выберите бессрочную лицензию."
        elif self.starts_on and self.ends_on < self.starts_on:
            errors["ends_on"] = "Дата окончания не может быть раньше даты начала."
        if self.previous_id:
            if self.previous_id == self.pk:
                errors["previous"] = "Нельзя продлить лицензию самой собой."
            elif self.starts_on and self.previous.starts_on >= self.starts_on:
                errors["starts_on"] = "Новый период должен начинаться позже предыдущего."
        if errors:
            raise ValidationError(errors)

    def status_on(self, today):
        if self.starts_on > today:
            return "future"
        if self.perpetual:
            return "perpetual"
        if self.ends_on < today:
            return "expired"
        if months_before(self.ends_on) <= today:
            return "expiring"
        return "active"

    def needs_reminder_on(self, today):
        # Reminders depend on the end date, including for a purchased future period.
        return bool(not self.perpetual and self.ends_on and months_before(self.ends_on) <= today <= self.ends_on + timedelta(days=5))

    @property
    def status(self):
        return self.status_on(timezone.localdate())

    @property
    def status_label(self):
        return {"future": "Ещё не началась", "perpetual": "Бессрочная", "expired": "Срок истёк", "expiring": "Истекает", "active": "Действует"}[self.status]

    @property
    def days_remaining(self):
        return (self.ends_on - timezone.localdate()).days if self.ends_on else None

    @property
    def is_red(self):
        return bool(not self.perpetual and self.ends_on and months_before(self.ends_on) <= timezone.localdate())

    @property
    def has_renewal(self):
        return hasattr(self, "renewal")

    def history(self):
        chain, node, seen = [], self, set()
        while node.previous_id and node.pk not in seen:
            seen.add(node.pk)
            node = node.previous
        seen.clear()
        while node and node.pk not in seen:
            seen.add(node.pk)
            chain.append(node)
            node = getattr(node, "renewal", None)
        return chain
