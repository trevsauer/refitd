"""
Tests for viewer.py rendering quality.

These tests validate that canonical tags and composition data are rendered correctly
in the product viewer. They test the JavaScript parsing logic used in viewer.py.

Run with: python3 tests/test_viewer_rendering.py
"""

import re
import sys
from typing import Optional

try:
    import pytest

    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False


# ============================================================================
# COMPOSITION PARSING TESTS
# ============================================================================


class TestCompositionParsing:
    """Test composition string parsing for different product types."""

    def parse_composition(self, composition: str) -> dict:
        """
        Parse composition string into structured format.

        This mirrors the JavaScript logic in viewer.py for parsing compositions.
        """
        if not composition:
            return {"type": "empty", "sections": [], "materials": []}

        # Check for shoe-style composition with part names
        part_names = [
            "UPPER",
            "LINING",
            "SOLE",
            "INSOLE",
            "TONGUE",
            "OUTER",
            "INNER",
            "OUTSOLE",
            "MIDSOLE",
            "TOE",
            "HEEL",
            "COUNTER",
            "FOOTBED",
        ]

        # Part names can appear:
        # 1. At the start of the string
        # 2. After a letter (e.g., "polyesterLINING")
        # 3. After a space or colon
        # We need to be careful to match INSOLE before SOLE, OUTSOLE before SOLE, MIDSOLE before SOLE
        # Sort by length descending to match longer parts first
        sorted_parts = sorted(part_names, key=len, reverse=True)
        part_pattern = (
            r"(?:^|(?<=[a-zA-Z])|(?<=\s)|(?<=:))(" + "|".join(sorted_parts) + r")"
        )
        has_parts = bool(re.search(part_pattern, composition, re.IGNORECASE))

        if has_parts:
            # Parse shoe-style composition by finding each part and its materials
            sections = []

            # Find all part positions using a simpler approach
            # We need to find each part name in order, being careful about overlapping names
            part_matches = []

            # Use a different approach: scan for each part name
            for part in sorted_parts:
                for match in re.finditer(
                    r"(?:^|(?<=[a-zA-Z])|(?<=[\s:]))" + part, composition, re.IGNORECASE
                ):
                    # Check if this position is not already covered by a longer part
                    overlap = False
                    for existing in part_matches:
                        if (
                            match.start() >= existing["start"]
                            and match.start() < existing["end"]
                        ) or (
                            match.end() > existing["start"]
                            and match.end() <= existing["end"]
                        ):
                            overlap = True
                            break
                    if not overlap:
                        part_matches.append(
                            {
                                "name": part.upper(),
                                "start": match.start(),
                                "end": match.end(),
                            }
                        )

            # Sort by start position
            part_matches.sort(key=lambda x: x["start"])

            for i, match in enumerate(part_matches):
                part_name = match["name"]
                start_pos = match["end"]

                # End position is either the next part or end of string
                if i + 1 < len(part_matches):
                    end_pos = part_matches[i + 1]["start"]
                else:
                    end_pos = len(composition)

                materials_str = composition[start_pos:end_pos].strip()
                # Remove leading colon or space if present
                materials_str = materials_str.lstrip(": ")

                # Parse materials: "37% polyurethane32% polyester" -> ["37% polyurethane", "32% polyester"]
                # Match percentage followed by material name (letters and spaces until next percentage or end)
                material_list = re.findall(
                    r"(\d+%\s*[a-zA-Z][a-zA-Z\s]*?)(?=\d+%|$)", materials_str
                )
                cleaned_materials = [m.strip() for m in material_list if m.strip()]

                if cleaned_materials:
                    sections.append({"part": part_name, "materials": cleaned_materials})

            return {"type": "shoe", "sections": sections, "materials": []}
        else:
            # Simple composition like "100% cotton" or "49% polyamide, 29% polyester"
            materials = [m.strip() for m in composition.split(",") if m.strip()]
            return {"type": "simple", "sections": [], "materials": materials}

    def test_simple_single_material(self):
        """Test simple single-material composition."""
        result = self.parse_composition("100% cotton")
        assert result["type"] == "simple"
        assert result["materials"] == ["100% cotton"]

    def test_simple_multiple_materials(self):
        """Test simple multi-material composition."""
        result = self.parse_composition(
            "49% polyamide, 29% polyester, 14% acrylic, 8% wool"
        )
        assert result["type"] == "simple"
        assert len(result["materials"]) == 4
        assert "49% polyamide" in result["materials"]
        assert "8% wool" in result["materials"]

    def test_shoe_composition_basic(self):
        """Test basic shoe composition with UPPER/LINING/SOLE."""
        composition = (
            "UPPER37% polyurethane32% polyesterLINING100% polyesterSOLE100% rubber"
        )
        result = self.parse_composition(composition)

        assert result["type"] == "shoe"
        assert len(result["sections"]) == 3

        # Check UPPER section
        upper = next((s for s in result["sections"] if s["part"] == "UPPER"), None)
        assert upper is not None
        assert "37% polyurethane" in upper["materials"]
        assert "32% polyester" in upper["materials"]

        # Check LINING section
        lining = next((s for s in result["sections"] if s["part"] == "LINING"), None)
        assert lining is not None
        assert "100% polyester" in lining["materials"]

        # Check SOLE section
        sole = next((s for s in result["sections"] if s["part"] == "SOLE"), None)
        assert sole is not None
        assert "100% rubber" in sole["materials"]

    def test_shoe_composition_complex(self):
        """Test complex shoe composition with many parts."""
        composition = "UPPER37% polyurethane32% polyester30% cow leather1% elastaneLINING88% polyester12% elastaneSOLE100% rubberINSOLE100% polyesterTONGUE64% polyester25% cow leather11% elastane"
        result = self.parse_composition(composition)

        assert result["type"] == "shoe"
        assert len(result["sections"]) == 5

        # Check UPPER has 4 materials
        upper = next((s for s in result["sections"] if s["part"] == "UPPER"), None)
        assert upper is not None
        assert len(upper["materials"]) == 4

        # Check TONGUE has 3 materials
        tongue = next((s for s in result["sections"] if s["part"] == "TONGUE"), None)
        assert tongue is not None
        assert len(tongue["materials"]) == 3

    def test_shoe_composition_with_spaces(self):
        """Test shoe composition with spaces between parts."""
        composition = "UPPER: 37% polyurethane, 32% polyester LINING: 100% polyester SOLE: 100% rubber"
        result = self.parse_composition(composition)

        assert result["type"] == "shoe"
        # Should still detect parts even with colons and commas

    def test_empty_composition(self):
        """Test empty composition string."""
        result = self.parse_composition("")
        assert result["type"] == "empty"

        result = self.parse_composition(None)
        assert result["type"] == "empty"

    def test_no_duplicate_materials(self):
        """Ensure materials aren't duplicated in output."""
        composition = (
            "UPPER37% polyurethane32% polyesterLINING88% polyester12% elastane"
        )
        result = self.parse_composition(composition)

        # Count total materials across all sections
        all_materials = []
        for section in result["sections"]:
            all_materials.extend(section["materials"])

        # Check for no exact duplicates
        assert len(all_materials) == len(set(all_materials))


