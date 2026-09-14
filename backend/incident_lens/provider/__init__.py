"""Provider-neutral, bounded grounded-answer generation.

The provider package owns the network boundary for an OpenAI-compatible
chat-completions endpoint.  It deliberately exposes only a small structured
answer type; arbitrary tool calls, SQL, and shell content are not part of the
interface.
"""

from .client import (
    DeterministicFallbackGenerator,
    GroundedAnswer,
    OpenAICompatibleProvider,
    ProviderCallCapError,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
    ProviderValidationError,
    UnknownCitationError,
    build_answer_generator,
)

__all__ = [
    "DeterministicFallbackGenerator",
    "GroundedAnswer",
    "OpenAICompatibleProvider",
    "ProviderCallCapError",
    "ProviderError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ProviderValidationError",
    "UnknownCitationError",
    "build_answer_generator",
]
