from __future__ import annotations

import csv
import hmac
import io
import secrets
from hashlib import sha256
from typing import cast
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi_admin.template import templates
from fastapi_admin.utils import check_password
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.dashboard_data import (
    AdminDashboardData,
    AdminDashboardNotFoundError,
    initials,
)
from app.admin.tortoise_models import Admin, AdminProfile
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.coach_client import CoachClient, CoachClientStatus
from app.models.storybook import Storybook
from app.models.user import User
from app.repositories.coach_client_repository import CoachClientRepository
from app.repositories.nutrition_plan_repository import NutritionPlanRepository
from app.repositories.routine_macro_log_repository import RoutineMacroLogRepository
from app.repositories.routine_repository import RoutineRepository
from app.repositories.storybook_repository import StorybookRepository, StoryPageRepository
from app.repositories.user_repository import UserRepository
from app.services.ai_service import AIService
from app.services.email_service import EmailService
from app.services.storage_service import StorageService, StorageServiceError
from app.services.storybook_service import (
    StorybookGenerationJob,
    StorybookService,
    StorybookServiceError,
)

router = APIRouter()
_RESET_TOKEN_PREFIX = "admin:password-reset:"


def _current_admin(request: Request) -> Admin | None:
    return getattr(request.state, "admin", None)


def _login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(
        url=f"{request.app.admin_path}/login",
        status_code=303,
    )


def _redirect(request: Request, path: str, *, notice: str | None = None) -> RedirectResponse:
    target = f"{request.app.admin_path}{path}"
    if notice:
        separator = "&" if "?" in target else "?"
        target = f"{target}{separator}notice={quote(notice)}"
    return RedirectResponse(url=target, status_code=303)


def _days(value: int) -> int:
    return value if value in {7, 30, 90} else 7


def _csrf_token(request: Request) -> str:
    session_token = request.cookies.get("access_token", "")
    return hmac.new(
        settings.secret_key.encode(),
        session_token.encode(),
        sha256,
    ).hexdigest()


def _csrf_valid(request: Request, submitted: str) -> bool:
    return hmac.compare_digest(_csrf_token(request), submitted)


def _template_response(
    name: str,
    context: dict[str, object],
    *,
    status_code: int = 200,
) -> Response:
    return cast(
        Response,
        templates.TemplateResponse(
            name,
            context=context,
            status_code=status_code,
        ),
    )


async def _admin_profile(admin: Admin) -> AdminProfile:
    profile = await AdminProfile.get_or_none(admin_id=admin.id)
    if profile is not None:
        return profile
    default_email = admin.username if "@" in admin.username else ""
    return await AdminProfile.create(
        admin_id=admin.id,
        display_name="Storybook Admin",
        email=default_email,
    )


async def _page_context(
    request: Request,
    *,
    data: AdminDashboardData,
    section: str,
    title: str,
    days: int = 7,
) -> dict[str, object] | None:
    admin = _current_admin(request)
    if admin is None:
        return None
    profile = await _admin_profile(admin)
    return {
        "request": request,
        "title": title,
        "current_section": section,
        "days": _days(days),
        "admin_profile": profile,
        "admin_initials": initials(profile.display_name),
        "csrf_token": _csrf_token(request),
        "notice": request.query_params.get("notice"),
        **data.navigation(),
    }


def _storybook_service(db: Session) -> StorybookService:
    return StorybookService(
        db=db,
        ai_service=AIService(),
        storybook_repository=StorybookRepository(db),
        story_page_repository=StoryPageRepository(db),
        routine_repository=RoutineRepository(db),
        routine_macro_log_repository=RoutineMacroLogRepository(db),
        nutrition_plan_repository=NutritionPlanRepository(db),
        user_repository=UserRepository(db),
        coach_client_repository=CoachClientRepository(db),
    )


async def _create_storybook_job(db: Session, client_id: UUID) -> StorybookGenerationJob:
    relationship = db.scalar(
        select(CoachClient)
        .where(
            CoachClient.client_id == client_id,
            CoachClient.status == CoachClientStatus.ACCEPTED,
        )
        .order_by(CoachClient.created_at.desc())
    )
    if relationship is None:
        raise StorybookServiceError("Client has no accepted coach assignment")
    coach = db.get(User, relationship.coach_id)
    if coach is None:
        raise StorybookServiceError("Assigned coach was not found")
    return await _storybook_service(db).create_storybook_generation(
        current_coach=coach,
        client_id=client_id,
        selfie=None,
        wake_up_time=None,
        bed_time=None,
        image_style=None,
        name=None,
        age=None,
        gender=None,
        fitness_goal=None,
        height=None,
        weight=None,
        target_weight=None,
        bio=None,
        fitness_motivation=None,
    )


