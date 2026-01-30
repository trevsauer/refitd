"""
Embeddings Service - Text embeddings for semantic search

Uses text embeddings to enable semantic search across products,
finding similar items based on meaning rather than exact matches.

Usage:
    from src.ai import EmbeddingsService

    embeddings = EmbeddingsService(supabase_client)

    # Generate and store embeddings for all products
    await embeddings.generate_all_embeddings()

    # Search for similar products
    results = await embeddings.search("casual summer outfit", limit=10)
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Optional, Union

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

console = Console()

# Import clients - prefer OpenAI, fallback to Ollama
try:
    from .openai_client import OpenAIClient, OpenAIConfig

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from .ollama_client import OllamaClient, OllamaConfig

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Type alias for either client
AIClient = (
    Union["OpenAIClient", "OllamaClient"]
    if OPENAI_AVAILABLE or OLLAMA_AVAILABLE
    else Any
)


@dataclass
class EmbeddingsConfig:
    """Configuration for embeddings service."""

    batch_size: int = 10  # Products to process at once
    # OpenAI text-embedding-3-small: 1536 dimensions
    # OpenAI text-embedding-3-large: 3072 dimensions
    # Ollama nomic-embed-text: 768 dimensions
    embedding_dimension: int = 1536  # Default for OpenAI text-embedding-3-small


class EmbeddingsService:
    """
    Service for generating and managing product embeddings.

    Enables semantic search by converting product text into
    vector embeddings that can be compared for similarity.
    """

    def __init__(
        self,
        supabase_client=None,
        ai_client: Optional[AIClient] = None,
        config: Optional[EmbeddingsConfig] = None,
        use_openai: bool = True,
    ):
        """
        Initialize the EmbeddingsService.

        Args:
            supabase_client: Supabase client for product data
            ai_client: Pre-configured AI client (OpenAI or Ollama)
            config: Embeddings configuration
            use_openai: If True, prefer OpenAI; if False, use Ollama
        """
        self.supabase = supabase_client
        self.client = ai_client
        self.config = config or EmbeddingsConfig()
        self._owns_client = ai_client is None
        self._use_openai = use_openai and OPENAI_AVAILABLE

    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            if self._use_openai and OPENAI_AVAILABLE:
                self.client = OpenAIClient()
                console.print("[green]Using OpenAI embeddings[/green]")
            elif OLLAMA_AVAILABLE:
                self.client = OllamaClient()
                console.print("[yellow]Using Ollama embeddings[/yellow]")
            else:
                raise RuntimeError("No AI client available. Install openai or ollama.")
            await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._owns_client and self.client:
            await self.client.close()

    def _get_client(self) -> AIClient:
        """Get the AI client (OpenAI or Ollama)."""
        if self.client is None:
            if self._use_openai and OPENAI_AVAILABLE:
                self.client = OpenAIClient()
            elif OLLAMA_AVAILABLE:
                self.client = OllamaClient()
            else:
                raise RuntimeError("No AI client available. Install openai or ollama.")
            self._owns_client = True
        return self.client

    def _build_embedding_text(self, product: dict) -> str:
        """
        Build text representation of a product for embedding.

        Combines name, description, category, colors, and tags
        into a single text that captures the product's essence.
        """
        parts = []

        # Product name is most important
        if product.get("name"):
            parts.append(product["name"])

        # Category provides context
        if product.get("category"):
            parts.append(f"Category: {product['category']}")

        # Description adds detail
        if product.get("description"):
            # Truncate long descriptions
            desc = product["description"][:500]
            parts.append(desc)

        # Colors are searchable
        colors = product.get("colors", [])
        if colors:
            if isinstance(colors, str):
                parts.append(f"Colors: {colors}")
            elif isinstance(colors, list):
                parts.append(f"Colors: {', '.join(colors)}")

        # Tags are highly relevant
        tags = product.get("tags", [])
        if tags:
            if isinstance(tags, str):
                parts.append(f"Style: {tags}")
            elif isinstance(tags, list):
                parts.append(f"Style: {', '.join(tags)}")

        # Price range context
        if product.get("price"):
            try:
                price = float(str(product["price"]).replace("$", "").replace(",", ""))
                if price < 50:
                    parts.append("budget-friendly affordable")
                elif price > 150:
                    parts.append("premium luxury")
            except (ValueError, TypeError):
                pass

        return " | ".join(parts)

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for arbitrary text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        client = self._get_client()
        return await client.embed(text)

    async def embed_product(self, product: dict) -> list[float]:
        """
        Generate embedding for a product.

        Args:
            product: Product dict with name, description, etc.

        Returns:
            Embedding vector
        """
        text = self._build_embedding_text(product)
        return await self.embed_text(text)

    async def generate_all_embeddings(
        self,
        products: Optional[list[dict]] = None,
        show_progress: bool = True,
    ) -> dict[str, list[float]]:
        """
        Generate embeddings for all products.

        Args:
            products: List of products (fetches from Supabase if None)
            show_progress: Show progress bar

        Returns:
            Dict mapping product_id to embedding vector
        """
        # Fetch products if not provided
        if products is None:
            if self.supabase is None:
                raise ValueError("Supabase client required to fetch products")

            response = self.supabase.table("products").select("*").execute()
            products = response.data or []

        if not products:
            console.print("[yellow]No products to embed[/yellow]")
            return {}

        embeddings = {}
        client = self._get_client()

        # Check AI service availability
        if not await client.is_available():
            console.print(
                "[red]AI service not available. Check your API key or Ollama server.[/red]"
            )
            return {}

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Generating embeddings...",
                    total=len(products),
                )

                for product in products:
                    product_id = product.get("id", product.get("product_id", ""))
                    embedding = await self.embed_product(product)

                    if embedding:
                        embeddings[product_id] = embedding

                    progress.update(task, advance=1)
        else:
            for product in products:
                product_id = product.get("id", product.get("product_id", ""))
                embedding = await self.embed_product(product)

                if embedding:
                    embeddings[product_id] = embedding

        console.print(f"[green]Generated {len(embeddings)} embeddings[/green]")
        return embeddings

    async def store_embeddings(
        self,
        embeddings: dict[str, list[float]],
    ) -> int:
        """
        Store embeddings in Supabase.

        Requires pgvector extension and embeddings column in products table.

        Args:
            embeddings: Dict mapping product_id to embedding vector

        Returns:
            Number of embeddings stored
        """
        if self.supabase is None:
            raise ValueError("Supabase client required to store embeddings")

        stored = 0
        for product_id, embedding in embeddings.items():
            try:
                # Update the product with its embedding
                self.supabase.table("products").update({"embedding": embedding}).eq(
                    "id", product_id
                ).execute()
                stored += 1
            except Exception as e:
                console.print(
                    f"[red]Error storing embedding for {product_id}: {e}[/red]"
                )

        console.print(f"[green]Stored {stored} embeddings in database[/green]")
        return stored

    async def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[dict]:
        """
        Semantic search for products matching a query.

        Args:
            query: Natural language search query
            limit: Maximum results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of matching products with similarity scores
        """
        if self.supabase is None:
            raise ValueError("Supabase client required for search")

        # Generate query embedding
        query_embedding = await self.embed_text(query)

        if not query_embedding:
            console.print("[red]Failed to generate query embedding[/red]")
            return []

        try:
            # Use Supabase's pgvector similarity search
            # This requires a function like match_products in Supabase
            response = self.supabase.rpc(
                "match_products",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": threshold,
                    "match_count": limit,
                },
            ).execute()

            return response.data or []

        except Exception as e:
            console.print(f"[yellow]Semantic search not available: {e}[/yellow]")
            console.print("[dim]Falling back to in-memory search...[/dim]")

            # Fallback: in-memory similarity search
            return await self._in_memory_search(query_embedding, limit, threshold)

    async def _in_memory_search(
        self,
        query_embedding: list[float],
        limit: int,
        threshold: float,
    ) -> list[dict]:
        """
        Fallback in-memory similarity search.

        Loads all products and computes similarity locally.
        Not recommended for large datasets.
        """
        import math

        # Fetch all products with embeddings
        response = self.supabase.table("products").select("*").execute()
        products = response.data or []

        # Products without embeddings need them generated
        results = []

        for product in products:
            # Get or generate embedding
            product_embedding = product.get("embedding")

            if not product_embedding:
                # Generate embedding on the fly (slower)
                product_embedding = await self.embed_product(product)

            if product_embedding:
                # Calculate cosine similarity
                similarity = self._cosine_similarity(query_embedding, product_embedding)

                if similarity >= threshold:
                    results.append(
                        {
                            **product,
                            "similarity": similarity,
                        }
                    )

        # Sort by similarity and return top results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math

        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = math.sqrt(sum(x * x for x in a))
        magnitude_b = math.sqrt(sum(x * x for x in b))

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    async def find_similar(
        self,
        product_id: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Find products similar to a given product.

        Args:
            product_id: ID of the reference product
            limit: Maximum similar products to return

        Returns:
            List of similar products with similarity scores
        """
        if self.supabase is None:
            raise ValueError("Supabase client required")

        # Get the reference product
        response = (
            self.supabase.table("products").select("*").eq("id", product_id).execute()
        )

        if not response.data:
            console.print(f"[red]Product {product_id} not found[/red]")
            return []

        product = response.data[0]

        # Get or generate embedding
        embedding = product.get("embedding")
        if not embedding:
            embedding = await self.embed_product(product)

        if not embedding:
            return []

        # Search for similar products
        try:
            response = self.supabase.rpc(
                "match_products",
                {
                    "query_embedding": embedding,
                    "match_threshold": 0.5,
                    "match_count": limit + 1,  # +1 to exclude self
                },
            ).execute()

            # Filter out the reference product
            results = [p for p in (response.data or []) if p.get("id") != product_id]
            return results[:limit]

        except Exception as e:
            console.print(f"[yellow]Database similarity search failed: {e}[/yellow]")
            return await self._in_memory_search(embedding, limit + 1, 0.5)


