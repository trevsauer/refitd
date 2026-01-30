"""
Chat Assistant - Conversational AI for fashion recommendations

Provides a conversational interface for users to:
- Get outfit recommendations
- Ask about product details
- Get styling advice
- Understand product compatibility

Usage:
    from src.ai import ChatAssistant

    assistant = ChatAssistant(supabase_client)

    # Single question
    response = await assistant.ask("What goes well with blue jeans?")

    # Multi-turn conversation
    response = await assistant.chat([
        {"role": "user", "content": "I need a casual summer outfit"},
        {"role": "assistant", "content": "I'd suggest..."},
        {"role": "user", "content": "Something with linen?"},
    ])
"""

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Union

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

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

from .embeddings import EmbeddingsService

# Type alias for either client
AIClient = (
    Union["OpenAIClient", "OllamaClient"]
    if OPENAI_AVAILABLE or OLLAMA_AVAILABLE
    else Any
)


SYSTEM_PROMPT = """You are a helpful fashion assistant for a men's clothing store called Refitd.

Your role is to:
1. Help users find clothes that match their style preferences
2. Suggest outfit combinations that work well together
3. Provide styling advice based on occasions, seasons, and personal preferences
4. Answer questions about specific products in the catalog
5. Recommend alternatives when items are unavailable

Style guidelines:
- Be friendly but concise - users want quick, helpful answers
- Focus on practical styling advice
- Consider body type, occasion, and personal style
- Suggest complete outfits when appropriate
- Mention specific products from the catalog when relevant

Current context:
{context}

When suggesting products, use information from the catalog context provided.
If no context is provided, give general styling advice."""


@dataclass
class ChatConfig:
    """Configuration for chat assistant."""

    temperature: float = 0.7
    max_tokens: int = 1024
    use_product_context: bool = True
    max_context_products: int = 5


@dataclass
class Message:
    """Represents a chat message."""

    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)


