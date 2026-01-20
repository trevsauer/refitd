#!/usr/bin/env python3
"""
Zara ETL Pipeline - Main Entry Point

Scrapes men's clothing products from Zara, extracts product data and images,
and saves them to Supabase (or local files).

Usage:
    python main.py                    # Run with default settings
    python main.py --all              # Scrape ALL products from ALL categories
    python main.py --all -c jackets   # Scrape ALL jackets
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

# Available categories with descriptions
AVAILABLE_CATEGORIES = {
    # Clothing
    "tshirts": {"url": "/us/en/man-tshirts-l855.html", "desc": "T-Shirts & casual tops"},
    "shirts": {"url": "/us/en/man-shirts-l737.html", "desc": "Dress shirts & button-ups"},
    "trousers": {"url": "/us/en/man-trousers-l838.html", "desc": "Trousers & dress pants"},
    "jeans": {"url": "/us/en/man-jeans-l659.html", "desc": "Jeans & denim"},
    "shorts": {"url": "/us/en/man-shorts-l722.html", "desc": "Shorts & bermudas"},
    "jackets": {"url": "/us/en/man-jackets-l715.html", "desc": "Jackets & outerwear"},
    "blazers": {"url": "/us/en/man-blazers-l608.html", "desc": "Blazers & sport coats"},
    "suits": {"url": "/us/en/man-suits-l599.html", "desc": "Suits & formal wear"},
    # Footwear & Accessories
    "shoes": {"url": "/us/en/man-shoes-l769.html", "desc": "All footwear"},
    "bags": {"url": "/us/en/man-bags-l563.html", "desc": "Bags & backpacks"},
    "accessories": {"url": "/us/en/man-accessories-l537.html", "desc": "Belts, hats, scarves, etc."},
    "underwear": {"url": "/us/en/man-underwear-l789.html", "desc": "Underwear & socks"},
    # Discovery
    "new-in": {"url": "/us/en/man-new-in-l716.html", "desc": "New arrivals"},
}


class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter that preserves formatting and adds width."""
    def __init__(self, prog):
        super().__init__(prog, max_help_position=40, width=100)


