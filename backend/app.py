"""FabAI backend HTTP server.

Phase 0 skeleton: only `/health`, plain HTTP. Phase 3 replaces this with
`build_app(container)` wiring the full pipeline and device API.
"""

from __future__ import annotations

from aiohttp import web

from config import Settings


async def health_handler(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "fabai-backend"})


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health_handler)
    return app


def main() -> None:
    settings = Settings.load()
    print(f"FabAI backend on http://0.0.0.0:{settings.port}", flush=True)
    web.run_app(build_app(), host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
