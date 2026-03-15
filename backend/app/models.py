from pydantic import BaseModel, Field, model_validator


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
    board: Board