def parse_args():
    """Parse command line arguments."""

    # Build category list for help text
    category_list = "\n".join([
        f"    {name:<14} {info['desc']}"
        for name, info in AVAILABLE_CATEGORIES.items()
    ])

    epilog = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE CATEGORIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{category_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXAMPLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Basic Usage:
    python main.py                          Default: 2 products per category
    python main.py -n 10                    10 products per category
    python main.py --all                    ALL products from ALL categories

  Single Category:
    python main.py --all -c jackets         ALL jackets
    python main.py -n 5 -c tshirts          5 t-shirts
    python main.py --all -c new-in          All new arrivals

  Multiple Categories:
    python main.py --all -c tshirts jeans   All t-shirts and jeans
    python main.py -n 10 -c shoes bags      10 shoes + 10 bags

  Debugging & Testing:
    python main.py --headless false         Watch the browser scrape
    python main.py --no-images              Skip image downloads (faster)
    python main.py -n 1 -c tshirts          Quick test: 1 product

  Storage Options:
    python main.py --no-supabase            Local files only (no cloud)
    python main.py --local                  Save to BOTH Supabase AND local

  Database Management:
    python main.py --stats                  View scraping statistics
    python main.py --wipe                   ⚠️  DELETE all products
    python main.py --force                  Re-scrape already-scraped products
    python main.py --clear-tracking         Clear tracking DB, then scrape

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMON WORKFLOWS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  First-time full scrape:
    python main.py --all

  Daily update (only new products):
    python main.py --all
    (Already-scraped products are automatically skipped)

  Complete refresh (re-scrape everything):
    python main.py --all --force

  Start fresh (wipe DB and rescrape):
    python main.py --wipe
    python main.py --all

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DATA OUTPUT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Supabase (default):
    • Products table with all metadata
    • Images stored in Supabase Storage bucket
    • Size availability (in_stock, low_on_stock, out_of_stock)

  Local files (--no-supabase or --local):
    • ./data/zara/mens/<category>/<product_id>/
        ├── metadata.json    (product data)
        └── images/          (downloaded images)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOTES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • Products are tracked to avoid duplicate scraping
  • Use --force to override tracking and re-scrape
  • The viewer (python viewer.py) provides a web UI at http://localhost:5001
  • Requires .env file with SUPABASE_URL and SUPABASE_KEY for cloud storage
"""

    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                        ZARA WEB SCRAPER ETL PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scrapes men's clothing products from Zara, including:
  • Product metadata (name, price, description, colors, materials)
  • Size availability (in stock, low stock, out of stock)
  • Product images (multiple per product)

Data is saved to Supabase (cloud) by default, with optional local file storage.
""",
        epilog=epilog,
        formatter_class=CustomHelpFormatter,
    )

    # Scraping options group
    scrape_group = parser.add_argument_group(
        "Scraping Options",
        "Control what and how much to scrape"
    )

    scrape_group.add_argument(
        "--products", "-n",
        type=int,
        default=2,
        metavar="NUM",
        help="Products to scrape per category (default: 2)",
    )

    scrape_group.add_argument(
        "--all", "-a",
        action="store_true",
        help="Scrape ALL products (overrides --products)",
    )

    scrape_group.add_argument(
        "--categories", "-c",
        type=str,
        nargs="+",
        default=list(AVAILABLE_CATEGORIES.keys()),
        metavar="CAT",
        help="Categories to scrape (default: all). See list below.",
    )

    scrape_group.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image downloads (faster, metadata only)",
    )

    # Browser options group
    browser_group = parser.add_argument_group(
        "Browser Options",
        "Control the browser behavior"
    )

    browser_group.add_argument(
        "--headless",
        type=str,
        default="true",
        choices=["true", "false"],
        metavar="BOOL",
        help="Run browser invisibly (default: true). Set 'false' to watch.",
    )

    # Storage options group
    storage_group = parser.add_argument_group(
        "Storage Options",
        "Control where data is saved"
    )

    storage_group.add_argument(
        "--no-supabase",
        action="store_true",
        help="Disable cloud storage (local files only)",
    )

    storage_group.add_argument(
        "--local",
        action="store_true",
        help="Also save to local files (in addition to Supabase)",
    )

    storage_group.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        metavar="DIR",
        help="Local output directory (default: ./data)",
    )

    # Database management group
    db_group = parser.add_argument_group(
        "Database Management",
        "Manage tracking and product databases"
    )

    db_group.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-scrape products (ignore tracking)",
    )

    db_group.add_argument(
        "--clear-tracking",
        action="store_true",
        help="Clear tracking database before scraping",
    )

    db_group.add_argument(
        "--stats",
        action="store_true",
        help="Show tracking statistics and exit",
    )

    db_group.add_argument(
        "--wipe",
        action="store_true",
        help="⚠️  DELETE ALL products from Supabase and exit",
    )

    return parser.parse_args()


def create_config(args) -> PipelineConfig:
    """Create pipeline configuration from arguments."""
    # Build category dict based on selected categories
    all_categories = {k: v["url"] for k, v in AVAILABLE_CATEGORIES.items()}

    selected_categories = {
        k: v for k, v in all_categories.items() if k in args.categories
    }

    # Handle --all flag: use a very high number to effectively scrape all products
    products_per_category = 9999 if args.all else args.products

    scraper_config = ScraperConfig(
        products_per_category=products_per_category,
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

    # Handle --wipe flag: wipe all products and exit
    if args.wipe:
        console.print("\n[bold red]⚠️  WARNING: This will DELETE ALL products from Supabase![/bold red]")
        console.print("[yellow]This will also clear the local tracking database.[/yellow]")
        console.print("[yellow]This action cannot be undone.[/yellow]\n")

        confirm = input("Type 'DELETE ALL' to confirm: ")
        if confirm == "DELETE ALL":
            try:
                # Wipe Supabase
                from src.loaders.supabase_loader import SupabaseLoader
                loader = SupabaseLoader()
                deleted_count = loader.wipe_all()
                console.print(f"\n[green]✓ Wiped {deleted_count} products from Supabase[/green]")

                # Also clear the tracking database
                tracking_deleted = tracker.clear()
                console.print(f"[green]✓ Cleared {tracking_deleted} records from tracking database[/green]")

                return 0
            except Exception as e:
                console.print(f"\n[red]Error wiping database: {e}[/red]")
                return 1
        else:
            console.print("[yellow]Wipe cancelled[/yellow]")
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
