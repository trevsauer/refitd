"""
ReFitd Canonical Item Tagger

Implements the ReFitd Item Tagging Specification for structured,
controlled fashion tagging with confidence scores.

This is the SENSOR LAYER - it produces tags with confidence scores.
The POLICY LAYER (tag_policy.py) then decides which tags to accept.

Usage:
    from src.ai import ReFitdTagger

    async with ReFitdTagger() as tagger:
        result = await tagger.tag_product(
            image_url="https://...",
            title="Relaxed Fit Cotton T-Shirt",
            category="top_base",
            description="100% cotton crew neck tee..."
        )
        # Returns AI sensor output with confidence scores
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, TypedDict

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

# Import OpenAI client
try:
    from .openai_client import OpenAIClient, OpenAIConfig

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


# =============================================================================
# CANONICAL TAG VOCABULARIES (from ReFitd Item Tagging Specification)
# =============================================================================

# Product categories
CATEGORIES = Literal["top_base", "top_mid", "bottom", "outerwear", "shoes"]

# Style Identity (1-2 max, primary retrieval signal)
STYLE_IDENTITY_TAGS = frozenset(
    {
        "minimal",
        "classic",
        "preppy",
        "workwear",
        "streetwear",
        "rugged",
        "tailoring",
        "elevated-basics",
        "normcore",
        "sporty",
        "outdoorsy",
        "western",
        "vintage",
        "grunge",
        "punk",
        "utilitarian",
    }
)

# Fit tags (exactly one required)
FIT_TAGS = frozenset(
    {
        "skinny",  # Bottoms only
        "slim",
        "regular",
        "relaxed",
        "oversized",  # Tops and outerwear only
    }
)

# Silhouette - category aware (exactly one required)
SILHOUETTE_BOTTOM_TAGS = frozenset(
    {
        "straight",
        "tapered",
        "wide",
    }
)

SILHOUETTE_UPPER_TAGS = frozenset(
    {
        "boxy",
        "structured",
        "relaxed",
        "longline",
        "tailored",
    }
)

# Formality (exactly one required, ordered scale 1-5)
FORMALITY_TAGS = frozenset(
    {
        "athletic",  # Level 1
        "casual",  # Level 2
        "smart-casual",  # Level 3
        "business-casual",  # Level 4
        "formal",  # Level 5
    }
)

# Context (0-2 max, optional supporting layer)
CONTEXT_TAGS = frozenset(
    {
        "everyday",
        "work-appropriate",
        "travel",
        "evening",
        "weekend",
    }
)

# Materials - apparel (1-2 max)
MATERIALS_APPAREL_TAGS = frozenset(
    {
        "denim",
        "cotton",
        "wool",
        "linen",
        "leather",
        "synthetic",
        "blend",
    }
)

# Materials - shoes (1-2 max)
MATERIALS_SHOES_TAGS = frozenset(
    {
        "leather",
        "suede",
        "canvas",
        "knit",
        "synthetic",
        "blend",
    }
)

# Construction / Details - category aware (0-2 max)
DETAILS_BOTTOM_TAGS = frozenset(
    {
        "pleated",
        "flat-front",
        "cargo",
        "drawstring",
        "elastic-waist",
    }
)

DETAILS_UPPER_TAGS = frozenset(
    {
        "structured-shoulder",
        "dropped-shoulder",
    }
)

# Color Family (exactly one required)
COLOR_FAMILY_TAGS = frozenset(
    {
        "black",
        "white",
        "grey",
        "navy",
        "brown",
        "beige",
        "olive",
        "blue",
        "green",
        "red",
        "multi",
    }
)

# Pattern (0-1 max)
PATTERN_TAGS = frozenset(
    {
        "solid",
        "stripe",
        "check",
        "textured",
    }
)

# Pairing & Versatility (0-3 max, scoring only)
PAIRING_TAGS = frozenset(
    {
        "neutral-base",
        "statement-piece",
        "easy-dress-up",
        "easy-dress-down",
        "high-versatility",
    }
)

# Shoe-specific tags
SHOE_TYPE_TAGS = frozenset(
    {
        "sneakers",
        "boots",
        "loafers",
        "derbies",
        "oxfords",
        "sandals",
        "dress-shoes",  # Fallback bucket
    }
)

SHOE_PROFILE_TAGS = frozenset(
    {
        "sleek",
        "standard",
        "chunky",
    }
)

SHOE_CLOSURE_TAGS = frozenset(
    {
        "lace-up",
        "slip-on",
        "buckle",
    }
)


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================


class TagWithConfidence(TypedDict):
    tag: str
    confidence: float


class AITagOutput(TypedDict, total=False):
    """Sensor layer output with confidence scores.

    Note: Color and materials/composition are scraped directly, not AI-generated.
    Note: Fit is not AI-generated.
    Formality IS now AI-generated (for comparison with scraped values).
    """

    # Apparel fields
    style_identity: list[TagWithConfidence]
    silhouette: TagWithConfidence
    formality: TagWithConfidence  # AI-generated formality
    context: list[TagWithConfidence]
    construction_details: list[TagWithConfidence]
    pattern: TagWithConfidence
    pairing_tags: list[TagWithConfidence]

    # Shoe-specific fields
    shoe_type: TagWithConfidence
    profile: TagWithConfidence
    closure: TagWithConfidence


# =============================================================================
# SYSTEM PROMPT (Canonical)
# =============================================================================

SYSTEM_PROMPT = """You are a fashion item tagging system for ReFitd.

