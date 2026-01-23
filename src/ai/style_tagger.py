"""
Style Tagger - Vision-based style tag generation

Uses a vision model to analyze clothing product images and generate
relevant style tags for categorization and search.

Usage:
    from src.ai import StyleTagger

    tagger = StyleTagger()
    tags = await tagger.generate_tags(image_url, product_name)
    # Returns: ["casual", "minimal", "neutral", "summer"]
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .ollama_client import OllamaClient, OllamaConfig

console = Console()


# Predefined style vocabulary for consistent tagging
# This is the built-in default vocabulary. Users can extend this via the
# custom_vocabulary table in Supabase using the Vocabulary Manager UI.
STYLE_CATEGORIES = {
    "aesthetic": [
        "minimal",
        "maximalist",
        "classic",
        "modern",
        "vintage",
        "retro",
        "bohemian",
        "streetwear",
        "preppy",
        "athleisure",
        "grunge",
        "smart-casual",
        "formal",
        "business",
        "workwear",
        "loungewear",
    ],
    "fit": [
        "slim",
        "regular",
        "relaxed",
        "oversized",
        "tailored",
        "fitted",
        "loose",
        "cropped",
        "longline",
        "boxy",
    ],
    "pattern": [
        "solid",
        "striped",
        "checked",
        "plaid",
        "printed",
        "graphic",
        "floral",
        "geometric",
        "abstract",
        "camo",
        "tie-dye",
    ],
    "material_feel": [
        "cotton",
        "linen",
        "denim",
        "leather",
        "wool",
        "synthetic",
        "knit",
        "woven",
        "jersey",
        "fleece",
        "corduroy",
        "satin",
    ],
    "season": [
        "summer",
        "winter",
        "spring",
        "fall",
        "all-season",
        "transitional",
    ],
    "occasion": [
        "casual",
        "formal",
        "business",
        "party",
        "beach",
        "outdoor",
        "athletic",
        "lounge",
        "date-night",
        "travel",
        "everyday",
    ],
    "color_mood": [
        "neutral",
        "bold",
        "muted",
        "earthy",
        "pastel",
        "monochrome",
        "colorful",
        "dark",
        "light",
        "vibrant",
    ],
    "details": [
        "pocket",
        "zip",
        "button",
        "collar",
        "hood",
        "logo",
        "embroidered",
        "distressed",
        "raw-hem",
        "pleated",
    ],
}

# Flatten for validation
ALL_VALID_TAGS = set()
for category_tags in STYLE_CATEGORIES.values():
    ALL_VALID_TAGS.update(category_tags)


def load_custom_vocabulary(supabase_client: Any) -> dict[str, list[str]]:
    """
    Load custom vocabulary from Supabase.

    Args:
        supabase_client: Supabase client instance

    Returns:
        Dictionary of category -> list of tags
    """
    if not supabase_client:
        return {}

    try:
        result = supabase_client.table("custom_vocabulary").select("*").execute()

        vocabulary = {}
        for item in result.data or []:
            category = item.get("category")
            tag = item.get("tag")
            if category and tag:
                if category not in vocabulary:
                    vocabulary[category] = []
                vocabulary[category].append(tag)

        return vocabulary
    except Exception as e:
        console.print(f"[yellow]Could not load custom vocabulary: {e}[/yellow]")
        return {}


def get_merged_vocabulary(
    supabase_client: Any = None,
) -> tuple[dict[str, list[str]], set[str]]:
    """
    Get the merged vocabulary (built-in + custom).

    Args:
        supabase_client: Optional Supabase client for loading custom vocabulary

    Returns:
        Tuple of (category dict, flattened set of all valid tags)
    """
    # Start with built-in vocabulary (deep copy)
    merged = {k: list(v) for k, v in STYLE_CATEGORIES.items()}

    # Load and merge custom vocabulary
    custom = load_custom_vocabulary(supabase_client)

    for category, tags in custom.items():
        if category in merged:
            # Add to existing category (avoid duplicates)
            existing = set(merged[category])
            for tag in tags:
                if tag not in existing:
                    merged[category].append(tag)
        else:
            # New custom category
            merged[category] = list(tags)

    # Flatten for validation
    all_tags = set()
    for category_tags in merged.values():
        all_tags.update(category_tags)

    return merged, all_tags


@dataclass
class TaggingConfig:
    """Configuration for style tagging."""

    max_tags: int = 8
    min_tags: int = 3
    temperature: float = 0.3  # Low temp for consistency
    validate_tags: bool = True  # Only return tags from vocabulary


STYLE_TAGGER_PROMPT = """You are a fashion expert analyzing clothing product images.

