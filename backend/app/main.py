from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.ai import OPENROUTER_MODEL, OpenRouterClient, build_chat_messages
from app.models import (
  AiBoardUpdate,
    Board,
    BoardRecord,
    ChatMessageCreate,
    ChatReply,
    ChatSessionRecord,
)
from app.repository import BoardRepository

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_OUT_DIR = ROOT_DIR / "frontend" / "out"
DEFAULT_DB_PATH = ROOT_DIR / "backend" / "data" / "app.db"


class AiTestResponse(BaseModel):
    model: str
    reply: str


def placeholder_html() -> str:
    return """
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Project Management MVP</title>
        <style>
          :root {
            color-scheme: light;
            --accent-yellow: #ecad0a;
            --primary-blue: #209dd7;
            --secondary-purple: #753991;
            --navy-dark: #032147;
            --gray-text: #888888;
            --surface: #f7f8fb;
            --card: #ffffff;
          }

          * { box-sizing: border-box; }

          body {
            margin: 0;
            min-height: 100vh;
            font-family: "Segoe UI", sans-serif;
            color: var(--navy-dark);
            background:
              radial-gradient(circle at top left, rgba(32, 157, 215, 0.16), transparent 35%),
              radial-gradient(circle at bottom right, rgba(117, 57, 145, 0.12), transparent 30%),
              var(--surface);
          }

          main {
            max-width: 960px;
            margin: 0 auto;
            padding: 72px 24px;
          }

          .hero {
            background: rgba(255, 255, 255, 0.86);
            border: 1px solid rgba(3, 33, 71, 0.08);
            border-radius: 32px;
            padding: 40px;
            box-shadow: 0 18px 40px rgba(3, 33, 71, 0.12);
          }

          .eyebrow {
            margin: 0;
            color: var(--gray-text);
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.3em;
            text-transform: uppercase;
          }

          h1 {
            margin: 16px 0 12px;
            font-size: clamp(2.5rem, 5vw, 4rem);
            line-height: 1;
          }

          p {
            max-width: 56ch;
            margin: 0;
            color: var(--gray-text);
            line-height: 1.7;
          }

          .status {
            display: inline-flex;
            align-items: center;
            gap: 12px;
            margin-top: 28px;
            border-radius: 999px;
            background: var(--card);
            border: 1px solid rgba(3, 33, 71, 0.08);
            padding: 12px 18px;
            font-size: 14px;
            font-weight: 600;
          }

          .dot {
            width: 12px;
            height: 12px;
            border-radius: 999px;
            background: var(--accent-yellow);
          }

          code {
            font-family: "SFMono-Regular", monospace;
            color: var(--secondary-purple);
          }
        </style>
      </head>
      <body>
        <main>
          <section class="hero">
            <p class="eyebrow">Part 2 Scaffolding</p>
            <h1>FastAPI hello world is running.</h1>
            <p>
              This placeholder page is served from the backend so the Docker and
              script flow can be verified before the frontend is integrated at
              <code>/</code>.
            </p>
            <div class="status">
              <span class="dot"></span>
              API ready at <code>/api/hello</code>
            </div>
          </section>
        </main>
      </body>
    </html>
    """


def create_app(
    frontend_out_dir: Path | None = None,
    db_path: Path | None = None,
    ai_client: OpenRouterClient | None = None,
) -> FastAPI:
    app = FastAPI(title="Project Management MVP")
    repository = BoardRepository(db_path or DEFAULT_DB_PATH)
    repository.initialize()

    @app.get("/api/hello")
    async def read_hello() -> dict[str, str]:
        return {"message": "hello from fastapi"}

    @app.get("/api/board/{username}", response_model=BoardRecord)
    async def read_board(username: str) -> BoardRecord:
        current_board_state_id, board = repository.get_or_create_board(username)
        return BoardRecord(
            username=username,
            current_board_state_id=current_board_state_id,
            board=board,
        )

    @app.put("/api/board/{username}", response_model=BoardRecord)
    async def update_board(username: str, board: Board) -> BoardRecord:
        current_board_state_id, saved_board = repository.replace_board(username, board)
        return BoardRecord(
            username=username,
            current_board_state_id=current_board_state_id,
            board=saved_board,
        )

    @app.post("/api/chat/{username}/messages", response_model=ChatReply)
    async def create_chat_message(
        username: str,
        chat_message: ChatMessageCreate,
    ) -> ChatReply:
        current_board_state_id, board = repository.get_board_snapshot(username)
        user_content = chat_message.message.strip()

        history = repository.list_chat_history(username)
        client = ai_client or OpenRouterClient()
        raw_reply = await client.complete_messages(
            build_chat_messages(
                history=history + [{"role": "user", "content": user_content}],
                board_json=board.model_dump(by_alias=True),
            )
        )

        try:
          parsed_reply = json.loads(raw_reply)
          reply_text = parsed_reply["reply"].strip()
          if not reply_text:
            raise ValueError("Reply must not be blank.")
        except Exception:
            raise HTTPException(
                status_code=502,
                detail="AI response was malformed.",
            ) from None

        chat_id, _ = repository.append_chat_message(
            username=username,
            role="user",
            content=user_content,
            board_state_id=current_board_state_id,
        )

        next_board_state_id = current_board_state_id
        next_board = board
        board_update_payload = parsed_reply.get("board_update")
        if board_update_payload is not None:
          try:
            board_update = AiBoardUpdate.model_validate(board_update_payload)
            next_board_state_id, next_board = repository.apply_board_state(
              username,
              board_update.board,
            )
          except Exception:
            # Keep the assistant reply even if the board mutation is invalid.
            next_board_state_id = current_board_state_id
            next_board = board

        _, assistant_message = repository.append_chat_message(
            username=username,
            role="assistant",
          content=reply_text,
            board_state_id=next_board_state_id,
        )
        return ChatReply(
            chat_id=chat_id,
            assistant_message=assistant_message,
            current_board_state_id=next_board_state_id,
            board=next_board,
        )

    @app.post("/api/chat/{username}/session", response_model=ChatSessionRecord)
    async def start_chat_session(username: str) -> ChatSessionRecord:
        chat_id = repository.reset_chat_session(username)
        return ChatSessionRecord(chat_id=chat_id)

    @app.post("/api/ai/test", response_model=AiTestResponse)
    async def ai_connectivity_test() -> AiTestResponse:
        client = OpenRouterClient()
        reply = await client.connectivity_test()
        return AiTestResponse(model=OPENROUTER_MODEL, reply=reply)

    static_dir = frontend_out_dir or FRONTEND_OUT_DIR
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def read_root() -> str:
            return placeholder_html()

    return app


app = create_app()