Your task is to analyze real retail fashion products using:
• product images
• product title
• product category
• product description

and return structured, controlled tags that follow the ReFitd Item Tagging Specification exactly.

You are not generating opinions, recommendations, outfits, marketing copy, or explanations.
You are producing machine-readable tags for a deterministic outfit generation engine.

NOTE: Color and composition/materials are already scraped from the retailer, so you do NOT need to tag those.
NOTE: Fit is NOT needed - focus on style identity, silhouette, formality, pattern, construction details, and pairing tags.
NOTE: Formality IS required - use the formality scale to indicate the dress code appropriateness.

IMPORTANT: If something is uncertain, prefer including the tag with lower confidence rather than omitting it, unless it would be misleading. It's better to provide a tag with 0.5-0.7 confidence than to omit it entirely.

Never invent tags outside the allowed vocabulary. Never exceed tag count limits."""


def build_user_prompt(
    category: str,
    title: str,
    description: str = "",
    brand: str = "",
) -> str:
    """Build the user prompt for tagging a product."""

    # Category-specific vocabulary info
    if category == "shoes":
        silhouette_info = "N/A for shoes"
        details_info = "N/A for shoes"
        shoe_section = f"""
### SHOE-SPECIFIC (Required for shoes):
- Shoe Type (exactly 1): {", ".join(sorted(SHOE_TYPE_TAGS))}
- Profile / Bulk (exactly 1): {", ".join(sorted(SHOE_PROFILE_TAGS))}
- Closure (0-1): {", ".join(sorted(SHOE_CLOSURE_TAGS))}
"""
    elif category == "bottom":
        silhouette_info = ", ".join(sorted(SILHOUETTE_BOTTOM_TAGS))
        details_info = ", ".join(sorted(DETAILS_BOTTOM_TAGS))
        shoe_section = ""
    else:  # top_base, top_mid, outerwear
        silhouette_info = ", ".join(sorted(SILHOUETTE_UPPER_TAGS))
        details_info = ", ".join(sorted(DETAILS_UPPER_TAGS))
        shoe_section = ""

    prompt = f"""## PRODUCT TO ANALYZE

**Brand:** {brand or "Unknown"}
**Title:** {title}
**Category:** {category}
**Description:** {description or "No description provided"}

---

## ALLOWED TAGS (Use ONLY these)

NOTE: Color and composition/materials are already scraped - DO NOT include them.
NOTE: Fit is NOT needed - focus on the tags below.
NOTE: Formality IS required - use the scale below.

### Style Identity (1-2 max, REQUIRED):
{", ".join(sorted(STYLE_IDENTITY_TAGS))}

### Silhouette (exactly 1, REQUIRED for apparel):
{silhouette_info}

### Formality (exactly 1, REQUIRED - indicates dress code appropriateness):
{", ".join(sorted(FORMALITY_TAGS))}
Scale: athletic (1) → casual (2) → smart-casual (3) → business-casual (4) → formal (5)

### Context (0-2, optional):
{", ".join(sorted(CONTEXT_TAGS))}

### Construction / Details (0-2, optional):
{details_info}

### Pattern (0-1, optional):
{", ".join(sorted(PATTERN_TAGS))}

