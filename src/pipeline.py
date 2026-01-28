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
        use_supabase: bool = True,
        save_local: bool = False,
        expand_colors: bool = False,
    ):
        self.config = pipeline_config or config
        self.extractor = None
        self.transformer = ProductTransformer()
        self.loader = FileLoader(self.config.storage)
        self.force_rescrape = force_rescrape
        self.use_supabase = use_supabase
        self.save_local = save_local
        self.expand_colors = expand_colors  # Create separate entries per color variant
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
                self.save_local = True  # Fall back to local storage

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

            # AI TAGGING PHASE - Generate ReFitd canonical tags
            console.print("\n[bold blue]═══ AI TAGGING PHASE ═══[/bold blue]")
            await self._generate_refitd_tags(self.transformed_products)

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

                # Get ALL product URLs from the category (pass a high limit to get more options)
                # We'll iterate through them until we find enough NEW products
                max_to_fetch = max(50, self.config.scraper.products_per_category * 3)
                product_urls = await extractor.get_category_product_urls(
                    category_key, limit=max_to_fetch
                )

                # Track how many NEW products we've scraped for this category
                new_products_scraped = 0
                target_new_products = self.config.scraper.products_per_category

                # Extract each product, skipping already-scraped ones
                for url in product_urls:
                    # Check if we've reached the target number of NEW products
                    if new_products_scraped >= target_new_products:
                        break

                    # Extract product ID from URL to check if already scraped
                    product_id = extractor._extract_product_id(url)

                    if product_id in scraped_ids:
                        console.print(
                            f"[dim]⏭️  Skipping already scraped: {product_id}[/dim]"
                        )
                        self.skipped_count += 1
                        continue

                    await extractor._random_delay()

                    if self.expand_colors:
                        # Extract and create separate entries for each color variant
                        color_variants = await extractor.extract_products_by_color(
                            url, category_key
                        )

                        for product in color_variants:
                            products.append(product)
                            new_products_scraped += 1

                            # Mark as scraped in the tracking database
                            if self.tracker:
                                self.tracker.mark_scraped(
                                    product_id=product.product_id,
                                    url=product.url,
                                    category=product.category,
                                    name=product.name,
                                    price=product.price_current,
                                )
                    else:
                        # Original behavior: single product per URL
                        product = await extractor.extract_product(url, category_key)

                        if product:
                            products.append(product)
                            new_products_scraped += 1

                            # Mark as scraped in the tracking database
                            if self.tracker:
                                self.tracker.mark_scraped(
                                    product_id=product.product_id,
                                    url=product.url,
                                    category=product.category,
                                    name=product.name,
                                    price=product.price_current,
                                )

                console.print(
                    f"[green]Category {category_key}: {new_products_scraped} new products scraped[/green]"
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
        saved_paths = []

        # Save to Supabase if enabled
        if self.use_supabase and self.supabase_loader:
            console.print("[cyan]Saving to Supabase...[/cyan]")
            for product, raw in zip(products, raw_products):
                try:
                    # Convert Pydantic models to dicts for JSON storage
                    weight_dict = (
                        product.weight.model_dump() if product.weight else None
                    )
                    style_tags_list = (
                        [tag.model_dump() for tag in product.style_tags]
                        if product.style_tags
                        else None
                    )
                    formality_dict = (
                        product.formality.model_dump() if product.formality else None
                    )

                    await self.supabase_loader.save_product(
                        product_id=product.product_id,
                        name=product.name,
                        category=product.category,
                        url=raw.url,
                        price_current=product.price.current,
                        price_original=product.price.original,
                        currency=product.price.currency,
                        description=product.description,
                        colors=product.colors,
                        color=getattr(
                            raw, "color", None
                        ),  # Single color for this variant
                        parent_product_id=getattr(
                            raw, "parent_product_id", None
                        ),  # Parent product ID
                        sizes=product.sizes,
                        materials=product.materials,
                        fit=product.fit,
                        weight=weight_dict,
                        style_tags=style_tags_list,
                        formality=formality_dict,
                        image_urls=raw.image_urls,
                        composition=raw.composition,
                    )
                except Exception as e:
                    console.print(
                        f"[red]Failed to save {product.name} to Supabase: {e}[/red]"
                    )
            console.print(
                f"[green]✓ Saved {len(products)} products to Supabase[/green]"
            )

        # Save to local files if enabled
        if self.save_local:
            console.print("[cyan]Saving to local files...[/cyan]")
            saved_paths = await self.loader.save_all_products(products, image_urls_map)
            console.print(f"[green]✓ Saved {len(saved_paths)} products locally[/green]")
        else:
            # Return placeholder paths for products saved to Supabase
            saved_paths = [Path(f"supabase://{p.product_id}") for p in products]

        return saved_paths

    async def _generate_refitd_tags(self, products: list[ProductMetadata]) -> None:
        """
        AI Tagging phase: Generate ReFitd canonical tags for all scraped products.

        Uses GPT-4o vision to analyze product images and generate structured tags
        following the ReFitd Item Tagging Specification.
        """
        import json
        import os

        if not self.use_supabase or not self.supabase_loader:
            console.print("[yellow]Skipping AI tagging - Supabase not enabled[/yellow]")
            return

        try:
            from src.ai.refitd_tagger import ReFitdTagger
            from src.ai.tag_policy import apply_tag_policy
        except ImportError as e:
            console.print(
                f"[yellow]Skipping AI tagging - ReFitdTagger not available: {e}[/yellow]"
            )
            return

        supabase_url = os.getenv("SUPABASE_URL")
        bucket_name = "product-images"

        if not supabase_url:
            console.print("[yellow]Skipping AI tagging - SUPABASE_URL not set[/yellow]")
            return

        # Category mapping from Zara to ReFitd categories
        category_mapping = {
            "tshirts": "top_base",
            "shirts": "top_base",
            "polos": "top_base",
            "sweaters": "top_mid",
            "sweatshirts": "top_mid",
            "cardigans": "top_mid",
            "trousers": "bottom",
            "jeans": "bottom",
            "shorts": "bottom",
            "jackets": "outerwear",
            "blazers": "outerwear",
            "coats": "outerwear",
            "suits": "outerwear",
            "shoes": "shoes",
        }

        console.print(
            f"[cyan]Generating ReFitd canonical tags for {len(products)} products...[/cyan]"
        )

        try:
            async with ReFitdTagger() as tagger:
                tagged_count = 0

                for product in products:
                    product_id = product.product_id

                    # Get the image paths from the database (they were just saved)
                    try:
                        result = (
                            self.supabase_loader.client.table("products")
                            .select("image_paths")
                            .eq("product_id", product_id)
                            .execute()
                        )
                        if not result.data or not result.data[0].get("image_paths"):
                            console.print(
                                f"  [yellow]No images found for {product_id}[/yellow]"
                            )
                            continue

                        image_paths = result.data[0]["image_paths"]
                        image_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{image_paths[0]}"
                    except Exception as e:
                        console.print(
                            f"  [red]Error getting image path for {product_id}: {e}[/red]"
                        )
                        continue

                    # Map category
                    original_category = product.category.lower()
                    refitd_category = category_mapping.get(
                        original_category, "top_base"
                    )

                    console.print(f"  [dim]Tagging: {product.name[:40]}...[/dim]")

                    # Generate AI sensor output
                    ai_output = await tagger.tag_product(
                        image_url=image_url,
                        title=product.name,
                        category=refitd_category,
                        description=product.description or "",
                        brand="Zara",
                    )

                    if not ai_output:
                        console.print(f"    [yellow]No AI output generated[/yellow]")
                        continue

                    # Apply policy to get canonical tags
                    policy_result = apply_tag_policy(ai_output)

                    # Save to database
                    try:
                        update_data = {
                            "tags_ai_raw": json.dumps(ai_output),
                            "tags_final": policy_result.tags_final.to_dict(),
                            "curation_status_refitd": policy_result.curation_status,
                            "tag_policy_version": policy_result.tag_policy_version,
                        }

                        self.supabase_loader.client.table("products").update(
                            update_data
                        ).eq("product_id", product_id).execute()

                        tagged_count += 1
                        status_icon = {
                            "approved": "[green]✓[/green]",
                            "needs_review": "[yellow]⚠[/yellow]",
                            "needs_fix": "[red]✗[/red]",
                        }.get(policy_result.curation_status, "?")

                        style_str = (
                            ", ".join(policy_result.tags_final.style_identity)
                            if policy_result.tags_final.style_identity
                            else "none"
                        )

                        # Build layer info for tops
                        layer_str = ""
                        if policy_result.tags_final.top_layer_role:
                            layer_str = (
                                f" | Layer: {policy_result.tags_final.top_layer_role}"
                            )

                        # Build formality info
                        formality_str = ""
                        if policy_result.tags_final.formality:
                            formality_str = (
                                f" | Formality: {policy_result.tags_final.formality}"
                            )

                        console.print(
                            f"    {status_icon} Style: {style_str}{layer_str}{formality_str}"
                        )

                    except Exception as e:
                        console.print(f"    [red]Error saving tags: {e}[/red]")

                console.print(
                    f"[green]✓ Generated ReFitd tags for {tagged_count}/{len(products)} products[/green]"
                )

        except Exception as e:
            console.print(f"[red]AI Tagging failed: {e}[/red]")
            import traceback

            traceback.print_exc()

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