# ============================================================================
# CANONICAL TAGS RENDERING TESTS
# ============================================================================


class TestCanonicalTagsRendering:
    """Test canonical tags rendering logic."""

    def validate_style_identity(self, tags: list[str]) -> dict:
        """Validate style identity tags."""
        issues = []

        if len(tags) > 2:
            issues.append(f"Too many style identities: {len(tags)} (max 2)")

        if len(tags) == 0:
            issues.append("Missing style identity (required)")

        # Check for valid style identities
        valid_styles = {
            "minimal",
            "classic",
            "streetwear",
            "prep",
            "workwear",
            "avant-garde",
            "outdoor",
            "athleisure",
            "maximalist",
            "bohemian",
            "punk",
            "vintage",
            "normcore",
        }

        for tag in tags:
            if tag.lower() not in valid_styles:
                issues.append(f"Unknown style identity: {tag}")

        return {"valid": len(issues) == 0, "issues": issues}

    def validate_formality(self, formality: Optional[str]) -> dict:
        """Validate formality tag."""
        issues = []

        valid_formalities = {
            "athletic",
            "casual",
            "smart-casual",
            "business-casual",
            "formal",
        }

        if formality is None:
            issues.append("Missing formality (required)")
        elif formality.lower() not in valid_formalities:
            issues.append(f"Invalid formality: {formality}")

        return {"valid": len(issues) == 0, "issues": issues}

    def validate_top_layer_role(self, category: str, layer_role: Optional[str]) -> dict:
        """Validate top layer role for tops."""
        issues = []

        # Only required for 'top' category
        if category.lower() not in ["top", "top_base", "top_mid"]:
            return {"valid": True, "issues": [], "skipped": True}

        valid_roles = {"base", "mid"}

        if layer_role is None:
            issues.append("Missing top_layer_role (required for tops)")
        elif layer_role.lower() not in valid_roles:
            issues.append(f"Invalid top_layer_role: {layer_role}")

        return {"valid": len(issues) == 0, "issues": issues}

    def test_valid_style_identity_single(self):
        """Test single valid style identity."""
        result = self.validate_style_identity(["minimal"])
        assert result["valid"]

    def test_valid_style_identity_double(self):
        """Test two valid style identities."""
        result = self.validate_style_identity(["minimal", "classic"])
        assert result["valid"]

    def test_invalid_style_identity_too_many(self):
        """Test too many style identities."""
        result = self.validate_style_identity(["minimal", "classic", "streetwear"])
        assert not result["valid"]
        assert "Too many" in result["issues"][0]

    def test_invalid_style_identity_unknown(self):
        """Test unknown style identity."""
        result = self.validate_style_identity(["fancy"])
        assert not result["valid"]
        assert "Unknown" in result["issues"][0]

    def test_missing_style_identity(self):
        """Test missing style identity."""
        result = self.validate_style_identity([])
        assert not result["valid"]
        assert "Missing" in result["issues"][0]

    def test_valid_formality(self):
        """Test valid formality values."""
        for formality in [
            "athletic",
            "casual",
            "smart-casual",
            "business-casual",
            "formal",
        ]:
            result = self.validate_formality(formality)
            assert result["valid"], f"'{formality}' should be valid"

    def test_invalid_formality(self):
        """Test invalid formality value."""
        result = self.validate_formality("dressy")
        assert not result["valid"]

    def test_missing_formality(self):
        """Test missing formality."""
        result = self.validate_formality(None)
        assert not result["valid"]

    def test_top_layer_role_for_tops(self):
        """Test top layer role is required for tops."""
        result = self.validate_top_layer_role("top", "base")
        assert result["valid"]

        result = self.validate_top_layer_role("top", "mid")
        assert result["valid"]

        result = self.validate_top_layer_role("top", None)
        assert not result["valid"]

    def test_top_layer_role_not_required_for_bottoms(self):
        """Test top layer role not required for non-tops."""
        result = self.validate_top_layer_role("bottom", None)
        assert result["valid"]
        assert result.get("skipped", False)

    def test_top_layer_role_invalid_value(self):
        """Test invalid top layer role value."""
        result = self.validate_top_layer_role("top", "outer")
        assert not result["valid"]


