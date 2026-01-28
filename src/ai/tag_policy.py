"""
ReFitd Tag Policy Layer

Applies confidence thresholds and category rules to AI sensor output.
Produces canonical tags (confidence-free) for the generator.

This is the DECISION LAYER:
- AI (sensor) proposes tags with confidence
- Policy (this module) decides what to accept/suppress/default
- Generator only sees approved canonical tags

Usage:
    from src.ai.tag_policy import apply_tag_policy
    from src.ai.refitd_tagger import ReFitdTagger, AITagOutput

    # Get AI sensor output
    ai_output: AITagOutput = await tagger.tag_product(...)

    # Apply policy
    result = apply_tag_policy(ai_output, category="bottom")

    # result contains:
    # - tags_final: canonical tags for generator
    # - curation_status: "approved" | "needs_review" | "needs_fix"
    # - curation_reasons: list of reasons
    # - suppressed_tags: tags that were dropped
    # - defaults_applied: fallback values used
"""

from dataclasses import dataclass, field
from typing import Any, Optional

from .refitd_tagger import (
    AITagOutput,
    CONTEXT_TAGS,
    DETAILS_BOTTOM_TAGS,
    DETAILS_UPPER_TAGS,
    FORMALITY_TAGS,
    PAIRING_TAGS,
    PATTERN_TAGS,
    SHOE_CLOSURE_TAGS,
    SHOE_PROFILE_TAGS,
    SHOE_TYPE_TAGS,
    SILHOUETTE_BOTTOM_TAGS,
    SILHOUETTE_UPPER_TAGS,
    STYLE_IDENTITY_TAGS,
    TagWithConfidence,
)


# =============================================================================
# POLICY VERSION
# =============================================================================

POLICY_VERSION = "tag_policy_v2.3"


# =============================================================================
# TOP LAYER ROLE DEFINITIONS
# =============================================================================
# For "top" category items, classify as base or mid layer

TOP_LAYER_BASE = [
    "tshirt",
    "t-shirt",
    "tee",
    "long sleeve",
    "shirt",
    "polo",
    "tank",
    "henley",
]
TOP_LAYER_MID = [
    "sweater",
    "cardigan",
    "hoodie",
    "knit",
    "pullover",
    "sweatshirt",
    "fleece",
]


# =============================================================================
# CONFIDENCE THRESHOLDS
# =============================================================================
# Updated to be more inclusive: prefer including tags with lower confidence
# rather than omitting them, unless they would be misleading.


@dataclass
class PolicyThresholds:
    """Configurable confidence thresholds for tag acceptance.

    Philosophy: Include tags with lower confidence rather than omit them.
    The generator can use confidence-weighted scoring, and curators can
    review edge cases. It's better to have more data than less.

    Note: Fit, color, and materials are NOT AI-generated.
    Color and composition are scraped directly from retailers.
    Formality is now AI-generated for comparison with scraped values.
    """

    # Style Identity (primary retrieval signal)
    style_identity_auto: float = 0.75
    style_identity_flag: float = 0.50

    # Silhouette (required for apparel)
    silhouette_auto: float = 0.70
    silhouette_allow: float = 0.45

    # Context (optional)
    context_allow: float = 0.55

    # Construction/Details (optional)
    details_allow: float = 0.65
    details_flag: float = 0.50

    # Pattern (optional)
    pattern_allow: float = 0.55

    # Pairing tags (scoring-only, very lenient)
    pairing_allow: float = 0.40

    # Formality (AI-generated, exactly one required)
    formality_auto: float = 0.70
    formality_flag: float = 0.50

    # Shoes
    shoe_type_auto: float = 0.65
    shoe_profile_allow: float = 0.50
    shoe_closure_allow: float = 0.50


# Default thresholds
DEFAULT_THRESHOLDS = PolicyThresholds()


# =============================================================================
# RESULT TYPES
# =============================================================================


@dataclass
class SuppressedTag:
    """Record of a suppressed tag."""

    field: str
    tag: str
    confidence: float
    reason: str


@dataclass
class AppliedDefault:
    """Record of a default value applied."""

    field: str
    value: str
    reason: str


