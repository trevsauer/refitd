#!/usr/bin/env python3
"""
Analyze all available men's clothing categories on Zara using ITXRest API.
Uses the same approach as size extraction - direct HTTP calls bypassing browser detection.
"""

import asyncio
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Zara US Store ID
STORE_ID = "11719"

# Known Zara men's category IDs (extracted from URLs like man-tshirts-l855.html)
CATEGORIES = [
    {"name": "T-Shirts", "slug": "tshirts", "id": "855", "url": "/us/en/man-tshirts-l855.html"},
    {"name": "Shirts", "slug": "shirts", "id": "737", "url": "/us/en/man-shirts-l737.html"},
    {"name": "Trousers", "slug": "trousers", "id": "838", "url": "/us/en/man-trousers-l838.html"},
    {"name": "Jeans", "slug": "jeans", "id": "659", "url": "/us/en/man-jeans-l659.html"},
    {"name": "Shorts", "slug": "shorts", "id": "722", "url": "/us/en/man-shorts-l722.html"},
    {"name": "Jackets", "slug": "jackets", "id": "715", "url": "/us/en/man-jackets-l715.html"},
    {"name": "Blazers", "slug": "blazers", "id": "608", "url": "/us/en/man-blazers-l608.html"},
    {"name": "Suits", "slug": "suits", "id": "599", "url": "/us/en/man-suits-l599.html"},
    {"name": "Sweatshirts", "slug": "sweatshirts", "id": "839", "url": "/us/en/man-sweatshirts-l839.html"},
    {"name": "Knitwear", "slug": "knitwear", "id": "756", "url": "/us/en/man-knitwear-l756.html"},
    {"name": "Polo Shirts", "slug": "polo-shirts", "id": "857", "url": "/us/en/man-polo-shirts-l857.html"},
    {"name": "Shoes", "slug": "shoes", "id": "769", "url": "/us/en/man-shoes-l769.html"},
    {"name": "Bags", "slug": "bags", "id": "563", "url": "/us/en/man-bags-l563.html"},
    {"name": "Accessories", "slug": "accessories", "id": "537", "url": "/us/en/man-accessories-l537.html"},
    {"name": "Underwear", "slug": "underwear", "id": "789", "url": "/us/en/man-underwear-l789.html"},
    {"name": "New In", "slug": "new-in", "id": "716", "url": "/us/en/man-new-in-l716.html"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.zara.com/us/en/",
}


async def get_category_products_itxrest(client: httpx.AsyncClient, category_id: str) -> tuple[int, list]:
    """
    Get products for a category using Zara's ITXRest API.
    Similar to how we get product sizes.
    """
    # Try the category endpoint in ITXRest
    api_url = f"https://www.zara.com/itxrest/2/catalog/store/{STORE_ID}/category/{category_id}/product"

    try:
        response = await client.get(api_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "products" in data:
                return len(data["products"]), data["products"]
            elif isinstance(data, list):
                return len(data), data
        console.print(f"[dim]  ITXRest category returned {response.status_code}[/dim]")
    except Exception as e:
        console.print(f"[dim]  ITXRest error: {e}[/dim]")

    return 0, []


async def get_category_products_v3(client: httpx.AsyncClient, category_id: str) -> tuple[int, list]:
    """
    Try version 3 of the API.
    """
    api_url = f"https://www.zara.com/itxrest/3/catalog/store/{STORE_ID}/category/{category_id}"

    try:
        response = await client.get(api_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                if "productGroups" in data:
                    total = 0
                    products = []
                    for group in data["productGroups"]:
                        elements = group.get("elements", [])
                        total += len(elements)
                        products.extend(elements)
                    return total, products
                elif "products" in data:
                    return len(data["products"]), data["products"]
        console.print(f"[dim]  V3 API returned {response.status_code}[/dim]")
    except Exception as e:
        console.print(f"[dim]  V3 error: {e}[/dim]")

    return 0, []


async def get_category_from_web_api(client: httpx.AsyncClient, category_id: str) -> tuple[int, list]:
    """
    Try the web API endpoint that the website uses.
    """
    # This is the endpoint the Zara website uses for category pages
    api_url = f"https://www.zara.com/us/en/category/{category_id}/products"

    try:
        response = await client.get(api_url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return len(data), data
            elif isinstance(data, dict) and "products" in data:
                return len(data["products"]), data["products"]
        console.print(f"[dim]  Web API returned {response.status_code}[/dim]")
    except Exception as e:
        console.print(f"[dim]  Web API error: {e}[/dim]")

    return 0, []


async def get_category_algolia(client: httpx.AsyncClient, category_id: str) -> int:
    """
    Try Algolia search which some retailers use.
    """
    # Some retailers use Algolia - let's check if Zara does
    api_url = f"https://www.zara.com/us/en/categories/man/l{category_id}"

    try:
        response = await client.get(api_url, headers=HEADERS, timeout=15, follow_redirects=True)
        if response.status_code == 200:
            # Check for product count in response
            import re
            text = response.text
            # Look for product count indicators
            matches = re.findall(r'"totalCount"\s*:\s*(\d+)', text)
            if matches:
                return int(matches[0])
            matches = re.findall(r'"total"\s*:\s*(\d+)', text)
            if matches:
                return int(matches[0])
    except Exception:
        pass

    return 0


async def analyze_categories():
    """Analyze all men's categories using the ITXRest API."""
    console.print(Panel("Analyzing Zara Men's Categories (ITXRest API)", style="bold blue"))
    console.print("[cyan]Using the same API approach as size extraction...[/cyan]\n")

    results = []

    async with httpx.AsyncClient(follow_redirects=True) as client:
        for cat in CATEGORIES:
            console.print(f"  Checking {cat['name']} (ID: {cat['id']})...")

            # Try multiple API approaches
            count = 0

            # Method 1: ITXRest category/product endpoint
            count, _ = await get_category_products_itxrest(client, cat['id'])

            # Method 2: Try V3 API if V2 failed
            if count == 0:
                count, _ = await get_category_products_v3(client, cat['id'])

            # Method 3: Try web API
            if count == 0:
                count, _ = await get_category_from_web_api(client, cat['id'])

            # Method 4: Try Algolia/search
            if count == 0:
                count = await get_category_algolia(client, cat['id'])

            results.append({
                "name": cat["name"],
                "slug": cat["slug"],
                "id": cat["id"],
                "url": cat["url"],
                "product_count": count
            })

            status = "[green]" if count > 0 else "[yellow]"
            console.print(f"    → {status}{count}[/] products")

            await asyncio.sleep(0.3)  # Rate limiting

    # Display results
    console.print("\n")
    table = Table(title="Zara Men's Categories Analysis", show_lines=True)
    table.add_column("Category", style="cyan")
    table.add_column("Slug", style="yellow")
    table.add_column("ID", style="dim")
    table.add_column("Products", justify="right", style="green")

    # Sort by product count
    results.sort(key=lambda x: x["product_count"], reverse=True)

    total = 0
    for r in results:
        table.add_row(
            r["name"],
            r["slug"],
            r["id"],
            str(r["product_count"]) if r["product_count"] > 0 else "[dim]0[/dim]"
        )
        total += r["product_count"]

    console.print(table)
    console.print(f"\n[bold]Total Products (with overlap): {total}[/bold]")

    # If all zeros, suggest alternative
    if total == 0:
        console.print("\n[yellow]Note: API returned no results. The category API may require browser cookies.[/yellow]")
        console.print("[yellow]The browser-based scraper still works for actual product scraping.[/yellow]")

    # Print config format
    console.print("\n[bold cyan]Config for settings.py:[/bold cyan]")
    console.print("categories = {")
    for r in sorted(results, key=lambda x: x["name"]):
        console.print(f'    "{r["slug"]}": "{r["url"]}",')
    console.print("}")

    return results


if __name__ == "__main__":
    asyncio.run(analyze_categories())