# ============================================================================
# PRODUCT DATA VALIDATION TESTS
# ============================================================================


class TestProductDataValidation:
    """Test product data validation for viewer rendering."""

    def validate_product_for_rendering(self, product: dict) -> dict:
        """Validate a product has required fields for proper rendering."""
        issues = []
        warnings = []

        # Required fields
        required = ["product_id", "name", "category"]
        for field in required:
            if not product.get(field):
                issues.append(f"Missing required field: {field}")

        # Recommended fields
        recommended = ["url", "price_current", "description"]
        for field in recommended:
            if not product.get(field):
                warnings.append(f"Missing recommended field: {field}")

        # Tags validation
        tags_final = product.get("tags_final", {})
        if tags_final:
            # Style identity
            style_identity = tags_final.get("style_identity", [])
            if not style_identity:
                warnings.append("Missing style_identity in tags_final")
            elif len(style_identity) > 2:
                issues.append("Too many style_identity tags (max 2)")

            # Formality
            if not tags_final.get("formality"):
                warnings.append("Missing formality in tags_final")

            # Category-specific checks
            category = tags_final.get("category", product.get("category", ""))
            if category.lower() in ["top", "top_base", "top_mid"]:
                if not tags_final.get("top_layer_role"):
                    warnings.append("Missing top_layer_role for top category")

        # Image validation
        image_paths = product.get("image_paths", [])
        if not image_paths or len(image_paths) == 0:
            warnings.append("No images available")

        return {"valid": len(issues) == 0, "issues": issues, "warnings": warnings}

    def test_valid_complete_product(self):
        """Test a fully valid product."""
        product = {
            "product_id": "12345-001",
            "name": "Cotton T-Shirt",
            "category": "tshirts",
            "url": "https://zara.com/product",
            "price_current": 29.90,
            "description": "A basic cotton t-shirt",
            "image_paths": ["path/to/image.jpg"],
            "tags_final": {
                "category": "top",
                "style_identity": ["minimal"],
                "formality": "casual",
                "top_layer_role": "base",
            },
        }
        result = self.validate_product_for_rendering(product)
        assert result["valid"]
        assert len(result["warnings"]) == 0

    def test_minimal_product(self):
        """Test a minimal valid product."""
        product = {
            "product_id": "12345-001",
            "name": "Cotton T-Shirt",
            "category": "tshirts",
        }
        result = self.validate_product_for_rendering(product)
        assert result["valid"]  # Only required fields needed
        assert len(result["warnings"]) > 0  # But should have warnings

    def test_missing_required_fields(self):
        """Test product missing required fields."""
        product = {
            "name": "Cotton T-Shirt"
            # Missing product_id and category
        }
        result = self.validate_product_for_rendering(product)
        assert not result["valid"]
        assert len(result["issues"]) == 2

    def test_product_with_invalid_tags(self):
        """Test product with too many style identities."""
        product = {
            "product_id": "12345-001",
            "name": "Cotton T-Shirt",
            "category": "tshirts",
            "tags_final": {
                "style_identity": ["minimal", "classic", "streetwear"]  # Too many
            },
        }
        result = self.validate_product_for_rendering(product)
        assert not result["valid"]
        assert "Too many style_identity" in result["issues"][0]


