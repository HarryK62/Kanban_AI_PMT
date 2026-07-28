from typing import Literal

from pydantic import BaseModel, Field, model_validator

MVP_COLUMN_IDS = [
    "col-backlog",
    "col-discovery",
    "col-progress",
    "col-review",
    "col-done",
]


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    card_ids: list[str] = Field(alias="cardIds")

    model_config = {"populate_by_name": True}


class Board(BaseModel):
    version: int
    title: str
    columns: list[Column]
    cards: dict[str, Card]

    @model_validator(mode="after")
    def validate_consistency(self) -> "Board":
        column_ids = [column.id for column in self.columns]
        if column_ids != MVP_COLUMN_IDS:
            raise ValueError("Board must preserve the fixed MVP columns and order.")

        if len(column_ids) != len(set(column_ids)):
            raise ValueError("Column ids must be unique.")

        referenced_card_ids: list[str] = []
        for column in self.columns:
            for card_id in column.card_ids:
                if card_id not in self.cards:
                    raise ValueError(f"Column references unknown card id: {card_id}")
                referenced_card_ids.append(card_id)

        if len(referenced_card_ids) != len(set(referenced_card_ids)):
            raise ValueError("Each card must appear in only one column.")

        for key, card in self.cards.items():
            if key != card.id:
                raise ValueError(f"Card key does not match card id: {key}")

        return self


class BoardRecord(BaseModel):
    username: str
    current_board_state_id: int
    board: Board


class ChatMessageCreate(BaseModel):
    message: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_message(self) -> "ChatMessageCreate":
        if not self.message.strip():
            raise ValueError("Message must not be blank.")
        return self


class ChatMessageRecord(BaseModel):
    id: int
    sequence_number: int
    role: Literal["user", "assistant"]
    content: str


class ChatReply(BaseModel):
    chat_id: int
    assistant_message: ChatMessageRecord
    current_board_state_id: int
    board: Board


class ChatSessionRecord(BaseModel):
    chat_id: int


class AiBoardUpdate(BaseModel):
    kind: Literal["replace_board"]
    board: Board


class AiStructuredReply(BaseModel):
    reply: str = Field(min_length=1)
    board_update: AiBoardUpdate | None = None


class SignupRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    username: str
    token: str
