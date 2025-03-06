# from fastapi import UploadFile
#
#
#
from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException

from AI.glee_agent import (
    generate_reply_suggestions_detail,
    generate_reply_suggestions_accent_purpose,
    generate_suggestions_situation,
)
from app.core.enums import SuggestionTagType
from app.suggester.suggester_collection import SuggesterCollection
from app.suggester.suggester_document import SuggesterDocument, SuggesterDTO


class SuggesterService:

    @staticmethod
    async def create_suggestion(
        user_id: ObjectId, title: str, suggestion: str, tag: list[SuggestionTagType]
    ) -> SuggesterDocument:
        """Suggestion 저장하기"""

        tag_str = [tag.value for tag in tag]
        suggestion_dto = SuggesterDTO(
            user_id=user_id,
            title=title,
            tag=tag_str,
            suggestion=suggestion,
            updated_at=datetime.now(),
            created_at=datetime.now(),
        )
        return await SuggesterCollection.create(suggestion_dto)

    @staticmethod
    async def get_suggestion_by_id(suggestion_id: str) -> SuggesterDocument:
        """ID를 기반으로 AI 추천 데이터 가져오기"""
        data = await SuggesterCollection.get_by_id(suggestion_id)
        if data is None or not data:
            raise HTTPException(status_code=404, detail="Suggestion not found")

        return SuggesterDocument(**data)

    @staticmethod
    async def get_suggestions_by_user(user_id: ObjectId) -> list[SuggesterDocument]:
        """특정 사용자의 모든 AI 추천 데이터 가져오기"""
        data_list = await SuggesterCollection.get_by_user(user_id)
        return [SuggesterDocument(**data) for data in data_list]

    @staticmethod
    async def delete_suggestion(suggestion_id: str) -> bool:
        """AI 추천 데이터 삭제"""
        return await SuggesterCollection.delete(suggestion_id)

    @staticmethod
    async def update_suggestion(
        suggestion_id: str, title: str, suggestion: str, tags: list[SuggestionTagType]
    ) -> SuggesterDocument:
        return await SuggesterCollection.update(suggestion_id, title, suggestion, tags)

    @staticmethod
    async def generate_suggestions(
        situation: str, tone: str | None = None, usage: str | None = None, detail: str | None = None
    ) -> tuple[list[str], list[str]]:
        if situation and tone and usage and detail:
            suggestions, title = generate_reply_suggestions_detail(situation, tone, usage, detail)
        elif situation and tone and usage:
            suggestions, title = generate_reply_suggestions_accent_purpose(situation, tone, usage)
        elif situation:
            suggestions, title = generate_suggestions_situation(situation)
        else:
            raise HTTPException(status_code=400, detail="Invalid Generate Suggestion Request")
        return suggestions, title

    @staticmethod
    async def update_suggestion_tags(
        suggestion_id: str,
        tags: list[SuggestionTagType],
    ) -> SuggesterDocument:
        return await SuggesterCollection.update_tag(suggestion_id, tags)

    @staticmethod
    async def get_recommend_suggestions(query: str | None) -> list[SuggesterDocument]:
        data_list = await SuggesterCollection.get_recommend_documents(query)
        return [SuggesterDocument(**data) for data in data_list]

    @staticmethod
    async def find_suggestions_by_text(query: str, user_id: ObjectId) -> list[SuggesterDocument] | None:
        """본문에 특정 텍스트가 포함된 문서 검색"""
        data_list = await SuggesterCollection.find_by_text(query, user_id)
        try:
            return [SuggesterDocument(**data) for data in data_list] if data_list else None
        except:
            raise HTTPException(status_code=404, detail="Suggestion not found")