async def _process_storybook_job(job: StorybookGenerationJob) -> None:
    with SessionLocal() as db:
        await _storybook_service(db).process_storybook_generation(job=job)


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request, days: int = 7) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    with SessionLocal() as db:
        data = AdminDashboardData(db)
        context = await _page_context(
            request,
            data=data,
            section="overview",
            title="Overview | Storybook Pro",
            days=days,
        )
        assert context is not None
        context.update(data.overview(days=_days(days)))
    return _template_response("dashboard.html", context)


@router.get("/clients", response_class=HTMLResponse)
async def clients(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    days: int = 7,
) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    with SessionLocal() as db:
        data = AdminDashboardData(db)
        context = await _page_context(
            request,
            data=data,
            section="clients",
            title="Clients | Storybook Pro",
            days=days,
        )
        assert context is not None
        context.update(
            {
                "clients": data.list_clients(
                    search=q,
                    status_filter=status,
                    days=_days(days),
                ),
                "search": q or "",
                "status_filter": status or "",
            }
        )
    return _template_response("clients.html", context)


@router.get("/clients/{client_id}", response_class=HTMLResponse)
async def client_profile(request: Request, client_id: UUID, days: int = 7) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    try:
        with SessionLocal() as db:
            data = AdminDashboardData(db)
            context = await _page_context(
                request,
                data=data,
                section="clients",
                title="Client profile | Storybook Pro",
                days=days,
            )
            assert context is not None
            context["client"] = data.get_client(client_id=client_id, days=_days(days))
    except AdminDashboardNotFoundError:
        return _redirect(request, "/clients", notice="Client not found")
    return _template_response("client_profile.html", context)


@router.get("/clients/{client_id}/weekly", response_class=HTMLResponse)
async def client_weekly(request: Request, client_id: UUID, days: int = 7) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    try:
        with SessionLocal() as db:
            data = AdminDashboardData(db)
            context = await _page_context(
                request,
                data=data,
                section="clients",
                title="Weekly overview | Storybook Pro",
                days=days,
            )
            assert context is not None
            context.update(data.weekly_overview(client_id=client_id))
    except AdminDashboardNotFoundError:
        return _redirect(request, "/clients", notice="Client not found")
    return _template_response("weekly_overview.html", context)


@router.get("/storybooks", response_class=HTMLResponse)
async def storybooks(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    days: int = 30,
) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    with SessionLocal() as db:
        data = AdminDashboardData(db)
        context = await _page_context(
            request,
            data=data,
            section="storybooks",
            title="Storybooks | Storybook Pro",
            days=days,
        )
        assert context is not None
        context.update(
            {
                "storybooks": data.list_storybooks(
                    search=q,
                    status_filter=status,
                    days=_days(days),
                ),
                "search": q or "",
                "status_filter": status or "",
            }
        )
    return _template_response("storybooks.html", context)


@router.get("/storybooks/bulk", response_class=HTMLResponse)
async def bulk_storybooks(request: Request, days: int = 7) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    with SessionLocal() as db:
        data = AdminDashboardData(db)
        context = await _page_context(
            request,
            data=data,
            section="storybooks",
            title="Bulk generate | Storybook Pro",
            days=days,
        )
        assert context is not None
        candidates = data.bulk_candidates()
        ready_count = sum(bool(candidate["ready"]) for candidate in candidates)
        context.update(
            {
                "candidates": candidates,
                "ready_count": ready_count,
                "total_pages": ready_count * 10,
                "estimated_minutes": ready_count * 2,
            }
        )
    return _template_response("bulk_storybooks.html", context)


