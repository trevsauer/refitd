"""
OpenAI API Client

Provides a simple async wrapper for the OpenAI API.
Supports text generation, vision models (GPT-4o), and embeddings.

Usage:
    from src.ai import OpenAIClient

    client = OpenAIClient()

    # Text generation
    response = await client.generate("What is fashion?")

    # Vision (with image)
    response = await client.generate_with_image("Describe this clothing", image_url)

    # Embeddings
    embedding = await client.embed("casual summer outfit")
"""

import asyncio
import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

import httpx
from openai import AsyncOpenAI
from rich.console import Console

console = Console()


@dataclass
class OpenAIConfig:
    """Configuration for OpenAI client."""

    api_key: Optional[str] = None

    # Model selections
    chat_model: str = "gpt-5.2"  # GPT-5.2 for text
    vision_model: str = "gpt-5.2"  # GPT-5.2 has vision capabilities
    embedding_model: str = "text-embedding-3-small"  # Fast, efficient embeddings

    # Timeouts
    timeout_seconds: float = 120.0

    # Generation settings
    temperature: float = 0.7
    max_tokens: int = 1024


class OpenAIClient:
    """
    Async client for OpenAI API.

    Handles text generation, vision models, and embeddings.
    Drop-in replacement for OllamaClient with the same interface.
    """

    def __init__(self, config: Optional[OpenAIConfig] = None):
        self.config = config or OpenAIConfig()
        # Get API key from config or environment
        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )
        self._client = AsyncOpenAI(
            api_key=api_key,
            timeout=self.config.timeout_seconds,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Initialize the client (no-op for OpenAI, kept for compatibility)."""
        pass

    async def close(self) -> None:
        """Close the client (no-op for OpenAI, kept for compatibility)."""
        pass

    async def is_available(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            # Make a simple models list call to verify API key works
            models = await self._client.models.list()
            return True
        except Exception as e:
            console.print(f"[red]OpenAI API not available: {e}[/red]")
            return False

    async def list_models(self) -> list[str]:
        """List available models."""
        try:
            models = await self._client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            console.print(f"[red]Error listing models: {e}[/red]")
            return []

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
        model = model or self.config.chat_model
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        try:
            # GPT-5.x models use max_completion_tokens instead of max_tokens
            token_limit = max_tokens or self.config.max_tokens
            if model.startswith("gpt-5"):
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature or self.config.temperature,
                    max_completion_tokens=token_limit,
                )
            else:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature or self.config.temperature,
                    max_tokens=token_limit,
                )

            return response.choices[0].message.content or ""

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
        model = model or self.config.vision_model

        # Prepare image for API
        image_content = await self._prepare_image_for_api(image)
        if not image_content:
            console.print("[red]Failed to prepare image[/red]")
            return ""

        try:
            # GPT-5.x models use max_completion_tokens instead of max_tokens
            if model.startswith("gpt-5"):
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                image_content,
                            ],
                        }
                    ],
                    temperature=temperature or self.config.temperature,
                    max_completion_tokens=self.config.max_tokens,
                )
            else:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                image_content,
                            ],
                        }
                    ],
                    temperature=temperature or self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

            return response.choices[0].message.content or ""

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
        model = model or self.config.chat_model

        try:
            # GPT-5.x models use max_completion_tokens instead of max_tokens
            if model.startswith("gpt-5"):
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature or self.config.temperature,
                    max_completion_tokens=self.config.max_tokens,
                )
            else:
                response = await self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature or self.config.temperature,
                    max_tokens=self.config.max_tokens,
                )

            return response.choices[0].message.content or ""

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
        model = model or self.config.embedding_model

        try:
            response = await self._client.embeddings.create(
                model=model,
                input=text,
            )

            return response.data[0].embedding

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
        model = model or self.config.embedding_model

        try:
            response = await self._client.embeddings.create(
                model=model,
                input=texts,
            )

            # Sort by index to maintain order
            sorted_embeddings = sorted(response.data, key=lambda x: x.index)
            return [e.embedding for e in sorted_embeddings]

        except Exception as e:
            console.print(f"[red]Error generating batch embeddings: {e}[/red]")
            return []

    async def _prepare_image_for_api(
        self, image: Union[str, Path, bytes]
    ) -> Optional[dict]:
        """Convert image to OpenAI API format."""
        try:
            # If it's a URL, use URL format
            if isinstance(image, str) and image.startswith(("http://", "https://")):
                return {"type": "image_url", "image_url": {"url": image}}

            # For file path or bytes, convert to base64
            if isinstance(image, bytes):
                image_b64 = base64.b64encode(image).decode("utf-8")
                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                }

            image_path = Path(image) if isinstance(image, str) else image

            if image_path.exists():
                with open(image_path, "rb") as f:
                    image_data = f.read()
                image_b64 = base64.b64encode(image_data).decode("utf-8")

                # Detect image type from extension
                ext = image_path.suffix.lower()
                mime_type = {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }.get(ext, "image/jpeg")

                return {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                }

            return None

        except Exception as e:
            console.print(f"[red]Error preparing image: {e}[/red]")
            return None


async def test_client():
    """Test the OpenAI client."""
    console.print("\n[bold cyan]Testing OpenAI Client[/bold cyan]\n")

    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv()

    try:
        async with OpenAIClient() as client:
            # Check availability
            available = await client.is_available()
            console.print(f"OpenAI API available: {'✓' if available else '✗'}")

            if not available:
                console.print("[red]Please check your OPENAI_API_KEY[/red]")
                return

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

            # Test vision (with a sample image URL)
            console.print("\n[cyan]Testing vision...[/cyan]")
            test_image = "https://static.zara.net/assets/public/a95b/5c8f/3d324a14a5c8/b8c8e8a3a84a/00761306250-e1/00761306250-e1.jpg"
            vision_response = await client.generate_with_image(
                "Describe this clothing item briefly.",
                test_image,
                temperature=0.3,
            )
            console.print(f"Vision response: {vision_response[:300]}...")

    except ValueError as e:
        console.print(f"[red]Configuration error: {e}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    asyncio.run(test_client())
