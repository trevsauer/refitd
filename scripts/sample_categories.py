#!/usr/bin/env python3
"""
Category Sampler - Scrape one product from each Zara category.

This script provides a robust way to sample one product from each configured
category. It's useful for:
- Testing the scraper pipeline
- Validating category URLs
- Getting representative samples for each category
- Quick data collection for development

Features:
- Scrapes exactly 1 product per category
- Continues to next category even if one fails
- Retry logic with exponential backoff
- Progress tracking and detailed logging
- Saves to Supabase or local files
- Generates a summary report

Usage:
    python sample_categories.py                    # Scrape all categories
    python sample_categories.py --categories tshirts,pants,jackets
    python sample_categories.py --supabase         # Save to Supabase
    python sample_categories.py --dry-run          # Just list categories
    python sample_categories.py --skip-existing    # Skip categories with existing products
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import config, PipelineConfig
from src.extractors.zara_extractor import RawProductData, ZaraExtractor

console = Console()


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class CategoryResult:
    """Result of scraping a single category."""

    category: str
    success: bool
    product: Optional[RawProductData] = None
    error: Optional[str] = None
    attempts: int = 0
    duration_seconds: float = 0.0
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class SamplerConfig:
    """Configuration for the category sampler."""

    categories: list[str] = field(default_factory=list)  # Empty = all categories
    max_retries: int = 3
    retry_delay_base: float = 5.0  # Base delay for exponential backoff
    use_supabase: bool = False
    dry_run: bool = False
    skip_existing: bool = False
    output_dir: Optional[Path] = None
    browser_type: str = "firefox"
    headless: bool = True


# =============================================================================
# CATEGORY SAMPLER
# =============================================================================


class CategorySampler:
    """
    Samples one product from each category.

    This class handles:
    - Iterating through categories
    - Retry logic with exponential backoff
    - Error handling and recovery
    - Progress tracking
    - Result aggregation
    """

    def __init__(self, sampler_config: SamplerConfig):
        self.config = sampler_config
        self.results: list[CategoryResult] = []
        self.extractor: Optional[ZaraExtractor] = None

        # Get pipeline config for scraper settings
        self.pipeline_config = PipelineConfig()
        self.pipeline_config.scraper.headless = sampler_config.headless

    def get_categories_to_scrape(self) -> list[str]:
        """Get the list of categories to scrape."""
        all_categories = list(self.pipeline_config.scraper.categories.keys())

        if self.config.categories:
            # Filter to only specified categories
            categories = [c for c in self.config.categories if c in all_categories]
            invalid = [c for c in self.config.categories if c not in all_categories]
            if invalid:
                console.print(
                    f"[yellow]⚠ Unknown categories (skipping): {', '.join(invalid)}[/yellow]"
                )
            return categories

        return all_categories

    async def check_existing_products(self, category: str) -> bool:
        """Check if we already have products for a category."""
        if self.config.use_supabase:
            try:
                from src.loaders.supabase_loader import SupabaseLoader

                async with SupabaseLoader() as loader:
                    # Query for products in this category
                    # Note: This is a simplified check - actual implementation
                    # may need to query differently based on your schema
                    return False  # TODO: Implement actual check
            except Exception:
                return False
        else:
            # Check local files
            category_dir = self.pipeline_config.storage.output_dir / category
            if category_dir.exists():
                product_dirs = [d for d in category_dir.iterdir() if d.is_dir()]
                return len(product_dirs) > 0
            return False

    async def scrape_one_product(self, category: str) -> Optional[RawProductData]:
        """
        Scrape a single product from a category.

        Args:
            category: Category key (e.g., 'tshirts', 'jackets')

        Returns:
            RawProductData if successful, None otherwise
        """
        # Get product URLs for this category (limit to 5 to have fallbacks)
        urls = await self.extractor.get_category_product_urls(category, limit=5)

        if not urls:
            console.print(f"[yellow]No product URLs found for {category}[/yellow]")
            return None

        # Try each URL until we get a successful extraction
        for i, url in enumerate(urls):
            console.print(
                f"[dim]  Trying product {i + 1}/{len(urls)}: {url[:80]}...[/dim]"
            )

            try:
                # Try extracting with color variants first
                products = await self.extractor.extract_products_by_color(url, category)

                if products and len(products) > 0:
                    return products[0]  # Return first color variant

            except Exception as e:
                console.print(f"[dim]  Failed: {str(e)[:100]}[/dim]")
                continue

        return None

    async def scrape_category_with_retry(self, category: str) -> CategoryResult:
        """
        Scrape a category with retry logic.

        Uses exponential backoff on failures.
        """
        start_time = time.time()
        result = CategoryResult(category=category, success=False)

        # Check if we should skip
        if self.config.skip_existing:
            has_existing = await self.check_existing_products(category)
            if has_existing:
                result.skipped = True
                result.skip_reason = "Already has products"
                result.success = True
                result.duration_seconds = time.time() - start_time
                return result

        for attempt in range(1, self.config.max_retries + 1):
            result.attempts = attempt

            try:
                console.print(
                    f"\n[bold cyan]📦 Scraping {category}[/bold cyan] (attempt {attempt}/{self.config.max_retries})"
                )

                product = await self.scrape_one_product(category)

                if product:
                    result.success = True
                    result.product = product
                    console.print(f"[bold green]✓ Success: {product.name}[/bold green]")
                    break
                else:
                    result.error = "No product could be extracted"

            except Exception as e:
                result.error = str(e)
                console.print(f"[red]✗ Error: {str(e)[:100]}[/red]")

            # If not the last attempt, wait before retrying
            if attempt < self.config.max_retries:
                delay = self.config.retry_delay_base * (
                    2 ** (attempt - 1)
                )  # Exponential backoff
                console.print(f"[dim]  Waiting {delay:.1f}s before retry...[/dim]")
                await asyncio.sleep(delay)

        result.duration_seconds = time.time() - start_time
        return result

    async def save_product(self, product: RawProductData) -> bool:
        """Save a product to storage (Supabase or local)."""
        try:
            if self.config.use_supabase:
                from src.loaders.supabase_loader import SupabaseLoader

                loader = SupabaseLoader()
                await loader.save_product(
                    product_id=product.product_id,
                    name=product.name,
                    category=product.category,
                    url=product.url,
                    price_current=product.price_current,
                    price_original=product.price_original,
                    currency=product.currency,
                    description=product.description,
                    colors=product.colors,
                    color=product.color,
                    parent_product_id=product.parent_product_id,
                    sizes=product.sizes,
                    materials=product.materials,
                    fit=product.fit,
                    composition=product.composition,
                    composition_structured=product.composition_structured,
                    image_urls=product.image_urls,  # No limit - config handles it
                )
            else:
                # Save to local files
                product_dir = self.pipeline_config.storage.get_product_dir(
                    product.product_id, product.category
                )
                product_dir.mkdir(parents=True, exist_ok=True)

                # Save metadata
                metadata_file = product_dir / "metadata.json"
                with open(metadata_file, "w") as f:
                    json.dump(
                        {
                            "product_id": product.product_id,
                            "name": product.name,
                            "url": product.url,
                            "category": product.category,
                            "price_current": product.price_current,
                            "price_original": product.price_original,
                            "currency": product.currency,
                            "description": product.description,
                            "colors": product.colors,
                            "color": product.color,
                            "sizes": product.sizes,
                            "materials": product.materials,
                            "composition": product.composition,
                            "images": [
                                url.split("/")[-1] for url in product.image_urls
                            ],
                            "image_urls": product.image_urls,
                            "scraped_at": product.scraped_at,
                        },
                        f,
                        indent=2,
                    )

                console.print(f"[dim]  Saved to: {product_dir}[/dim]")

            return True

        except Exception as e:
            console.print(f"[red]  Failed to save: {e}[/red]")
            return False

    async def run(self) -> list[CategoryResult]:
        """
        Run the category sampler.

        Returns:
            List of CategoryResult objects
        """
        categories = self.get_categories_to_scrape()

        if not categories:
            console.print("[red]No categories to scrape![/red]")
            return []

        # Print header
        console.print()
        console.print(
            Panel(
                f"[bold]Category Sampler[/bold]\n\n"
                f"Categories: {len(categories)}\n"
                f"Storage: {'Supabase' if self.config.use_supabase else 'Local files'}\n"
                f"Skip existing: {self.config.skip_existing}",
                title="🔍 Configuration",
            )
        )

        if self.config.dry_run:
            console.print("\n[yellow]DRY RUN - No scraping will be performed[/yellow]")
            table = Table(title="Categories to Scrape")
            table.add_column("Category", style="cyan")
            table.add_column("URL Path", style="dim")

            for cat in categories:
                url_path = self.pipeline_config.scraper.categories.get(cat, "N/A")
                table.add_row(cat, url_path)

            console.print(table)
            return []

        # Initialize extractor
        scraper_config = self.pipeline_config.scraper
        scraper_config.products_per_category = 1  # We only need 1

        console.print("\n[bold blue]Starting browser...[/bold blue]")

        try:
            async with ZaraExtractor(
                scraper_config=scraper_config, browser_type=self.config.browser_type
            ) as extractor:
                self.extractor = extractor

                # Process each category
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "[cyan]Processing categories...", total=len(categories)
                    )

                    for i, category in enumerate(categories):
                        progress.update(task, description=f"[cyan]{category}...")

                        result = await self.scrape_category_with_retry(category)
                        self.results.append(result)

                        # Save product if successful
                        if result.success and result.product:
                            await self.save_product(result.product)

                        progress.update(task, advance=1)

                        # Small delay between categories
                        if i < len(categories) - 1:
                            await asyncio.sleep(2)

        except Exception as e:
            console.print(f"[bold red]Fatal error: {e}[/bold red]")

        # Print summary
        self.print_summary()

        return self.results

    def print_summary(self):
        """Print a summary of the scraping results."""
        console.print("\n")

        # Create summary table
        table = Table(title="📊 Scraping Summary")
        table.add_column("Category", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Product", style="dim")
        table.add_column("Attempts", justify="center")
        table.add_column("Time", justify="right")

        success_count = 0
        failed_count = 0
        skipped_count = 0

        for result in self.results:
            if result.skipped:
                status = "[yellow]⏭ SKIPPED[/yellow]"
                product_name = result.skip_reason or "N/A"
                skipped_count += 1
            elif result.success:
                status = "[green]✓ SUCCESS[/green]"
                product_name = (
                    result.product.name[:40] + "..."
                    if result.product and len(result.product.name) > 40
                    else (result.product.name if result.product else "N/A")
                )
                success_count += 1
            else:
                status = "[red]✗ FAILED[/red]"
                product_name = (
                    result.error[:40] + "..."
                    if result.error and len(result.error) > 40
                    else (result.error or "Unknown error")
                )
                failed_count += 1

            table.add_row(
                result.category,
                status,
                product_name,
                str(result.attempts),
                f"{result.duration_seconds:.1f}s",
            )

        console.print(table)

        # Print totals
        total = len(self.results)
        console.print(f"\n[bold]Total:[/bold] {total} categories")
        console.print(f"  [green]✓ Success: {success_count}[/green]")
        console.print(f"  [red]✗ Failed: {failed_count}[/red]")
        console.print(f"  [yellow]⏭ Skipped: {skipped_count}[/yellow]")

        if failed_count > 0:
            console.print(
                f"\n[yellow]💡 Tip: Run with --categories to retry specific categories[/yellow]"
            )


# =============================================================================
# CLI
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Scrape one product from each Zara category",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Scrape all categories to local files
    python sample_categories.py

    # Scrape specific categories only
    python sample_categories.py --categories tshirts,pants,jackets

    # Save to Supabase instead of local files
    python sample_categories.py --supabase

    # Skip categories that already have products
    python sample_categories.py --skip-existing

    # Just list categories without scraping
    python sample_categories.py --dry-run

    # Show browser window for debugging
    python sample_categories.py --no-headless
        """,
    )

    parser.add_argument(
        "--categories",
        "-c",
        type=str,
        help="Comma-separated list of categories to scrape (default: all)",
    )

    parser.add_argument(
        "--supabase",
        "-s",
        action="store_true",
        help="Save to Supabase instead of local files",
    )

    parser.add_argument(
        "--dry-run", "-d", action="store_true", help="List categories without scraping"
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip categories that already have products",
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per category (default: 3)",
    )

    parser.add_argument(
        "--no-headless", action="store_true", help="Show browser window (for debugging)"
    )

    parser.add_argument(
        "--browser",
        type=str,
        choices=["firefox", "chromium", "webkit"],
        default="firefox",
        help="Browser to use (default: firefox)",
    )

    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available categories and exit",
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Handle --list-categories
    if args.list_categories:
        console.print("\n[bold]Available Categories:[/bold]\n")
        table = Table()
        table.add_column("Category Key", style="cyan")
        table.add_column("URL Path", style="dim")

        for cat, path in config.scraper.categories.items():
            table.add_row(cat, path)

        console.print(table)
        console.print(
            f"\n[dim]Total: {len(config.scraper.categories)} categories[/dim]"
        )
        return 0

    # Build sampler config
    sampler_config = SamplerConfig(
        categories=args.categories.split(",") if args.categories else [],
        max_retries=args.max_retries,
        use_supabase=args.supabase,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        browser_type=args.browser,
        headless=not args.no_headless,
    )

    # Run sampler
    sampler = CategorySampler(sampler_config)

    try:
        results = await sampler.run()

        # Return appropriate exit code
        failed = sum(1 for r in results if not r.success and not r.skipped)
        if failed > 0:
            return 1
        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user[/yellow]")
        return 130


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
