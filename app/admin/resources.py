from fastapi_admin.app import app
from fastapi_admin.resources import Action, Model, ToolbarAction
from fastapi_admin.widgets import filters
from starlette.requests import Request

from app.admin.tortoise_models import Notification, Storybook, Subscription, User
from app.models.storybook import StorybookStatus


class ReadOnlyResource:
    async def get_toolbar_actions(self, request: Request) -> list[ToolbarAction]:
        return []

    async def get_actions(self, request: Request) -> list[Action]:
        return []

    async def get_bulk_actions(self, request: Request) -> list[Action]:
        return []


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
        "phone_number",
        "role",
        "is_email_verified",
        "is_active",
        "created_at",
        "updated_at",
    ]

    async def get_toolbar_actions(self, request: Request) -> list[ToolbarAction]:
        return []

    async def get_bulk_actions(self, request: Request) -> list[Action]:
        return []

    async def get_actions(self, request: Request) -> list[Action]:
        return [action for action in await super().get_actions(request) if action.name == "update"]


@app.register
class StorybookResource(ReadOnlyResource, Model):
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
        "cover_image_url",
        "generated_at",
        "created_at",
        "updated_at",
    ]


@app.register
class SubscriptionResource(ReadOnlyResource, Model):
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
class NotificationResource(ReadOnlyResource, Model):
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
