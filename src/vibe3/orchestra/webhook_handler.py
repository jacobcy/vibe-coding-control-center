"""Shim for vibe3.orchestra.webhook_handler - moved to vibe3.server.app."""

from vibe3.server.app import _verify_signature, make_webhook_router

__all__ = ["make_webhook_router", "_verify_signature"]
