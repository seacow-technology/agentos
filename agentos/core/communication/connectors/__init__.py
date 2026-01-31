"""Connectors for external communication services.

This module provides connector implementations for various
external services including web search, web fetch, RSS, email, and messaging.
"""

from agentos.core.communication.connectors.base import BaseConnector
from agentos.core.communication.connectors.web_search import WebSearchConnector
from agentos.core.communication.connectors.web_fetch import WebFetchConnector
from agentos.core.communication.connectors.rss import RSSConnector
from agentos.core.communication.connectors.email_smtp import EmailSMTPConnector
from agentos.core.communication.connectors.slack import SlackConnector

__all__ = [
    "BaseConnector",
    "WebSearchConnector",
    "WebFetchConnector",
    "RSSConnector",
    "EmailSMTPConnector",
    "SlackConnector",
]
