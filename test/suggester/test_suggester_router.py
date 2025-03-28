from pathlib import Path

import pytest
from unittest.mock import patch, AsyncMock
from bson import ObjectId
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.enums import PurposeType, SuggestionTagType, ToneType, ContentLength
from app.suggester.suggester_document import SuggesterDocument
from app.user.user_document import UserDocument


@pytest.mark.asyncio
async def test_generate_suggestion_with_tone_usage_detail() -> None:
    data = {
        "situation": "카카오톡으로 사과하려는 상황이야",
        "tone": ToneType.FRIENDLY.value,
        "usage": "사과",
        "detail": "앞으로도 친하게 지내고 싶은 친구야",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/suggester/generate", json=data)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_generate_suggestion_with_situation() -> None:
    data = {
        "situation": "카카오톡으로 사과하려는 상황이야",
        "tone": "",
        "usage": "",
        "detail": "",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/suggester/generate", json=data)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_generate_suggestion_with_situation_usage_tone() -> None:
    data = {
        "situation": "카카오톡으로 사과하려는 상황이야",
        "tone": ToneType.FRIENDLY.value,
        "detail": "",
        "usage": "사과",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/suggester/generate", json=data)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_save_suggestion(auth_header: dict[str, str]) -> None:
    """유저가 생성한 ai 글제안 - 저장"""

    data = {"title": "Test Title", "tags": [SuggestionTagType.APOLOGY.value], "suggestion": "This is a test suggestion"}

    with patch(
        "app.suggester.suggester_service.SuggesterService.create_suggestion", new_callable=AsyncMock
    ) as mock_create_suggestion:
        mock_create_suggestion.return_value = AsyncMock(
            id=str(ObjectId()),
            tag=data["tags"],
            title=data["title"],
            suggestion=data["suggestion"],
            updated_at="2024-02-25T12:00:00",
            created_at="2024-02-25T12:00:00",
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/suggester", json=data, headers=auth_header)

    assert response.status_code == 200
    assert response.json()["suggestion"] == data["suggestion"]
    assert "id" in response.json()


@pytest.mark.asyncio
async def test_get_suggestion(exists_suggestion: SuggesterDocument, auth_header: dict[str, str]) -> None:
    """ID를 기반으로 ai 추천 데이터 가져오기"""

    with patch(
        "app.suggester.suggester_service.SuggesterService.get_suggestion_by_id", new_callable=AsyncMock
    ) as mock_get_suggestion:
        mock_get_suggestion.return_value = AsyncMock(
            id=exists_suggestion.id,
            user_id=exists_suggestion.user_id,
            tag=exists_suggestion.tag,
            title=exists_suggestion.title,
            suggestion=exists_suggestion.suggestion,
            updated_at=exists_suggestion.updated_at,
            created_at=exists_suggestion.created_at,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/suggester/{exists_suggestion.id}", headers=auth_header)

    assert response.status_code == 200
    assert response.json()["id"] == str(exists_suggestion.id)
    assert response.json()["title"] == exists_suggestion.title
    assert response.json()["suggestion"] == exists_suggestion.suggestion


@pytest.mark.asyncio
async def test_get_my_suggestions(auth_header: dict[str, str]) -> None:
    """현재 사용자의 모든 추천 데이터 가져오기"""
    with patch(
        "app.suggester.suggester_service.SuggesterService.get_suggestions_by_user", new_callable=AsyncMock
    ) as mock_get_my_suggestions:
        mock_get_my_suggestions.return_value = [
            AsyncMock(
                id=str(ObjectId()),
                tag=[SuggestionTagType.FAVORITES],
                title="First test",
                suggestion="First test",
                updated_at="2024-02-25T12:00:00",
                created_at="2024-02-25T12:00:00",
            ),
            AsyncMock(
                id=str(ObjectId()),
                tag=[SuggestionTagType.SCHOOL],
                title="Second test",
                suggestion="Second test",
                updated_at="2024-02-25T12:00:00",
                created_at="2024-02-25T12:00:00",
            ),
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/suggester/user/me", headers=auth_header)

    assert response.status_code == 200
    assert len(response.json()["suggestions"]) == 2


@pytest.mark.asyncio
async def test_delete_suggestion(exists_suggestion: SuggesterDocument, auth_header: dict[str, str]) -> None:
    """추천 데이터 삭제 테스트"""
    with (
        patch(
            "app.suggester.suggester_service.SuggesterService.get_suggestion_by_id", new_callable=AsyncMock
        ) as mock_get_suggestion,
        patch(
            "app.suggester.suggester_service.SuggesterService.delete_suggestion", new_callable=AsyncMock
        ) as mock_delete_suggestion,
    ):
        mock_get_suggestion.return_value = AsyncMock(
            id=exists_suggestion.id,
            title=exists_suggestion.title,
            tag=exists_suggestion.tag,
            user_id=exists_suggestion.user_id,
            suggestion=exists_suggestion.suggestion,
            updated_at=exists_suggestion.updated_at,
            created_at=exists_suggestion.created_at,
        )

        mock_delete_suggestion.return_value = True  # 삭제 성공

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(f"/suggester/{str(exists_suggestion.id)}", headers=auth_header)

    assert response.status_code == 200
    assert response.json()["message"] == "Suggestion deleted successfully"


@pytest.mark.asyncio
async def test_analyze_images_to_response_to_photo(test_image_path: Path, auth_header: dict[str, str]) -> None:

    # 파일을 바이너리 모드로 읽기
    with open(test_image_path, "rb") as f:
        image_data = f.read()

    # 업로드할 파일 리스트
    files = {
        "image_file_1": ("test_image.jpg", image_data, "image/png"),
        "image_file_2": ("test_image.jpg", image_data, "image/png"),
    }
    purpose_value = str(PurposeType.PHOTO_RESPONSE.value)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/suggester/analyze/image", files=files, data={"purpose": purpose_value}, headers=auth_header
        )

    assert response.status_code == 200
    assert response.json()["purpose"] == PurposeType.PHOTO_RESPONSE.value


@pytest.mark.asyncio
async def test_analyze_images_to_similar_vibe(test_image_path: Path, auth_header: dict[str, str]) -> None:

    # 파일을 바이너리 모드로 읽기
    with open(test_image_path, "rb") as f:
        image_data = f.read()

    # 업로드할 파일 리스트
    files = {
        "image_file_1": ("test_image.jpg", image_data, "image/png"),
        "image_file_2": ("test_image.jpg", image_data, "image/png"),
    }
    purpose_value = str(PurposeType.SIMILAR_VIBE_RESPONSE.value)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/suggester/analyze/image", files=files, data={"purpose": purpose_value}, headers=auth_header
        )

    assert response.status_code == 200
    assert response.json()["purpose"] == PurposeType.SIMILAR_VIBE_RESPONSE.value
    assert response.json()["tone"] != ""
    assert response.json()["usage"] != ""


@pytest.mark.asyncio
async def test_update_suggestion(test_user: UserDocument, auth_header: dict[str, str]) -> None:
    suggestion_id = str(ObjectId())
    suggestion = "Origin suggestion"
    update_suggestion = "Updated suggestion"
    title = "Test title"
    tags = [SuggestionTagType.FAVORITES]
    tags_str = [SuggestionTagType.FAVORITES.value]

    data = {"tags": tags_str, "suggestion": update_suggestion, "title": title}
    with (
        patch(
            "app.suggester.suggester_service.SuggesterService.update_suggestion", new_callable=AsyncMock
        ) as mock_update_suggestion,
        patch(
            "app.suggester.suggester_service.SuggesterService.get_suggestion_by_id", new_callable=AsyncMock
        ) as mock_get_suggestion,
    ):

        mock_update_suggestion.return_value = AsyncMock(
            id=ObjectId(suggestion_id),
            tag=tags,
            title=title,
            suggestion=update_suggestion,
            updated_at="2024-02-25T12:00:00",
            created_at="2024-02-25T12:00:00",
            user_id=test_user.id,
        )
        mock_get_suggestion.return_value = AsyncMock(
            id=ObjectId(suggestion_id),
            tag=tags,
            title=title,
            suggestion=suggestion,
            updated_at="2024-02-25T12:00:00",
            created_at="2024-02-25T12:00:00",
            user_id=test_user.id,
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.put(f"/suggester/{suggestion_id}", json=data, headers=auth_header)

    assert response.status_code == 200
    assert response.json()["suggestion"] == update_suggestion
    assert response.json()["tags"] == tags_str


@pytest.mark.asyncio
async def test_get_recommend_suggestion(exists_suggestion: SuggesterDocument) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/suggester/recommend")

    assert response.status_code == 200
    assert response.json()["suggestions"] != []
    assert response.json()["suggestions"][0]["id"] == str(exists_suggestion.id)


@pytest.mark.asyncio
async def test_search(exists_suggestion: SuggesterDocument, auth_header: dict[str, str]) -> None:
    """본문에 'Test' 단어가 포함된 제안 검색 테스트"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/suggester/search",
            params={"query": "Test"},  # ✅ 검색할 단어
            headers=auth_header,
        )

    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data, "Response should contain 'suggestions' key"
    assert len(data["suggestions"]) > 0, "At least one suggestion should be found"

    for suggestion in data["suggestions"]:
        assert "Test" in suggestion["suggestion"], "Suggestion content should contain 'Test'"


@pytest.mark.asyncio
async def test_get_suggestion_counts(exists_suggestion: SuggesterDocument, auth_header: dict[str, str]) -> None:
    """본문에 'Test' 단어가 포함된 제안 검색 테스트"""

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/suggester/count",
            headers=auth_header,
        )

    assert response.status_code == 200
    data = response.json()
    assert "user_suggestion_count" in data and "recommended_suggestion_count" in data
    assert int(data["user_suggestion_count"]) > 0
    assert int(data["recommended_suggestion_count"]) > 0


@pytest.mark.asyncio
async def test_regenerate_suggestion(auth_header: dict[str, str]) -> None:

    data = {
        "exist_suggestion": "내가 저번에 한 말 때문에 상처 받았다면 정말 미안해. 내가 너무 생각없이 말한 것 같아. 다신 이런일 없도록 조심할게",
        "length": ContentLength.EXTEND.value,
        "detail": "앞으로 잘 지내자는 내용을 추가 해줘",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/suggester/regenerate",
            headers=auth_header,
            json=data,
        )

    assert response.status_code == 200
    data = response.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0
