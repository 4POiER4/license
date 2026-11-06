import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import IntegrityError, connection, transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import ContractForm, ContractLicenseFormSet, LicenseForm
from .models import Contract, License


class DepartmentLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        result = super().form_valid(form)
        self.request.session["show_reminders"] = True
        return result


@require_GET
def health(request):
    try:
        connection.ensure_connection()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def license_queryset():
    return License.objects.select_related("contract", "previous", "renewal").order_by("perpetual", "ends_on", "software", "id")


def filtered_licenses(request, rows):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    currency = request.GET.get("currency", "")
    today = timezone.localdate()
    if query:
        rows = rows.filter(Q(software__icontains=query) | Q(contract__number__icontains=query) | Q(contract__vendor__icontains=query))
    if currency in Contract.Currency.values:
        rows = rows.filter(contract__currency=currency)
    rows = list(rows)
    if status == "attention":
        rows = [row for row in rows if row.needs_reminder_on(today)]
    elif status in {"active", "expiring", "expired", "perpetual", "future"}:
        rows = [row for row in rows if row.status_on(today) == status]
    return rows


@login_required
def dashboard(request):
    all_rows = list(license_queryset())
    today = timezone.localdate()
    stats = {"total": len(all_rows), "active": sum(x.status_on(today) in {"active", "expiring"} for x in all_rows),
        "perpetual": sum(x.perpetual for x in all_rows), "expired": sum(x.status_on(today) == "expired" for x in all_rows),
        "attention": sum(x.needs_reminder_on(today) for x in all_rows), "contracts": Contract.objects.count()}
    rows = filtered_licenses(request, license_queryset())
    return render(request, "registry/dashboard.html", {"section": "dashboard", "stats": stats,
        "page_obj": Paginator(rows, 30).get_page(request.GET.get("page")), "filtered_count": len(rows),
        "currencies": Contract.Currency.choices, "title": "Реестр лицензий"})


@login_required
def contracts(request):
    rows = Contract.objects.prefetch_related("licenses")
    query = request.GET.get("q", "").strip()
    if query:
        rows = rows.filter(Q(number__icontains=query) | Q(vendor__icontains=query))
    totals = Contract.objects.values("currency").annotate(amount=Sum("total_amount")).order_by("currency")
    return render(request, "registry/contracts.html", {"section": "contracts", "title": "Договоры", "totals": totals,
        "page_obj": Paginator(rows, 30).get_page(request.GET.get("page"))})


@login_required
def contract_detail(request, pk):
    contract = get_object_or_404(Contract.objects.prefetch_related("licenses__renewal"), pk=pk)
    return render(request, "registry/contract_detail.html", {"contract": contract, "section": "contracts", "title": f"Договор № {contract.number}"})


@login_required
def contract_create(request):
    previous = None
    initial_positions = None
    if request.GET.get("renew"):
        previous = get_object_or_404(License, pk=request.GET["renew"])
        if previous.has_renewal:
            messages.info(request, "У этой записи уже есть продление.")
            return redirect("license_detail", pk=previous.renewal.pk)
        initial_positions = [{"software": previous.software, "quantity": previous.quantity,
            "starts_on": max(timezone.localdate(), (previous.ends_on or timezone.localdate()) + timedelta(days=1))}]
    form = ContractForm(request.POST if request.method == "POST" else None, initial={"signed_on": timezone.localdate()})
    formset = ContractLicenseFormSet(request.POST if request.method == "POST" else None, prefix="positions", initial=initial_positions)
    if previous:
        for position in formset.forms:
            if request.POST.get(position.add_prefix("DELETE")) not in {"on", "true", "1"}:
                position.instance.previous = previous
                break
    if request.method == "POST":
        form_valid, positions_valid = form.is_valid(), formset.is_valid()
        if form_valid and positions_valid:
            try:
                with transaction.atomic():
                    if previous:
                        locked = License.objects.select_for_update().get(pk=previous.pk)
                        if locked.has_renewal:
                            raise IntegrityError("Already renewed")
                    contract = form.save()
                    formset.instance = contract
                    formset.save()
                messages.success(request, "Договор и все позиции ПО сохранены. История продления сохранена." if previous else "Договор и все позиции ПО сохранены.")
                return redirect("contract_detail", pk=contract.pk)
            except IntegrityError:
                form.add_error(None, "Договор или продление уже были созданы другим сотрудником. Обновите страницу.")
    return render(request, "registry/contract_form.html", {"form": form, "formset": formset, "previous": previous,
        "section": "contracts", "title": "Продление по новому договору" if previous else "Новый договор"})