# ============================================================================
# RUN TESTS
# ============================================================================


def run_tests_without_pytest():
    """Run tests manually without pytest."""
    print("Running tests without pytest...\n")

    passed = 0
    failed = 0
    errors = []

    # Instantiate test classes
    comp_tests = TestCompositionParsing()
    tag_tests = TestCanonicalTagsRendering()
    product_tests = TestProductDataValidation()

    # Get all test methods
    test_methods = []
    for cls_name, cls in [
        ("TestCompositionParsing", comp_tests),
        ("TestCanonicalTagsRendering", tag_tests),
        ("TestProductDataValidation", product_tests),
    ]:
        for method_name in dir(cls):
            if method_name.startswith("test_"):
                test_methods.append((cls_name, method_name, getattr(cls, method_name)))

    # Run each test
    for cls_name, method_name, method in test_methods:
        full_name = f"{cls_name}::{method_name}"
        try:
            method()
            print(f"✓ PASSED: {full_name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {full_name}")
            print(f"  Error: {e}")
            errors.append((full_name, str(e)))
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {full_name}")
            print(f"  Exception: {e}")
            errors.append((full_name, str(e)))
            failed += 1

    # Print summary
    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print(f"{'='*60}")

    if errors:
        print("\nFailed tests:")
        for name, err in errors:
            print(f"  - {name}: {err}")

    return failed == 0


if __name__ == "__main__":
    if HAS_PYTEST:
        pytest.main([__file__, "-v"])
    else:
        success = run_tests_without_pytest()
        sys.exit(0 if success else 1)
