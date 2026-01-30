#!/usr/bin/env python3
"""
Tests for product category classification.

This test suite validates that products are correctly classified into categories
based on their names. The classification logic mirrors the JavaScript implementation
in viewer.py.

Run tests:
    python test_category_classification.py

Or with pytest:
    pytest test_category_classification.py -v
"""

import re
from dataclasses import dataclass
from typing import Optional


# =============================================================================
# CLASSIFICATION LOGIC (mirrors JavaScript in viewer.py)
# =============================================================================


def has_word(text: str, word: str) -> bool:
    """
    Check if a word exists as a complete word (not part of another word).
    This prevents "pants" from matching in "participants".
    """
    # Escape special regex characters
    escaped_word = re.escape(word)
    # Match word with optional plural suffix (s or es)
    pattern = rf"\b{escaped_word}(s|es)?\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


def has_any_word(text: str, keywords: list[str]) -> bool:
    """Check if any of the keywords match as complete words."""
    return any(has_word(text, kw) for kw in keywords)


@dataclass
class ClassificationResult:
    """Result of product classification."""

    main: str  # Main category (e.g., 'bottoms', 'outerwear')
    sub: Optional[str]  # Subcategory (e.g., 'pants', 'jackets')
    display_category: str  # Human-readable name (e.g., 'Pants', 'Jackets')


