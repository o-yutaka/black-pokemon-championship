import live_server
from complete_public_view import CompletePublicBattleView
from runtime_truth import build_health

# Keep one runtime entrypoint. The strict projection is patched before any session is created.
live_server.PublicBattleView = CompletePublicBattleView
app = live_server.app


async def runtime_health():
    return build_health(live_server)


# live_server mounts the frontend at "/" after declaring its API routes. Replace the old
# ambiguous health route while preserving the static mount as the final fallback route.
_static_routes = [route for route in app.router.routes if route.__class__.__name__ == "Mount"]
app.router.routes = [
    route
    for route in app.router.routes
    if route.__class__.__name__ != "Mount" and getattr(route, "path", None) != "/api/health"
]
app.add_api_route("/api/health", runtime_health, methods=["GET"], name="runtime-health")
app.router.routes.extend(_static_routes)

__all__ = ["app"]