@router.post("/storybooks/bulk")
async def generate_bulk_storybooks(
    request: Request,
    background_tasks: BackgroundTasks,
    client_ids: list[str] = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(request, "/storybooks/bulk", notice="Your session expired. Try again.")

    queued = 0
    errors = 0
    unique_ids = list(dict.fromkeys(client_ids))[:20]
    with SessionLocal() as db:
        for raw_id in unique_ids:
            try:
                job = await _create_storybook_job(db, UUID(raw_id))
            except (ValueError, StorybookServiceError):
                errors += 1
                continue
            background_tasks.add_task(_process_storybook_job, job)
            queued += 1
    notice = f"Queued {queued} storybook{'s' if queued != 1 else ''}"
    if errors:
        notice += f"; {errors} could not be queued"
    return _redirect(request, "/storybooks", notice=notice)


@router.post("/storybooks/{storybook_id}/regenerate")
async def regenerate_storybook(
    request: Request,
    background_tasks: BackgroundTasks,
    storybook_id: UUID,
    csrf_token: str = Form(...),
) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(request, "/storybooks", notice="Your session expired. Try again.")
    try:
        with SessionLocal() as db:
            storybook = db.get(Storybook, storybook_id)
            if storybook is None:
                raise StorybookServiceError("Storybook not found")
            job = await _create_storybook_job(db, storybook.user_id)
            background_tasks.add_task(_process_storybook_job, job)
    except StorybookServiceError as exc:
        return _redirect(request, "/storybooks", notice=str(exc))
    return _redirect(request, "/storybooks", notice="Storybook regeneration queued")


@router.post("/clients/{client_id}/generate")
async def generate_client_storybook(
    request: Request,
    background_tasks: BackgroundTasks,
    client_id: UUID,
    csrf_token: str = Form(...),
) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(
            request,
            f"/clients/{client_id}/weekly",
            notice="Your session expired. Try again.",
        )
    try:
        with SessionLocal() as db:
            job = await _create_storybook_job(db, client_id)
            background_tasks.add_task(_process_storybook_job, job)
    except StorybookServiceError as exc:
        return _redirect(request, f"/clients/{client_id}/weekly", notice=str(exc))
    return _redirect(
        request,
        f"/clients/{client_id}/weekly",
        notice="Storybook generation queued",
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    tab: str = "profile",
    days: int = 7,
) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    with SessionLocal() as db:
        data = AdminDashboardData(db)
        context = await _page_context(
            request,
            data=data,
            section="settings",
            title="Settings | Storybook Pro",
            days=days,
        )
        assert context is not None
        context["settings_tab"] = tab if tab in {"profile", "account"} else "profile"
    return _template_response("settings.html", context)


@router.post("/settings/profile")
async def update_profile(
    request: Request,
    display_name: str = Form(...),
    bio: str = Form(default=""),
    csrf_token: str = Form(...),
) -> Response:
    admin = _current_admin(request)
    if admin is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(request, "/settings", notice="Your session expired. Try again.")
    normalized_name = display_name.strip()
    if len(normalized_name) < 2:
        return _redirect(
            request,
            "/settings",
            notice="Display name must have at least 2 characters",
        )
    profile = await _admin_profile(admin)
    profile.display_name = normalized_name[:100]
    profile.bio = bio.strip()[:2000] or None  # type: ignore[assignment]
    await profile.save(update_fields=["display_name", "bio", "updated_at"])
    return _redirect(request, "/settings", notice="Profile saved")


@router.post("/settings/account")
async def update_account(
    request: Request,
    email: str = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    admin = _current_admin(request)
    if admin is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(
            request,
            "/settings?tab=account",
            notice="Your session expired. Try again.",
        )
    normalized_email = email.strip().lower()
    if "@" not in normalized_email or len(normalized_email) > 255:
        return _redirect(request, "/settings?tab=account", notice="Enter a valid email address")
    profile = await _admin_profile(admin)
    profile.email = normalized_email
    await profile.save(update_fields=["email", "updated_at"])
    return _redirect(request, "/settings?tab=account", notice="Email address updated")


@router.post("/settings/password")
async def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(...),
) -> Response:
    admin = _current_admin(request)
    if admin is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(
            request,
            "/settings?tab=account",
            notice="Your session expired. Try again.",
        )
    if not check_password(current_password, admin.password):
        return _redirect(request, "/settings?tab=account", notice="Current password is incorrect")
    if len(new_password) < 8:
        return _redirect(
            request,
            "/settings?tab=account",
            notice="New password must have at least 8 characters",
        )
    if new_password != confirm_password:
        return _redirect(request, "/settings?tab=account", notice="New passwords do not match")
    admin.password = new_password
    await admin.save(update_fields=["password"])
    return _redirect(request, "/settings?tab=account", notice="Password updated")


@router.post("/settings/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    csrf_token: str = Form(...),
) -> Response:
    admin = _current_admin(request)
    if admin is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(request, "/settings", notice="Your session expired. Try again.")
    try:
        avatar_url = await StorageService().upload_image(
            file=file,
            folder="admin",
            user_id=UUID(int=admin.id),
        )
    except StorageServiceError as exc:
        return _redirect(request, "/settings", notice=str(exc))
    profile = await _admin_profile(admin)
    profile.avatar_url = avatar_url
    await profile.save(update_fields=["avatar_url", "updated_at"])
    return _redirect(request, "/settings", notice="Avatar updated")


@router.post("/settings/avatar/remove")
async def remove_avatar(
    request: Request,
    csrf_token: str = Form(...),
) -> Response:
    admin = _current_admin(request)
    if admin is None:
        return _login_redirect(request)
    if not _csrf_valid(request, csrf_token):
        return _redirect(request, "/settings", notice="Your session expired. Try again.")
    profile = await _admin_profile(admin)
    profile.avatar_url = None  # type: ignore[assignment]
    await profile.save(update_fields=["avatar_url", "updated_at"])
    return _redirect(request, "/settings", notice="Avatar removed")


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request) -> Response:
    return _template_response(
        "forgot_password.html",
        {
            "request": request,
            "title": "Reset password | Storybook Pro",
        },
    )


