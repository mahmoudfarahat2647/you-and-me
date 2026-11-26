"""Use cases for managing channel profiles."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from src.core.dto.channel_dto import (
    ChannelProfileResult,
    CreateChannelInput,
    UpdateChannelInput,
)
from src.core.entities.channel import ChannelProfile, ChannelValidationError
from src.core.ports.channel_repository import ChannelRepository


class ChannelNotFoundError(Exception):
    """Raised when a requested channel profile cannot be found."""
    pass


def _channel_to_result(channel: ChannelProfile) -> ChannelProfileResult:
    return ChannelProfileResult(
        id=channel.id,
        name=channel.name,
        topic_focus=channel.topic_focus,
        language=channel.language,
        default_narrator=channel.default_narrator,
        visual_style=channel.visual_style,
        video_format=channel.video_format,
        budget_limit_usd=channel.budget_limit_usd,
        upload_destination=channel.upload_destination,
        created_at=channel.created_at.isoformat(),
        updated_at=channel.updated_at.isoformat(),
    )


class CreateChannelUseCase:
    """Creates and persists a new channel profile."""

    def __init__(self, repository: ChannelRepository) -> None:
        self._repository = repository

    def execute(self, input_data: CreateChannelInput) -> ChannelProfileResult:
        if not input_data.name or not input_data.name.strip():
            raise ChannelValidationError("Channel name cannot be empty.")

        now = datetime.now(timezone.utc)
        channel = ChannelProfile(
            id=str(uuid.uuid4()),
            name=input_data.name,
            topic_focus=input_data.topic_focus,
            language=input_data.language,
            default_narrator=input_data.default_narrator,
            visual_style=input_data.visual_style,
            video_format=input_data.video_format,
            budget_limit_usd=input_data.budget_limit_usd,
            upload_destination=input_data.upload_destination,
            created_at=now,
            updated_at=now,
        )
        result = _channel_to_result(channel)
        self._repository.save(result)
        return result


class UpdateChannelUseCase:
    """Updates an existing channel profile without mutating existing projects."""

    def __init__(self, repository: ChannelRepository) -> None:
        self._repository = repository

    def execute(self, input_data: UpdateChannelInput) -> ChannelProfileResult:
        existing = self._repository.get_by_id(input_data.id)
        if existing is None:
            raise ChannelNotFoundError(f"Channel profile '{input_data.id}' not found.")

        now = datetime.now(timezone.utc)
        created_at = datetime.fromisoformat(existing.created_at)
        channel = ChannelProfile(
            id=existing.id,
            name=input_data.name if input_data.name is not None else existing.name,
            topic_focus=input_data.topic_focus if input_data.topic_focus is not None else existing.topic_focus,
            language=input_data.language if input_data.language is not None else existing.language,
            default_narrator=(
                input_data.default_narrator
                if input_data.default_narrator is not None
                else existing.default_narrator
            ),
            visual_style=input_data.visual_style if input_data.visual_style is not None else existing.visual_style,
            video_format=input_data.video_format if input_data.video_format is not None else existing.video_format,
            budget_limit_usd=(
                input_data.budget_limit_usd
                if input_data.budget_limit_usd is not None
                else existing.budget_limit_usd
            ),
            upload_destination=(
                input_data.upload_destination
                if input_data.upload_destination is not None
                else existing.upload_destination
            ),
            created_at=created_at,
            updated_at=now,
        )
        result = _channel_to_result(channel)
        self._repository.save(result)
        return result


class GetChannelUseCase:
    """Retrieves a channel profile by ID."""

    def __init__(self, repository: ChannelRepository) -> None:
        self._repository = repository

    def execute(self, channel_id: str) -> Optional[ChannelProfileResult]:
        return self._repository.get_by_id(channel_id)


class ListChannelsUseCase:
    """Lists all channel profiles."""

    def __init__(self, repository: ChannelRepository) -> None:
        self._repository = repository

    def execute(self) -> List[ChannelProfileResult]:
        return self._repository.list_all()


class DeleteChannelUseCase:
    """Deletes a channel profile by ID."""

    def __init__(self, repository: ChannelRepository) -> None:
        self._repository = repository

    def execute(self, channel_id: str) -> bool:
        return self._repository.delete(channel_id)