def classify_product(
    name: str, tags_final: Optional[dict] = None
) -> ClassificationResult:
    """
    Classify a product based on its name.

    This mirrors the JavaScript classifyProduct() function in viewer.py.
    The classification follows a strict priority order to ensure
    more specific categories are matched before generic ones.

    Args:
        name: Product name
        tags_final: Optional tags_final dict from database

    Returns:
        ClassificationResult with main category, subcategory, and display name
    """
    name = name.lower()

    # =========================================================================
    # STEP 1: Check for BOTTOMS (pants, shorts, jeans, trousers)
    # =========================================================================

    # Check for shorts FIRST (before pants)
    if has_any_word(name, ["short", "bermuda"]):
        # Make sure it's not "short sleeve" which is a top
        if not has_any_word(name, ["sleeve", "shirt", "top", "tee", "t-shirt"]):
            return ClassificationResult("bottoms", "shorts", "Shorts")

    # Check for jeans (before generic pants)
    if has_any_word(name, ["jean", "denim pant", "denim trouser"]):
        return ClassificationResult("bottoms", "jeans", "Jeans")

    # Check for sweatsuits/tracksuits
    if has_any_word(
        name, ["sweatsuit", "tracksuit", "track pant", "jogger set", "matching set"]
    ):
        return ClassificationResult("bottoms", "sweatsuits", "Sweatsuits")

    # Check for pants/trousers
    if has_any_word(
        name,
        [
            "pant",
            "trouser",
            "chino",
            "jogger",
            "cargo pant",
            "dress pant",
            "suit pant",
            "slack",
        ],
    ):
        return ClassificationResult("bottoms", "pants", "Pants")

    # =========================================================================
    # STEP 2: Check for FOOTWEAR (Shoes & Boots)
    # =========================================================================

    # Check boots first (more specific than shoes)
    if has_any_word(
        name, ["boot", "chelsea", "combat boot", "ankle boot", "hiking boot"]
    ):
        return ClassificationResult("shoes", "boots", "Boots")

    # Check for shoes
    if has_any_word(
        name,
        [
            "shoe",
            "sneaker",
            "loafer",
            "derby",
            "sandal",
            "slipper",
            "moccasin",
            "espadrille",
            "trainer",
        ],
    ):
        return ClassificationResult("shoes", "shoes", "Shoes")

    # =========================================================================
    # STEP 3: Check for OUTERWEAR (jackets, coats, blazers, leather, vests)
    # =========================================================================

    # Leather (check early - very specific)
    if has_any_word(
        name,
        [
            "leather jacket",
            "leather coat",
            "leather bomber",
            "biker jacket",
            "moto jacket",
        ],
    ):
        return ClassificationResult("outerwear", "leather", "Leather")

    # Blazers (specific outerwear)
    if has_any_word(name, ["blazer", "sport coat", "sportcoat"]):
        return ClassificationResult("outerwear", "blazers", "Blazers")

    # Suits (check before generic jacket)
    if has_word(name, "suit") and not has_any_word(name, ["sweatsuit", "tracksuit"]):
        return ClassificationResult("outerwear", "suits", "Suits")

    # Coats (includes puffers, parkas, trenches)
    if has_any_word(name, ["coat", "parka", "puffer", "trench", "overcoat", "topcoat"]):
        return ClassificationResult("outerwear", "coats", "Coats")

    # Vests/Gilets
    if has_any_word(name, ["vest", "gilet", "waistcoat", "bodywarmer"]):
        return ClassificationResult("outerwear", "vests", "Vests")

    # Overshirts / Shackets
    if has_any_word(name, ["overshirt", "shacket", "shirt jacket"]):
        return ClassificationResult("outerwear", "overshirts", "Overshirts")

    # Jackets (general - check after more specific outerwear)
    if has_any_word(
        name,
        [
            "jacket",
            "bomber",
            "windbreaker",
            "anorak",
            "trucker",
            "down jacket",
            "quilted",
            "padded",
        ],
    ):
        return ClassificationResult("outerwear", "jackets", "Jackets")

    # =========================================================================
    # STEP 4: Check for MID LAYER (sweaters, hoodies, sweatshirts, quarter-zip)
    # =========================================================================

    # Quarter-zip (check before sweaters)
    if has_any_word(
        name, ["quarter zip", "quarter-zip", "half zip", "half-zip", "1/4 zip"]
    ):
        return ClassificationResult("tops_mid", "quarterzip", "Quarter Zip")

    # Sweatshirts (check BEFORE checking for "shirt")
    if has_any_word(
        name, ["sweatshirt", "crewneck sweat", "crew neck sweat", "fleece"]
    ):
        return ClassificationResult("tops_mid", "sweatshirts", "Sweatshirts")

    # Hoodies
    if has_any_word(name, ["hoodie", "hooded"]):
        return ClassificationResult("tops_mid", "hoodies", "Hoodies")

    # Cardigans (check before generic sweaters)
    if has_word(name, "cardigan"):
        return ClassificationResult("tops_mid", "cardigans", "Cardigans")

    # Sweaters/Knits
    if has_any_word(name, ["sweater", "knit", "pullover", "jumper", "knitwear"]):
        return ClassificationResult("tops_mid", "sweaters", "Sweaters")

    # =========================================================================
    # STEP 5: Check for BASE LAYER (t-shirts, shirts, polos, tanks)
    # =========================================================================

    # T-shirts (check before generic "shirt")
    if has_any_word(name, ["t-shirt", "tshirt", "tee"]):
        return ClassificationResult("tops_base", "tshirts", "T-Shirts")

    # Tank tops
    if has_any_word(name, ["tank", "sleeveless top", "muscle tee"]):
        return ClassificationResult("tops_base", "tanks", "Tank Tops")

    # Polos
    if has_word(name, "polo"):
        return ClassificationResult("tops_base", "polos", "Polo Shirts")

    # Shirts (most generic - only if nothing else matched)
    if has_word(name, "shirt"):
        return ClassificationResult("tops_base", "shirts", "Shirts")

    # =========================================================================
    # STEP 6: Fallback - use tags_final if available
    # =========================================================================
    if tags_final and tags_final.get("category"):
        cat = tags_final["category"].lower()
        if cat == "bottom":
            return ClassificationResult("bottoms", "pants", "Pants")
        if cat == "outerwear":
            return ClassificationResult("outerwear", "jackets", "Jackets")
        if cat == "shoes":
            return ClassificationResult("shoes", "shoes", "Shoes")
        if cat == "top_mid" or tags_final.get("top_layer_role") == "mid":
            return ClassificationResult("tops_mid", "sweaters", "Sweaters")
        if cat in ("top_base", "top") or tags_final.get("top_layer_role") == "base":
            return ClassificationResult("tops_base", "tshirts", "T-Shirts")

    # =========================================================================
    # STEP 7: Last resort - uncategorized
    # =========================================================================
    return ClassificationResult("other", None, "Other")


