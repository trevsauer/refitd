"""
Ollama API Client

Provides a simple async wrapper for the Ollama REST API.
Supports text generation, vision models, and embeddings.

Usage:
    from src.ai import OllamaClient

    client = OllamaClient()

    # Text generation
    response = await client.generate("What is fashion?")

    # Vision (with image)
    response = await client.generate_with_image("Describe this clothing", image_path)

    # Embeddings
    embedding = await client.embed("casual summer outfit")
"""

import asyncio
import base64
import httpx
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass, field

from rich.console import Console

console = Console()


@dataclass
class OllamaConfig:
    """Configuration for Ollama client."""

    base_url: str = "http://localhost:11434"

    # Model selections (optimized for speed)
    chat_model: str = "phi3.5"              # Fast reasoning
    vision_model: str = "moondream"          # Fast image understanding
    embedding_model: str = "nomic-embed-text"  # Fast embeddings

    # Timeouts
    timeout_seconds: float = 120.0

    # Generation settings
    temperature: float = 0.7
    max_tokens: int = 1024


class OllamaClient:
    """
    Async client for Ollama API.

    Handles text generation, vision models, and embeddings.
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        self.config = config or OllamaConfig()
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=httpx.Timeout(self.config.timeout_seconds),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=httpx.Timeout(self.config.timeout_seconds),
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if Ollama server is running."""
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            client = self._get_client()
            response = await client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
            return []
        except Exception as e:
            console.print(f"[red]Error listing models: {e}[/red]")
            return []

    async def pull_model(self, model_name: str) -> bool:
        """Pull a model if not already available."""
        try:
            client = self._get_client()
            console.print(f"[cyan]Pulling model: {model_name}...[/cyan]")

            response = await client.post(
                "/api/pull",
                json={"name": model_name, "stream": False},
                timeout=httpx.Timeout(600.0),  # 10 min timeout for downloads
            )

            if response.status_code == 200:
                console.print(f"[green]✓ Model {model_name} ready[/green]")
                return True
            else:
                console.print(f"[red]Failed to pull {model_name}: {response.text}[/red]")
                return False

        except Exception as e:
            console.print(f"[red]Error pulling model: {e}[/red]")
            return False

    async def ensure_models(self) -> bool:
        """Ensure all required models are available."""
        models = await self.list_models()
        required = [
            self.config.chat_model,
            self.config.vision_model,
            self.config.embedding_model,
        ]

        all_ready = True
        for model in required:
            # Check if model (or variant) is available
            model_base = model.split(":")[0]
            if not any(model_base in m for m in models):
                console.print(f"[yellow]Model {model} not found, pulling...[/yellow]")
                success = await self.pull_model(model)
                if not success:
                    all_ready = False

        return all_ready

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate text response from a prompt.

        Args:
            prompt: The user prompt
            model: Model to use (defaults to chat_model)
            system: Optional system prompt
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text response
        """
        client = self._get_client()
        model = model or self.config.chat_model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
                "num_predict": max_tokens or self.config.max_tokens,
            },
        }

        if system:
            payload["system"] = system

        try:
            response = await client.post("/api/generate", json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                console.print(f"[red]Generation error: {response.status_code}[/red]")
                return ""

        except Exception as e:
            console.print(f"[red]Error generating response: {e}[/red]")
            return ""

    async def generate_with_image(
        self,
        prompt: str,
        image: Union[str, Path, bytes],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Generate text response from a prompt and image.

        Args:
            prompt: The user prompt describing what to analyze
            image: Image as file path, URL, or bytes
            model: Vision model to use (defaults to vision_model)
            temperature: Sampling temperature

        Returns:
            Generated text response
        """
        client = self._get_client()
        model = model or self.config.vision_model

        # Convert image to base64
        image_b64 = await self._prepare_image(image)
        if not image_b64:
            return ""

        payload = {
            "model": model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
            },
        }

        try:
            response = await client.post("/api/generate", json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("response", "")
            else:
                console.print(f"[red]Vision generation error: {response.status_code}[/red]")
                return ""

        except Exception as e:
            console.print(f"[red]Error generating vision response: {e}[/red]")
            return ""

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Multi-turn chat conversation.

        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model: Model to use
            temperature: Sampling temperature

        Returns:
            Assistant's response
        """
        client = self._get_client()
        model = model or self.config.chat_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.config.temperature,
            },
        }

        try:
            response = await client.post("/api/chat", json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")
            else:
                console.print(f"[red]Chat error: {response.status_code}[/red]")
                return ""

        except Exception as e:
            console.print(f"[red]Error in chat: {e}[/red]")
            return ""

    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> list[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Text to embed
            model: Embedding model to use

        Returns:
            Embedding vector as list of floats
        """
        client = self._get_client()
        model = model or self.config.embedding_model

        payload = {
            "model": model,
            "prompt": text,
        }

        try:
            response = await client.post("/api/embeddings", json=payload)

            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
            else:
                console.print(f"[red]Embedding error: {response.status_code}[/red]")
                return []

        except Exception as e:
            console.print(f"[red]Error generating embedding: {e}[/red]")
            return []

    async def embed_batch(
        self,
        texts: list[str],
        model: Optional[str] = None,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            model: Embedding model to use

        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            embedding = await self.embed(text, model)
            embeddings.append(embedding)
        return embeddings

    async def _prepare_image(self, image: Union[str, Path, bytes]) -> Optional[str]:
        """Convert image to base64 string."""
        try:
            if isinstance(image, bytes):
                return base64.b64encode(image).decode("utf-8")

            image_path = Path(image) if isinstance(image, str) else image

            # Check if it's a URL
            if isinstance(image, str) and image.startswith(("http://", "https://")):
                async with httpx.AsyncClient() as client:
                    response = await client.get(image)
                    if response.status_code == 200:
                        return base64.b64encode(response.content).decode("utf-8")
                    return None

            # Read from file
            if image_path.exists():
                with open(image_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")

            return None

        except Exception as e:
            console.print(f"[red]Error preparing image: {e}[/red]")
            return None


async def test_client():
    """Test the Ollama client."""
    console.print("\n[bold cyan]Testing Ollama Client[/bold cyan]\n")

    async with OllamaClient() as client:
        # Check availability
        available = await client.is_available()
        console.print(f"Ollama available: {'✓' if available else '✗'}")

        if not available:
            console.print("[red]Please start Ollama: ollama serve[/red]")
            return

        # List models
        models = await client.list_models()
        console.print(f"Available models: {models}")

        # Test text generation
        console.print("\n[cyan]Testing text generation...[/cyan]")
        response = await client.generate(
            "What are 3 key elements of casual men's fashion? Be brief.",
            temperature=0.5,
        )
        console.print(f"Response: {response[:500]}...")

        # Test embeddings
        console.print("\n[cyan]Testing embeddings...[/cyan]")
        embedding = await client.embed("casual summer t-shirt")
        console.print(f"Embedding dimensions: {len(embedding)}")
        console.print(f"First 5 values: {embedding[:5]}")


if __name__ == "__main__":
    asyncio.run(test_client())
