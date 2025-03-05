import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form

from AI.glee_agent import analyze_situation, analyze_situation_accent_purpose
from app.history.history_service import HistoryService
from app.suggester.suggester_request import (
    GenerateSuggestionRequest,
    SuggestionRequest,
    UpdateSuggestionTagsRequest,
)
from app.suggester.suggester_response import (
    AnalyzeImagesConversationResponse,
    SuggestionResponse,
    DeleteSuggestionResponse,
    GenerateSuggestion,
    GenerateSuggestionsResponse,
    SuggestionsResponse,
)
from app.core.enums import PurposeType
from app.suggester.suggester_service import SuggesterService
from app.user.user_document import UserDocument
from app.utils.jwt_handler import JwtHandler
from app.utils.models.suggestion import Suggestion

router = APIRouter(prefix="/suggester", tags=["suggester"])
logger = logging.getLogger(__name__)


@router.get("/recommend", response_model=SuggestionsResponse)
async def get_recommend_suggestions() -> SuggestionsResponse:
    suggestions = await SuggesterService.get_recommend_suggestions()
    suggestion_responses = [
        SuggestionResponse(
            id=str(suggestion.id),
            title=suggestion.title,
            tags=suggestion.tag,
            suggestion=suggestion.suggestion,
            updated_at=suggestion.updated_at,
            created_at=suggestion.created_at,
        )
        for suggestion in suggestions
    ]
    logger.info("Returning recommended suggestions")
    return SuggestionsResponse(
        suggestions=suggestion_responses,
    )


@router.post(
    "/analyze/image",
    summary="최대 사진 4장까지 보내면 AI 상황을 분석하여 대답함",
    response_model=AnalyzeImagesConversationResponse,
)
async def analyze_images(
    purpose: PurposeType = Form(...),
    image_file_1: Optional[UploadFile] = File(None),
    image_file_2: Optional[UploadFile] = File(None),
    image_file_3: Optional[UploadFile] = File(None),
    image_file_4: Optional[UploadFile] = File(None),
) -> AnalyzeImagesConversationResponse:

    logger.info("Received image analysis request")
    image_files = [file for file in [image_file_1, image_file_2, image_file_3, image_file_4] if file is not None]
    if len(image_files) > 4:
        raise HTTPException(status_code=400, detail="You can only upload up to 4 images.")

    elif len(image_files) == 0:
        raise HTTPException(status_code=400, detail="You must upload at least one image.")

    files_data = [(file.filename, await file.read()) for file in image_files]
    logger.info(f"Analyzing images for purpose: {purpose}")
    if purpose == PurposeType.PHOTO_RESPONSE:
        situation = analyze_situation(files_data)
        tone = ""
        usage = ""

    elif purpose == PurposeType.SIMILAR_VIBE_RESPONSE:
        situation, tone, usage = analyze_situation_accent_purpose(files_data)
    else:
        raise HTTPException(status_code=400, detail="Invalid purpose.")
    logger.info("Image analysis completed successfully")
    return AnalyzeImagesConversationResponse(situation=situation, tone=tone, usage=usage, purpose=purpose)


@router.post(
    "/generate",
    summary="상황, 말투, 용도, 상세 정보를 받아 AI 글을 생성하여 반환",
    response_model=GenerateSuggestionsResponse,
)
async def generate_suggestion(
    request: GenerateSuggestionRequest,
    user: UserDocument | None = Depends(JwtHandler.get_optional_current_user),  # ✅ JWT 인증된 사용자
) -> GenerateSuggestionsResponse:
    logger.info(f"Generating suggestions - User: {user.nickname if user else 'Guest'}, Request: {request}")

    suggestions, titles = await SuggesterService.generate_suggestions(
        situation=request.situation, tone=request.tone, usage=request.usage, detail=request.detail
    )

    result = [GenerateSuggestion(title=title, content=suggestion) for title, suggestion in zip(titles, suggestions)]

    logger.info(f"Generated suggestions - User: {user.nickname if user else 'Guest'}, Suggestions: {result}")

    if user:
        _suggestions = [Suggestion(title=suggestion.title, content=suggestion.content) for suggestion in result]
        await HistoryService.create_history(user.id, _suggestions)

    return GenerateSuggestionsResponse(suggestions=result)


