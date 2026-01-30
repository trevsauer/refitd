#!/usr/bin/env python3
"""
Test script to verify composition extraction from Zara products.
Run this to make sure composition is being scraped correctly before running the full pipeline.
"""

import asyncio
import re

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async


# Test products with known compositions from your screenshots
TEST_PRODUCTS = [
    {
        "url": "https://www.zara.com/us/en/baggy-fit-jeans-p04806330.html",
        "expected_composition": "100% cotton",
        "name": "Baggy Fit Jeans",
    },
    {
        "url": "https://www.zara.com/us/en/knit-lozenge-pattern-polo-with-distressed-effect-p02893402.html",
        "expected_composition": "49% polyamide, 29% polyester, 14% acrylic, 8% wool",
        "name": "Knit Lozenge Pattern Polo",
    },
]


def extract_product_id(url: str) -> str:
    """Extract product ID from URL."""
    match = re.search(r"-p(\d+)\.html", url)
    if match:
        return match.group(1)
    return url.split("/")[-1].replace(".html", "")


async def test_api_extraction(product_id: str) -> dict:
    """Test composition extraction from Zara API."""
    api_url = f"https://www.zara.com/itxrest/2/catalog/store/11719/product/{product_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.zara.com/us/en/",
    }

    results = {
        "api_status": None,
        "raw_response_keys": [],
        "detail_keys": [],
        "color_keys": [],
        "composition_found": None,
        "raw_materials": None,
        "materials": None,
        "detailed_composition": None,
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(api_url, headers=headers, timeout=15)
            results["api_status"] = response.status_code

            if response.status_code == 200:
                data = response.json()
                results["raw_response_keys"] = list(data.keys())

                if "detail" in data:
                    results["detail_keys"] = list(data["detail"].keys())

                    if "colors" in data["detail"]:
                        colors = data["detail"]["colors"]
                        if colors:
                            first_color = colors[0]
                            results["color_keys"] = list(first_color.keys())

                            # Check for rawMaterials
                            if "rawMaterials" in first_color:
                                results["raw_materials"] = first_color["rawMaterials"]

                            # Check for materials
                            if "materials" in first_color:
                                results["materials"] = first_color["materials"]

                            # Check for composition
                            if "composition" in first_color:
                                results["composition_found"] = first_color[
                                    "composition"
                                ]

                    # Also check at detail level
                    if "rawMaterials" in data["detail"]:
                        results["raw_materials"] = data["detail"]["rawMaterials"]
                    if "composition" in data["detail"]:
                        results["composition_found"] = data["detail"]["composition"]
                    if "detailedComposition" in data["detail"]:
                        results["detailed_composition"] = data["detail"][
                            "detailedComposition"
                        ]

    except Exception as e:
        results["error"] = str(e)

    return results


async def test_dom_extraction(url: str) -> dict:
    """Test composition extraction from DOM."""
    results = {
        "page_loaded": False,
        "composition_from_page_text": None,
        "composition_from_selectors": None,
        "page_text_snippet": None,
    }

    try:
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            )
            page = await context.new_page()
            await stealth_async(page)

            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            results["page_loaded"] = True

            # Try to click "COMPOSITION & CARE" button
            try:
                composition_buttons = await page.query_selector_all(
                    'button:has-text("COMPOSITION"), button:has-text("Composition")'
                )
                for btn in composition_buttons:
                    try:
                        await btn.click()
                        await asyncio.sleep(1)
                        print("  ✓ Clicked COMPOSITION button")
                    except:
                        pass
            except Exception as e:
                print(f"  Could not click composition button: {e}")

            # Get full page text and search for composition
            page_text = await page.evaluate("() => document.body.innerText")

            # Look for "Composition:" in the page text
            comp_match = re.search(
                r"Composition:?\s*([\d]+%[^\n]*)", page_text, re.IGNORECASE
            )
            if comp_match:
                results["composition_from_page_text"] = comp_match.group(1).strip()

            # Also try to find percentage patterns with material names
            material_pattern = re.findall(
                r"\d+%\s*[a-zA-Z]+(?:\s*,\s*\d+%\s*[a-zA-Z]+)*", page_text
            )
            if material_pattern:
                # Filter to only those with material keywords
                material_keywords = [
                    "cotton",
                    "polyester",
                    "wool",
                    "silk",
                    "linen",
                    "nylon",
                    "polyamide",
                    "acrylic",
                    "viscose",
                    "elastane",
                    "spandex",
                    "rayon",
                    "cashmere",
                    "leather",
                    "denim",
                    "modal",
                    "lyocell",
                    "tencel",
                ]
                valid = [
                    m
                    for m in material_pattern
                    if any(kw in m.lower() for kw in material_keywords)
                ]
                if valid:
                    results["composition_from_selectors"] = valid[0]

            # Get a snippet of page text around "Composition" for debugging
            if "composition" in page_text.lower():
                idx = page_text.lower().find("composition")
                start = max(0, idx - 50)
                end = min(len(page_text), idx + 200)
                results["page_text_snippet"] = page_text[start:end].replace("\n", " ")

            await browser.close()

    except Exception as e:
        results["error"] = str(e)

    return results


async def main():
    print("=" * 60)
    print("ZARA COMPOSITION EXTRACTION TEST")
    print("=" * 60)

    for product in TEST_PRODUCTS:
        print(f"\n{'─' * 60}")
        print(f"Testing: {product['name']}")
        print(f"URL: {product['url']}")
        print(f"Expected: {product['expected_composition']}")
        print("─" * 60)

        product_id = extract_product_id(product["url"])
        print(f"\nProduct ID: {product_id}")

        # Test API extraction
        print("\n📡 Testing API extraction...")
        api_results = await test_api_extraction(product_id)
        print(f"  API Status: {api_results['api_status']}")
        print(f"  Response Keys: {api_results['raw_response_keys']}")
        print(f"  Detail Keys: {api_results['detail_keys']}")
        print(f"  Color Keys: {api_results['color_keys']}")
        print(f"  rawMaterials: {api_results['raw_materials']}")
        print(f"  materials: {api_results['materials']}")
        print(f"  composition: {api_results['composition_found']}")
        print(f"  detailedComposition: {api_results['detailed_composition']}")
        if "error" in api_results:
            print(f"  ❌ Error: {api_results['error']}")

        # Test DOM extraction
        print("\n🌐 Testing DOM extraction...")
        dom_results = await test_dom_extraction(product["url"])
        print(f"  Page Loaded: {dom_results['page_loaded']}")
        print(f"  From Page Text: {dom_results['composition_from_page_text']}")
        print(f"  From Selectors: {dom_results['composition_from_selectors']}")
        if dom_results.get("page_text_snippet"):
            print(f"  Page Snippet: ...{dom_results['page_text_snippet']}...")
        if "error" in dom_results:
            print(f"  ❌ Error: {dom_results['error']}")

        # Summary
        found_composition = (
            api_results.get("composition_found")
            or api_results.get("raw_materials")
            or dom_results.get("composition_from_page_text")
            or dom_results.get("composition_from_selectors")
        )

        print(f"\n📊 RESULT:")
        if found_composition:
            print(f"  ✅ Found composition: {found_composition}")
            if (
                product["expected_composition"].lower()
                in str(found_composition).lower()
            ):
                print(f"  ✅ Matches expected!")
            else:
                print(
                    f"  ⚠️  Does not exactly match expected: {product['expected_composition']}"
                )
        else:
            print(f"  ❌ Could not extract composition!")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