@dataclass
class CanonicalTags:
    """Final canonical tags for the generator (no confidence).

    Note: Color and composition/materials are scraped from retailers.
    Formality is now AI-generated (in addition to scraped value for comparison).
    """

    category: str
    style_identity: list[str] = field(default_factory=list)
    silhouette: Optional[str] = None
    context: list[str] = field(default_factory=list)
    construction_details: list[str] = field(default_factory=list)
    pattern: Optional[str] = None
    pairing_tags: list[str] = field(default_factory=list)

    # AI-generated formality (for comparison with scraped formality)
    formality: Optional[str] = (
        None  # One of: athletic, casual, smart-casual, business-casual, formal
    )

    # Top-specific: layer role (base or mid)
    top_layer_role: Optional[str] = None  # "base" or "mid"

    # Shoe-specific
    shoe_type: Optional[str] = None
    profile: Optional[str] = None
    closure: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = {"category": self.category}

        if self.style_identity:
            result["style_identity"] = self.style_identity
        if self.silhouette:
            result["silhouette"] = self.silhouette
        if self.context:
            result["context"] = self.context
        if self.construction_details:
            result["construction_details"] = self.construction_details
        if self.pattern:
            result["pattern"] = self.pattern
        if self.pairing_tags:
            result["pairing_tags"] = self.pairing_tags

        # Formality (AI-generated)
        if self.formality:
            result["formality"] = self.formality

        # Top-specific
        if self.top_layer_role:
            result["top_layer_role"] = self.top_layer_role

        # Shoe-specific
        if self.shoe_type:
            result["shoe_type"] = self.shoe_type
        if self.profile:
            result["profile"] = self.profile
        if self.closure:
            result["closure"] = self.closure

        return result


@dataclass
class PolicyResult:
    """Complete result from policy application."""

    tags_final: CanonicalTags
    curation_status: str  # "approved" | "needs_review" | "needs_fix"
    curation_reasons: list[str]
    suppressed_tags: list[SuppressedTag]
    defaults_applied: list[AppliedDefault]
    tag_policy_version: str = POLICY_VERSION

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "tags_final": self.tags_final.to_dict(),
            "curation_status": self.curation_status,
            "curation_reasons": self.curation_reasons,
            "suppressed_tags": [
                {
                    "field": s.field,
                    "tag": s.tag,
                    "confidence": s.confidence,
                    "reason": s.reason,
                }
                for s in self.suppressed_tags
            ],
            "defaults_applied": [
                {"field": d.field, "value": d.value, "reason": d.reason}
                for d in self.defaults_applied
            ],
            "tag_policy_version": self.tag_policy_version,
        }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _is_bottom(category: str) -> bool:
    return category == "bottom"


def _is_top(category: str) -> bool:
    return category in ("top", "top_base", "top_mid")


def _is_top_or_outer(category: str) -> bool:
    return category in ("top", "top_base", "top_mid", "outerwear")


def _is_shoes(category: str) -> bool:
    return category == "shoes"


def _determine_top_layer_role(name: str, subcategory: str) -> Optional[str]:
    """Determine if a top is base layer or mid layer based on name/subcategory.

    Base layer: tshirts, long sleeve tees, shirts, polos, tanks, henleys
    Mid layer: sweaters, cardigans, hoodies, knit pullovers, sweatshirts, fleece

    Returns "base", "mid", or None if cannot determine.
    """
    # Combine name and subcategory for matching
    text = f"{name} {subcategory}".lower()

    # Check mid layer first (more specific items)
    for keyword in TOP_LAYER_MID:
        if keyword in text:
            return "mid"

    # Check base layer
    for keyword in TOP_LAYER_BASE:
        if keyword in text:
            return "base"

    return None


def _pick_top_n(
    tag_objs: list[TagWithConfidence],
    n: int,
    min_conf: float,
) -> list[TagWithConfidence]:
    """Pick top N tags by confidence above threshold."""
    eligible = [x for x in tag_objs if x.get("confidence", 0) >= min_conf]
    eligible.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    return eligible[:n]


# =============================================================================
# MAIN POLICY FUNCTION
# =============================================================================


