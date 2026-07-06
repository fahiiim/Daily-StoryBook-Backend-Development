from fastapi_admin.app import app
from fastapi_admin.resources import Model
from fastapi_admin.widgets import filters

from app.admin.tortoise_models import Notification, Storybook, Subscription, User, WeeklySummary
from app.models.storybook import StorybookStatus


@app.register
class UserResource(Model):
    label = "Users"
    model = User
    icon = "fas fa-user"
    filters = [
        filters.Search(
            name="email",
            label="Email",
            search_mode="contains",
            placeholder="Search by email",
        ),
        filters.Search(
            name="full_name",
            label="Name",
            search_mode="contains",
            placeholder="Search by name",
        ),
    ]
    fields = [
        "id",
        "email",
        "full_name",
        "role",
        "is_active",
        "created_at",
        "updated_at",
    ]


@app.register
class StorybookResource(Model):
    label = "Storybooks"
    model = Storybook
    icon = "fas fa-book"
    filters = [filters.Enum(name="status", label="Status", enum=StorybookStatus)]
    fields = [
        "id",
        "user_id",
        "date",
        "status",
        "pdf_url",
        "generated_at",
        "created_at",
        "updated_at",
    ]


@app.register
class WeeklySummaryResource(Model):
    label = "Weekly Summaries"
    model = WeeklySummary
    icon = "fas fa-calendar"
    fields = [
        "id",
        "user_id",
        "week_start",
        "week_end",
        "summary",
        "image_url",
        "generated_at",
        "created_at",
    ]


@app.register
class SubscriptionResource(Model):
    label = "Subscriptions"
    model = Subscription
    icon = "fas fa-credit-card"
    fields = [
        "id",
        "user_id",
        "plan_name",
        "status",
        "current_period_end",
        "created_at",
        "updated_at",
    ]


@app.register
class NotificationResource(Model):
    label = "Notifications"
    model = Notification
    icon = "fas fa-bell"
    fields = [
        "id",
        "user_id",
        "title",
        "message",
        "type",
        "is_read",
        "created_at",
    ]
