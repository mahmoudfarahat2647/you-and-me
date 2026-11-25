"""API routes for managing channel profiles."""
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.core.dto.channel_dto import (
    ChannelProfileResult,
    CreateChannelInput,
    UpdateChannelInput,
)
from src.core.entities.channel import ChannelValidationError
from src.core.ports.channel_repository import ChannelRepository
from src.core.use_cases.channel_use_cases import (
    ChannelNotFoundError,
    CreateChannelUseCase,
    DeleteChannelUseCase,
    GetChannelUseCase,
    ListChannelsUseCase,
    UpdateChannelUseCase,
)

router = APIRouter(prefix="/channels", tags=["channels"])


class CreateChannelRequest(BaseModel):
    name: str = Field(..., min_length=1)
    topic_focus: str = Field("")
    language: str = Field("Arabic")
    default_narrator: str = Field("arabic-narrator-v2")
    visual_style: str = Field("Cinematic Documentary")
    video_format: str = Field("16:9")
    budget_limit_usd: float = Field(10.0, ge=0.0)
    upload_destination: str = Field("YouTube")


class UpdateChannelRequest(BaseModel):
    name: Optional[str] = None
    topic_focus: Optional[str] = None
    language: Optional[str] = None
    default_narrator: Optional[str] = None
    visual_style: Optional[str] = None
    video_format: Optional[str] = None
    budget_limit_usd: Optional[float] = Field(None, ge=0.0)
    upload_destination: Optional[str] = None


class ChannelResponse(BaseModel):
    id: str
    name: str
    topic_focus: str
    language: str
    default_narrator: str
    visual_style: str
    video_format: str
    budget_limit_usd: float
    upload_destination: str
    created_at: str
    updated_at: str

    @classmethod
    def from_result(cls, res: ChannelProfileResult) -> "ChannelResponse":
        return cls(
            id=res.id,
            name=res.name,
            topic_focus=res.topic_focus,
            language=res.language,
            default_narrator=res.default_narrator,
            visual_style=res.visual_style,
            video_format=res.video_format,
            budget_limit_usd=res.budget_limit_usd,
            upload_destination=res.upload_destination,
            created_at=res.created_at,
            updated_at=res.updated_at,
        )


def get_channel_repository() -> ChannelRepository:
    """Dependency provider placeholder overridden at app startup."""
    raise NotImplementedError("Channel repository dependency must be configured.")


@router.get("", response_model=List[ChannelResponse])
def list_channels(
    repo: ChannelRepository = Depends(get_channel_repository),
) -> List[ChannelResponse]:
    results = ListChannelsUseCase(repo).execute()
    return [ChannelResponse.from_result(item) for item in results]


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    request: CreateChannelRequest,
    repo: ChannelRepository = Depends(get_channel_repository),
) -> ChannelResponse:
    try:
        result = CreateChannelUseCase(repo).execute(
            CreateChannelInput(
                name=request.name,
                topic_focus=request.topic_focus,
                language=request.language,
                default_narrator=request.default_narrator,
                visual_style=request.visual_style,
                video_format=request.video_format,
                budget_limit_usd=request.budget_limit_usd,
                upload_destination=request.upload_destination,
            )
        )
        return ChannelResponse.from_result(result)
    except ChannelValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.get("/{channel_id}", response_model=ChannelResponse)
def get_channel(
    channel_id: str,
    repo: ChannelRepository = Depends(get_channel_repository),
) -> ChannelResponse:
    result = GetChannelUseCase(repo).execute(channel_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel profile '{channel_id}' not found.",
        )
    return ChannelResponse.from_result(result)


@router.put("/{channel_id}", response_model=ChannelResponse)
@router.patch("/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: str,
    request: UpdateChannelRequest,
    repo: ChannelRepository = Depends(get_channel_repository),
) -> ChannelResponse:
    try:
        result = UpdateChannelUseCase(repo).execute(
            UpdateChannelInput(
                id=channel_id,
                name=request.name,
                topic_focus=request.topic_focus,
                language=request.language,
                default_narrator=request.default_narrator,
                visual_style=request.visual_style,
                video_format=request.video_format,
                budget_limit_usd=request.budget_limit_usd,
                upload_destination=request.upload_destination,
            )
        )
        return ChannelResponse.from_result(result)
    except ChannelNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
    except ChannelValidationError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err))


@router.delete("/{channel_id}")
def delete_channel(
    channel_id: str,
    repo: ChannelRepository = Depends(get_channel_repository),
) -> Dict[str, bool]:
    deleted = DeleteChannelUseCase(repo).execute(channel_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel profile '{channel_id}' not found.",
        )
    return {"deleted": True}
