"""
Zara product extractor using Playwright with stealth settings.
Handles JavaScript rendering and anti-bot detection.
"""

import asyncio
import random
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from playwright_stealth import stealth_async
from rich.console import Console

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from config.settings import config, ScraperConfig

console = Console()


@dataclass
class RawProductData:
    """Raw product data extracted from Zara."""

    product_id: str
    name: str
    url: str
    category: str
    price_current: Optional[float] = None
    price_original: Optional[float] = None
    currency: str = "USD"
    description: Optional[str] = None
    colors: list = field(default_factory=list)
    sizes: list = field(default_factory=list)
    materials: list = field(default_factory=list)
    image_urls: list = field(default_factory=list)
    fit: Optional[str] = None  # slim, relaxed, wide, regular, etc.
    weight: Optional[str] = None  # light, medium, heavy
    scraped_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class ZaraExtractor:
    """Extracts product data from Zara website using Playwright."""

    def __init__(
        self,
        scraper_config: Optional[ScraperConfig] = None,
        browser_type: str = "firefox",
    ):
        self.config = scraper_config or config.scraper
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
        self.browser_type = browser_type  # "firefox", "chromium", or "webkit"

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Start the browser with stealth settings."""
        console.print(f"[bold blue]Starting {self.browser_type} browser...[/bold blue]")

        self.playwright = await async_playwright().start()

        # Use Firefox by default (more stable on macOS ARM)
        # Fall back to other browsers if needed
        browser_launchers = {
            "firefox": self.playwright.firefox,
            "chromium": self.playwright.chromium,
            "webkit": self.playwright.webkit,
        }

        launcher = browser_launchers.get(self.browser_type, self.playwright.firefox)

        try:
            self.browser = await launcher.launch(
                headless=self.config.headless,
            )
        except Exception as e:
            console.print(f"[yellow]Failed to launch {self.browser_type}: {e}[/yellow]")
            console.print("[yellow]Trying Firefox as fallback...[/yellow]")
            self.browser = await self.playwright.firefox.launch(
                headless=self.config.headless,
            )

        # Firefox user agents
        firefox_user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]

        user_agent = (
            random.choice(firefox_user_agents)
            if self.browser_type == "firefox"
            else random.choice(self.config.user_agents)
        )

        self.context = await self.browser.new_context(
            viewport={
                "width": self.config.viewport_width,
                "height": self.config.viewport_height,
            },
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
        )

        console.print("[bold green]Browser started successfully[/bold green]")

    async def close(self) -> None:
        """Close the browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        console.print("[bold blue]Browser closed[/bold blue]")

    async def _create_stealth_page(self) -> Page:
        """Create a new page with stealth settings."""
        page = await self.context.new_page()
        await stealth_async(page)
        return page

    async def _random_delay(self, base_delay: Optional[float] = None) -> None:
        """Add a random delay to mimic human behavior."""
        delay = base_delay or self.config.page_delay_seconds
        jitter = random.uniform(0.5, 1.5)
        await asyncio.sleep(delay * jitter)

    async def get_category_product_urls(
        self, category_key: str, limit: Optional[int] = None
    ) -> list[str]:
        """
        Get product URLs from a category page.

        Args:
            category_key: Key from config categories (e.g., 'tshirts', 'pants', 'jackets')
            limit: Maximum number of product URLs to return

        Returns:
            List of product URLs
        """
        limit = limit or self.config.products_per_category
        category_path = self.config.categories.get(category_key)

        if not category_path:
            console.print(f"[bold red]Unknown category: {category_key}[/bold red]")
            return []

        url = f"{self.config.base_url}{category_path}"
        console.print(f"[cyan]Fetching category: {category_key} from {url}[/cyan]")

        page = await self._create_stealth_page()

        try:
            await page.goto(
                url, wait_until="networkidle", timeout=self.config.timeout_ms
            )
            await self._random_delay()

            # Scroll to load more products (lazy loading)
            await self._scroll_page(page)

            # Extract product links - Zara uses product-link class
            product_links = await page.evaluate(
                """
                () => {
                    const links = [];
                    // Try multiple selectors for product links
                    const selectors = [
                        'a.product-link',
                        'a[href*="-p"][href$=".html"]',
                        '.product-grid-product a',
                        '[data-productid] a'
                    ];

                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const el of elements) {
                            const href = el.href;
                            // Filter for product pages (contain -p and end with .html)
                            if (href && href.includes('-p') && href.endsWith('.html') && !links.includes(href)) {
                                links.push(href);
                            }
                        }
                        if (links.length > 0) break;
                    }
                    return links;
                }
            """
            )

            console.print(
                f"[green]Found {len(product_links)} products in {category_key}[/green]"
            )
            return product_links[:limit]

        except Exception as e:
            console.print(
                f"[bold red]Error fetching category {category_key}: {e}[/bold red]"
            )
            return []
        finally:
            await page.close()

    async def _scroll_page(self, page: Page, scroll_count: int = 3) -> None:
        """Scroll page to trigger lazy loading."""
        for i in range(scroll_count):
            await page.evaluate("window.scrollBy(0, window.innerHeight)")
            await asyncio.sleep(0.5)

    async def extract_product(
        self, url: str, category: str
    ) -> Optional[RawProductData]:
        """
        Extract product data from a product page.

        Args:
            url: Product page URL
            category: Category name for organization

        Returns:
            RawProductData object or None if extraction fails
        """
        console.print(f"[cyan]Extracting product: {url}[/cyan]")

        page = await self._create_stealth_page()

        try:
            await page.goto(
                url, wait_until="networkidle", timeout=self.config.timeout_ms
            )
            await self._random_delay(2.0)

            # Extract product ID from URL
            product_id = self._extract_product_id(url)

            # Extract product name
            name = await self._extract_text(
                page,
                [
                    "h1.product-detail-info__header-name",
                    'h1[class*="product-name"]',
                    ".product-detail-info h1",
                    "h1",
                ],
            )

            # Extract prices
            price_current, price_original = await self._extract_prices(page)

            # Extract description
            description = await self._extract_text(
                page,
                [
                    ".expandable-text__inner-content p",
                    ".product-detail-description p",
                    '[class*="description"] p',
                ],
            )

            # Extract colors
            colors = await self._extract_colors(page)

            # Extract sizes
            sizes = await self._extract_sizes(page)

            # Extract materials/composition
            materials = await self._extract_materials(page)

            # Extract image URLs
            image_urls = await self._extract_images(page)

            product_data = RawProductData(
                product_id=product_id,
                name=name or "Unknown",
                url=url,
                category=category,
                price_current=price_current,
                price_original=price_original,
                description=description,
                colors=colors,
                sizes=sizes,
                materials=materials,
                image_urls=image_urls,
            )

            console.print(f"[green]✓ Extracted: {name} ({product_id})[/green]")
            return product_data

        except Exception as e:
            console.print(f"[bold red]Error extracting product {url}: {e}[/bold red]")
            return None
        finally:
            await page.close()

    def _extract_product_id(self, url: str) -> str:
        """Extract product ID from URL."""
        # Zara URLs are like: /us/en/product-name-p12345678.html
        match = re.search(r"-p(\d+)\.html", url)
        if match:
            return match.group(1)
        return url.split("/")[-1].replace(".html", "")

    async def _extract_text(self, page: Page, selectors: list[str]) -> Optional[str]:
        """Extract text from first matching selector."""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text:
                        return text.strip()
            except:
                continue
        return None

    async def _extract_prices(
        self, page: Page
    ) -> tuple[Optional[float], Optional[float]]:
        """Extract current and original prices."""
        price_current = None
        price_original = None

        try:
            # Try to get price data from the page
            price_data = await page.evaluate(
                """
                () => {
                    const result = {current: null, original: null};

                    // Try current price selectors
                    const currentSelectors = [
                        '.money-amount__main',
                        '.price__amount--current',
                        '[data-qa="product-price"]',
                        '.product-detail-info__price .money-amount'
                    ];

                    for (const sel of currentSelectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = el.textContent.trim();
                            const match = text.match(/[\\d.,]+/);
                            if (match) {
                                result.current = parseFloat(match[0].replace(',', ''));
                                break;
                            }
                        }
                    }

                    // Try original price (crossed out) selectors
                    const originalSelectors = [
                        '.price__amount--old',
                        '.money-amount--old',
                        '[class*="original-price"]',
                        'del .money-amount'
                    ];

                    for (const sel of originalSelectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const text = el.textContent.trim();
                            const match = text.match(/[\\d.,]+/);
                            if (match) {
                                result.original = parseFloat(match[0].replace(',', ''));
                                break;
                            }
                        }
                    }

                    return result;
                }
            """
            )

            price_current = price_data.get("current")
            price_original = price_data.get("original")

        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract prices: {e}[/yellow]")

        return price_current, price_original

    async def _extract_colors(self, page: Page) -> list[str]:
        """Extract available colors."""
        try:
            colors = await page.evaluate(
                """
                () => {
                    const colors = [];
                    const selectors = [
                        '.product-detail-color-selector__color-name',
                        '[class*="color-name"]',
                        '.product-detail-selected-color',
                    ];

                    for (const sel of selectors) {
                        const elements = document.querySelectorAll(sel);
                        for (const el of elements) {
                            const text = el.textContent.trim();
                            if (text && !colors.includes(text)) {
                                colors.push(text);
                            }
                        }
                        if (colors.length > 0) break;
                    }
                    return colors;
                }
            """
            )
            return colors
        except:
            return []

    async def _extract_sizes(self, page: Page) -> list[dict]:
        """Extract available sizes with availability status.

        Returns a list of dicts: [{"size": "M", "available": true}, ...]
        """
        try:
            sizes = await page.evaluate(
                """
                () => {
                    const sizes = [];
                    const seenSizes = new Set();

                    // Try different selector strategies for Zara's size buttons
                    const buttonSelectors = [
                        '.size-selector__size-list button',
                        '.product-size-selector__size-list button',
                        '[class*="size-selector"] button',
                        '[data-qa="size-selector"] button',
                        '.product-detail-size-selector button',
                        '[class*="SizeSelector"] button'
                    ];

                    for (const sel of buttonSelectors) {
                        const buttons = document.querySelectorAll(sel);
                        for (const btn of buttons) {
                            // Get the size text from span or button itself
                            const span = btn.querySelector('span');
                            const text = (span ? span.textContent : btn.textContent).trim();

                            // Skip invalid entries
                            if (!text || text.length > 10 || text === 'Add' || seenSizes.has(text)) {
                                continue;
                            }

                            // Check if size is available (not disabled/out of stock)
                            // Zara uses various patterns to indicate unavailability
                            const isDisabled = btn.disabled ||
                                btn.hasAttribute('disabled') ||
                                btn.classList.contains('is-disabled') ||
                                btn.classList.contains('size-selector__size--disabled') ||
                                btn.classList.contains('disabled') ||
                                btn.classList.contains('out-of-stock') ||
                                btn.getAttribute('aria-disabled') === 'true' ||
                                btn.closest('[class*="disabled"]') !== null;

                            // Also check for visual indicators (strikethrough, grayed out)
                            const style = window.getComputedStyle(btn);
                            const hasStrikethrough = style.textDecoration.includes('line-through');
                            const isGrayedOut = parseFloat(style.opacity) < 0.5;

                            const available = !isDisabled && !hasStrikethrough && !isGrayedOut;

                            sizes.push({
                                size: text,
                                available: available
                            });
                            seenSizes.add(text);
                        }
                        if (sizes.length > 0) break;
                    }

                    // Fallback: try list items if buttons didn't work
                    if (sizes.length === 0) {
                        const liSelectors = [
                            '.size-selector__size-list li',
                            '.product-size-selector__size-list li'
                        ];

                        for (const sel of liSelectors) {
                            const items = document.querySelectorAll(sel);
                            for (const li of items) {
                                const text = li.textContent.trim();
                                if (!text || text.length > 10 || text === 'Add' || seenSizes.has(text)) {
                                    continue;
                                }

                                const isDisabled = li.classList.contains('is-disabled') ||
                                    li.classList.contains('disabled') ||
                                    li.classList.contains('out-of-stock');

                                sizes.push({
                                    size: text,
                                    available: !isDisabled
                                });
                                seenSizes.add(text);
                            }
                            if (sizes.length > 0) break;
                        }
                    }

                    return sizes;
                }
            """
            )
            return sizes
        except:
            return []

    async def _extract_materials(self, page: Page) -> list[str]:
        """Extract material/composition information."""
        try:
            materials = await page.evaluate(
                """
                () => {
                    const materials = [];
                    const selectors = [
                        '.product-detail-info__composition li',
                        '[class*="composition"] li',
                        '.structured-component-text-block-paragraph span',
                    ];

                    for (const sel of selectors) {
                        const elements = document.querySelectorAll(sel);
                        for (const el of elements) {
                            const text = el.textContent.trim();
                            if (text && text.includes('%') && !materials.includes(text)) {
                                materials.push(text);
                            }
                        }
                        if (materials.length > 0) break;
                    }
                    return materials;
                }
            """
            )
            return materials
        except:
            return []

    async def _extract_images(self, page: Page) -> list[str]:
        """Extract product image URLs."""
        image_urls = []

        try:
            # First, scroll through the page to trigger lazy loading
            await self._scroll_page(page, scroll_count=5)
            await asyncio.sleep(2)

            # Try to extract images using multiple strategies
            image_urls = await page.evaluate(
                """
                () => {
                    const images = new Set();

                    // Strategy 1: Look for ALL img tags and check for product images
                    document.querySelectorAll('img').forEach(img => {
                        const src = img.src || '';
                        const srcset = img.srcset || '';
                        const dataSrc = img.getAttribute('data-src') || '';

                        // Check all possible sources
                        [src, dataSrc].forEach(url => {
                            if (url && (url.includes('static.zara') || url.includes('zara.com')) &&
                                !url.includes('transparent') && !url.includes('placeholder') &&
                                !url.includes('logo') && !url.includes('icon')) {
                                images.add(url.split('?')[0]);
                            }
                        });

                        // Check srcset for higher res
                        if (srcset) {
                            const sources = srcset.split(',').map(s => s.trim().split(' ')[0]);
                            sources.forEach(url => {
                                if (url && (url.includes('static.zara') || url.includes('zara.com')) &&
                                    !url.includes('transparent') && !url.includes('placeholder')) {
                                    images.add(url.split('?')[0]);
                                }
                            });
                        }
                    });

                    // Strategy 2: Look for picture elements with source tags
                    document.querySelectorAll('picture source').forEach(source => {
                        const srcset = source.srcset || '';
                        if (srcset) {
                            const sources = srcset.split(',').map(s => s.trim().split(' ')[0]);
                            sources.forEach(url => {
                                if (url && (url.includes('static.zara') || url.includes('zara.com')) &&
                                    !url.includes('transparent')) {
                                    images.add(url.split('?')[0]);
                                }
                            });
                        }
                    });

                    // Strategy 3: Check all elements for background-image styles
                    document.querySelectorAll('*').forEach(el => {
                        const style = window.getComputedStyle(el);
                        const bgImage = style.backgroundImage;
                        if (bgImage && bgImage !== 'none') {
                            const match = bgImage.match(/url\\(['"]?(https?:[^'"\\)]+)['"]?\\)/);
                            if (match && match[1] && (match[1].includes('static.zara') || match[1].includes('zara.com'))) {
                                images.add(match[1].split('?')[0]);
                            }
                        }
                    });

                    // Strategy 4: Look in data attributes across all elements
                    document.querySelectorAll('[data-src], [data-srcset], [data-image], [data-original]').forEach(el => {
                        ['data-src', 'data-srcset', 'data-image', 'data-original'].forEach(attr => {
                            const value = el.getAttribute(attr) || '';
                            if (value && (value.includes('static.zara') || value.includes('zara.com'))) {
                                if (value.includes(',')) {
                                    value.split(',').forEach(url => {
                                        const cleanUrl = url.trim().split(' ')[0];
                                        if (cleanUrl) images.add(cleanUrl.split('?')[0]);
                                    });
                                } else {
                                    images.add(value.split('?')[0]);
                                }
                            }
                        });
                    });

                    // Strategy 5: Search the page HTML for image URLs as a fallback
                    const html = document.documentElement.innerHTML;
                    const urlPattern = /https?:\\/\\/static\\.zara\\.net\\/photos[^"'\\s)]+\\.jpg/gi;
                    const matches = html.match(urlPattern) || [];
                    matches.forEach(url => images.add(url.split('?')[0]));

                    // Filter results
                    const filtered = Array.from(images).filter(url => {
                        // Must be a reasonable image URL
                        return url.length > 20 &&
                               (url.endsWith('.jpg') || url.endsWith('.png') || url.endsWith('.webp') ||
                                url.includes('/w/') || url.includes('/photos/'));
                    });

                    return filtered;
                }
            """
            )

            console.print(f"[dim]Found {len(image_urls)} image URLs from DOM[/dim]")

        except Exception as e:
            console.print(f"[yellow]Warning: DOM image extraction failed: {e}[/yellow]")

        # If no images found, try to get them from network requests
        if not image_urls:
            console.print(
                "[dim]Trying to capture images from page screenshots...[/dim]"
            )
            # Take a screenshot as fallback - at least we have something
            try:
                screenshot_path = (
                    f"/tmp/zara_debug_{datetime.now().strftime('%H%M%S')}.png"
                )
                await page.screenshot(path=screenshot_path, full_page=True)
                console.print(f"[dim]Debug screenshot saved: {screenshot_path}[/dim]")
            except:
                pass

        return image_urls[: config.storage.max_images_per_product]

    async def extract_all_products(self) -> list[RawProductData]:
        """
        Extract products from all configured categories.

        Returns:
            List of RawProductData objects
        """
        all_products = []

        for category_key in self.config.categories.keys():
            console.print(
                f"\n[bold magenta]Processing category: {category_key}[/bold magenta]"
            )

            # Get product URLs
            product_urls = await self.get_category_product_urls(category_key)

            # Extract each product
            for url in product_urls:
                await self._random_delay()
                product = await self.extract_product(url, category_key)
                if product:
                    all_products.append(product)

        console.print(
            f"\n[bold green]Extracted {len(all_products)} products total[/bold green]"
        )
        return all_products


async def main():
    """Test the extractor."""
    async with ZaraExtractor() as extractor:
        products = await extractor.extract_all_products()
        for p in products:
            console.print(
                f"  - {p.name}: ${p.price_current} ({len(p.image_urls)} images)"
            )


if __name__ == "__main__":
    asyncio.run(main())
