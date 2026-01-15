#!/usr/bin/env python3
"""
Zara ETL Pipeline - Main Entry Point

Scrapes men's clothing products from Zara, extracts product data and images,
and saves them to an organized directory structure.

Usage:
    python main.py                    # Run with default settings (6 products)
    python main.py --headless false   # Run with visible browser for debugging
    python main.py --products 5       # Scrape 5 products per category
"""
import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import PipelineConfig, ScraperConfig, StorageConfig
from rich.console import Console
from src.pipeline import ZaraPipeline

console = Console()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Zara ETL Pipeline - Scrape men's clothing products"
    )

    parser.add_argument(
        "--products",
        "-n",
        type=int,
        default=2,
        help="Number of products to scrape per category (default: 2)",
    )

    parser.add_argument(
        "--headless",
        type=str,
        default="true",
        choices=["true", "false"],
        help="Run browser in headless mode (default: true)",
    )

    parser.add_argument(
        "--categories",
        type=str,
        nargs="+",
        default=["tshirts", "pants", "jackets"],
        help="Categories to scrape (default: tshirts pants jackets)",
    )

    parser.add_argument(
        "--output", type=str, default=None, help="Output directory (default: ./data)"
    )

    parser.add_argument(
        "--no-images", action="store_true", help="Skip downloading images"
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force re-scrape all products, ignoring tracking database",
    )

    parser.add_argument(
        "--clear-tracking",
        action="store_true",
        help="Clear the tracking database before running",
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show tracking statistics and exit",
    )

    parser.add_argument(
        "--no-supabase",
        action="store_true",
        help="Disable Supabase storage (local files only)",
    )

    parser.add_argument(
        "--local",
        action="store_true",
        help="Also save to local files (in addition to Supabase)",
    )

    return parser.parse_args()


def create_config(args) -> PipelineConfig:
    """Create pipeline configuration from arguments."""
    # Build category dict based on selected categories
    all_categories = {
        "tshirts": "/us/en/man-tshirts-l855.html",
        "pants": "/us/en/man-trousers-l838.html",
        "jackets": "/us/en/man-jackets-l640.html",
    }

    selected_categories = {
        k: v for k, v in all_categories.items() if k in args.categories
    }

    scraper_config = ScraperConfig(
        products_per_category=args.products,
        headless=args.headless.lower() == "true",
        categories=selected_categories,
    )

    storage_config = StorageConfig(
        download_images=not args.no_images,
    )

    if args.output:
        storage_config.base_dir = Path(args.output)

    return PipelineConfig(
        scraper=scraper_config,
        storage=storage_config,
    )


async def run_pipeline(
    config: PipelineConfig,
    force_rescrape: bool = False,
    use_supabase: bool = True,
    save_local: bool = False,
) -> dict:
    """Run the ETL pipeline with given config."""
    pipeline = ZaraPipeline(
        config,
        force_rescrape=force_rescrape,
        use_supabase=use_supabase,
        save_local=save_local,
    )
    return await pipeline.run()


def main():
    """Main entry point."""
    args = parse_args()

    # Import tracker for stats and clear operations
    from src.tracking import ProductTracker

    tracker = ProductTracker()

    # Handle --stats flag: show tracking stats and exit
    if args.stats:
        console.print("\n[bold cyan]Tracking Database Statistics[/bold cyan]")
        tracker.print_stats()
        return 0

    # Handle --clear-tracking flag: clear database before running
    if args.clear_tracking:
        deleted = tracker.clear()
        console.print(
            f"[yellow]Cleared {deleted} records from tracking database[/yellow]"
        )

    console.print(
        "\n[bold cyan]═══════════════════════════════════════════[/bold cyan]"
    )
    console.print("[bold cyan]       ZARA WEB SCRAPER ETL PIPELINE        [/bold cyan]")
    console.print(
        "[bold cyan]═══════════════════════════════════════════[/bold cyan]\n"
    )

    console.print(f"[dim]Products per category:[/dim] {args.products}")
    console.print(f"[dim]Categories:[/dim] {', '.join(args.categories)}")
    console.print(f"[dim]Headless mode:[/dim] {args.headless}")
    console.print(f"[dim]Download images:[/dim] {not args.no_images}")
    console.print(f"[dim]Force re-scrape:[/dim] {args.force}")

    # Supabase is enabled by default unless --no-supabase is passed
    use_supabase = not args.no_supabase
    save_local = (
        args.local or args.no_supabase
    )  # Save locally if --local or --no-supabase

    console.print(f"[dim]Use Supabase:[/dim] {use_supabase}")
    console.print(f"[dim]Save locally:[/dim] {save_local}")

    config = create_config(args)

    try:
        result = asyncio.run(
            run_pipeline(
                config,
                force_rescrape=args.force,
                use_supabase=use_supabase,
                save_local=save_local,
            )
        )

        if result["success"]:
            console.print(
                "\n[bold green]═══════════════════════════════════════════[/bold green]"
            )
            console.print(
                "[bold green]       PIPELINE COMPLETED SUCCESSFULLY     [/bold green]"
            )
            console.print(
                "[bold green]═══════════════════════════════════════════[/bold green]"
            )
            console.print(f"\n[green]Output saved to: {result['output_dir']}[/green]")
            return 0
        else:
            console.print(
                f"\n[bold red]Pipeline failed: {result.get('error')}[/bold red]"
            )
            return 1

    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline cancelled by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[bold red]Unexpected error: {e}[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
