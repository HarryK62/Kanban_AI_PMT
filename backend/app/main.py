from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles


ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_OUT_DIR = ROOT_DIR / "frontend" / "out"


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


def create_app(frontend_out_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="Project Management MVP")

    @app.get("/api/hello")
    async def read_hello() -> dict[str, str]:
        return {"message": "hello from fastapi"}

    static_dir = frontend_out_dir or FRONTEND_OUT_DIR
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def read_root() -> str:
            return placeholder_html()

    return app


app = create_app()