def apply_tag_policy(
    tags_ai_raw: AITagOutput,
    category: Optional[str] = None,
    thresholds: Optional[PolicyThresholds] = None,
    product_name: Optional[str] = None,
    subcategory: Optional[str] = None,
) -> PolicyResult:
    """
    Apply policy to AI sensor output.

    Args:
        tags_ai_raw: Raw AI output with confidence scores
        category: Product category (or extracted from tags_ai_raw)
        thresholds: Custom thresholds (defaults to PolicyThresholds)
        product_name: Product name for determining top layer role
        subcategory: Product subcategory for determining top layer role

    Returns:
        PolicyResult with canonical tags and curation info

    Note: Fit, color, and materials are NOT processed here as they are
    not AI-generated. Color and composition come from scraping.
    Formality is now AI-generated for comparison with scraped values.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    category = category or tags_ai_raw.get("category", "top")

    reasons: list[str] = []
    suppressed: list[SuppressedTag] = []
    defaults: list[AppliedDefault] = []

    tags_final = CanonicalTags(category=category)

    # -------------------------------------------------------------------------
    # 0. TOP LAYER ROLE (required for "top" category)
    # -------------------------------------------------------------------------
    if _is_top(category):
        name = product_name or ""
        subcat = subcategory or ""
        layer_role = _determine_top_layer_role(name, subcat)

        if layer_role:
            tags_final.top_layer_role = layer_role
        else:
            # Could not determine, flag for review
            reasons.append("missing_top_layer_role")
            # Default to base layer
            tags_final.top_layer_role = "base"
            defaults.append(
                AppliedDefault(
                    "top_layer_role", "base", "could_not_determine_from_name"
                )
            )

    # -------------------------------------------------------------------------
    # 1. STYLE IDENTITY (1-2 max, REQUIRED)
    # -------------------------------------------------------------------------
    style_raw = tags_ai_raw.get("style_identity", [])
    style_selected = []

    for obj in style_raw:
        tag = obj.get("tag")
        conf = obj.get("confidence", 0)

        if tag not in STYLE_IDENTITY_TAGS:
            suppressed.append(SuppressedTag("style_identity", tag, conf, "illegal_tag"))
            reasons.append("illegal_tag_returned")
            continue

        if conf < thresholds.style_identity_flag:
            suppressed.append(
                SuppressedTag("style_identity", tag, conf, "below_flag_threshold")
            )
            continue

        style_selected.append(obj)

    # Take top 2 by confidence
    style_selected = _pick_top_n(style_selected, 2, thresholds.style_identity_flag)
    tags_final.style_identity = [x["tag"] for x in style_selected]

    if not tags_final.style_identity:
        reasons.append("missing_style_identity")
    elif any(
        x.get("confidence", 0) < thresholds.style_identity_auto for x in style_selected
    ):
        reasons.append("style_identity_needs_passive_review")

    # -------------------------------------------------------------------------
    # 1b. FORMALITY (exactly 1, AI-generated for comparison with scraped)
    # -------------------------------------------------------------------------
    formality_obj = tags_ai_raw.get("formality")

    if formality_obj is not None:
        tag = formality_obj.get("tag")
        conf = formality_obj.get("confidence", 0)

        if tag not in FORMALITY_TAGS:
            suppressed.append(SuppressedTag("formality", tag, conf, "illegal_tag"))
            reasons.append("illegal_formality_tag")
        elif conf < thresholds.formality_flag:
            suppressed.append(
                SuppressedTag("formality", tag, conf, "below_flag_threshold")
            )
        else:
            tags_final.formality = tag
            if conf < thresholds.formality_auto:
                reasons.append("formality_low_confidence")

    # Fallback for missing formality (default to casual)
    if not tags_final.formality:
        tags_final.formality = "casual"
        defaults.append(AppliedDefault("formality", "casual", "default_fallback"))

    # -------------------------------------------------------------------------
    # 2. SILHOUETTE (exactly 1, REQUIRED for apparel, category-aware)
    # -------------------------------------------------------------------------
    if not _is_shoes(category):
        silhouette_obj = tags_ai_raw.get("silhouette")
        valid_silhouettes = (
            SILHOUETTE_BOTTOM_TAGS if _is_bottom(category) else SILHOUETTE_UPPER_TAGS
        )

        if silhouette_obj is None:
            reasons.append("missing_silhouette")
        else:
            tag = silhouette_obj.get("tag")
            conf = silhouette_obj.get("confidence", 0)

            if tag not in valid_silhouettes:
                suppressed.append(
                    SuppressedTag("silhouette", tag, conf, "invalid_for_category")
                )
                reasons.append("missing_silhouette")
            elif conf < thresholds.silhouette_allow:
                suppressed.append(
                    SuppressedTag("silhouette", tag, conf, "below_allow_threshold")
                )
                reasons.append("missing_silhouette")
            else:
                tags_final.silhouette = tag
                if conf < thresholds.silhouette_auto:
                    reasons.append("silhouette_low_confidence")

        # Fallback for missing silhouette
        if not tags_final.silhouette:
            default_sil = "straight" if _is_bottom(category) else "relaxed"
            tags_final.silhouette = default_sil
            defaults.append(
                AppliedDefault(
                    "silhouette", default_sil, "required_missing_or_suppressed"
                )
            )

    # -------------------------------------------------------------------------
    # 3. CONTEXT (0-2, optional)
    # -------------------------------------------------------------------------
    context_raw = tags_ai_raw.get("context", [])
    context_selected = []

    for obj in context_raw:
        tag = obj.get("tag")
        conf = obj.get("confidence", 0)

        if tag not in CONTEXT_TAGS:
            suppressed.append(SuppressedTag("context", tag, conf, "illegal_tag"))
            continue

        if conf < thresholds.context_allow:
            suppressed.append(
                SuppressedTag("context", tag, conf, "below_allow_threshold")
            )
            continue

        context_selected.append(obj)

    context_selected = _pick_top_n(context_selected, 2, thresholds.context_allow)
    tags_final.context = [x["tag"] for x in context_selected]

    # -------------------------------------------------------------------------
    # 4. CONSTRUCTION / DETAILS (0-2, optional, category-aware)
    # -------------------------------------------------------------------------
    if not _is_shoes(category):
        details_raw = tags_ai_raw.get("construction_details", [])
        valid_details = (
            DETAILS_BOTTOM_TAGS if _is_bottom(category) else DETAILS_UPPER_TAGS
        )
        details_selected = []

        for obj in details_raw:
            tag = obj.get("tag")
            conf = obj.get("confidence", 0)

            if tag not in valid_details:
                suppressed.append(
                    SuppressedTag(
                        "construction_details", tag, conf, "invalid_for_category"
                    )
                )
                reasons.append("category_inappropriate_detail")
                continue

            if conf < thresholds.details_flag:
                suppressed.append(
                    SuppressedTag(
                        "construction_details", tag, conf, "below_flag_threshold"
                    )
                )
                continue

            details_selected.append(obj)

        details_selected = _pick_top_n(details_selected, 2, thresholds.details_flag)
        tags_final.construction_details = [x["tag"] for x in details_selected]

    # -------------------------------------------------------------------------
    # 5. PATTERN (0-1, optional)
    # -------------------------------------------------------------------------
    pattern_obj = tags_ai_raw.get("pattern")

    if pattern_obj:
        tag = pattern_obj.get("tag")
        conf = pattern_obj.get("confidence", 0)

        if tag not in PATTERN_TAGS:
            suppressed.append(SuppressedTag("pattern", tag, conf, "illegal_tag"))
        elif conf < thresholds.pattern_allow:
            suppressed.append(
                SuppressedTag("pattern", tag, conf, "below_allow_threshold")
            )
        else:
            tags_final.pattern = tag

    # -------------------------------------------------------------------------
    # 6. PAIRING TAGS (0-3, scoring only)
    # -------------------------------------------------------------------------
    pairing_raw = tags_ai_raw.get("pairing_tags", [])
    pairing_selected = []

    for obj in pairing_raw:
        tag = obj.get("tag")
        conf = obj.get("confidence", 0)

        if tag not in PAIRING_TAGS:
            suppressed.append(SuppressedTag("pairing_tags", tag, conf, "illegal_tag"))
            continue

        if conf < thresholds.pairing_allow:
            suppressed.append(
                SuppressedTag("pairing_tags", tag, conf, "below_allow_threshold")
            )
            continue

        pairing_selected.append(obj)

    pairing_selected = _pick_top_n(pairing_selected, 3, thresholds.pairing_allow)
    tags_final.pairing_tags = [x["tag"] for x in pairing_selected]

    # -------------------------------------------------------------------------
    # 7. SHOE-SPECIFIC FIELDS
    # -------------------------------------------------------------------------
    if _is_shoes(category):
        # Shoe Type (required)
        shoe_type_obj = tags_ai_raw.get("shoe_type")

        if shoe_type_obj is None:
            reasons.append("missing_shoe_type")
        else:
            tag = shoe_type_obj.get("tag")
            conf = shoe_type_obj.get("confidence", 0)

            if tag not in SHOE_TYPE_TAGS:
                suppressed.append(SuppressedTag("shoe_type", tag, conf, "illegal_tag"))
                reasons.append("missing_shoe_type")
            elif conf < thresholds.shoe_type_auto:
                suppressed.append(
                    SuppressedTag("shoe_type", tag, conf, "below_auto_threshold")
                )
                reasons.append("shoe_type_low_confidence")
                # Still allow it, but flag for review
                tags_final.shoe_type = tag
            else:
                tags_final.shoe_type = tag

        # Fallback for missing shoe type
        if not tags_final.shoe_type:
            tags_final.shoe_type = "dress-shoes"
            defaults.append(
                AppliedDefault(
                    "shoe_type", "dress-shoes", "required_missing_or_suppressed"
                )
            )

        # Profile (required for shoes)
        profile_obj = tags_ai_raw.get("profile")

        if profile_obj is None:
            reasons.append("missing_shoe_profile")
        else:
            tag = profile_obj.get("tag")
            conf = profile_obj.get("confidence", 0)

            if tag not in SHOE_PROFILE_TAGS:
                suppressed.append(SuppressedTag("profile", tag, conf, "illegal_tag"))
            elif conf < thresholds.shoe_profile_allow:
                suppressed.append(
                    SuppressedTag("profile", tag, conf, "below_allow_threshold")
                )
            else:
                tags_final.profile = tag

        # Fallback for missing profile
        if not tags_final.profile:
            tags_final.profile = "standard"
            defaults.append(AppliedDefault("profile", "standard", "default_fallback"))

        # Closure (optional)
        closure_obj = tags_ai_raw.get("closure")

        if closure_obj:
            tag = closure_obj.get("tag")
            conf = closure_obj.get("confidence", 0)

            if tag not in SHOE_CLOSURE_TAGS:
                suppressed.append(SuppressedTag("closure", tag, conf, "illegal_tag"))
            elif conf < thresholds.shoe_closure_allow:
                suppressed.append(
                    SuppressedTag("closure", tag, conf, "below_allow_threshold")
                )
            else:
                tags_final.closure = tag

    # -------------------------------------------------------------------------
    # 8. DETERMINE CURATION STATUS
    # -------------------------------------------------------------------------
    status = "approved"

    # Critical failures -> needs_fix
    critical_reasons = ["missing_style_identity", "missing_shoe_type"]
    if any(r in reasons for r in critical_reasons):
        status = "needs_fix"

    # Review triggers -> needs_review
    if status == "approved":
        review_triggers = [
            "style_identity_needs_passive_review",
            "category_inappropriate_detail",
            "illegal_tag_returned",
            "silhouette_low_confidence",
            "shoe_type_low_confidence",
        ]
        if any(r in reasons for r in review_triggers):
            status = "needs_review"

    # Deduplicate reasons
    reasons = list(dict.fromkeys(reasons))

    return PolicyResult(
        tags_final=tags_final,
        curation_status=status,
        curation_reasons=reasons,
        suppressed_tags=suppressed,
        defaults_applied=defaults,
        tag_policy_version=POLICY_VERSION,
    )


# =============================================================================
# BATCH PROCESSING
# =============================================================================


def apply_tag_policy_batch(
    ai_outputs: dict[str, AITagOutput],
    thresholds: Optional[PolicyThresholds] = None,
) -> dict[str, PolicyResult]:
    """
    Apply policy to multiple AI outputs.

    Args:
        ai_outputs: Dict mapping product_id to AITagOutput
        thresholds: Custom thresholds

    Returns:
        Dict mapping product_id to PolicyResult
    """
    results = {}

    for product_id, ai_output in ai_outputs.items():
        category = ai_output.get("category")
        results[product_id] = apply_tag_policy(ai_output, category, thresholds)

    return results


# =============================================================================
# TESTING
# =============================================================================

if __name__ == "__main__":
    import json

    # Test with sample AI output
    sample_ai_output: AITagOutput = {
        "category": "bottom",
        "style_identity": [
            {"tag": "workwear", "confidence": 0.77},
            {"tag": "rugged", "confidence": 0.65},
        ],
        "silhouette": {"tag": "straight", "confidence": 0.86},
        "context": [{"tag": "everyday", "confidence": 0.82}],
        "construction_details": [{"tag": "flat-front", "confidence": 0.74}],
        "pattern": {"tag": "solid", "confidence": 0.85},
        "pairing_tags": [
            {"tag": "neutral-base", "confidence": 0.72},
            {"tag": "easy-dress-down", "confidence": 0.68},
        ],
    }

    result = apply_tag_policy(sample_ai_output)

    print("\n=== POLICY RESULT ===\n")
    print(f"Status: {result.curation_status}")
    print(f"Reasons: {result.curation_reasons}")
    print(f"\nCanonical Tags:")
    print(json.dumps(result.tags_final.to_dict(), indent=2))
    print(f"\nSuppressed: {len(result.suppressed_tags)}")
    for s in result.suppressed_tags:
        print(f"  - {s.field}: {s.tag} ({s.confidence:.2f}) - {s.reason}")
    print(f"\nDefaults Applied: {len(result.defaults_applied)}")
    for d in result.defaults_applied:
        print(f"  - {d.field}: {d.value} - {d.reason}")
