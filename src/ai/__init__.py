"""
AI Service Module for Refitd

Provides AI-powered features using OpenAI (preferred) or Ollama (fallback):
- ReFitd canonical item tagging (structured tags with confidence)
- Style tag generation from product images
- Semantic search with embeddings
- Product linking and recommendations
- Conversational assistant

Configuration:
- Set OPENAI_API_KEY in .env file to use OpenAI GPT-5.2
- Or install and run Ollama locally as fallback

OpenAI Setup:
- Sign up at https://platform.openai.com
- Get API key from dashboard
- Add to .env: OPENAI_API_KEY=sk-...

Ollama Setup (fallback):
- Install: brew install ollama
- Start: ollama serve
"""

# Import OpenAI client (preferred)
try:
    from .openai_client import OpenAIClient, OpenAIConfig

    OPENAI_AVAILABLE = True
except ImportError:
    OpenAIClient = None
    OpenAIConfig = None
    OPENAI_AVAILABLE = False

# Import Ollama client (fallback)
try:
    from .ollama_client import OllamaClient, OllamaConfig

    OLLAMA_AVAILABLE = True
except ImportError:
    OllamaClient = None
    OllamaConfig = None
    OLLAMA_AVAILABLE = False

from .chat import ChatAssistant
from .embeddings import EmbeddingsService

# Import services - both old and new taggers
from .style_tagger import StyleTagger

# Import ReFitd canonical tagger (new structured tagging system)
try:
    from .refitd_tagger import AITagOutput, ReFitdTagger, ReFitdTaggerConfig
    from .tag_policy import (
        apply_tag_policy,
        apply_tag_policy_batch,
        CanonicalTags,
        POLICY_VERSION,
        PolicyResult,
        PolicyThresholds,
    )

    REFITD_TAGGER_AVAILABLE = True
except ImportError:
    ReFitdTagger = None
    ReFitdTaggerConfig = None
    AITagOutput = None
    apply_tag_policy = None
    apply_tag_policy_batch = None
    PolicyResult = None
    CanonicalTags = None
    PolicyThresholds = None
    POLICY_VERSION = None
    REFITD_TAGGER_AVAILABLE = False

__all__ = [
    # Clients
    "OpenAIClient",
    "OpenAIConfig",
    "OllamaClient",
    "OllamaConfig",
    # Services
    "StyleTagger",
    "EmbeddingsService",
    "ChatAssistant",
    # ReFitd Canonical Tagger
    "ReFitdTagger",
    "ReFitdTaggerConfig",
    "AITagOutput",
    "apply_tag_policy",
    "apply_tag_policy_batch",
    "PolicyResult",
    "CanonicalTags",
    "PolicyThresholds",
    "POLICY_VERSION",
    # Availability flags
    "OPENAI_AVAILABLE",
    "OLLAMA_AVAILABLE",
    "REFITD_TAGGER_AVAILABLE",
]