# =============================================================================
# TEST CASES
# =============================================================================


class TestCategoryClassification:
    """Test suite for category classification."""

    # -------------------------------------------------------------------------
    # BOTTOMS TESTS
    # -------------------------------------------------------------------------

    def test_pants_basic(self):
        """Basic pants should be classified as Pants."""
        assert classify_product("Slim Fit Stretch Pants").display_category == "Pants"
        assert classify_product("Slim Fit Stretch Pants").main == "bottoms"
        assert classify_product("Slim Fit Stretch Pants").sub == "pants"

    def test_pants_variations(self):
        """Various pant names should all be classified as Pants."""
        pant_names = [
            "Relaxed Fit Trousers",
            "Slim Fit Chinos",
            "Cargo Pants",
            "Dress Pants",
            "Suit Pants",
            "Joggers",
            "Wide Leg Trousers",
            "Pleated Pants",
            "Linen Trousers",
            "Cotton Slacks",
        ]
        for name in pant_names:
            result = classify_product(name)
            assert (
                result.display_category == "Pants"
            ), f"'{name}' should be Pants, got {result.display_category}"

    def test_jeans(self):
        """Jeans should be classified separately from pants."""
        jeans_names = [
            "Slim Fit Jeans",
            "Relaxed Jeans",
            "Skinny Jeans",
            "Straight Leg Jeans",
            "Denim Pants",  # Should match "denim pant"
        ]
        for name in jeans_names:
            result = classify_product(name)
            assert (
                result.display_category == "Jeans"
            ), f"'{name}' should be Jeans, got {result.display_category}"

    def test_shorts(self):
        """Shorts should be classified correctly."""
        shorts_names = [
            "Relaxed Fit Shorts",
            "Bermuda Shorts",
            "Linen Shorts",
            "Swim Shorts",
            "Cargo Shorts",
            "100% Linen Relaxed Fit Shorts",
        ]
        for name in shorts_names:
            result = classify_product(name)
            assert (
                result.display_category == "Shorts"
            ), f"'{name}' should be Shorts, got {result.display_category}"

    def test_short_sleeve_not_shorts(self):
        """Short sleeve shirts should NOT be classified as Shorts."""
        short_sleeve_names = [
            "Short Sleeve Shirt",
            "Short Sleeve T-Shirt",
            "Short Sleeve Polo",
        ]
        for name in short_sleeve_names:
            result = classify_product(name)
            assert (
                result.display_category != "Shorts"
            ), f"'{name}' should NOT be Shorts, got {result.display_category}"

    def test_sweatsuits(self):
        """Sweatsuits/tracksuits should be classified correctly."""
        sweatsuit_names = [
            "Tracksuit Bottoms",
            "Track Pants",
            "Jogger Set",
            "Matching Set Pants",
        ]
        for name in sweatsuit_names:
            result = classify_product(name)
            assert (
                result.display_category == "Sweatsuits"
            ), f"'{name}' should be Sweatsuits, got {result.display_category}"

    # -------------------------------------------------------------------------
    # FOOTWEAR TESTS
    # -------------------------------------------------------------------------

    def test_shoes(self):
        """Various shoes should be classified correctly."""
        shoe_names = [
            "Leather Loafers",
            "Canvas Sneakers",
            "Derby Shoes",
            "Suede Sandals",
            "Leather Moccasins",
            "Canvas Trainers",
            "Espadrilles",
            "Oxford Shoes",  # "shoes" keyword makes this match
        ]
        for name in shoe_names:
            result = classify_product(name)
            assert (
                result.display_category == "Shoes"
            ), f"'{name}' should be Shoes, got {result.display_category}"

    def test_boots(self):
        """Boots should be classified separately from shoes."""
        boot_names = [
            "Chelsea Boots",
            "Ankle Boots",
            "Combat Boots",
            "Hiking Boots",
            "Leather Boots",
            "Suede Chelsea Boots",
        ]
        for name in boot_names:
            result = classify_product(name)
            assert (
                result.display_category == "Boots"
            ), f"'{name}' should be Boots, got {result.display_category}"

    # -------------------------------------------------------------------------
    # OUTERWEAR TESTS
    # -------------------------------------------------------------------------

    def test_jackets(self):
        """Jackets should be classified correctly."""
        jacket_names = [
            "Bomber Jacket",
            "Windbreaker",
            "Trucker Jacket",
            "Down Jacket",
            "Quilted Jacket",
            "Padded Jacket",
            "80% Down - 20% Feather Water Repellent Jacket",
            "Lightweight Jacket",
        ]
        for name in jacket_names:
            result = classify_product(name)
            assert (
                result.display_category == "Jackets"
            ), f"'{name}' should be Jackets, got {result.display_category}"

    def test_coats(self):
        """Coats should be classified separately from jackets."""
        coat_names = [
            "Wool Coat",
            "Trench Coat",
            "Parka",
            "Puffer Coat",
            "Overcoat",
            "Topcoat",
        ]
        for name in coat_names:
            result = classify_product(name)
            assert (
                result.display_category == "Coats"
            ), f"'{name}' should be Coats, got {result.display_category}"

    def test_blazers(self):
        """Blazers should be classified correctly."""
        blazer_names = [
            "Linen Blazer",
            "100% Linen Suit Blazer",
            "Wool Blazer",
            "Sport Coat",
            "Cotton Blazer",
        ]
        for name in blazer_names:
            result = classify_product(name)
            assert (
                result.display_category == "Blazers"
            ), f"'{name}' should be Blazers, got {result.display_category}"

    def test_suits(self):
        """Suits should be classified correctly."""
        suit_names = [
            "Two Piece Suit",
            "Linen Suit",
            "Wool Suit",
            "Suit Jacket",  # Should be Suits, not Jackets
        ]
        for name in suit_names:
            result = classify_product(name)
            assert (
                result.display_category == "Suits"
            ), f"'{name}' should be Suits, got {result.display_category}"

    def test_leather(self):
        """Leather jackets should be classified as Leather."""
        leather_names = [
            "Leather Jacket",
            "Leather Bomber",
            "Biker Jacket",
            "Moto Jacket",
        ]
        for name in leather_names:
            result = classify_product(name)
            assert (
                result.display_category == "Leather"
            ), f"'{name}' should be Leather, got {result.display_category}"

    def test_vests(self):
        """Vests should be classified correctly."""
        vest_names = [
            "Down Vest",
            "Quilted Gilet",
            "Waistcoat",
            "Bodywarmer",
        ]
        for name in vest_names:
            result = classify_product(name)
            assert (
                result.display_category == "Vests"
            ), f"'{name}' should be Vests, got {result.display_category}"

    def test_overshirts(self):
        """Overshirts should be classified correctly."""
        overshirt_names = [
            "Cotton Overshirt",
            "Flannel Overshirt",
            "Shacket",
            "Shirt Jacket",
        ]
        for name in overshirt_names:
            result = classify_product(name)
            assert (
                result.display_category == "Overshirts"
            ), f"'{name}' should be Overshirts, got {result.display_category}"

    # -------------------------------------------------------------------------
    # MID LAYER TESTS
    # -------------------------------------------------------------------------

    def test_sweaters(self):
        """Sweaters should be classified correctly."""
        sweater_names = [
            "Wool Sweater",
            "Cashmere Pullover",
            "Cotton Knit",
            "Merino Jumper",
            "Cable Knit Sweater",
        ]
        for name in sweater_names:
            result = classify_product(name)
            assert (
                result.display_category == "Sweaters"
            ), f"'{name}' should be Sweaters, got {result.display_category}"

    def test_cardigans(self):
        """Cardigans should be classified correctly."""
        cardigan_names = [
            "Wool Cardigan",
            "Cotton Cardigan",
            "Button Front Cardigan",
        ]
        for name in cardigan_names:
            result = classify_product(name)
            assert (
                result.display_category == "Cardigans"
            ), f"'{name}' should be Cardigans, got {result.display_category}"

    def test_hoodies(self):
        """Hoodies should be classified correctly."""
        hoodie_names = [
            "Zip Up Hoodie",
            "Pullover Hoodie",
            "Cotton Hoodie",
        ]
        for name in hoodie_names:
            result = classify_product(name)
            assert (
                result.display_category == "Hoodies"
            ), f"'{name}' should be Hoodies, got {result.display_category}"

    def test_hooded_sweatshirt_is_sweatshirt(self):
        """A hooded sweatshirt can be either Hoodies or Sweatshirts - we classify as Sweatshirts."""
        # "Hooded Sweatshirt" contains both "hooded" and "sweatshirt"
        # Since sweatshirts are checked first in the priority order, it's Sweatshirts
        # This is acceptable behavior - the item could reasonably be in either category
        result = classify_product("Hooded Sweatshirt")
        assert result.display_category in [
            "Hoodies",
            "Sweatshirts",
        ], f"Expected Hoodies or Sweatshirts, got {result.display_category}"

    def test_sweatshirts(self):
        """Sweatshirts should be classified correctly."""
        sweatshirt_names = [
            "Crewneck Sweatshirt",
            "Cotton Sweatshirt",
            "Fleece Pullover",
            "French Terry Sweatshirt",
            "Contrast Collar Polo Sweatshirt",  # The original bug case!
        ]
        for name in sweatshirt_names:
            result = classify_product(name)
            assert (
                result.display_category == "Sweatshirts"
            ), f"'{name}' should be Sweatshirts, got {result.display_category}"

    def test_quarter_zip(self):
        """Quarter zips should be classified correctly."""
        quarterzip_names = [
            "Quarter Zip Pullover",
            "Half Zip Sweater",
            "Quarter-Zip Fleece",
        ]
        for name in quarterzip_names:
            result = classify_product(name)
            assert (
                result.display_category == "Quarter Zip"
            ), f"'{name}' should be Quarter Zip, got {result.display_category}"

    # -------------------------------------------------------------------------
    # BASE LAYER TESTS
    # -------------------------------------------------------------------------

    def test_tshirts(self):
        """T-shirts should be classified correctly."""
        tshirt_names = [
            "Basic T-Shirt",
            "Cotton Tee",
            "V-Neck T-Shirt",
            "Graphic Tshirt",
            "Relaxed Fit Tee",
        ]
        for name in tshirt_names:
            result = classify_product(name)
            assert (
                result.display_category == "T-Shirts"
            ), f"'{name}' should be T-Shirts, got {result.display_category}"

    def test_shirts(self):
        """Shirts should be classified correctly."""
        shirt_names = [
            "Oxford Shirt",
            "Linen Shirt",
            "Cotton Shirt",
            "Dress Shirt",
            "Button Down Shirt",
        ]
        for name in shirt_names:
            result = classify_product(name)
            assert (
                result.display_category == "Shirts"
            ), f"'{name}' should be Shirts, got {result.display_category}"

    def test_polos(self):
        """Polos should be classified correctly."""
        polo_names = [
            "Pique Polo",
            "Cotton Polo Shirt",
            "Slim Fit Polo",
        ]
        for name in polo_names:
            result = classify_product(name)
            assert (
                result.display_category == "Polo Shirts"
            ), f"'{name}' should be Polo Shirts, got {result.display_category}"

    def test_polo_sweatshirt_is_sweatshirt(self):
        """A polo sweatshirt should be Sweatshirts, not Polos."""
        # This was one of the original bugs!
        result = classify_product("Contrast Collar Polo Sweatshirt")
        assert (
            result.display_category == "Sweatshirts"
        ), f"Expected Sweatshirts, got {result.display_category}"

    def test_tanks(self):
        """Tank tops should be classified correctly."""
        tank_names = [
            "Cotton Tank Top",
            "Muscle Tank",
            "Sleeveless Top",
        ]
        for name in tank_names:
            result = classify_product(name)
            assert (
                result.display_category == "Tank Tops"
            ), f"'{name}' should be Tank Tops, got {result.display_category}"

    # -------------------------------------------------------------------------
    # EDGE CASES & REGRESSION TESTS
    # -------------------------------------------------------------------------

    def test_original_bug_cases(self):
        """Test the original bug cases that started this fix."""
        # Case 1: Pants classified as Polos
        result = classify_product("Slim Fit Stretch Pants")
        assert result.main == "bottoms"
        assert result.sub == "pants"
        assert result.display_category == "Pants"

        # Case 2: Jacket classified as Shorts
        result = classify_product("80% Down - 20% Feather Water Repellent Jacket")
        assert result.main == "outerwear"
        assert result.sub == "jackets"
        assert result.display_category == "Jackets"

        # Case 3: Shorts classified as Suits
        result = classify_product("100% Linen Relaxed Fit Shorts")
        assert result.main == "bottoms"
        assert result.sub == "shorts"
        assert result.display_category == "Shorts"

        # Case 4: Sweatshirt classified as T-Shirts
        result = classify_product("Contrast Collar Polo Sweatshirt")
        assert result.main == "tops_mid"
        assert result.sub == "sweatshirts"
        assert result.display_category == "Sweatshirts"

        # Case 5: Blazer in Shirts section
        result = classify_product("100% Linen Suit Blazer")
        assert result.main == "outerwear"
        assert result.sub == "blazers"
        assert result.display_category == "Blazers"

    def test_word_boundary_matching(self):
        """Test that word boundaries are respected."""
        # "participants" should NOT match "pants"
        result = classify_product("Event Participants List")
        assert result.display_category != "Pants"

        # "booted" should NOT match "boot"
        result = classify_product("Computer Booted Up")
        assert result.display_category != "Boots"

    def test_case_insensitivity(self):
        """Test that classification is case-insensitive."""
        assert classify_product("SLIM FIT PANTS").display_category == "Pants"
        assert classify_product("slim fit pants").display_category == "Pants"
        assert classify_product("Slim Fit Pants").display_category == "Pants"

    def test_fallback_to_tags_final(self):
        """Test fallback to tags_final when name doesn't match."""
        # Product with unrecognizable name should use tags_final
        tags = {"category": "bottom"}
        result = classify_product("XYZ123 Product", tags_final=tags)
        assert result.display_category == "Pants"

        tags = {"category": "outerwear"}
        result = classify_product("XYZ123 Product", tags_final=tags)
        assert result.display_category == "Jackets"

    def test_unknown_product(self):
        """Test that unknown products are classified as Other."""
        result = classify_product("Random Product Name")
        assert result.main == "other"
        assert result.display_category == "Other"


# =============================================================================
# MAIN
# =============================================================================


def run_tests():
    """Run all tests and report results."""
    import traceback

    test_class = TestCategoryClassification()
    test_methods = [m for m in dir(test_class) if m.startswith("test_")]

    passed = 0
    failed = 0
    failures = []

    print("=" * 70)
    print("CATEGORY CLASSIFICATION TESTS")
    print("=" * 70)
    print()

    for method_name in test_methods:
        method = getattr(test_class, method_name)
        try:
            method()
            print(f"✅ PASS: {method_name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL: {method_name}")
            print(f"   Error: {e}")
            failed += 1
            failures.append((method_name, str(e), traceback.format_exc()))
        except Exception as e:
            print(f"❌ ERROR: {method_name}")
            print(f"   Error: {e}")
            failed += 1
            failures.append((method_name, str(e), traceback.format_exc()))

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failures:
        print("\nFAILURE DETAILS:")
        for method_name, error, tb in failures:
            print(f"\n--- {method_name} ---")
            print(error)

    return failed == 0


if __name__ == "__main__":
    import sys

    success = run_tests()
    sys.exit(0 if success else 1)
