"""
Product transformer for cleaning and normalizing scraped data.
Includes inference logic for fit, weight, style tags, and formality.
"""

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PriceInfo(BaseModel):
    """Price information model."""

    current: Optional[float] = None
    original: Optional[float] = None
    currency: str = "USD"
    discount_percentage: Optional[float] = None


class FormalityInfo(BaseModel):
    """Formality assessment model."""

    score: int = Field(ge=1, le=5, default=3)  # 1-5 scale
    label: str = "Smart Casual"  # Human-readable label
    reasoning: list[str] = Field(
        default_factory=list
    )  # Factors that influenced the score


class WeightInfo(BaseModel):
    """Weight assessment model."""

    value: str  # light, medium, heavy
    reasoning: list[str] = Field(
        default_factory=list
    )  # Factors that influenced the assessment


class StyleTagInfo(BaseModel):
    """Style tag with reasoning."""

    tag: str
    reasoning: str  # Why this tag was applied


class SizeInfo(BaseModel):
    """Size with availability status."""

    size: str
    available: bool = True  # Whether the size is in stock


class ProductMetadata(BaseModel):
    """Validated and cleaned product metadata."""

    product_id: str
    name: str
    brand: str = "Zara"
    category: str
    subcategory: Optional[str] = None
    url: str
    price: PriceInfo
    description: Optional[str] = None
    colors: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)
    fit: Optional[str] = None  # slim, relaxed, wide, regular, oversized, etc.
    weight: Optional[WeightInfo] = None  # Weight with reasoning
    style_tags: list[StyleTagInfo] = Field(
        default_factory=list
    )  # Style tags with reasoning
    formality: Optional[FormalityInfo] = None  # Formality assessment
    scraped_at: str

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        """Clean and normalize product name."""
        if not v:
            return "Unknown Product"
        # Remove extra whitespace
        v = re.sub(r"\s+", " ", v).strip()
        # Title case
        return v.title()

    @field_validator("description")
    @classmethod
    def clean_description(cls, v: Optional[str]) -> Optional[str]:
        """Clean description text."""
        if not v:
            return None
        # Remove extra whitespace and newlines
        v = re.sub(r"\s+", " ", v).strip()
        return v if v else None

    @field_validator("colors", "sizes", "materials")
    @classmethod
    def clean_list(cls, v: list) -> list:
        """Clean list items."""
        if not v:
            return []
        # Remove duplicates while preserving order, clean whitespace
        seen = set()
        result = []
        for item in v:
            cleaned = str(item).strip()
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                result.append(cleaned)
        return result