@router.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password(request: Request, email: str = Form(...)) -> Response:
    normalized_email = email.strip().lower()
    profile = await AdminProfile.get_or_none(email=normalized_email)
    debug_reset_url: str | None = None
    if profile is not None:
        token = secrets.token_urlsafe(32)
        await request.app.redis.set(
            f"{_RESET_TOKEN_PREFIX}{token}",
            str(profile.admin_id),
            ex=900,
        )
        reset_url = (
            f"{settings.app_public_base_url.rstrip('/')}"
            f"{request.app.admin_path}/reset-password?token={quote(token)}"
        )
        EmailService().send_email(
            to=normalized_email,
            subject="Reset your Storybook Pro password",
            body=f"Use this link within 15 minutes to reset your password: {reset_url}",
        )
        if settings.app_debug:
            debug_reset_url = reset_url
    return _template_response(
        "forgot_password.html",
        {
            "request": request,
            "title": "Reset password | Storybook Pro",
            "message": "If that email is registered, a reset link has been sent.",
            "debug_reset_url": debug_reset_url,
        },
    )


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str) -> Response:
    admin_id = await request.app.redis.get(f"{_RESET_TOKEN_PREFIX}{token}")
    return _template_response(
        "reset_password.html",
        {
            "request": request,
            "title": "Choose a password | Storybook Pro",
            "token": token,
            "valid": admin_id is not None,
        },
    )


@router.post("/reset-password")
async def reset_password(
    request: Request,
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> Response:
    key = f"{_RESET_TOKEN_PREFIX}{token}"
    admin_id = await request.app.redis.get(key)
    if admin_id is None:
        return _template_response(
            "reset_password.html",
            {
                "request": request,
                "title": "Choose a password | Storybook Pro",
                "token": token,
                "valid": False,
            },
            status_code=400,
        )
    if len(new_password) < 8 or new_password != confirm_password:
        return _template_response(
            "reset_password.html",
            {
                "request": request,
                "title": "Choose a password | Storybook Pro",
                "token": token,
                "valid": True,
                "error": ("Passwords must match and contain at least 8 characters."),
            },
            status_code=400,
        )
    admin = await Admin.get(id=int(admin_id))
    admin.password = new_password
    await admin.save(update_fields=["password"])
    await request.app.redis.delete(key)
    return RedirectResponse(
        url=f"{request.app.admin_path}/login?reset=1",
        status_code=303,
    )


@router.get("/export/{section}.csv")
async def export_csv(request: Request, section: str) -> Response:
    if _current_admin(request) is None:
        return _login_redirect(request)
    output = io.StringIO()
    writer = csv.writer(output)
    with SessionLocal() as db:
        data = AdminDashboardData(db)
        if section == "storybooks":
            writer.writerow(["ID", "Client", "Date", "Status", "Pages", "PDF URL"])
            writer.writerows(data.export_storybooks())
            filename = "storybook-export.csv"
        else:
            writer.writerow(["ID", "Name", "Email", "Goal", "Adherence %", "Status", "Last active"])
            writer.writerows(data.export_clients())
            filename = "client-export.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
