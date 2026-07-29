import live_server
from complete_public_view import CompletePublicBattleView

# Keep one runtime entrypoint. The strict projection is patched before any session is created.
live_server.PublicBattleView = CompletePublicBattleView
app = live_server.app

__all__ = ["app"]