### Pairing & Versatility (0-3, optional scoring tags):
{", ".join(sorted(PAIRING_TAGS))}
{shoe_section}
---

## CONFIDENCE GUIDELINES

IMPORTANT: Prefer including tags with lower confidence rather than omitting them, unless they would be misleading.

| Confidence | Meaning |
|------------|---------|
| 0.85–1.00 | Visually obvious or explicitly stated |
| 0.65–0.84 | Strong inference from images + text |
| 0.45–0.64 | Plausible but uncertain - STILL INCLUDE |
| < 0.45 | Only omit if it would be misleading |

> It's better to include a tag with 0.5 confidence than to omit it entirely.

---

## OUTPUT FORMAT (JSON ONLY)

Return ONLY valid JSON matching this structure. Omit optional fields if not applicable:

```json
{{
  "style_identity": [
    {{ "tag": "minimal", "confidence": 0.86 }}
  ],
  "silhouette": {{ "tag": "relaxed", "confidence": 0.78 }},
  "formality": {{ "tag": "casual", "confidence": 0.85 }},
  "context": [
    {{ "tag": "everyday", "confidence": 0.82 }}
  ],
  "construction_details": [
    {{ "tag": "flat-front", "confidence": 0.74 }}
  ],
  "pattern": {{ "tag": "solid", "confidence": 0.92 }},
  "pairing_tags": [
    {{ "tag": "neutral-base", "confidence": 0.75 }}
  ]
}}
```

For SHOES, also include:
- "shoe_type": {{ "tag": "sneakers", "confidence": 0.92 }}
- "profile": {{ "tag": "sleek", "confidence": 0.77 }}
- "closure": {{ "tag": "lace-up", "confidence": 0.85 }}

And OMIT: silhouette, construction_details

---

## EXPLICITLY FORBIDDEN

- ❌ Color or color_family tags (already scraped)
- ❌ Materials or composition tags (already scraped)
- ❌ Fit tags
- ❌ Era / decade tags (70s, 90s, Y2K)
- ❌ Garment archetypes (bomber, chore jacket, parka)
- ❌ Trend language or vibes
- ❌ Free-text descriptors
- ❌ Any tags NOT in the allowed lists above
- ❌ Any text outside the JSON