@router.post("", response_model=SuggestionResponse, summary="유저가 생성한 글제안 - 저장")
async def save_suggestion(
    request: SuggestionRequest,
    user: UserDocument = Depends(JwtHandler.get_current_user),  # ✅ JWT 인증된 사용자
) -> SuggestionResponse:
    logger.info(f"User {user.id} is saving a suggestion: {request.title}")
    new_suggestion = await SuggesterService.create_suggestion(user.id, request.title, request.suggestion, request.tags)
    logger.info(f"Suggestion saved successfully with ID: {new_suggestion.id}")

    return SuggestionResponse(
        id=str(new_suggestion.id),
        title=new_suggestion.title,
        tags=new_suggestion.tag,
        suggestion=new_suggestion.suggestion,
        updated_at=new_suggestion.updated_at,
        created_at=new_suggestion.created_at,
    )


@router.get("/{suggestion_id}", response_model=SuggestionResponse, summary="글 제안 가져오기")
async def get_suggestion(
    suggestion_id: str,
    user: UserDocument = Depends(JwtHandler.get_current_user),  # ✅ JWT 인증된 사용자
) -> SuggestionResponse:
    logger.info(f"Fetching suggestion with ID: {suggestion_id}")
    suggestion = await SuggesterService.get_suggestion_by_id(suggestion_id)

    if not suggestion:
        logger.error(f"Suggestion with ID {suggestion_id} not found")
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # ✅ 사용자가 자신의 데이터만 조회할 수 있도록 제한
    if suggestion.user_id != user.id:
        logger.error(f"Unauthorized access attempt by user {user.id} for suggestion {suggestion_id}")

        raise HTTPException(status_code=403, detail="Access denied")
    logger.info(f"Suggestion {suggestion_id} fetched successfully")

    return SuggestionResponse(
        id=str(suggestion.id),
        title=suggestion.title,
        tags=suggestion.tag,
        suggestion=suggestion.suggestion,
        updated_at=suggestion.updated_at,
        created_at=suggestion.created_at,
    )


@router.get("/user/me", response_model=SuggestionsResponse, summary="내 글 제안 가져오기")
async def get_my_suggestions(
    user: UserDocument = Depends(JwtHandler.get_current_user),  # ✅ JWT 인증된 사용자
) -> SuggestionsResponse:
    logger.info(f"Fetching suggestions for user: {user.id}")

    my_suggestions = await SuggesterService.get_suggestions_by_user(user.id)
    suggestion_responses = [
        SuggestionResponse(
            id=str(my_suggestion.id),
            title=my_suggestion.title,
            tags=my_suggestion.tag,
            suggestion=my_suggestion.suggestion,
            updated_at=my_suggestion.updated_at,
            created_at=my_suggestion.created_at,
        )
        for my_suggestion in my_suggestions
    ]
    logger.info(f"Fetched {len(my_suggestions)} suggestions for user {user.id}")

    return SuggestionsResponse(
        suggestions=suggestion_responses,
    )


@router.get("/user/summary")
async def get_my_suggestions_summary(
    user: UserDocument = Depends(JwtHandler.get_current_user),  # ✅ JWT 인증된 사용자
) -> SuggestionsResponse:
    logger.info(f"Fetching summary for user: {user.id}")

    my_suggestions = await SuggesterService.get_suggestions_by_user(user.id)
    suggestion_responses = [
        SuggestionResponse(
            id=str(my_suggestion.id),
            title=my_suggestion.title,
            tags=[],
            suggestion=my_suggestion.suggestion,
            updated_at=my_suggestion.updated_at,
            created_at=my_suggestion.created_at,
        )
        for my_suggestion in my_suggestions
    ]
    logger.info(f"Fetched summary with {len(my_suggestions)} suggestions for user {user.id}")
    return SuggestionsResponse(
        suggestions=suggestion_responses,
    )


