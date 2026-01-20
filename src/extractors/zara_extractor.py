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

        # Extract product ID from URL first
        product_id = self._extract_product_id(url)
        
        # Try to get data from ITXRest API first (more reliable)
        api_data = await self._get_product_from_api(product_id)
        
        page = await self._create_stealth_page()

        try:
            await page.goto(
                url, wait_until="networkidle", timeout=self.config.timeout_ms
            )
            await self._random_delay(2.0)

            # Extract product name - try API data first, then DOM
            name = None
            if api_data and api_data.get("name"):
                name = api_data["name"]
            else:
                name = await self._extract_text(
                    page,
                    [
                        "h1.product-detail-info__header-name",
                        'h1[class*="product-name"]',
                        ".product-detail-info h1",
                        "h1",
                    ],
                )

            # Validate: Skip if we still don't have a valid name
            if not name or name == "Unknown" or len(name) < 2:
                # Try to extract name from URL as last resort
                url_name = self._extract_name_from_url(url)
                if url_name:
                    name = url_name
                else:
                    console.print(f"[yellow]⚠ Skipping product {product_id}: Could not extract name[/yellow]")
                    return None

            # Extract prices - try API first, then DOM
            price_current = None
            price_original = None
            if api_data and api_data.get("price"):
                price_current = api_data["price"]
                price_original = api_data.get("original_price")
            else:
                price_current, price_original = await self._extract_prices(page)

            # Extract description
            description = None
            if api_data and api_data.get("description"):
                description = api_data["description"]
            else:
                description = await self._extract_text(
                    page,
                    [
                        ".expandable-text__inner-content p",
                        ".product-detail-description p",
                        '[class*="description"] p',
                    ],
                )

            # Extract colors - try API first
            colors = []
            if api_data and api_data.get("colors"):
                colors = api_data["colors"]
            else:
                colors = await self._extract_colors(page)

            # Extract sizes (uses API internally)
            sizes = await self._extract_sizes(page)

            # Extract materials/composition
            materials = await self._extract_materials(page)

            # Extract image URLs - try API first, then DOM
            image_urls = []
            if api_data and api_data.get("images"):
                image_urls = api_data["images"]
            else:
                image_urls = await self._extract_images(page)

            # Final validation: Must have either images OR a valid price
            if not image_urls and not price_current:
                console.print(f"[yellow]⚠ Skipping product {product_id}: No images and no price (likely blocked)[/yellow]")
                return None

            product_data = RawProductData(
                product_id=product_id,
                name=name,
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

    async def _get_product_from_api(self, product_id: str) -> Optional[dict]:
        """
        Get product data from Zara's ITXRest API.
        
        Returns dict with: name, price, original_price, description, colors, images
        """
        try:
            import httpx
            
            api_url = f"https://www.zara.com/itxrest/2/catalog/store/11719/product/{product_id}"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.zara.com/us/en/",
            }
            
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(api_url, headers=headers, timeout=10)
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                result = {}
                
                # Extract name
                result["name"] = data.get("name", "")
                
                # Extract description
                if "detail" in data:
                    desc_parts = []
                    for key in ["description", "longDescription"]:
                        if data["detail"].get(key):
                            desc_parts.append(data["detail"][key])
                    result["description"] = " ".join(desc_parts) if desc_parts else None
                
                # Extract colors and images from first color variant
                if "detail" in data and "colors" in data["detail"]:
                    colors_data = data["detail"]["colors"]
                    if colors_data:
                        # Get color names
                        result["colors"] = [c.get("name", "") for c in colors_data if c.get("name")]
                        
                        # Get images from first color
                        first_color = colors_data[0]
                        if "xmedia" in first_color:
                            images = []
                            for media in first_color["xmedia"]:
                                if media.get("path") and media.get("name"):
                                    # Build the image URL
                                    img_url = f"https://static.zara.net/photos/{media['path']}/{media['name']}"
                                    # Get a reasonable size
                                    img_url = img_url.replace(".jpg", ".jpg?ts=1&w=850")
                                    images.append(img_url)
                            result["images"] = images[:5]  # Limit to 5 images
                        
                        # Get price from first color's first size
                        if "sizes" in first_color and first_color["sizes"]:
                            first_size = first_color["sizes"][0]
                            if "price" in first_size:
                                # Price is in cents
                                result["price"] = first_size["price"] / 100
                            if "oldPrice" in first_size:
                                result["original_price"] = first_size["oldPrice"] / 100
                
                if result.get("name"):
                    console.print(f"[dim]Got product data from API: {result.get('name')}[/dim]")
                    return result
                    
        except Exception as e:
            console.print(f"[dim]API lookup failed: {e}[/dim]")
        
        return None

    def _extract_name_from_url(self, url: str) -> Optional[str]:
        """Extract a product name from the URL as a fallback."""
        try:
            # URL format: /us/en/product-name-here-p12345678.html
            match = re.search(r'/([^/]+)-p\d+\.html', url)
            if match:
                name_slug = match.group(1)
                # Convert slug to title case
                name = name_slug.replace('-', ' ').title()
                return name
        except:
            pass
        return None

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

        Uses Zara's ITXRest API for reliable size data.
        Falls back to DOM extraction if API fails.
        Returns a list of dicts: [{"size": "M", "available": true}, ...]
        """
        try:
            import httpx

            # Get the product ID from the current URL
            url = page.url
            product_id = self._extract_product_id(url)

            if not product_id:
                console.print("[yellow]Could not extract product ID for size lookup[/yellow]")
                return []

            # Query Zara's ITXRest API directly using httpx (not browser)
            # This bypasses any browser-based bot detection
            api_url = f"https://www.zara.com/itxrest/2/catalog/store/11719/product/{product_id}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.zara.com/us/en/",
            }

            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(api_url, headers=headers, timeout=10)

                if response.status_code != 200:
                    console.print(f"[yellow]Size API returned status {response.status_code}[/yellow]")
                    return []

                data = response.json()
                sizes = []
                seen_sizes = set()

                # Extract sizes from the first color variant
                if "detail" in data and "colors" in data["detail"]:
                    colors = data["detail"]["colors"]
                    if colors:
                        first_color = colors[0]
                        if "sizes" in first_color:
                            for size in first_color["sizes"]:
                                size_name = size.get("name", "")
                                if size_name and size_name not in seen_sizes:
                                    availability = size.get("availability", "unknown")
                                    sizes.append({
                                        "size": size_name,
                                        "available": availability in ("in_stock", "low_on_stock"),
                                        "availability": availability,
                                        "sku": size.get("sku")
                                    })
                                    seen_sizes.add(size_name)

                if sizes:
                    console.print(f"[dim]Found {len(sizes)} sizes via API: {[s['size'] for s in sizes]}[/dim]")

                return sizes

        except Exception as e:
            console.print(f"[yellow]Warning: Could not extract sizes via API: {e}[/yellow]")
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