@login_required
def contract_edit(request, pk):
    contract = get_object_or_404(Contract, pk=pk)
    form = ContractForm(request.POST if request.method == "POST" else None, instance=contract)
    # Prices already recorded in this currency must not silently change meaning.
    form.fields["currency"].disabled = True
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Данные договора обновлены.")
        return redirect("contract_detail", pk=pk)
    return render(request, "registry/contract_form.html", {"form": form, "contract": contract, "section": "contracts", "title": "Редактирование договора"})


@login_required
def license_create(request):
    previous = None
    if request.GET.get("renew"):
        previous = get_object_or_404(License, pk=request.GET["renew"])
        if previous.has_renewal:
            messages.info(request, "У этой записи уже есть продление. Откройте последний период в истории.")
            return redirect("license_detail", pk=previous.renewal.pk)
    initial = {"starts_on": timezone.localdate(), "quantity": 1}
    if request.GET.get("contract"):
        initial["contract"] = get_object_or_404(Contract, pk=request.GET["contract"])
    if previous:
        initial.update({"software": previous.software, "quantity": previous.quantity, "contract": previous.contract,
            "starts_on": max(timezone.localdate(), (previous.ends_on or timezone.localdate()) + timedelta(days=1))})
    form = LicenseForm(request.POST if request.method == "POST" else None, initial=initial)
    if previous:
        form.instance.previous = previous
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if previous:
                    previous = License.objects.select_for_update().get(pk=previous.pk)
                    if previous.has_renewal:
                        raise IntegrityError("Already renewed")
                item = form.save()
            messages.success(request, "Продление сохранено. Предыдущий период остался в истории." if previous else "Лицензия добавлена.")
            return redirect("license_detail", pk=item.pk)
        except IntegrityError:
            form.add_error(None, "Запись уже была продлена другим сотрудником. Обновите страницу.")
    return render(request, "registry/license_form.html", {"form": form, "previous": previous, "section": "dashboard", "title": "Продление лицензии" if previous else "Новая лицензия"})


@login_required
def license_edit(request, pk):
    item = get_object_or_404(License, pk=pk)
    form = LicenseForm(request.POST if request.method == "POST" else None, instance=item)
    if request.method == "POST" and form.is_valid():
        if item.has_renewal and form.cleaned_data["starts_on"] >= item.renewal.starts_on:
            form.add_error("starts_on", "Этот период должен начинаться раньше следующего продления.")
        else:
            form.save()
            messages.success(request, "Данные лицензии обновлены.")
            return redirect("license_detail", pk=pk)
    return render(request, "registry/license_form.html", {"form": form, "item": item, "section": "dashboard", "title": "Редактирование лицензии"})


@login_required
def license_detail(request, pk):
    item = get_object_or_404(license_queryset(), pk=pk)
    return render(request, "registry/license_detail.html", {"item": item, "history": item.history(), "section": "dashboard", "title": item.software})


@login_required
def notifications(request):
    return render(request, "registry/notifications.html", {"section": "notifications", "title": "Уведомления"})


@login_required
def renewals(request):
    rows = license_queryset().filter(previous__isnull=False).order_by("-created_at")
    return render(request, "registry/renewals.html", {"section": "renewals", "title": "История продлений", "page_obj": Paginator(rows, 30).get_page(request.GET.get("page"))})


def csv_safe(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@login_required
def export_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="licenses.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(["ПО", "Количество", "Стоимость позиции", "Валюта", "Номер договора", "Дата договора", "Сумма договора", "Контрагент", "Начало", "Окончание", "Бессрочная", "Статус", "Предыдущая запись"])
    for row in filtered_licenses(request, license_queryset()):
        writer.writerow([csv_safe(row.software), row.quantity, row.cost, row.contract.currency, csv_safe(row.contract.number),
            row.contract.signed_on, row.contract.total_amount, csv_safe(row.contract.vendor), row.starts_on,
            row.ends_on or "", "Да" if row.perpetual else "Нет", row.status_label, row.previous_id or ""])
    return response
