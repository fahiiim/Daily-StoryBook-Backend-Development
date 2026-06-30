import asyncio
from typing import Any

import httpx
from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.ai import RegenerateImageRequest, RegeneratePageRequest, StorybookGenerateRequest

logger = get_logger(__name__)


class AIServiceError(Exception):
    pass


class AIServiceConfigError(AIServiceError):
    pass


class AIServiceTimeoutError(AIServiceError):
    pass


class AIServiceConnectionError(AIServiceError):
    pass


class AIServiceResponseError(AIServiceError):
    def __init__(self, *, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AIService:
    def __init__(self) -> None:
        self.base_url = settings.ai_backend_base_url.rstrip("/")
        self.timeout_seconds = settings.ai_backend_timeout_seconds
        self.max_retries = max(0, settings.ai_backend_max_retries)
        self.retry_backoff_seconds = max(0.0, settings.ai_backend_retry_backoff_seconds)

        if not self.base_url.startswith(("http://", "https://")):
            raise AIServiceConfigError("AI_BACKEND_BASE_URL must start with http:// or https://")

    async def generate_storybook(
        self,
        *,
        payload: StorybookGenerateRequest,
        selfie: UploadFile,
    ) -> dict[str, Any]:
        file_bytes = await selfie.read()
        files = {
            "selfie": (
                selfie.filename or "selfie.png",
                file_bytes,
                selfie.content_type or "application/octet-stream",
            )
        }
        form_data = {key: str(value) for key, value in payload.model_dump(exclude_none=True).items()}

        response_data = await self._request_with_retry(
            method="POST",
            path="/storybook/generate",
            data=form_data,
            files=files,
        )
        return self._ensure_json_response(response_data)

    async def get_storybook(self, *, book_id: str) -> dict[str, Any]:
        response_data = await self._request_with_retry(
            method="GET",
            path=f"/storybook/{book_id}",
        )
        return self._ensure_json_response(response_data)

    async def get_storybook_page(self, *, book_id: str, page_number: int) -> dict[str, Any]:
        response_data = await self._request_with_retry(
            method="GET",
            path=f"/storybook/{book_id}/page/{page_number}",
        )
        return self._ensure_json_response(response_data)

    async def regenerate_page(
        self,
        *,
        book_id: str,
        page_number: int,
        payload: RegeneratePageRequest,
    ) -> dict[str, Any]:
        response_data = await self._request_with_retry(
            method="POST",
            path=f"/storybook/{book_id}/page/{page_number}/regenerate",
            json=payload.model_dump(exclude_none=True),
        )
        return self._ensure_json_response(response_data)

    async def regenerate_image(
        self,
        *,
        book_id: str,
        page_number: int,
        payload: RegenerateImageRequest,
    ) -> dict[str, Any]:
        response_data = await self._request_with_retry(
            method="POST",
            path=f"/storybook/{book_id}/page/{page_number}/image",
            json=payload.model_dump(exclude_none=True),
        )
        return self._ensure_json_response(response_data)

    async def rebuild_pdf(self, *, book_id: str) -> dict[str, Any]:
        response_data = await self._request_with_retry(
            method="POST",
            path=f"/storybook/{book_id}/rebuild-pdf",
        )
        return self._ensure_json_response(response_data)

    async def _request_with_retry(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"

        for attempt in range(self.max_retries + 1):
            try:
                timeout = httpx.Timeout(self.timeout_seconds)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        json=json,
                        data=data,
                        files=files,
                    )

                if response.status_code >= 500 and attempt < self.max_retries:
                    await self._sleep_before_retry(attempt=attempt)
                    continue

                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                return response.text
            except httpx.TimeoutException as exc:
                logger.warning("ai_request_timeout", attempt=attempt, url=url)
                if attempt < self.max_retries:
                    await self._sleep_before_retry(attempt=attempt)
                    continue
                raise AIServiceTimeoutError("AI service request timed out") from exc
            except httpx.RequestError as exc:
                logger.warning("ai_request_network_error", attempt=attempt, url=url, error=str(exc))
                if attempt < self.max_retries:
                    await self._sleep_before_retry(attempt=attempt)
                    continue
                raise AIServiceConnectionError("Failed to connect to AI service") from exc
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code >= 500 and attempt < self.max_retries:
                    await self._sleep_before_retry(attempt=attempt)
                    continue

                error_body = self._read_error_body(exc.response)
                logger.warning(
                    "ai_request_http_error",
                    status_code=status_code,
                    url=url,
                    error=error_body,
                )
                raise AIServiceResponseError(
                    status_code=status_code,
                    detail=error_body,
                ) from exc

        raise AIServiceError("Unexpected AI service error")

    async def _sleep_before_retry(self, *, attempt: int) -> None:
        backoff = self.retry_backoff_seconds * (2**attempt)
        if backoff > 0:
            await asyncio.sleep(backoff)

    @staticmethod
    def _read_error_body(response: httpx.Response) -> str:
        try:
            data = response.json()
            return str(data)
        except ValueError:
            return response.text or "AI backend error"

    @staticmethod
    def _ensure_json_response(data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            return data
        raise AIServiceError("AI backend returned a non-JSON response")