#!/usr/bin/env python3
"""
Quick analysis of Zara men's categories.
Scrolls each category page fully and counts products.
"""

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

CATEGORIES = [
    {"name": "T-Shirts", "slug": "tshirts", "url": "https://www.zara.com/us/en/man-tshirts-l855.html"},
    {"name": "Shirts", "slug": "shirts", "url": "https://www.zara.com/us/en/man-shirts-l737.html"},
    {"name": "Trousers", "slug": "trousers", "url": "https://www.zara.com/us/en/man-trousers-l838.html"},
    {"name": "Jeans", "slug": "jeans", "url": "https://www.zara.com/us/en/man-jeans-l659.html"},
    {"name": "Shorts", "slug": "shorts", "url": "https://www.zara.com/us/en/man-shorts-l722.html"},
    {"name": "Jackets", "slug": "jackets", "url": "https://www.zara.com/us/en/man-jackets-l715.html"},
    {"name": "Blazers", "slug": "blazers", "url": "https://www.zara.com/us/en/man-blazers-l608.html"},
    {"name": "Suits", "slug": "suits", "url": "https://www.zara.com/us/en/man-suits-l599.html"},
    {"name": "Shoes", "slug": "shoes", "url": "https://www.zara.com/us/en/man-shoes-l769.html"},
    {"name": "Bags", "slug": "bags", "url": "https://www.zara.com/us/en/man-bags-l563.html"},
    {"name": "Accessories", "slug": "accessories", "url": "https://www.zara.com/us/en/man-accessories-l537.html"},
    {"name": "Underwear", "slug": "underwear", "url": "https://www.zara.com/us/en/man-underwear-l789.html"},
    {"name": "New In", "slug": "new-in", "url": "https://www.zara.com/us/en/man-new-in-l716.html"},
]


async def count_category_products(page, url: str) -> int:
    """Count all products in a category by scrolling to bottom."""
    await page.goto(url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(2)

    previous_count = 0
    same_count_times = 0

    # Scroll until no more products load
    while same_count_times < 3:
        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

        # Count products
        count = await page.evaluate(r"""
            () => {
                const products = new Set();
                document.querySelectorAll('a').forEach(link => {
                    const match = link.href.match(/-p(\d+)\.html/);
                    if (match) products.add(match[1]);
                });
                return products.size;
            }
        """)

        if count == previous_count:
            same_count_times += 1
        else:
            same_count_times = 0
            previous_count = count

    return previous_count


async def analyze_categories():
    """Analyze all categories."""
    console.print(Panel("Zara Men's Categories - Product Count", style="bold blue"))

    results = []

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
        )
        page = await context.new_page()
        await stealth_async(page)

        # Accept cookies
        console.print("[dim]Loading initial page...[/dim]")
        await page.goto("https://www.zara.com/us/en/", timeout=30000)
        await asyncio.sleep(2)
        try:
            await page.click("#onetrust-accept-btn-handler", timeout=3000)
        except:
            pass

        for cat in CATEGORIES:
            console.print(f"  {cat['name']}...", end=" ")
            try:
                count = await count_category_products(page, cat['url'])
                results.append({"name": cat["name"], "slug": cat["slug"], "url": cat["url"], "count": count})
                console.print(f"[green]{count}[/green]")
            except Exception as e:
                results.append({"name": cat["name"], "slug": cat["slug"], "url": cat["url"], "count": 0})
                console.print(f"[red]Error[/red]")

        await browser.close()

    # Results table
    console.print("\n")
    table = Table(title="Category Analysis", show_lines=True)
    table.add_column("Category", style="cyan")
    table.add_column("Slug", style="yellow")
    table.add_column("Products", justify="right", style="green")

    results.sort(key=lambda x: x["count"], reverse=True)
    total = 0
    for r in results:
        if r["count"] > 0:
            table.add_row(r["name"], r["slug"], str(r["count"]))
            total += r["count"]

    console.print(table)
    console.print(f"\n[bold]Total: {total}[/bold] (some overlap)")

    # Config
    console.print("\n[cyan]settings.py config:[/cyan]")
    for r in sorted(results, key=lambda x: x["name"]):
        if r["count"] > 0:
            console.print(f'"{r["slug"]}": "{r["url"].replace("https://www.zara.com", "")}",  # {r["count"]}')


if __name__ == "__main__":
    asyncio.run(analyze_categories())
