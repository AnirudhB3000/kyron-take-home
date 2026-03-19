from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.conversation import Conversation


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    def create(self) -> Conversation:
        timestamp = datetime.now(UTC)
        conversation = Conversation(
            id=str(uuid4()),
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._conversations[conversation.id] = conversation
        return conversation

    def get(self, conversation_id: str) -> Conversation:
        return self._conversations[conversation_id]

    def save(self, conversation: Conversation) -> Conversation:
        conversation.updated_at = datetime.now(UTC)
        self._conversations[conversation.id] = conversation
        return conversation
