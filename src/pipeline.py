"""
Main ETL pipeline orchestrating extraction, transformation, and loading.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(__file__).rsplit("/", 2)[0])
from config.settings import config, PipelineConfig
from src.extractors.zara_extractor import RawProductData, ZaraExtractor
from src.loaders.file_loader import FileLoader
from src.tracking import ProductTracker
from src.transformers.product_transformer import ProductMetadata, ProductTransformer

console = Console()

# Optional Supabase loader (only imported if needed)
SupabaseLoader = None


def _get_supabase_loader():
    """Lazily import SupabaseLoader to avoid import errors when not using Supabase."""
    global SupabaseLoader
    if SupabaseLoader is None:
        from src.loaders.supabase_loader import SupabaseLoader as _SupabaseLoader

        SupabaseLoader = _SupabaseLoader
    return SupabaseLoader


class ZaraPipeline:
    """
    ETL Pipeline for scraping Zara products.

    Orchestrates:
    - Extract: Scrape product data from Zara website
    - Transform: Clean and validate product data
    - Load: Save to organized directory structure
    """

    def __init__(
        self,
        pipeline_config: Optional[PipelineConfig] = None,
        force_rescrape: bool = False,
        use_supabase: bool = False,
    ):
        self.config = pipeline_config or config
        self.extractor = None
        self.transformer = ProductTransformer()
        self.loader = FileLoader(self.config.storage)
        self.force_rescrape = force_rescrape
        self.use_supabase = use_supabase
        self.supabase_loader = None

        # Initialize Supabase loader if requested
        if use_supabase:
            try:
                LoaderClass = _get_supabase_loader()
                self.supabase_loader = LoaderClass()
                console.print("[green]✓ Supabase loader initialized[/green]")
            except Exception as e:
                console.print(f"[red]Failed to initialize Supabase: {e}[/red]")
                console.print("[yellow]Falling back to file storage[/yellow]")
                self.use_supabase = False

        # Initialize tracker if enabled
        self.tracker: Optional[ProductTracker] = None
        if self.config.tracking.enabled:
            self.tracker = ProductTracker(self.config.tracking.db_path)

        # Store raw data for image URL mapping
        self.raw_products: list[RawProductData] = []
        self.transformed_products: list[ProductMetadata] = []
        self.skipped_count: int = 0

    async def run(self) -> dict:
        """
        Run the complete ETL pipeline.

        Returns:
            Summary dict with pipeline results
        """
        start_time = datetime.now()

        self._print_header()

        try:
            # EXTRACT
            console.print("\n[bold blue]═══ EXTRACT PHASE ═══[/bold blue]")
            self.raw_products = await self._extract()

            if not self.raw_products:
                console.print(
                    "[bold red]No products extracted. Aborting pipeline.[/bold red]"
                )
                return {"success": False, "error": "No products extracted"}

            # TRANSFORM
            console.print("\n[bold blue]═══ TRANSFORM PHASE ═══[/bold blue]")
            self.transformed_products = self._transform(self.raw_products)

            if not self.transformed_products:
                console.print(
                    "[bold red]No products transformed. Aborting pipeline.[/bold red]"
                )
                return {"success": False, "error": "No products transformed"}

            # LOAD
            console.print("\n[bold blue]═══ LOAD PHASE ═══[/bold blue]")
            saved_paths = await self._load(self.transformed_products, self.raw_products)

            # Generate and save summary
            await self.loader.save_summary(self.transformed_products)

            # Print final summary
            elapsed = (datetime.now() - start_time).total_seconds()
            self._print_summary(elapsed, saved_paths)

            return {
                "success": True,
                "products_extracted": len(self.raw_products),
                "products_saved": len(saved_paths),
                "elapsed_seconds": elapsed,
                "output_dir": str(self.config.storage.output_dir),
            }

        except Exception as e:
            console.print(f"[bold red]Pipeline failed: {e}[/bold red]")
            return {"success": False, "error": str(e)}

    async def _extract(self) -> list[RawProductData]:
        """Extract phase: scrape products from Zara, skipping already-scraped ones."""
        products = []

        # Get already-scraped product IDs if tracking is enabled
        scraped_ids: set[str] = set()
        if self.tracker and not self.force_rescrape:
            scraped_ids = self.tracker.get_scraped_ids()
            if scraped_ids:
                console.print(
                    f"[dim]Tracking: {len(scraped_ids)} products already scraped[/dim]"
                )
                self.tracker.print_stats()

        async with ZaraExtractor(self.config.scraper) as extractor:
            for category_key in self.config.scraper.categories.keys():
                console.print(
                    f"\n[bold magenta]Processing category: {category_key}[/bold magenta]"
                )

                # Get product URLs
                product_urls = await extractor.get_category_product_urls(category_key)

                # Extract each product, skipping already-scraped ones
                for url in product_urls:
                    # Extract product ID from URL to check if already scraped
                    product_id = extractor._extract_product_id(url)

                    if product_id in scraped_ids:
                        console.print(
                            f"[dim]⏭️  Skipping already scraped: {product_id}[/dim]"
                        )
                        self.skipped_count += 1
                        continue

                    await extractor._random_delay()
                    product = await extractor.extract_product(url, category_key)

                    if product:
                        products.append(product)

                        # Mark as scraped in the tracking database
                        if self.tracker:
                            self.tracker.mark_scraped(
                                product_id=product.product_id,
                                url=product.url,
                                category=product.category,
                                name=product.name,
                                price=product.price_current,
                            )

        if self.skipped_count > 0:
            console.print(
                f"[yellow]Skipped {self.skipped_count} previously scraped products[/yellow]"
            )

        console.print(f"[green]Extracted {len(products)} new products[/green]")
        return products

    def _transform(self, raw_products: list[RawProductData]) -> list[ProductMetadata]:
        """Transform phase: clean and validate product data."""
        transformed = self.transformer.transform_batch(raw_products)
        console.print(f"[green]Transformed {len(transformed)} products[/green]")
        return transformed

    async def _load(
        self, products: list[ProductMetadata], raw_products: list[RawProductData]
    ) -> list[Path]:
        """Load phase: save products and images to storage."""
        # Create image URL mapping from raw data
        image_urls_map = {raw.product_id: raw.image_urls for raw in raw_products}

        # Save to Supabase if enabled
        if self.use_supabase and self.supabase_loader:
            console.print("[cyan]Saving to Supabase...[/cyan]")
            for product, raw in zip(products, raw_products):
                try:
                    await self.supabase_loader.save_product(
                        product_id=product.id,
                        name=product.name,
                        category=product.category,
                        url=raw.url,
                        price_current=product.price.current,
                        price_original=product.price.original,
                        currency=product.price.currency,
                        description=product.description,
                        colors=product.colors,
                        sizes=product.sizes,
                        materials=product.materials,
                        fit=product.fit,
                        image_urls=raw.image_urls,
                    )
                except Exception as e:
                    console.print(
                        f"[red]Failed to save {product.name} to Supabase: {e}[/red]"
                    )
            console.print(
                f"[green]✓ Saved {len(products)} products to Supabase[/green]"
            )

        # Also save to local files (as backup or if Supabase not enabled)
        saved_paths = await self.loader.save_all_products(products, image_urls_map)
        return saved_paths

    def _print_header(self):
        """Print pipeline header."""
        header = Panel(
            "[bold white]ZARA ETL PIPELINE[/bold white]\n"
            f"[dim]Categories: {', '.join(self.config.scraper.categories.keys())}[/dim]\n"
            f"[dim]Products per category: {self.config.scraper.products_per_category}[/dim]\n"
            f"[dim]Output: {self.config.storage.output_dir}[/dim]",
            title="🛍️ Web Scraper",
            border_style="blue",
        )
        console.print(header)

    def _print_summary(self, elapsed: float, saved_paths: list[Path]):
        """Print final pipeline summary."""
        table = Table(title="Pipeline Results", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Products Extracted", str(len(self.raw_products)))
        table.add_row("Products Saved", str(len(saved_paths)))
        table.add_row("Time Elapsed", f"{elapsed:.1f} seconds")
        table.add_row("Output Directory", str(self.config.storage.output_dir))

        console.print("\n")
        console.print(table)

        # List saved products
        if self.transformed_products:
            console.print("\n[bold]Saved Products:[/bold]")
            for product in self.transformed_products:
                console.print(
                    f"  • [cyan]{product.name}[/cyan] "
                    f"(${product.price.current or 'N/A'}) - "
                    f"{len(product.images)} images"
                )


async def main():
    """Run the Zara ETL pipeline."""
    pipeline = ZaraPipeline()
    result = await pipeline.run()

    if result["success"]:
        console.print("\n[bold green]✓ Pipeline completed successfully![/bold green]")
    else:
        console.print(
            f"\n[bold red]✗ Pipeline failed: {result.get('error')}[/bold red]"
        )

    return result


if __name__ == "__main__":
    asyncio.run(main())
