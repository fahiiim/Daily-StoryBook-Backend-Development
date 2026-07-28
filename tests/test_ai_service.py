import pytest

from app.services.ai_service import AIService


class _DummyUploadFile:
    def __init__(self) -> None:
        self.filename = "selfie.png"
        self.content_type = "image/png"

    async def read(self) -> bytes:
        return b"image-bytes"


@pytest.mark.asyncio
async def test_generate_storybook_from_backend_uses_non_duplicated_path(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AIService()
    captured: dict[str, str] = {}

    async def _fake_request_with_retry(*, method: str, path: str, json=None, data=None, files=None):
        _ = method
        _ = json
        _ = data
        _ = files
        captured["path"] = path
        return {"ok": True}

    monkeypatch.setattr(service, "_request_with_retry", _fake_request_with_retry)

    await service.generate_storybook_from_backend(
        context_json="{}",
        selfie=_DummyUploadFile(),
    )

    assert captured["path"] == "/storybook/generate/from-backend"