@router.put("/{suggestion_id}", response_model=SuggestionResponse, summary="내 글 제안 수정")
async def update_suggestion(
    request: SuggestionRequest,
    suggestion_id: str,
    user: UserDocument = Depends(JwtHandler.get_current_user),  # ✅ JWT 인증된 사용자
) -> SuggestionResponse:
    logger.info(f"User {user.id} requested to update suggestion {suggestion_id}")

    suggestion = await SuggesterService.get_suggestion_by_id(suggestion_id)

    if not suggestion:
        logger.error(f"Suggestion {suggestion_id} not found")

        raise HTTPException(status_code=404, detail="Suggestion not found")

    # ✅ 사용자가 자신의 데이터만 수정할 수 있도록 제한
    if suggestion.user_id != user.id:
        logger.error(f"Failed to update suggestion {suggestion_id}")
        raise HTTPException(status_code=403, detail="Access denied")

    updated_suggestion = await SuggesterService.update_suggestion(
        suggestion_id, request.title, request.suggestion, request.tags
    )

    if not updated_suggestion:
        logger.error(f"Failed to update suggestion {suggestion_id}")
        raise HTTPException(status_code=500, detail="Failed to delete suggestion")
    logger.info(f"Suggestion {suggestion_id} updated successfully")

    return SuggestionResponse(
        id=str(updated_suggestion.id),
        title=updated_suggestion.title,
        tags=updated_suggestion.tag,
        suggestion=updated_suggestion.suggestion,
        updated_at=updated_suggestion.updated_at,
        created_at=updated_suggestion.created_at,
    )


@router.delete("/{suggestion_id}", response_model=DeleteSuggestionResponse, summary="내 글 제안 삭제")
async def delete_suggestion(
    suggestion_id: str,
    user: UserDocument = Depends(JwtHandler.get_current_user),  # ✅ JWT 인증된 사용자
) -> DeleteSuggestionResponse:
    suggestion = await SuggesterService.get_suggestion_by_id(suggestion_id)
    logger.info(f"User {user.id} requested to delete suggestion {suggestion_id}")
    if not suggestion:
        logger.error(f"Suggestion {suggestion_id} not found")

        raise HTTPException(status_code=404, detail="Suggestion not found")

    # ✅ 사용자가 자신의 데이터만 삭제할 수 있도록 제한
    if suggestion.user_id != user.id:
        logger.error(f"Unauthorized delete attempt by user {user.id} on suggestion {suggestion_id}")

        raise HTTPException(status_code=403, detail="Access denied")

    success = await SuggesterService.delete_suggestion(suggestion_id)
    if not success:
        logger.error(f"Failed to delete suggestion {suggestion_id}")

        raise HTTPException(status_code=500, detail="Failed to delete suggestion")

    return DeleteSuggestionResponse(
        message="Suggestion deleted successfully",
        deleted_suggestion_id=suggestion_id,
    )


@router.put("/tag")
async def update_suggestion_tag(
    request: UpdateSuggestionTagsRequest, user: UserDocument = Depends(JwtHandler.get_current_user)
) -> SuggestionResponse:
    logger.info(f"User {user.id} requested to update tags for suggestion {request.suggestion_id}")

    suggestion = await SuggesterService.get_suggestion_by_id(request.suggestion_id)

    if not suggestion:
        logger.error(f"Suggestion {request.suggestion_id} not found")

        raise HTTPException(status_code=404, detail="Suggestion not found")

    if suggestion.user_id != user.id:
        logger.error(f"Unauthorized tag update attempt by user {user.id} on suggestion {request.suggestion_id}")

        raise HTTPException(status_code=403, detail="Access denied")

    updated_suggestion = await SuggesterService.update_suggestion_tags(request.suggestion_id, request.tags)
    logger.info(f"Tags updated successfully for suggestion {request.suggestion_id}")

    return SuggestionResponse(
        id=str(updated_suggestion.id),
        title=updated_suggestion.title,
        tags=updated_suggestion.tag,
        suggestion=updated_suggestion.suggestion,
        updated_at=updated_suggestion.updated_at,
        created_at=updated_suggestion.created_at,
    )