Now analyze the product and return ONLY the JSON:"""

    return prompt


# =============================================================================
# RESPONSE PARSING
# =============================================================================


def parse_ai_response(response: str, category: str) -> Optional[AITagOutput]:
    """
    Parse and validate the AI response.

    Args:
        response: Raw AI response string
        category: Product category for validation

    Returns:
        Validated AITagOutput or None if parsing fails
    """
    # Extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", response)
    if not json_match:
        console.print("[red]No JSON found in response[/red]")
        return None

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON parse error: {e}[/red]")
        return None

    # Validate and clean the response
    result: AITagOutput = {}

    # Style Identity (required, 1-2 max)
    if "style_identity" in data:
        valid_styles = []
        for item in data["style_identity"][:2]:
            if isinstance(item, dict) and item.get("tag") in STYLE_IDENTITY_TAGS:
                valid_styles.append(
                    {
                        "tag": item["tag"],
                        "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                    }
                )
        if valid_styles:
            result["style_identity"] = valid_styles

    # Category-specific validation
    if category == "shoes":
        # Shoe Type (required for shoes)
        if "shoe_type" in data:
            item = data["shoe_type"]
            if isinstance(item, dict) and item.get("tag") in SHOE_TYPE_TAGS:
                result["shoe_type"] = {
                    "tag": item["tag"],
                    "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                }

        # Profile (required for shoes)
        if "profile" in data:
            item = data["profile"]
            if isinstance(item, dict) and item.get("tag") in SHOE_PROFILE_TAGS:
                result["profile"] = {
                    "tag": item["tag"],
                    "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                }

        # Closure (optional for shoes)
        if "closure" in data:
            item = data["closure"]
            if isinstance(item, dict) and item.get("tag") in SHOE_CLOSURE_TAGS:
                result["closure"] = {
                    "tag": item["tag"],
                    "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                }
    else:
        # Apparel: Silhouette (required for apparel)
        if "silhouette" in data:
            item = data["silhouette"]
            tag = item.get("tag") if isinstance(item, dict) else None

            valid_silhouettes = (
                SILHOUETTE_BOTTOM_TAGS
                if category == "bottom"
                else SILHOUETTE_UPPER_TAGS
            )
            if tag in valid_silhouettes:
                result["silhouette"] = {
                    "tag": tag,
                    "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                }

        # Construction Details (optional, category-aware)
        if "construction_details" in data:
            valid_details_set = (
                DETAILS_BOTTOM_TAGS if category == "bottom" else DETAILS_UPPER_TAGS
            )
            valid_details = []
            for item in data["construction_details"][:2]:
                if isinstance(item, dict) and item.get("tag") in valid_details_set:
                    valid_details.append(
                        {
                            "tag": item["tag"],
                            "confidence": _clamp_confidence(
                                item.get("confidence", 0.5)
                            ),
                        }
                    )
            if valid_details:
                result["construction_details"] = valid_details

    # Formality (required, exactly 1)
    if "formality" in data:
        item = data["formality"]
        if isinstance(item, dict) and item.get("tag") in FORMALITY_TAGS:
            result["formality"] = {
                "tag": item["tag"],
                "confidence": _clamp_confidence(item.get("confidence", 0.5)),
            }

    # Context (optional, 0-2)
    if "context" in data:
        valid_context = []
        for item in data["context"][:2]:
            if isinstance(item, dict) and item.get("tag") in CONTEXT_TAGS:
                valid_context.append(
                    {
                        "tag": item["tag"],
                        "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                    }
                )
        if valid_context:
            result["context"] = valid_context

    # Pattern (optional, 0-1)
    if "pattern" in data:
        item = data["pattern"]
        if isinstance(item, dict) and item.get("tag") in PATTERN_TAGS:
            result["pattern"] = {
                "tag": item["tag"],
                "confidence": _clamp_confidence(item.get("confidence", 0.5)),
            }

    # Pairing Tags (optional, 0-3)
    if "pairing_tags" in data:
        valid_pairing = []
        for item in data["pairing_tags"][:3]:
            if isinstance(item, dict) and item.get("tag") in PAIRING_TAGS:
                valid_pairing.append(
                    {
                        "tag": item["tag"],
                        "confidence": _clamp_confidence(item.get("confidence", 0.5)),
                    }
                )
        if valid_pairing:
            result["pairing_tags"] = valid_pairing

    return result if result else None


def _clamp_confidence(value: Any) -> float:
    """Clamp confidence value to 0.0-1.0 range."""
    try:
        conf = float(value)
        return max(0.0, min(1.0, conf))
    except (TypeError, ValueError):
        return 0.5


# =============================================================================
# MAIN TAGGER CLASS
# =============================================================================


@dataclass
class ReFitdTaggerConfig:
    """Configuration for the ReFitd tagger."""

    temperature: float = 0.3  # Low for consistency
    max_tokens: int = 1024
    retry_attempts: int = 2


class ReFitdTagger:
    """
    ReFitd Canonical Item Tagger.

    Sensor layer that produces structured tags with confidence scores.
    Uses GPT-4o vision to analyze product images and metadata.

    Output follows the ReFitd Item Tagging Specification exactly.
    """

    def __init__(
        self,
        config: Optional[ReFitdTaggerConfig] = None,
        ai_client: Optional["OpenAIClient"] = None,
    ):
        self.config = config or ReFitdTaggerConfig()
        self.client = ai_client
        self._owns_client = ai_client is None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._owns_client:
            if not OPENAI_AVAILABLE:
                raise RuntimeError(
                    "OpenAI client not available. Install openai package."
                )
            self.client = OpenAIClient()
            await self.client.connect()
            console.print("[green]ReFitd Tagger initialized with GPT-4o[/green]")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._owns_client and self.client:
            await self.client.close()

    async def tag_product(
        self,
        image_url: str,
        title: str,
        category: str,
        description: str = "",
        brand: str = "",
    ) -> Optional[AITagOutput]:
        """
        Generate structured tags for a product.

        This is the SENSOR LAYER output - contains confidence scores.
        Use tag_policy.apply_policy() to get final canonical tags.

        Args:
            image_url: URL to product image (must be accessible)
            title: Product title
            category: One of: top_base, top_mid, bottom, outerwear, shoes
            description: Product description
            brand: Brand name

        Returns:
            AITagOutput with confidence scores, or None if tagging fails
        """
        if not self.client:
            raise RuntimeError("Tagger not initialized. Use async context manager.")

        # Validate category
        if category not in ("top_base", "top_mid", "bottom", "outerwear", "shoes"):
            console.print(f"[yellow]Warning: Unknown category '{category}'[/yellow]")

        # Build prompt
        user_prompt = build_user_prompt(
            category=category,
            title=title,
            description=description,
            brand=brand,
        )

        # Call vision model
        for attempt in range(self.config.retry_attempts):
            try:
                response = await self.client.generate_with_image(
                    prompt=user_prompt,
                    image=image_url,
                    temperature=self.config.temperature,
                )

                if not response:
                    console.print(
                        f"[yellow]Empty response (attempt {attempt + 1})[/yellow]"
                    )
                    continue

                # Parse response
                result = parse_ai_response(response, category)

                if result:
                    # Add category to result
                    result["category"] = category
                    return result

                console.print(
                    f"[yellow]Failed to parse response (attempt {attempt + 1})[/yellow]"
                )

            except Exception as e:
                console.print(f"[red]Error on attempt {attempt + 1}: {e}[/red]")

        return None

    async def tag_products_batch(
        self,
        products: list[dict],
        show_progress: bool = True,
    ) -> dict[str, AITagOutput]:
        """
        Generate tags for multiple products.

        Args:
            products: List of dicts with keys:
                - id or product_id: Product identifier
                - image_url: URL to product image
                - name or title: Product name
                - category: Product category
                - description: Optional description
                - brand: Optional brand
            show_progress: Show progress bar

        Returns:
            Dict mapping product_id to AITagOutput
        """
        results = {}

        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Tagging {len(products)} products...",
                    total=len(products),
                )

                for product in products:
                    product_id = product.get("id") or product.get(
                        "product_id", "unknown"
                    )
                    image_url = product.get("image_url", "")
                    title = product.get("name") or product.get("title", "")
                    category = product.get("category", "top_base")
                    description = product.get("description", "")
                    brand = product.get("brand", "")

                    if not image_url:
                        console.print(
                            f"[yellow]Skipping {product_id}: no image URL[/yellow]"
                        )
                        progress.update(task, advance=1)
                        continue

                    result = await self.tag_product(
                        image_url=image_url,
                        title=title,
                        category=category,
                        description=description,
                        brand=brand,
                    )

                    if result:
                        results[product_id] = result
                    else:
                        console.print(f"[yellow]Failed to tag {product_id}[/yellow]")

                    progress.update(task, advance=1)
        else:
            for product in products:
                product_id = product.get("id") or product.get("product_id", "unknown")
                image_url = product.get("image_url", "")
                title = product.get("name") or product.get("title", "")
                category = product.get("category", "top_base")
                description = product.get("description", "")
                brand = product.get("brand", "")

                if image_url:
                    result = await self.tag_product(
                        image_url=image_url,
                        title=title,
                        category=category,
                        description=description,
                        brand=brand,
                    )
                    if result:
                        results[product_id] = result

        return results


# =============================================================================
# TESTING
# =============================================================================


async def test_tagger():
    """Test the ReFitd tagger."""
    from dotenv import load_dotenv

    load_dotenv()

    console.print("\n[bold cyan]Testing ReFitd Canonical Tagger[/bold cyan]\n")

    # Test product (would need a real Supabase image URL)
    test_product = {
        "image_url": "https://static.zara.net/assets/public/a95b/5c8f/3d324a14a5c8/b8c8e8a3a84a/00761306250-e1/00761306250-e1.jpg",
        "title": "RELAXED FIT LINEN BLEND SHIRT",
        "category": "top_base",
        "description": "Relaxed fit shirt made of a linen blend fabric. Lapel collar and long sleeves with buttoned cuffs.",
        "brand": "Zara",
    }

    async with ReFitdTagger() as tagger:
        console.print(f"[cyan]Tagging: {test_product['title']}[/cyan]")
        console.print(f"[dim]Category: {test_product['category']}[/dim]\n")

        result = await tagger.tag_product(
            image_url=test_product["image_url"],
            title=test_product["title"],
            category=test_product["category"],
            description=test_product["description"],
            brand=test_product["brand"],
        )

        if result:
            console.print("[green]AI Sensor Output (with confidence):[/green]")
            console.print_json(json.dumps(result, indent=2))
        else:
            console.print("[red]Failed to generate tags[/red]")


if __name__ == "__main__":
    asyncio.run(test_tagger())
