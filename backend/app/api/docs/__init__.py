"""
API Documentation

Enhanced OpenAPI documentation for the Vulcan Engine APIs.
"""

from .scheduling_docs import (
    DOMAIN_CONCEPT_DOCS,
    ERROR_RESPONSES,
    RESPONSE_EXAMPLES,
    SCHEDULING_OPENAPI_EXTRAS,
    SCHEDULING_TAGS,
    WEBSOCKET_MESSAGE_EXAMPLES,
    get_enhanced_openapi_schema,
)

__all__ = [
    "SCHEDULING_TAGS",
    "SCHEDULING_OPENAPI_EXTRAS",
    "RESPONSE_EXAMPLES",
    "ERROR_RESPONSES",
    "WEBSOCKET_MESSAGE_EXAMPLES",
    "DOMAIN_CONCEPT_DOCS",
    "get_enhanced_openapi_schema",
]
