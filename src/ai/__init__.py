"""
AI Service Module for Refitd

Provides AI-powered features using Ollama:
- Style tag generation from product images
- Semantic search with embeddings
- Product linking and recommendations
- Conversational assistant

Requires Ollama to be installed and running locally.
Install: brew install ollama
Start: ollama serve
"""

from .ollama_client import OllamaClient
from .style_tagger import StyleTagger
from .embeddings import EmbeddingsService
from .chat import ChatAssistant

__all__ = [
    "OllamaClient",
    "StyleTagger",
    "EmbeddingsService",
    "ChatAssistant",
]