class ProductTransformer:
    """Transforms raw product data into clean, validated format."""

    # Formality scale labels
    FORMALITY_LABELS = {
        1: "Very Casual",
        2: "Casual",
        3: "Smart Casual",
        4: "Business Casual",
        5: "Formal",
    }

    # Fit keywords to look for in name and description
    FIT_PATTERNS = {
        "slim": r"\b(slim|skinny|fitted|tailored)\b",
        "relaxed": r"\b(relaxed|loose|easy)\b",
        "wide": r"\b(wide|wide[- ]?leg|wide[- ]?fit)\b",
        "oversized": r"\b(oversized|over[- ]?sized|boxy|loose[- ]?fit)\b",
        "regular": r"\b(regular|standard|classic)\b",
        "cropped": r"\b(cropped|crop)\b",
        "straight": r"\b(straight|straight[- ]?leg|straight[- ]?fit)\b",
        "tapered": r"\b(tapered|taper)\b",
        "athletic": r"\b(athletic|sport|active)\b",
        "comfort": r"\b(comfort|comfortable)\b",
    }

    # Weight keywords to look for in description and materials
    WEIGHT_PATTERNS = {
        "light": r"\b(light|lightweight|thin|sheer|breathable|summer|airy)\b",
        "medium": r"\b(medium[- ]?weight|mid[- ]?weight|regular[- ]?weight)\b",
        "heavy": r"\b(heavy|heavyweight|thick|warm|winter|fleece|wool|dense|brushed)\b",
    }

    # Style tag inference rules
    STYLE_RULES = {
        "minimal": {
            "name_patterns": [r"\b(basic|essential|simple|plain)\b"],
            "description_patterns": [r"\b(simple|clean|minimal|essential)\b"],
            "color_hints": ["white", "black", "grey", "gray", "navy", "beige"],
        },
        "modern": {
            "name_patterns": [r"\b(modern|contemporary|tech|technical)\b"],
            "description_patterns": [r"\b(modern|innovative|technical|performance)\b"],
        },
        "classic": {
            "name_patterns": [r"\b(classic|traditional|timeless|heritage)\b"],
            "description_patterns": [r"\b(classic|traditional|timeless)\b"],
        },
        "casual": {
            "name_patterns": [r"\b(casual|everyday|relaxed|jogger)\b"],
            "description_patterns": [r"\b(casual|everyday|comfortable|easy)\b"],
            "category_hints": ["t-shirts", "tshirts", "joggers"],
        },
        "formal": {
            "name_patterns": [r"\b(suit|formal|dress|tailored|blazer)\b"],
            "description_patterns": [r"\b(formal|elegant|sophisticated|tailored)\b"],
        },
        "sporty": {
            "name_patterns": [r"\b(sport|athletic|active|training|running)\b"],
            "description_patterns": [
                r"\b(sport|athletic|active|performance|moisture)\b"
            ],
            "material_hints": ["polyester", "nylon", "spandex", "elastane"],
        },
        "streetwear": {
            "name_patterns": [r"\b(street|urban|graphic|oversized|hoodie)\b"],
            "description_patterns": [r"\b(street|urban|bold)\b"],
        },
        "layering": {
            "name_patterns": [r"\b(layer|layering|cardigan|vest|gilet)\b"],
            "description_patterns": [r"\b(layer|layering|versatile)\b"],
        },
        "premium": {
            "name_patterns": [r"\b(premium|luxury|limited|edition|leather)\b"],
            "description_patterns": [
                r"\b(premium|luxury|high[- ]?quality|exclusive)\b"
            ],
            "price_threshold": 150,
        },
        "sustainable": {
            "name_patterns": [r"\b(eco|sustainable|organic|recycled)\b"],
            "description_patterns": [
                r"\b(sustainable|organic|recycled|eco[- ]?friendly)\b"
            ],
            "material_hints": ["organic", "recycled"],
        },
        "water-resistant": {
            "name_patterns": [
                r"\b(water[- ]?repellent|water[- ]?resistant|waterproof)\b"
            ],
            "description_patterns": [
                r"\b(water[- ]?repellent|water[- ]?resistant|waterproof)\b"
            ],
        },
        "textured": {
            "name_patterns": [r"\b(textured|ribbed|knit|waffle|quilted)\b"],
            "description_patterns": [r"\b(textured|ribbed|knit|waffle|quilted)\b"],
        },
    }

    # =====================================================
    # FORMALITY INFERENCE RULES
    # Based on classic menswear formality principles
    # =====================================================

    # Garment types and their base formality scores
    GARMENT_FORMALITY = {
        # Very casual (1)
        "jogger": 1,
        "sweatpants": 1,
        "hoodie": 1,
        "sweatshirt": 1,
        "tank": 1,
        "shorts": 1,
        "flip flops": 1,
        # Casual (2)
        "t-shirt": 2,
        "tshirt": 2,
        "tee": 2,
        "polo": 2,
        "jeans": 2,
        "sneakers": 2,
        "chinos": 2,
        "cargo": 2,
        "parka": 2,
        # Smart casual (3)
        "button-down": 3,
        "oxford": 3,
        "cardigan": 3,
        "sweater": 3,
        "loafer": 3,
        "derby": 3,
        "chino": 3,
        "bomber": 3,
        # Business casual (4)
        "dress shirt": 4,
        "blazer": 4,
        "sport coat": 4,
        "trousers": 4,
        "dress pants": 4,
        "monk strap": 4,
        "oxford shoes": 4,
        # Formal (5)
        "suit": 5,
        "tuxedo": 5,
        "dinner jacket": 5,
        "dress shoes": 5,
        "formal": 5,
        "morning coat": 5,
        "tailcoat": 5,
    }

    # Colors and their formality modifiers
    COLOR_FORMALITY = {
        # More formal (darker, somber)
        "black": +0.5,
        "charcoal": +0.5,
        "navy": +0.3,
        "dark grey": +0.3,
        "dark gray": +0.3,
        "midnight": +0.3,
        # Neutral
        "grey": 0,
        "gray": 0,
        "white": 0,
        "cream": 0,
        "ivory": 0,
        # Less formal (brighter, casual)
        "brown": -0.2,
        "tan": -0.2,
        "beige": -0.1,
        "khaki": -0.2,
        "light blue": -0.2,
        "pastel": -0.3,
        "bright": -0.5,
        "red": -0.3,
        "yellow": -0.4,
        "orange": -0.4,
        "pink": -0.3,
        "green": -0.2,
        "turquoise": -0.3,
        "coral": -0.3,
    }

    # Materials and their formality modifiers
    MATERIAL_FORMALITY = {
        # More formal (smooth, refined)
        "silk": +0.5,
        "cashmere": +0.4,
        "worsted wool": +0.4,
        "worsted": +0.3,
        "merino": +0.2,
        "wool": +0.2,
        "satin": +0.3,
        "velvet": +0.3,
        "patent leather": +0.5,
        "leather": +0.2,
        "calf leather": +0.3,
        # Neutral
        "cotton": 0,
        "poplin": 0,
        "broadcloth": 0,
        # Less formal (textured, casual)
        "linen": -0.3,
        "denim": -0.4,
        "canvas": -0.3,
        "corduroy": -0.2,
        "tweed": -0.2,
        "flannel": -0.1,
        "fleece": -0.4,
        "jersey": -0.3,
        "terry": -0.4,
        "nylon": -0.3,
        "polyester": -0.2,
        "mesh": -0.4,
        "suede": -0.2,
        "nubuck": -0.2,
    }

    # Pattern formality modifiers (patterns = less formal)
    PATTERN_FORMALITY = {
        "solid": +0.2,
        "plain": +0.2,
        "pinstripe": +0.1,
        "subtle": 0,
        "striped": -0.1,
        "stripes": -0.1,
        "checked": -0.2,
        "check": -0.2,
        "plaid": -0.3,
        "houndstooth": -0.2,
        "glen": -0.2,
        "graphic": -0.4,
        "print": -0.3,
        "printed": -0.3,
        "floral": -0.3,
        "tropical": -0.4,
        "camo": -0.5,
        "tie-dye": -0.5,
    }

    # Structural elements formality modifiers
    STRUCTURE_FORMALITY = {
        # More formal (structured)
        "structured": +0.3,
        "tailored": +0.4,
        "lined": +0.2,
        "canvas": +0.2,
        "padded shoulders": +0.2,
        "peak lapel": +0.4,
        "peaked lapel": +0.4,
        "jetted pocket": +0.3,
        "welt pocket": +0.3,
        "french cuff": +0.3,
        "double cuff": +0.3,
        "cufflinks": +0.3,
        "wing collar": +0.4,
        # Less formal (unstructured)
        "unstructured": -0.2,
        "unlined": -0.2,
        "soft": -0.1,
        "notch lapel": 0,
        "patch pocket": -0.3,
        "elastic": -0.3,
        "drawstring": -0.4,
        "zip": -0.1,
        "zipper": -0.1,
        "button-down collar": -0.1,
    }

    # Category base scores
    CATEGORY_FORMALITY = {
        "tshirts": 2,
        "t-shirts": 2,
        "pants": 3,
        "trousers": 4,
        "jackets": 3,
        "blazers": 4,
        "suits": 5,
        "outerwear": 3,
        "sweaters": 3,
        "shirts": 3,
        "shoes": 3,
    }

    def __init__(self):
        self.category_mappings = {
            "tshirts": ("Tops", "T-Shirts"),
            "pants": ("Bottoms", "Pants"),
            "jackets": ("Outerwear", "Jackets"),
        }

    def _extract_fit(self, name: str, description: str) -> Optional[str]:
        """Extract fit type from product name and description."""
        text = f"{name} {description or ''}".lower()

        for fit_type, pattern in self.FIT_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return fit_type

        return None

    def _extract_weight(
        self, name: str, description: str, materials: list[str]
    ) -> Optional[WeightInfo]:
        """Extract weight/thickness from description and materials with reasoning."""
        text = f"{name} {description or ''} {' '.join(materials)}".lower()
        reasoning = []

        # Check for explicit weight mentions
        for weight_type, pattern in self.WEIGHT_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                reasoning.append(f"Explicit mention: '{match.group()}' in product text")
                return WeightInfo(value=weight_type, reasoning=reasoning)

        # Infer from materials if no explicit weight found
        heavy_materials = {
            "wool": "Wool is a naturally insulating, heavier fabric",
            "fleece": "Fleece is a thick, warm material",
            "denim": "Denim is a heavy cotton twill fabric",
            "leather": "Leather is a dense, substantial material",
            "down": "Down fill adds significant warmth and weight",
            "feather": "Feather fill provides insulation and body",
        }
        light_materials = {
            "linen": "Linen is a lightweight, breathable natural fiber",
            "silk": "Silk is a delicate, lightweight fabric",
            "mesh": "Mesh is an open-weave, airy material",
            "chiffon": "Chiffon is a sheer, lightweight fabric",
            "voile": "Voile is a thin, semi-transparent fabric",
        }

        materials_lower = " ".join(materials).lower()

        for mat, reason in heavy_materials.items():
            if mat in materials_lower:
                reasoning.append(reason)
                return WeightInfo(value="heavy", reasoning=reasoning)

        for mat, reason in light_materials.items():
            if mat in materials_lower:
                reasoning.append(reason)
                return WeightInfo(value="light", reasoning=reasoning)

        return None

    def _infer_style_tags(
        self,
        name: str,
        description: str,
        colors: list[str],
        materials: list[str],
        category: str,
        price: float,
    ) -> list[StyleTagInfo]:
        """Infer style tags from product attributes with reasoning."""
        tags = {}  # tag -> reasoning

        name_lower = name.lower()
        desc_lower = (description or "").lower()
        colors_lower = " ".join(colors).lower()
        materials_lower = " ".join(materials).lower()
        category_lower = category.lower()

        for tag, rules in self.STYLE_RULES.items():
            reasoning = None

            if "name_patterns" in rules:
                for pattern in rules["name_patterns"]:
                    match = re.search(pattern, name_lower, re.IGNORECASE)
                    if match:
                        reasoning = f"Name contains '{match.group()}'"
                        break

            if not reasoning and "description_patterns" in rules:
                for pattern in rules["description_patterns"]:
                    match = re.search(pattern, desc_lower, re.IGNORECASE)
                    if match:
                        reasoning = f"Description mentions '{match.group()}'"
                        break

            if not reasoning and "color_hints" in rules:
                for color_hint in rules["color_hints"]:
                    if color_hint in colors_lower:
                        reasoning = f"Color '{color_hint}' suggests this style"
                        break

            if not reasoning and "material_hints" in rules:
                for mat_hint in rules["material_hints"]:
                    if mat_hint in materials_lower:
                        reasoning = f"Material '{mat_hint}' is typical for this style"
                        break

            if not reasoning and "category_hints" in rules:
                for cat_hint in rules["category_hints"]:
                    if cat_hint in category_lower:
                        reasoning = f"Category '{category}' is typically this style"
                        break

            if not reasoning and "price_threshold" in rules:
                if price and price >= rules["price_threshold"]:
                    reasoning = f"Price ${price:.2f} exceeds ${rules['price_threshold']} threshold"

            if reasoning:
                tags[tag] = reasoning

        return sorted(
            [StyleTagInfo(tag=tag, reasoning=reason) for tag, reason in tags.items()],
            key=lambda x: x.tag,
        )

    def _infer_formality(
        self,
        name: str,
        description: str,
        colors: list[str],
        materials: list[str],
        category: str,
        fit: Optional[str],
    ) -> FormalityInfo:
        """
        Infer formality level based on classic menswear principles.

        Considers:
        - Garment type (t-shirt vs suit)
        - Colors (dark/somber = formal, bright = casual)
        - Materials (smooth = formal, textured = casual)
        - Patterns (solid = formal, patterned = casual)
        - Structure (structured = formal, unstructured = casual)

        Returns:
            FormalityInfo with score (1-5), label, and reasoning
        """
        text = f"{name} {description or ''}".lower()
        colors_lower = " ".join(colors).lower()
        materials_lower = " ".join(materials).lower()

        score = 3.0  # Start at smart casual baseline
        reasoning = []

        # 1. Determine base score from garment type
        garment_found = False
        for garment, base_score in self.GARMENT_FORMALITY.items():
            if garment in text:
                score = base_score
                reasoning.append(f"Base: {garment} ({base_score}/5)")
                garment_found = True
                break

        # If no specific garment found, use category
        if not garment_found and category:
            cat_lower = category.lower()
            for cat, cat_score in self.CATEGORY_FORMALITY.items():
                if cat in cat_lower:
                    score = cat_score
                    reasoning.append(f"Category: {category} ({cat_score}/5)")
                    break

        # 2. Adjust for colors
        color_adjustment = 0
        for color, adj in self.COLOR_FORMALITY.items():
            if color in colors_lower:
                color_adjustment = (
                    max(color_adjustment, adj)
                    if adj > 0
                    else min(color_adjustment, adj)
                )
        if color_adjustment != 0:
            score += color_adjustment
            direction = "darker/formal" if color_adjustment > 0 else "brighter/casual"
            reasoning.append(f"Color: {direction} ({color_adjustment:+.1f})")

        # 3. Adjust for materials
        material_adjustment = 0
        for material, adj in self.MATERIAL_FORMALITY.items():
            if material in materials_lower:
                material_adjustment += adj
        if material_adjustment != 0:
            score += material_adjustment
            direction = "refined" if material_adjustment > 0 else "casual"
            reasoning.append(f"Material: {direction} ({material_adjustment:+.1f})")

        # 4. Adjust for patterns
        pattern_adjustment = 0
        for pattern, adj in self.PATTERN_FORMALITY.items():
            if pattern in text:
                pattern_adjustment = adj
                break
        if pattern_adjustment != 0:
            score += pattern_adjustment
            direction = "solid/plain" if pattern_adjustment > 0 else "patterned"
            reasoning.append(f"Pattern: {direction} ({pattern_adjustment:+.1f})")

        # 5. Adjust for structural elements
        structure_adjustment = 0
        for structure, adj in self.STRUCTURE_FORMALITY.items():
            if structure in text:
                structure_adjustment += adj
        if structure_adjustment != 0:
            score += structure_adjustment
            direction = "structured" if structure_adjustment > 0 else "unstructured"
            reasoning.append(f"Structure: {direction} ({structure_adjustment:+.1f})")

        # 6. Adjust for fit (tailored = more formal, relaxed = casual)
        if fit:
            fit_adjustments = {
                "slim": +0.2,
                "tailored": +0.3,
                "fitted": +0.2,
                "regular": 0,
                "straight": 0,
                "relaxed": -0.2,
                "wide": -0.1,
                "oversized": -0.3,
                "athletic": -0.2,
                "comfort": -0.2,
            }
            if fit in fit_adjustments:
                adj = fit_adjustments[fit]
                if adj != 0:
                    score += adj
                    reasoning.append(f"Fit: {fit} ({adj:+.1f})")

        # Clamp score to 1-5 range
        final_score = max(1, min(5, round(score)))

        return FormalityInfo(
            score=final_score,
            label=self.FORMALITY_LABELS[final_score],
            reasoning=reasoning,
        )

    def transform(self, raw_data) -> Optional[ProductMetadata]:
        """Transform raw product data into clean ProductMetadata."""
        try:
            # Calculate discount percentage if both prices available
            discount = None
            if raw_data.price_original and raw_data.price_current:
                if raw_data.price_original > raw_data.price_current:
                    discount = round(
                        (1 - raw_data.price_current / raw_data.price_original) * 100, 1
                    )

            # Get category and subcategory
            category, subcategory = self.category_mappings.get(
                raw_data.category, (raw_data.category.title(), None)
            )

            # Build price info
            price = PriceInfo(
                current=raw_data.price_current,
                original=raw_data.price_original,
                currency=raw_data.currency,
                discount_percentage=discount,
            )

            # Extract fit from name and description
            fit = self._extract_fit(raw_data.name, raw_data.description)

            # Extract weight from description and materials
            weight = self._extract_weight(
                raw_data.name, raw_data.description, raw_data.materials
            )

            # Infer style tags
            style_tags = self._infer_style_tags(
                name=raw_data.name,
                description=raw_data.description,
                colors=raw_data.colors,
                materials=raw_data.materials,
                category=raw_data.category,
                price=raw_data.price_current or 0,
            )

            # Infer formality
            formality = self._infer_formality(
                name=raw_data.name,
                description=raw_data.description,
                colors=raw_data.colors,
                materials=raw_data.materials,
                category=raw_data.category,
                fit=fit,
            )

            # Create validated metadata
            metadata = ProductMetadata(
                product_id=raw_data.product_id,
                name=raw_data.name,
                category=category,
                subcategory=subcategory,
                url=raw_data.url,
                price=price,
                description=raw_data.description,
                colors=raw_data.colors,
                sizes=raw_data.sizes,
                materials=raw_data.materials,
                images=[],  # Will be filled with local filenames after download
                fit=fit,
                weight=weight,
                style_tags=style_tags,
                formality=formality,
                scraped_at=raw_data.scraped_at,
            )

            return metadata

        except Exception as e:
            print(f"Error transforming product {raw_data.product_id}: {e}")
            return None

    def transform_batch(self, raw_data_list: list) -> list[ProductMetadata]:
        """Transform a batch of raw product data."""
        results = []
        for raw_data in raw_data_list:
            transformed = self.transform(raw_data)
            if transformed:
                results.append(transformed)
        return results