# SQL function for Supabase (run once to enable pgvector search)
MATCH_PRODUCTS_SQL = """
-- Enable pgvector extension (run as admin)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to products table
ALTER TABLE products
ADD COLUMN IF NOT EXISTS embedding vector(768);

-- Create index for fast similarity search
CREATE INDEX IF NOT EXISTS products_embedding_idx
ON products USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create the match function
CREATE OR REPLACE FUNCTION match_products(
    query_embedding vector(768),
    match_threshold float,
    match_count int
)
RETURNS TABLE (
    id text,
    name text,
    description text,
    price text,
    category text,
    primary_image text,
    colors jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        products.id,
        products.name,
        products.description,
        products.price,
        products.category,
        products.primary_image,
        products.colors,
        1 - (products.embedding <=> query_embedding) as similarity
    FROM products
    WHERE products.embedding IS NOT NULL
    AND 1 - (products.embedding <=> query_embedding) > match_threshold
    ORDER BY products.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""


async def test_embeddings():
    """Test the embeddings service."""
    from dotenv import load_dotenv

    load_dotenv()

    console.print("\n[bold cyan]Testing Embeddings Service[/bold cyan]\n")

    async with EmbeddingsService() as embeddings:
        # Check AI service
        client = embeddings._get_client()
        if not await client.is_available():
            console.print("[red]AI service not available. Check your API key.[/red]")
            return

        # Test embedding generation
        console.print("[cyan]Testing text embedding...[/cyan]")
        test_text = "casual summer t-shirt for beach vacation"
        embedding = await embeddings.embed_text(test_text)

        console.print(f"[green]Embedding dimensions:[/green] {len(embedding)}")
        console.print(f"[dim]First 5 values: {embedding[:5]}[/dim]")

        # Test product embedding
        console.print("\n[cyan]Testing product embedding...[/cyan]")
        test_product = {
            "name": "RELAXED FIT LINEN BLEND SHIRT",
            "description": "A comfortable linen shirt perfect for summer",
            "category": "shirts",
            "colors": ["white", "beige"],
            "tags": ["casual", "summer", "linen"],
        }
        product_embedding = await embeddings.embed_product(test_product)

        console.print(
            f"[green]Product embedding dimensions:[/green] {len(product_embedding)}"
        )

        # Test similarity
        console.print("\n[cyan]Testing similarity calculation...[/cyan]")
        query_embedding = await embeddings.embed_text("linen summer shirt")
        similarity = embeddings._cosine_similarity(product_embedding, query_embedding)
        console.print(f"[green]Similarity score:[/green] {similarity:.4f}")

        # Show SQL setup
        console.print("\n[cyan]Supabase setup SQL:[/cyan]")
        console.print(
            "[dim]Run this in Supabase SQL editor to enable pgvector search:[/dim]"
        )
        console.print(f"[yellow]{MATCH_PRODUCTS_SQL[:500]}...[/yellow]")


if __name__ == "__main__":
    asyncio.run(test_embeddings())
