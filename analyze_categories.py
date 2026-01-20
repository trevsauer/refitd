#!/usr/bin/env python3
"""
Analyze all available men's clothing categories on Zara.
Finds all category URLs and counts products per category.
"""

import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


async def analyze_categories():
    """Find all men's categories and count products in each."""
    console.print(Panel("Analyzing Zara Men's Categories", style="bold blue"))

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            locale="en-US",
        )
        page = await context.new_page()
        await stealth_async(page)

        # Go to Zara Men's main page
        console.print("\n[cyan]Loading Zara Men's section...[/cyan]")
        await page.goto("https://www.zara.com/us/en/man-l713.html", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Accept cookies if present
        try:
            await page.click("#onetrust-accept-btn-handler", timeout=3000)
            await asyncio.sleep(1)
        except:
            pass

        # Click on the menu button to open navigation
        console.print("[cyan]Opening navigation menu...[/cyan]")
        try:
            # Look for menu/hamburger button or MAN link in header
            menu_clicked = False

            # Try clicking on "MAN" in the header to expand menu
            try:
                man_link = await page.wait_for_selector('a:has-text("MAN"), button:has-text("MAN")', timeout=5000)
                if man_link:
                    await man_link.hover()
                    await asyncio.sleep(2)
                    menu_clicked = True
            except:
                pass

            if not menu_clicked:
                # Try hamburger menu
                try:
                    menu_btn = await page.wait_for_selector('[aria-label="Menu"], [class*="menu-button"], button[class*="burger"]', timeout=3000)
                    if menu_btn:
                        await menu_btn.click()
                        await asyncio.sleep(2)
                        menu_clicked = True
                except:
                    pass

        except Exception as e:
            console.print(f"[yellow]Menu interaction: {e}[/yellow]")

        await asyncio.sleep(2)

        # Extract all category links from the page
        console.print("[cyan]Extracting category links...[/cyan]")

        categories = await page.evaluate(r"""
            () => {
                const categories = [];
                const seen = new Set();

                // Look for all links that look like category pages
                const links = document.querySelectorAll('a');

                for (const link of links) {
                    const href = link.href;
                    const text = link.textContent.trim();

                    // Match Zara category URLs: /us/en/man-{category}-l{number}.html
                    if (href && href.includes('/us/en/man-') && href.includes('-l') && href.endsWith('.html')) {
                        // Skip the main man page itself
                        if (href.includes('man-l713.html')) continue;

                        // Extract the category part
                        const match = href.match(/\/man-(.+?)-l(\d+)\.html/);
                        if (match && !seen.has(href)) {
                            seen.add(href);
                            categories.push({
                                url: href,
                                name: text || match[1].replace(/-/g, ' '),
                                slug: match[1],
                                id: match[2]
                            });
                        }
                    }
                }

                return categories;
            }
        """)

        console.print(f"[green]Found {len(categories)} categories from page links[/green]")

        # If we didn't find many, try scrolling and looking for subcategory sections
        if len(categories) < 5:
            console.print("[cyan]Scrolling to find more categories...[/cyan]")

            for _ in range(10):
                await page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(0.5)

            # Try again
            more_categories = await page.evaluate(r"""
                () => {
                    const categories = [];
                    const seen = new Set();
                    const links = document.querySelectorAll('a');

                    for (const link of links) {
                        const href = link.href;
                        const text = link.textContent.trim();

                        if (href && href.includes('/us/en/man-') && href.includes('-l') && href.endsWith('.html')) {
                            if (href.includes('man-l713.html')) continue;

                            const match = href.match(/\/man-(.+?)-l(\d+)\.html/);
                            if (match && !seen.has(href)) {
                                seen.add(href);
                                categories.push({
                                    url: href,
                                    name: text || match[1].replace(/-/g, ' '),
                                    slug: match[1],
                                    id: match[2]
                                });
                            }
                        }
                    }

                    return categories;
                }
            """)

            # Merge
            existing_urls = {c['url'] for c in categories}
            for cat in more_categories:
                if cat['url'] not in existing_urls:
                    categories.append(cat)
                    existing_urls.add(cat['url'])

            console.print(f"[green]Total categories after scroll: {len(categories)}[/green]")

        # Known Zara men's categories as fallback
        known_categories = [
            {"slug": "shirts", "name": "Shirts", "url": "https://www.zara.com/us/en/man-shirts-l737.html"},
            {"slug": "t-shirts", "name": "T-Shirts", "url": "https://www.zara.com/us/en/man-tshirts-l855.html"},
            {"slug": "polo-shirts", "name": "Polo Shirts", "url": "https://www.zara.com/us/en/man-polo-shirts-l857.html"},
            {"slug": "sweatshirts", "name": "Sweatshirts", "url": "https://www.zara.com/us/en/man-sweatshirts-l839.html"},
            {"slug": "hoodies", "name": "Hoodies", "url": "https://www.zara.com/us/en/man-sweatshirts-hoodies-l4910.html"},
            {"slug": "jackets", "name": "Jackets", "url": "https://www.zara.com/us/en/man-jackets-l715.html"},
            {"slug": "coats", "name": "Coats", "url": "https://www.zara.com/us/en/man-jackets-coats-l5478.html"},
            {"slug": "blazers", "name": "Blazers", "url": "https://www.zara.com/us/en/man-blazers-l608.html"},
            {"slug": "suits", "name": "Suits", "url": "https://www.zara.com/us/en/man-suits-l599.html"},
            {"slug": "trousers", "name": "Trousers", "url": "https://www.zara.com/us/en/man-trousers-l838.html"},
            {"slug": "jeans", "name": "Jeans", "url": "https://www.zara.com/us/en/man-jeans-l659.html"},
            {"slug": "shorts", "name": "Shorts", "url": "https://www.zara.com/us/en/man-shorts-l722.html"},
            {"slug": "knitwear", "name": "Knitwear", "url": "https://www.zara.com/us/en/man-knitwear-l756.html"},
            {"slug": "cardigans", "name": "Cardigans", "url": "https://www.zara.com/us/en/man-knitwear-cardigans-l1175.html"},
            {"slug": "sweaters", "name": "Sweaters", "url": "https://www.zara.com/us/en/man-knitwear-sweaters-l4890.html"},
            {"slug": "shoes", "name": "Shoes", "url": "https://www.zara.com/us/en/man-shoes-l769.html"},
            {"slug": "sneakers", "name": "Sneakers", "url": "https://www.zara.com/us/en/man-shoes-sneakers-l1403.html"},
            {"slug": "boots", "name": "Boots", "url": "https://www.zara.com/us/en/man-shoes-boots-l1521.html"},
            {"slug": "accessories", "name": "Accessories", "url": "https://www.zara.com/us/en/man-accessories-l537.html"},
            {"slug": "bags", "name": "Bags", "url": "https://www.zara.com/us/en/man-bags-l563.html"},
            {"slug": "belts", "name": "Belts", "url": "https://www.zara.com/us/en/man-accessories-belts-l1175.html"},
            {"slug": "underwear", "name": "Underwear", "url": "https://www.zara.com/us/en/man-underwear-l789.html"},
            {"slug": "socks", "name": "Socks", "url": "https://www.zara.com/us/en/man-underwear-socks-l1408.html"},
            {"slug": "basics", "name": "Basics", "url": "https://www.zara.com/us/en/man-basics-l4924.html"},
            {"slug": "linen", "name": "Linen", "url": "https://www.zara.com/us/en/man-linen-l4927.html"},
            {"slug": "new-in", "name": "New In", "url": "https://www.zara.com/us/en/man-new-in-l716.html"},
        ]

        # Merge known categories with discovered ones
        existing_urls = {c['url'] for c in categories}
        for cat in known_categories:
            if cat['url'] not in existing_urls:
                categories.append(cat)
                existing_urls.add(cat['url'])

        console.print(f"[green]Total categories to check: {len(categories)}[/green]")

        # Now visit each category and count products
        console.print("\n[cyan]Counting products per category...[/cyan]\n")

        results = []

        for cat in sorted(categories, key=lambda x: x['name']):
            url = cat['url']
            try:
                await page.goto(url, wait_until="networkidle", timeout=20000)
                await asyncio.sleep(2)

                # Scroll to load products
                for _ in range(5):
                    await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await asyncio.sleep(0.3)

                # Count product links
                product_count = await page.evaluate(r"""
                    () => {
                        const products = new Set();
                        const links = document.querySelectorAll('a');
                        for (const link of links) {
                            if (link.href && /-p\d+\.html/.test(link.href)) {
                                products.add(link.href);
                            }
                        }
                        return products.size;
                    }
                """)

                results.append({
                    'name': cat['name'],
                    'slug': cat['slug'],
                    'url': url,
                    'product_count': product_count
                })

                status = "[green]" if product_count > 0 else "[yellow]"
                console.print(f"  {cat['name']}: {status}{product_count}[/] products")

            except Exception as e:
                console.print(f"  {cat['name']}: [red]Error - {e}[/red]")
                results.append({
                    'name': cat['name'],
                    'slug': cat['slug'],
                    'url': url,
                    'product_count': 0
                })

        await browser.close()

        # Display results in a nice table
        console.print("\n")
        table = Table(title="Zara Men's Categories Analysis", show_lines=True)
        table.add_column("Category", style="cyan")
        table.add_column("Slug (for config)", style="yellow")
        table.add_column("Products", justify="right", style="green")
        table.add_column("URL Path", style="dim")

        # Sort by product count descending
        results.sort(key=lambda x: x['product_count'], reverse=True)

        total_products = 0
        for r in results:
            if r['product_count'] > 0:
                table.add_row(
                    r['name'],
                    r['slug'],
                    str(r['product_count']),
                    r['url'].replace('https://www.zara.com', '')
                )
                total_products += r['product_count']

        console.print(table)
        console.print(f"\n[bold]Total Products Across All Categories: {total_products}[/bold]")
        console.print("[dim](Note: Some products appear in multiple categories)[/dim]")

        # Print config format
        console.print("\n[bold cyan]Config Format for settings.py:[/bold cyan]")
        console.print("categories = {")
        for r in results:
            if r['product_count'] > 0:
                path = r['url'].replace('https://www.zara.com', '')
                console.print(f'    "{r["slug"]}": "{path}",')
        console.print("}")

        return results


if __name__ == "__main__":
    asyncio.run(analyze_categories())
