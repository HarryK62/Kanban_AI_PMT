import json
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.ai import (
    OPENROUTER_MODEL,
    OpenRouterClient,
    OpenRouterConfigurationError,
    OpenRouterRequestError,
    build_chat_messages,
)
from app.auth import InvalidUsernameError, WeakPasswordError, normalize_username
from app.models import (
    AiBoardUpdate,
    AiTestResponse,
    AuthResponse,
    Board,
    BoardRecord,
    BoardSummary,
    ChatMessageCreate,
    ChatReply,
    ChatSessionRecord,
    CreateBoardRequest,
    LoginRequest,
    SignupRequest,
)
from app.repository import (
    BoardNotFoundError,
    BoardRepository,
    InvalidCredentialsError,
    UsernameTakenError,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_OUT_DIR = ROOT_DIR / "frontend" / "out"
DEFAULT_DB_PATH = ROOT_DIR / "backend" / "data" / "app.db"

MALFORMED_AI_REPLY_DETAIL = "AI response was malformed."


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    return authorization.removeprefix("Bearer ").strip() or None


def _parse_ai_reply(raw_reply: str) -> tuple[str, Any]:
    """Split a raw AI response into its reply text and board_update payload.

    Raises a 502 if the response is not JSON of the expected shape, or if the
    reply text is blank. The board_update payload is returned unvalidated --
    callers validate it against AiBoardUpdate before persisting anything.
    """
    try:
        parsed_reply = json.loads(raw_reply)
        reply_text = parsed_reply["reply"].strip()
    except (AttributeError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=502, detail=MALFORMED_AI_REPLY_DETAIL
        ) from None

    if not reply_text:
        raise HTTPException(status_code=502, detail=MALFORMED_AI_REPLY_DETAIL)
    return reply_text, parsed_reply.get("board_update")


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

    @app.exception_handler(BoardNotFoundError)
    async def handle_board_not_found(
        _request: Request, error: BoardNotFoundError
    ) -> JSONResponse:
        """A board that is missing *or* owned by someone else is a 404.

        Answering 404 rather than 403 keeps the routes from revealing that
        another user's board id exists.
        """
        return JSONResponse(status_code=404, content={"detail": str(error)})

    def board_record(username: str, board_id: int, state_id: int, board: Board) -> BoardRecord:
        return BoardRecord(
            username=username,
            board_id=board_id,
            current_board_state_id=state_id,
            board=board,
        )

    @app.get("/api/hello")
    async def read_hello() -> dict[str, str]:
        return {"message": "hello from fastapi"}

    @app.post("/api/auth/signup", response_model=AuthResponse, status_code=201)
    async def signup(payload: SignupRequest) -> AuthResponse:
        try:
            user_id = repository.create_user(payload.username, payload.password)
        except (InvalidUsernameError, WeakPasswordError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from None
        except UsernameTakenError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None

        username = normalize_username(payload.username)
        repository.bootstrap_default_board(username)
        return AuthResponse(username=username, token=repository.create_session(user_id))

    @app.post("/api/auth/login", response_model=AuthResponse)
    async def login(payload: LoginRequest) -> AuthResponse:
        try:
            user_id = repository.verify_login(payload.username, payload.password)
        except InvalidCredentialsError as error:
            raise HTTPException(status_code=401, detail=str(error)) from None

        return AuthResponse(
            username=normalize_username(payload.username),
            token=repository.create_session(user_id),
        )

    @app.post("/api/auth/logout", status_code=204)
    async def logout(authorization: str | None = Header(default=None)) -> None:
        token = _extract_bearer_token(authorization)
        if token is not None:
            repository.delete_session(token)

    async def require_session(
        username: str, authorization: str | None = Header(default=None)
    ) -> str:
        token = _extract_bearer_token(authorization)
        if token is None:
            raise HTTPException(status_code=401, detail="Missing bearer token.")

        token_username = repository.get_username_for_token(token)
        if token_username is None or token_username != username:
            raise HTTPException(status_code=401, detail="Invalid or expired session.")
        return username

    @app.get("/api/boards/{username}", response_model=list[BoardSummary])
    async def list_boards(
        username: str, _authenticated_username: str = Depends(require_session)
    ) -> list[BoardSummary]:
        return repository.list_boards(username)

    @app.post("/api/boards/{username}", response_model=BoardRecord, status_code=201)
    async def create_board(
        username: str,
        payload: CreateBoardRequest,
        _authenticated_username: str = Depends(require_session),
    ) -> BoardRecord:
        board_id, state_id, board = repository.create_board(username, payload.title)
        return board_record(username, board_id, state_id, board)

    @app.get("/api/boards/{username}/{board_id}", response_model=BoardRecord)
    async def read_board(
        username: str,
        board_id: int,
        _authenticated_username: str = Depends(require_session),
    ) -> BoardRecord:
        state_id, board = repository.get_board(username, board_id)
        return board_record(username, board_id, state_id, board)

    @app.put("/api/boards/{username}/{board_id}", response_model=BoardRecord)
    async def update_board(
        username: str,
        board_id: int,
        board: Board,
        _authenticated_username: str = Depends(require_session),
    ) -> BoardRecord:
        state_id, saved_board = repository.replace_board(username, board_id, board)
        return board_record(username, board_id, state_id, saved_board)

    @app.delete("/api/boards/{username}/{board_id}", status_code=204)
    async def delete_board(
        username: str,
        board_id: int,
        _authenticated_username: str = Depends(require_session),
    ) -> None:
        repository.delete_board(username, board_id)

    @app.post("/api/chat/{username}/{board_id}/messages", response_model=ChatReply)
    async def create_chat_message(
        username: str,
        board_id: int,
        chat_message: ChatMessageCreate,
        _authenticated_username: str = Depends(require_session),
    ) -> ChatReply:
        current_board_state_id, board = repository.get_board(username, board_id)
        user_content = chat_message.message.strip()

        history = repository.list_chat_history(username, board_id)
        client = ai_client or OpenRouterClient()
        try:
            raw_reply = await client.complete_messages(
                build_chat_messages(
                    history=history + [{"role": "user", "content": user_content}],
                    board_json=board.model_dump(by_alias=True),
                )
            )
        except OpenRouterConfigurationError as error:
            raise HTTPException(status_code=500, detail=str(error)) from None
        except OpenRouterRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None

        # Parse before persisting anything: a malformed reply must not leave the
        # user message behind to be replayed as unanswered context next turn.
        reply_text, board_update_payload = _parse_ai_reply(raw_reply)

        chat_id, _ = repository.append_chat_message(
            username=username,
            board_id=board_id,
            role="user",
            content=user_content,
            board_state_id=current_board_state_id,
        )

        next_board_state_id = current_board_state_id
        next_board = board
        if board_update_payload is not None:
            try:
                board_update = AiBoardUpdate.model_validate(board_update_payload)
                next_board_state_id, next_board = repository.replace_board(
                    username, board_id, board_update.board
                )
            except Exception:
                # Keep the assistant reply even if the board mutation is invalid;
                # the board simply stays on its current state.
                pass

        _, assistant_message = repository.append_chat_message(
            username=username,
            board_id=board_id,
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

    @app.post("/api/chat/{username}/{board_id}/session", response_model=ChatSessionRecord)
    async def start_chat_session(
        username: str,
        board_id: int,
        _authenticated_username: str = Depends(require_session),
    ) -> ChatSessionRecord:
        return ChatSessionRecord(chat_id=repository.reset_chat_session(username, board_id))

    @app.post("/api/ai/test", response_model=AiTestResponse)
    async def ai_connectivity_test() -> AiTestResponse:
        client = OpenRouterClient()
        try:
            reply = await client.connectivity_test()
        except OpenRouterConfigurationError as error:
            raise HTTPException(status_code=500, detail=str(error)) from None
        except OpenRouterRequestError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None
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
