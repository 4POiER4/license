from datetime import timedelta
import os
from django.utils import timezone
from .models import License


def navigation(request):
    if not request.user.is_authenticated:
        return {}
    today = timezone.localdate()
    reminders = [item for item in License.objects.select_related("contract", "renewal").filter(perpetual=False, ends_on__gte=today - timedelta(days=5)).order_by("ends_on", "software") if item.needs_reminder_on(today)]
    return {"nav_reminders": reminders, "reminder_count": len(reminders), "today": today,
        "demo_mode": os.getenv("DEMO_MODE") == "1", "show_reminders": request.session.pop("show_reminders", False)}
