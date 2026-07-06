from tortoise import fields, models
from fastapi_admin.models import AbstractAdmin

from app.models.notification import NotificationType
from app.models.storybook import StorybookStatus
from app.models.subscription import SubscriptionStatus
from app.models.user import UserRole


class User(models.Model):
    id = fields.UUIDField(pk=True)
    email = fields.CharField(max_length=255)
    hashed_password = fields.CharField(max_length=255)
    full_name = fields.CharField(max_length=255)
    age = fields.IntField(null=True)
    gender = fields.CharField(max_length=50, null=True)
    occupation = fields.CharField(max_length=255, null=True)
    fitness_goal = fields.TextField(null=True)
    profile_image = fields.TextField(null=True)
    reference_image = fields.TextField(null=True)
    role = fields.CharEnumField(UserRole)
    is_active = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"


class Admin(AbstractAdmin):
    class Meta:
        table = "admin"


class Storybook(models.Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.UUIDField()
    ai_book_id = fields.TextField(null=True)
    date = fields.DateField()
    status = fields.CharEnumField(StorybookStatus)
    pdf_url = fields.TextField(null=True)
    generated_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "storybooks"


class Subscription(models.Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.UUIDField()
    plan_name = fields.TextField()
    status = fields.CharEnumField(SubscriptionStatus)
    current_period_end = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "subscriptions"


class Notification(models.Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.UUIDField()
    title = fields.TextField()
    message = fields.TextField()
    type = fields.CharEnumField(NotificationType)
    is_read = fields.BooleanField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notifications"


class WeeklySummary(models.Model):
    id = fields.UUIDField(pk=True)
    user_id = fields.UUIDField()
    week_start = fields.DateField()
    week_end = fields.DateField()
    summary = fields.TextField()
    image_url = fields.TextField(null=True)
    generated_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "weekly_summaries"