class ChatAssistant:
    """
    Conversational assistant for fashion recommendations.

    Uses semantic search to find relevant products and provides
    personalized styling advice based on user queries.
    """

    def __init__(
        self,
        supabase_client=None,
        ai_client: Optional[AIClient] = None,
        embeddings_service: Optional[EmbeddingsService] = None,
        config: Optional[ChatConfig] = None,
        use_openai: bool = True,
    ):
        """
        Initialize the ChatAssistant.

        Args:
            supabase_client: Supabase client for product data
            ai_client: Pre-configured AI client (OpenAI or Ollama)
            embeddings_service: Pre-configured embeddings service
            config: Chat configuration
            use_openai: If True, prefer OpenAI; if False, use Ollama
        """
        self.supabase = supabase_client
        self.client = ai_client
        self.embeddings = embeddings_service
        self.config = config or ChatConfig()
        self._owns_client = ai_client is None
        self._owns_embeddings = embeddings_service is None
        self._use_openai = use_openai and OPENAI_AVAILABLE
        self._conversation_history: list[Message] = []

    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            if self._use_openai and OPENAI_AVAILABLE:
                self.client = OpenAIClient()
                console.print("[green]Using OpenAI GPT-4o for chat[/green]")
            elif OLLAMA_AVAILABLE:
                self.client = OllamaClient()
                console.print("[yellow]Using Ollama for chat[/yellow]")
            else:
                raise RuntimeError("No AI client available. Install openai or ollama.")
            await self.client.connect()
        if self._owns_embeddings and self.supabase:
            self.embeddings = EmbeddingsService(
                supabase_client=self.supabase,
                ai_client=self.client,
            )
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

    async def _get_product_context(self, query: str) -> str:
        """Get relevant product context for the query."""
        if not self.embeddings or not self.config.use_product_context:
            return ""

        try:
            # Search for relevant products
            results = await self.embeddings.search(
                query=query,
                limit=self.config.max_context_products,
                threshold=0.5,
            )

            if not results:
                return "No specific products found matching this query."

            # Format products as context
            context_parts = ["Relevant products from catalog:"]
            for i, product in enumerate(results, 1):
                name = product.get("name", "Unknown")
                price = product.get("price", "N/A")
                category = product.get("category", "")
                colors = product.get("colors", [])
                similarity = product.get("similarity", 0)

                color_str = (
                    ", ".join(colors) if isinstance(colors, list) else str(colors)
                )

                context_parts.append(
                    f"{i}. {name} ({category}) - {price} - Colors: {color_str} "
                    f"[relevance: {similarity:.0%}]"
                )

            return "\n".join(context_parts)

        except Exception as e:
            console.print(f"[yellow]Could not fetch product context: {e}[/yellow]")
            return ""

    async def ask(
        self,
        question: str,
        include_context: bool = True,
    ) -> str:
        """
        Ask a single question.

        Args:
            question: User's question
            include_context: Whether to include product context

        Returns:
            Assistant's response
        """
        client = self._get_client()

        # Get product context if enabled
        context = ""
        if include_context and self.config.use_product_context:
            context = await self._get_product_context(question)

        # Build system prompt with context
        system = SYSTEM_PROMPT.format(
            context=context or "No product context available."
        )

        # Generate response
        response = await client.generate(
            prompt=question,
            system=system,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )

        # Track in history
        self._conversation_history.append(Message(role="user", content=question))
        self._conversation_history.append(Message(role="assistant", content=response))

        return response

    async def chat(
        self,
        messages: list[dict],
        include_context: bool = True,
    ) -> str:
        """
        Multi-turn chat conversation.

        Args:
            messages: List of {"role": "user/assistant", "content": "..."}
            include_context: Whether to include product context

        Returns:
            Assistant's response
        """
        client = self._get_client()

        # Get the last user message for context search
        last_user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_message = msg.get("content", "")
                break

        # Get product context if enabled
        context = ""
        if include_context and self.config.use_product_context and last_user_message:
            context = await self._get_product_context(last_user_message)

        # Build messages with system prompt
        system_message = {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                context=context or "No product context available."
            ),
        }

        full_messages = [system_message] + messages

        # Generate response
        response = await client.chat(
            messages=full_messages,
            temperature=self.config.temperature,
        )

        # Update history
        for msg in messages:
            self._conversation_history.append(
                Message(role=msg["role"], content=msg["content"])
            )
        self._conversation_history.append(Message(role="assistant", content=response))

        return response

    async def recommend_outfit(
        self,
        occasion: str,
        style_preference: Optional[str] = None,
        season: Optional[str] = None,
        budget: Optional[str] = None,
    ) -> str:
        """
        Get outfit recommendations for a specific occasion.

        Args:
            occasion: Event type (casual, formal, date, work, etc.)
            style_preference: User's style preference
            season: Current season
            budget: Budget constraints

        Returns:
            Outfit recommendations
        """
        # Build a detailed query
        query_parts = [f"outfit for {occasion}"]

        if style_preference:
            query_parts.append(f"in {style_preference} style")
        if season:
            query_parts.append(f"for {season}")
        if budget:
            query_parts.append(f"within {budget} budget")

        question = f"Can you recommend a complete {' '.join(query_parts)}? Please suggest specific items that would work well together."

        return await self.ask(question)

    async def find_alternatives(
        self,
        product_id: str,
        reason: str = "similar",
    ) -> str:
        """
        Find alternatives to a specific product.

        Args:
            product_id: ID of the reference product
            reason: Why user wants alternatives (similar, cheaper, different color)

        Returns:
            Alternative suggestions
        """
        if not self.supabase:
            return "Cannot find alternatives without database connection."

        # Get the reference product
        try:
            response = (
                self.supabase.table("products")
                .select("*")
                .eq("id", product_id)
                .execute()
            )

            if not response.data:
                return f"Product {product_id} not found."

            product = response.data[0]
            name = product.get("name", "Unknown")
            category = product.get("category", "")

            question = f"I'm looking at {name} ({category}). Can you suggest {reason} alternatives from the catalog?"

            return await self.ask(question)

        except Exception as e:
            return f"Error finding alternatives: {e}"

    async def explain_product(
        self,
        product_id: str,
    ) -> str:
        """
        Get detailed explanation about a product.

        Args:
            product_id: Product ID

        Returns:
            Product explanation with styling tips
        """
        if not self.supabase:
            return "Cannot explain product without database connection."

        try:
            response = (
                self.supabase.table("products")
                .select("*")
                .eq("id", product_id)
                .execute()
            )

            if not response.data:
                return f"Product {product_id} not found."

            product = response.data[0]

            # Build detailed product info
            info = f"""
Product: {product.get('name', 'Unknown')}
Category: {product.get('category', 'N/A')}
Price: {product.get('price', 'N/A')}
Description: {product.get('description', 'No description available')}
Colors: {product.get('colors', [])}
            """

            question = f"Please explain this product and provide styling tips:\n{info}"

            return await self.ask(question, include_context=False)

        except Exception as e:
            return f"Error explaining product: {e}"

    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return [
            {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp}
            for msg in self._conversation_history
        ]

    def clear_history(self) -> None:
        """Clear conversation history."""
        self._conversation_history.clear()

    async def interactive_chat(self) -> None:
        """
        Start an interactive chat session in the terminal.

        Type 'quit' or 'exit' to end the session.
        Type 'clear' to clear history.
        Type 'history' to see conversation history.
        """
        client = self._get_client()

        if not await client.is_available():
            console.print(
                "[red]AI service not available. Check your API key or Ollama server.[/red]"
            )
            return

        console.print(
            Panel(
                "[bold cyan]Refitd Fashion Assistant[/bold cyan]\n\n"
                "Ask me about:\n"
                "• Outfit recommendations\n"
                "• Styling advice\n"
                "• Product details\n"
                "• What to wear for occasions\n\n"
                "[dim]Type 'quit' to exit, 'clear' to reset, 'history' to see chat[/dim]",
                title="Welcome",
            )
        )

        messages = []

        while True:
            try:
                user_input = console.input("\n[bold cyan]You:[/bold cyan] ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ["quit", "exit", "q"]:
                    console.print("[dim]Goodbye![/dim]")
                    break

                if user_input.lower() == "clear":
                    messages.clear()
                    self.clear_history()
                    console.print("[dim]History cleared.[/dim]")
                    continue

                if user_input.lower() == "history":
                    if not messages:
                        console.print("[dim]No history yet.[/dim]")
                    else:
                        for msg in messages:
                            role = (
                                "[cyan]You[/cyan]"
                                if msg["role"] == "user"
                                else "[green]Assistant[/green]"
                            )
                            console.print(f"{role}: {msg['content'][:100]}...")
                    continue

                # Add user message
                messages.append({"role": "user", "content": user_input})

                # Generate response
                with console.status("[cyan]Thinking...[/cyan]"):
                    response = await self.chat(messages, include_context=True)

                # Add assistant response
                messages.append({"role": "assistant", "content": response})

                # Display response
                console.print("\n[bold green]Assistant:[/bold green]")
                console.print(Markdown(response))

            except KeyboardInterrupt:
                console.print("\n[dim]Goodbye![/dim]")
                break


async def test_chat():
    """Test the chat assistant."""
    from dotenv import load_dotenv

    load_dotenv()

    console.print("\n[bold cyan]Testing Chat Assistant[/bold cyan]\n")

    async with ChatAssistant() as assistant:
        # Check AI service
        client = assistant._get_client()
        if not await client.is_available():
            console.print("[red]AI service not available. Check your API key.[/red]")
            return

        # Test single question
        console.print("[cyan]Testing single question...[/cyan]")
        response = await assistant.ask(
            "What are some essential items for a casual summer wardrobe?",
            include_context=False,  # No Supabase in test
        )

        console.print("\n[green]Response:[/green]")
        console.print(Markdown(response))

        # Test outfit recommendation
        console.print("\n[cyan]Testing outfit recommendation...[/cyan]")
        response = await assistant.recommend_outfit(
            occasion="casual friday at work",
            style_preference="smart casual",
            season="summer",
        )

        console.print("\n[green]Response:[/green]")
        console.print(Markdown(response))

        # Show history
        console.print("\n[cyan]Conversation history:[/cyan]")
        for msg in assistant.get_history():
            role = "User" if msg["role"] == "user" else "Assistant"
            console.print(f"  {role}: {msg['content'][:80]}...")


if __name__ == "__main__":
    asyncio.run(test_chat())