Analyze this product image and generate style tags that describe:
1. Overall aesthetic (minimal, streetwear, preppy, etc.)
2. Fit and silhouette (slim, oversized, tailored, etc.)
3. Pattern/print (solid, striped, graphic, etc.)
4. Material appearance (cotton, denim, knit, etc.)
5. Season suitability (summer, winter, all-season, etc.)
6. Occasion (casual, formal, everyday, etc.)
7. Color mood (neutral, bold, muted, etc.)
8. Notable details (pocket, collar, distressed, etc.)

Product name for context: {product_name}

IMPORTANT: Return ONLY a JSON array of lowercase style tags. No explanations.
Example response: ["casual", "minimal", "cotton", "summer", "neutral", "slim"]

Generate 4-8 relevant tags for this product:"""


class StyleTagger:
    """
    Vision-based style tag generator for clothing products.

    Uses Moondream (or other vision model) to analyze product images
    and generate relevant style tags for categorization and search.

    The tagger validates generated tags against a vocabulary that combines:
    - Built-in default tags (defined in STYLE_CATEGORIES)
    - Custom user-defined tags (loaded from Supabase custom_vocabulary table)
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        config: Optional[TaggingConfig] = None,
        supabase_client: Any = None,
    ):
        self.client = ollama_client
        self.config = config or TaggingConfig()
        self._owns_client = ollama_client is None
        self.supabase_client = supabase_client

        # Load merged vocabulary (built-in + custom)
        self._style_categories, self._valid_tags = get_merged_vocabulary(
            supabase_client
        )

    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            self.client = OllamaClient()
            await self.client.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._owns_client and self.client:
            await self.client.close()

    def _get_client(self) -> OllamaClient:
        """Get the Ollama client."""
        if self.client is None:
            self.client = OllamaClient()
            self._owns_client = True
        return self.client

    async def generate_tags(
        self,
        image_url: str,
        product_name: str = "",
        product_description: str = "",
    ) -> list[str]:
        """
        Generate style tags for a product image.

        Args:
            image_url: URL of the product image
            product_name: Product name for context
            product_description: Optional product description

        Returns:
            List of style tags
        """
        client = self._get_client()

        # Build the prompt
        context = product_name
        if product_description:
            context += f" - {product_description[:200]}"

        prompt = STYLE_TAGGER_PROMPT.format(product_name=context)

        try:
            response = await client.generate_with_image(
                prompt=prompt,
                image=image_url,
                temperature=self.config.temperature,
            )

            if not response:
                console.print("[yellow]No response from vision model[/yellow]")
                return self._fallback_tags(product_name)

            # Parse the response
            tags = self._parse_tags(response)

            # Validate and clean
            if self.config.validate_tags:
                tags = self._validate_tags(tags)

            # Ensure we have enough tags
            if len(tags) < self.config.min_tags:
                tags = self._augment_tags(tags, product_name)

            return tags[: self.config.max_tags]

        except Exception as e:
            console.print(f"[red]Error generating tags: {e}[/red]")
            return self._fallback_tags(product_name)

    async def generate_tags_batch(
        self,
        products: list[dict],
        show_progress: bool = True,
    ) -> dict[str, list[str]]:
        """
        Generate tags for multiple products.

        Args:
            products: List of dicts with 'id', 'image_url', 'name' keys
            show_progress: Show progress bar

        Returns:
            Dict mapping product_id to list of tags
        """
        results = {}

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Generating tags for {len(products)} products...",
                    total=len(products),
                )

                for product in products:
                    product_id = product.get("id", product.get("product_id", ""))
                    image_url = product.get(
                        "image_url", product.get("primary_image", "")
                    )
                    name = product.get("name", "")
                    description = product.get("description", "")

                    if image_url:
                        tags = await self.generate_tags(
                            image_url=image_url,
                            product_name=name,
                            product_description=description,
                        )
                        results[product_id] = tags
                    else:
                        results[product_id] = self._fallback_tags(name)

                    progress.update(task, advance=1)
        else:
            for product in products:
                product_id = product.get("id", product.get("product_id", ""))
                image_url = product.get("image_url", product.get("primary_image", ""))
                name = product.get("name", "")
                description = product.get("description", "")

                if image_url:
                    tags = await self.generate_tags(
                        image_url=image_url,
                        product_name=name,
                        product_description=description,
                    )
                    results[product_id] = tags
                else:
                    results[product_id] = self._fallback_tags(name)

        return results

    def _parse_tags(self, response: str) -> list[str]:
        """Parse tags from model response."""
        # Try to find JSON array in response
        try:
            # Look for array pattern
            match = re.search(r"\[([^\]]+)\]", response)
            if match:
                array_str = f"[{match.group(1)}]"
                tags = json.loads(array_str)
                if isinstance(tags, list):
                    return [str(t).lower().strip() for t in tags if t]
        except json.JSONDecodeError:
            pass

        # Fallback: extract words that look like tags
        words = re.findall(r"[a-z][a-z-]+", response.lower())
        potential_tags = [w for w in words if w in self._valid_tags]

        if not potential_tags:
            # Even more aggressive: split on commas/spaces
            parts = re.split(r"[,\s]+", response.lower())
            potential_tags = [
                p.strip("\"'[]") for p in parts if p.strip("\"'[]") in self._valid_tags
            ]

        return potential_tags

    def _validate_tags(self, tags: list[str]) -> list[str]:
        """Filter tags to only those in our vocabulary (built-in + custom)."""
        validated = []
        for tag in tags:
            tag_clean = tag.lower().strip().replace(" ", "-")
            if tag_clean in self._valid_tags:
                validated.append(tag_clean)
            else:
                # Try to find a close match
                for valid_tag in self._valid_tags:
                    if tag_clean in valid_tag or valid_tag in tag_clean:
                        validated.append(valid_tag)
                        break

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for tag in validated:
            if tag not in seen:
                seen.add(tag)
                unique.append(tag)

        return unique

    def _fallback_tags(self, product_name: str) -> list[str]:
        """Generate basic tags from product name when vision fails."""
        tags = []
        name_lower = product_name.lower()

        # Check for category-specific tags
        category_keywords = {
            "tshirt": ["casual", "cotton", "everyday"],
            "t-shirt": ["casual", "cotton", "everyday"],
            "shirt": ["smart-casual", "woven", "collar"],
            "jeans": ["denim", "casual", "everyday"],
            "trousers": ["tailored", "formal", "smart-casual"],
            "shorts": ["casual", "summer", "relaxed"],
            "jacket": ["outerwear", "layering"],
            "blazer": ["formal", "tailored", "business"],
            "suit": ["formal", "tailored", "business"],
            "shoes": ["footwear"],
            "sneakers": ["casual", "athletic"],
        }

        for keyword, keyword_tags in category_keywords.items():
            if keyword in name_lower:
                tags.extend(keyword_tags)

        # Check for fit keywords
        fit_keywords = ["slim", "regular", "relaxed", "oversized", "fitted"]
        for fit in fit_keywords:
            if fit in name_lower:
                tags.append(fit)

        # Default tags if nothing found
        if not tags:
            tags = ["casual", "everyday"]

        return list(set(tags))[: self.config.max_tags]

    def _augment_tags(self, tags: list[str], product_name: str) -> list[str]:
        """Add more tags if we don't have enough."""
        fallback = self._fallback_tags(product_name)
        for tag in fallback:
            if tag not in tags:
                tags.append(tag)
        return tags

    @staticmethod
    def get_all_tags() -> dict[str, list[str]]:
        """Return all valid style tags by category."""
        return STYLE_CATEGORIES.copy()

    @staticmethod
    def get_tags_for_category(category: str) -> list[str]:
        """Get valid tags for a specific category."""
        return STYLE_CATEGORIES.get(category, [])


async def test_tagger():
    """Test the style tagger."""
    console.print("\n[bold cyan]Testing Style Tagger[/bold cyan]\n")

    # Test with a sample Zara product image
    test_image = "https://static.zara.net/assets/public/a95b/5c8f/3d324a14a5c8/b8c8e8a3a84a/00761306250-e1/00761306250-e1.jpg"
    test_name = "RELAXED FIT LINEN BLEND SHIRT"

    async with StyleTagger() as tagger:
        # Check if Ollama is available
        client = tagger._get_client()
        if not await client.is_available():
            console.print("[red]Ollama is not running. Start with: ollama serve[/red]")
            return

        console.print(f"[cyan]Analyzing: {test_name}[/cyan]")
        console.print(f"[dim]Image: {test_image}[/dim]\n")

        tags = await tagger.generate_tags(
            image_url=test_image,
            product_name=test_name,
        )

        console.print(f"[green]Generated tags:[/green] {tags}")

        # Show available tag categories
        console.print("\n[cyan]Available tag categories:[/cyan]")
        for category, category_tags in STYLE_CATEGORIES.items():
            console.print(f"  {category}: {', '.join(category_tags[:5])}...")


if __name__ == "__main__":
    asyncio.run(test_tagger())
