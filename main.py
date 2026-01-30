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
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import PipelineConfig, ScraperConfig, StorageConfig
from rich.console import Console
from src.pipeline import ZaraPipeline

console = Console()

# Available categories with descriptions
# NOTE: These are legacy URLs - actual URLs come from config/settings.py
AVAILABLE_CATEGORIES = {
    # Outerwear
    "jackets": {"url": "/us/en/man-jackets-l640.html", "desc": "Jackets & down jackets"},
    "outerwear": {"url": "/us/en/man-outerwear-l715.html", "desc": "All outerwear"},
    "leather": {"url": "/us/en/man-leather-l704.html", "desc": "Leather jackets & coats"},
    "blazers": {"url": "/us/en/man-blazers-l608.html", "desc": "Blazers & sport coats"},
    "suits": {"url": "/us/en/man-suits-l808.html", "desc": "Suits & formal wear"},
    "overshirts": {"url": "/us/en/man-overshirts-l3174.html", "desc": "Overshirts & shackets"},
    # Mid Layer
    "sweaters": {"url": "/us/en/man-knitwear-l681.html", "desc": "Sweaters & knitwear"},
    "quarter-zip": {"url": "/us/en/man-half-zip-tops-l16485.html", "desc": "Quarter-zip tops"},
    "hoodies": {"url": "/us/en/man-sweatshirts-l821.html", "desc": "Hoodies & sweatshirts"},
    # Base Layer
    "tshirts": {"url": "/us/en/man-tshirts-l855.html", "desc": "T-shirts & tank tops"},
    "shirts": {"url": "/us/en/man-shirts-l737.html", "desc": "Dress shirts & button-ups"},
    "polo-shirts": {"url": "/us/en/man-polos-l733.html", "desc": "Polo shirts"},
    # Bottoms
    "trousers": {"url": "/us/en/man-trousers-l838.html", "desc": "Pants & trousers"},
    "jeans": {"url": "/us/en/man-jeans-l659.html", "desc": "Jeans & denim"},
    "shorts": {"url": "/us/en/man-bermudas-l592.html", "desc": "Shorts & bermudas"},
    "sweatsuits": {"url": "/us/en/man-jogging-l679.html", "desc": "Sweatsuits & joggers"},
    # Footwear
    "shoes": {"url": "/us/en/man-shoes-l769.html", "desc": "All footwear"},
    "boots": {"url": "/us/en/man-shoes-boots-l781.html", "desc": "Boots"},
    # Accessories
    "bags": {"url": "/us/en/man-bags-l563.html", "desc": "Bags & backpacks"},
    "accessories": {"url": "/us/en/man-accessories-l537.html", "desc": "Accessories"},
    "colognes": {"url": "/us/en/man-accessories-perfumes-l551.html", "desc": "Colognes & perfumes"},
    # Discovery
    "new-in": {"url": "/us/en/man-new-in-l711.html", "desc": "New arrivals"},
    "best-sellers": {"url": "/us/en/man-all-products-l7465.html", "desc": "Best sellers"},
}


class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter that preserves formatting and adds width."""

    def __init__(self, prog):
        super().__init__(prog, max_help_position=40, width=100)


def parse_args():
    """Parse command line arguments."""

    # Build category list for help text
    category_list = "\n".join(
        [
            f"    {name:<14} {info['desc']}"
            for name, info in AVAILABLE_CATEGORIES.items()
        ]
    )

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
    python main.py --sample-all             1 product from EACH category (test all)

  Storage Options:
    python main.py --no-supabase            Local files only (no cloud)
    python main.py --local                  Save to BOTH Supabase AND local

    Database Management:
      python main.py --stats                  View scraping statistics
      python main.py --wipe                   ⚠️  DELETE all products
      python main.py --force                  Re-scrape already-scraped products
      python main.py --clear-tracking         Clear tracking DB, then scrape

    AI Features (requires Ollama: ollama serve):
      python main.py --ai-status              Check Ollama connection & models
      python main.py --generate-tags          Generate style tags for all products
      python main.py --generate-embeddings    Generate search embeddings
      python main.py --ai-chat                Start interactive chat assistant

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
        "Scraping Options", "Control what and how much to scrape"
    )

    scrape_group.add_argument(
        "--products",
        "-n",
        type=int,
        default=2,
        metavar="NUM",
        help="Products to scrape per category (default: 2)",
    )

    scrape_group.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Scrape ALL products (overrides --products)",
    )

    scrape_group.add_argument(
        "--sample-all",
        action="store_true",
        help="Scrape 1 product from EACH category (quick test of all categories)",
    )

    scrape_group.add_argument(
        "--categories",
        "-c",
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

    scrape_group.add_argument(
        "--no-expand-colors",
        action="store_true",
        help="Don't expand products by color (default: expand colors to create separate entries)",
    )

    # Browser options group
    browser_group = parser.add_argument_group(
        "Browser Options", "Control the browser behavior"
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
        "Storage Options", "Control where data is saved"
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
        "--output",
        "-o",
        type=str,
        default=None,
        metavar="DIR",
        help="Local output directory (default: ./data)",
    )

    # Database management group
    db_group = parser.add_argument_group(
        "Database Management", "Manage tracking and product databases"
    )

    db_group.add_argument(
        "--force",
        "-f",
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

    # AI features group
    ai_group = parser.add_argument_group(
        "AI Features",
        "AI-powered features (requires Ollama: brew install ollama && ollama serve)",
    )

    ai_group.add_argument(
        "--ai-status",
        action="store_true",
        help="Check Ollama connection and available models",
    )

    ai_group.add_argument(
        "--generate-tags",
        action="store_true",
        help="Generate AI style tags for products without tags",
    )

    ai_group.add_argument(
        "--generate-embeddings",
        action="store_true",
        help="Generate search embeddings for all products",
    )

    ai_group.add_argument(
        "--ai-chat",
        action="store_true",
        help="Start interactive AI fashion assistant chat",
    )

    ai_group.add_argument(
        "--tag-product",
        type=str,
        metavar="ID",
        help="Generate tags for a specific product by ID",
    )

    ai_group.add_argument(
        "--refitd-tags",
        action="store_true",
        help="Generate ReFitd canonical tags (structured with confidence scores)",
    )

    ai_group.add_argument(
        "--refitd-tag-product",
        type=str,
        metavar="ID",
        help="Generate ReFitd canonical tags for a specific product by ID",
    )

    # Sample & Tag group - streamlined workflow
    sample_group = parser.add_argument_group(
        "Sample & Tag",
        "Streamlined workflow: scrape one product per category and auto-tag with AI",
    )

    sample_group.add_argument(
        "--sample",
        action="store_true",
        help="Sample one product from each category and generate AI tags",
    )

    sample_group.add_argument(
        "--sample-categories",
        type=str,
        metavar="CATS",
        help="Comma-separated list of categories to sample (default: all)",
    )

    sample_group.add_argument(
        "--sample-skip-existing",
        action="store_true",
        help="Skip categories that already have products in the database",
    )

    sample_group.add_argument(
        "--sample-no-tags",
        action="store_true",
        help="Skip AI tagging (only scrape products)",
    )

    return parser.parse_args()


async def ai_status():
    """Check Ollama status and available models."""
    console.print("\n[bold cyan]AI Service Status[/bold cyan]\n")

    try:
        from src.ai import OllamaClient

        async with OllamaClient() as client:
            available = await client.is_available()

            if available:
                console.print("[green]✓ Ollama is running[/green]")

                models = await client.list_models()
                console.print(f"\n[cyan]Available models ({len(models)}):[/cyan]")
                for model in models:
                    console.print(f"  • {model}")

                # Check required models
                console.print("\n[cyan]Required models:[/cyan]")
                required = {
                    "phi3.5": "Chat/reasoning",
                    "moondream": "Vision/image analysis",
                    "nomic-embed-text": "Text embeddings",
                }

                for model, purpose in required.items():
                    found = any(model in m for m in models)
                    status = (
                        "[green]✓[/green]"
                        if found
                        else "[red]✗ (run: ollama pull " + model + ")[/red]"
                    )
                    console.print(f"  {model:<20} {purpose:<25} {status}")

                return 0
            else:
                console.print("[red]✗ Ollama is not running[/red]")
                console.print("\n[yellow]To start Ollama:[/yellow]")
                console.print("  1. Install: brew install ollama")
                console.print("  2. Start: ollama serve")
                console.print(
                    "  3. Pull models: ollama pull phi3.5 moondream nomic-embed-text"
                )
                return 1

    except ImportError as e:
        console.print(f"[red]Error importing AI module: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def ai_generate_tags():
    """Generate style tags for all products."""
    console.print("\n[bold cyan]Generating Style Tags[/bold cyan]\n")

    try:
        from src.ai import StyleTagger
        from src.loaders.supabase_loader import SupabaseLoader

        loader = SupabaseLoader()
        supabase_url = os.getenv("SUPABASE_URL")
        bucket_name = "product-images"

        # Get products without tags
        response = loader.client.table("products").select("*").execute()
        products = response.data or []

        # Filter to products without tags or with empty tags
        products_to_tag = [
            p for p in products if not p.get("tags") or len(p.get("tags", [])) == 0
        ]

        if not products_to_tag:
            console.print("[yellow]All products already have tags![/yellow]")
            return 0

        console.print(
            f"[cyan]Found {len(products_to_tag)} products without tags[/cyan]"
        )

        # Transform products to use Supabase storage URLs instead of original URLs
        for product in products_to_tag:
            image_paths = product.get("image_paths", [])
            if image_paths and supabase_url:
                # Use Supabase storage URL (publicly accessible)
                product["image_url"] = (
                    f"{supabase_url}/storage/v1/object/public/{bucket_name}/{image_paths[0]}"
                )
            else:
                product["image_url"] = None

        async with StyleTagger() as tagger:
            results = await tagger.generate_tags_batch(products_to_tag)

            # Save tags to database
            saved = 0
            for product_id, tags in results.items():
                try:
                    loader.client.table("products").update({"tags": tags}).eq(
                        "id", product_id
                    ).execute()
                    saved += 1
                    console.print(f"  [green]✓[/green] {product_id}: {tags}")
                except Exception as e:
                    console.print(f"  [red]✗[/red] {product_id}: {e}")

            console.print(f"\n[green]Generated tags for {saved} products[/green]")
            return 0

    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def ai_generate_embeddings():
    """Generate search embeddings for all products."""
    console.print("\n[bold cyan]Generating Search Embeddings[/bold cyan]\n")

    try:
        from src.ai import EmbeddingsService
        from src.loaders.supabase_loader import SupabaseLoader

        loader = SupabaseLoader()

        # Get all products
        response = loader.client.table("products").select("*").execute()
        products = response.data or []

        if not products:
            console.print("[yellow]No products found in database[/yellow]")
            return 0

        console.print(
            f"[cyan]Generating embeddings for {len(products)} products[/cyan]"
        )

        async with EmbeddingsService(
            supabase_client=loader.client
        ) as embeddings_service:
            # Generate embeddings
            embeddings = await embeddings_service.generate_all_embeddings(products)

            if embeddings:
                # Try to store in database
                try:
                    stored = await embeddings_service.store_embeddings(embeddings)
                    console.print(
                        f"\n[green]Stored {stored} embeddings in database[/green]"
                    )
                except Exception as e:
                    console.print(
                        f"\n[yellow]Could not store in database: {e}[/yellow]"
                    )
                    console.print(
                        "[dim]Embeddings were generated but need pgvector setup[/dim]"
                    )
                    console.print(
                        "\n[cyan]Run this SQL in Supabase to enable embedding storage:[/cyan]"
                    )
                    console.print("[dim]CREATE EXTENSION IF NOT EXISTS vector;[/dim]")
                    console.print(
                        "[dim]ALTER TABLE products ADD COLUMN IF NOT EXISTS embedding vector(768);[/dim]"
                    )

            return 0

    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def ai_chat():
    """Start interactive AI chat."""
    console.print("\n[bold cyan]Starting AI Fashion Assistant[/bold cyan]\n")

    try:
        from src.ai import ChatAssistant

        # Try to connect to Supabase for product context
        supabase_client = None
        try:
            from src.loaders.supabase_loader import SupabaseLoader

            loader = SupabaseLoader()
            supabase_client = loader.client
            console.print("[dim]Connected to Supabase for product context[/dim]")
        except Exception:
            console.print(
                "[yellow]Running without product context (Supabase not available)[/yellow]"
            )

        async with ChatAssistant(supabase_client=supabase_client) as assistant:
            await assistant.interactive_chat()
            return 0

    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def ai_tag_product(product_id: str):
    """Generate tags for a specific product."""
    console.print(
        f"\n[bold cyan]Generating Tags for Product: {product_id}[/bold cyan]\n"
    )

    try:
        from src.ai import StyleTagger
        from src.loaders.supabase_loader import SupabaseLoader

        loader = SupabaseLoader()
        supabase_url = os.getenv("SUPABASE_URL")
        bucket_name = "product-images"

        # Get the product
        response = (
            loader.client.table("products").select("*").eq("id", product_id).execute()
        )

        if not response.data:
            console.print(f"[red]Product {product_id} not found[/red]")
            return 1

        product = response.data[0]
        console.print(f"[cyan]Product: {product.get('name', 'Unknown')}[/cyan]")

        # Use Supabase storage URL for images (publicly accessible)
        image_paths = product.get("image_paths", [])
        if image_paths and supabase_url:
            image_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{image_paths[0]}"
        else:
            console.print("[yellow]No image available for this product[/yellow]")
            return 1

        async with StyleTagger() as tagger:
            console.print("[dim]Analyzing image with vision model...[/dim]")

            tags = await tagger.generate_tags(
                image_url=image_url,
                product_name=product.get("name", ""),
                product_description=product.get("description", ""),
            )

            console.print(f"\n[green]Generated tags:[/green] {tags}")

            # Optionally save to database
            try:
                loader.client.table("products").update({"tags": tags}).eq(
                    "id", product_id
                ).execute()
                console.print("[green]✓ Tags saved to database[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not save tags: {e}[/yellow]")

            return 0

    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1


async def ai_generate_refitd_tags():
    """Generate ReFitd canonical tags for all products."""
    console.print("\n[bold cyan]Generating ReFitd Canonical Tags[/bold cyan]\n")

    try:
        import json

        from src.ai import apply_tag_policy, ReFitdTagger
        from src.loaders.supabase_loader import SupabaseLoader

        loader = SupabaseLoader()
        supabase_url = os.getenv("SUPABASE_URL")
        bucket_name = "product-images"

        # Get products without canonical tags
        response = loader.client.table("products").select("*").execute()
        products = response.data or []

        # Filter to products without tags_final (or empty)
        products_to_tag = [p for p in products if not p.get("tags_final")]

        if not products_to_tag:
            console.print(
                "[yellow]All products already have ReFitd canonical tags![/yellow]"
            )
            return 0

        console.print(f"[cyan]Found {len(products_to_tag)} products to tag[/cyan]")

        # Map category names from Zara to ReFitd categories
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

        # Transform products to include required fields
        for product in products_to_tag:
            image_paths = product.get("image_paths", [])
            if image_paths and supabase_url:
                product["image_url"] = (
                    f"{supabase_url}/storage/v1/object/public/{bucket_name}/{image_paths[0]}"
                )
            else:
                product["image_url"] = None

            # Map category
            original_category = product.get("category", "").lower()
            product["refitd_category"] = category_mapping.get(
                original_category, "top_base"
            )

        # Filter products with valid image URLs
        products_with_images = [p for p in products_to_tag if p.get("image_url")]
        console.print(f"[cyan]{len(products_with_images)} products have images[/cyan]")

        async with ReFitdTagger() as tagger:
            saved = 0
            for product in products_with_images:
                product_id = product.get("id") or product.get("product_id", "")
                name = product.get("name", "")

                console.print(f"\n[cyan]Tagging: {name[:50]}...[/cyan]")

                # Generate AI sensor output
                ai_output = await tagger.tag_product(
                    image_url=product["image_url"],
                    title=name,
                    category=product["refitd_category"],
                    description=product.get("description", ""),
                    brand="Zara",
                )

                if not ai_output:
                    console.print(f"  [yellow]No AI output for {product_id}[/yellow]")
                    continue

                # Apply policy to get canonical tags
                policy_result = apply_tag_policy(ai_output)

                # Save to database
                try:
                    update_data = {
                        "tags_ai_raw": json.dumps(ai_output),  # Store AI sensor output
                        "tags_final": policy_result.tags_final.to_dict(),  # Store canonical tags
                        "curation_status": policy_result.curation_status,
                        "tag_policy_version": policy_result.tag_policy_version,
                    }

                    loader.client.table("products").update(update_data).eq(
                        "id", product_id
                    ).execute()

                    saved += 1
                    status_icon = {
                        "approved": "[green]✓[/green]",
                        "needs_review": "[yellow]⚠[/yellow]",
                        "needs_fix": "[red]✗[/red]",
                    }.get(policy_result.curation_status, "?")

                    console.print(
                        f"  {status_icon} Status: {policy_result.curation_status}"
                    )
                    console.print(
                        f"  [dim]Style: {policy_result.tags_final.style_identity}[/dim]"
                    )

                except Exception as e:
                    console.print(f"  [red]✗[/red] Error saving: {e}")

            console.print(
                f"\n[green]Generated canonical tags for {saved} products[/green]"
            )
            return 0

    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        console.print("[dim]Make sure ReFitdTagger is properly installed[/dim]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        return 1


async def ai_refitd_tag_product(product_id: str):
    """Generate ReFitd canonical tags for a specific product."""
    console.print(
        f"\n[bold cyan]Generating ReFitd Canonical Tags for: {product_id}[/bold cyan]\n"
    )

    try:
        import json

        from src.ai import apply_tag_policy, ReFitdTagger
        from src.loaders.supabase_loader import SupabaseLoader

        loader = SupabaseLoader()
        supabase_url = os.getenv("SUPABASE_URL")
        bucket_name = "product-images"

        # Get the product
        response = (
            loader.client.table("products").select("*").eq("id", product_id).execute()
        )

        if not response.data:
            console.print(f"[red]Product {product_id} not found[/red]")
            return 1

        product = response.data[0]
        console.print(f"[cyan]Product: {product.get('name', 'Unknown')}[/cyan]")
        console.print(f"[dim]Category: {product.get('category', 'Unknown')}[/dim]")

        # Get image URL
        image_paths = product.get("image_paths", [])
        if image_paths and supabase_url:
            image_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{image_paths[0]}"
        else:
            console.print("[yellow]No image available for this product[/yellow]")
            return 1

        # Map category
        category_mapping = {
            "tshirts": "top_base",
            "shirts": "top_base",
            "polos": "top_base",
            "sweaters": "top_mid",
            "sweatshirts": "top_mid",
            "trousers": "bottom",
            "jeans": "bottom",
            "shorts": "bottom",
            "jackets": "outerwear",
            "blazers": "outerwear",
            "coats": "outerwear",
            "shoes": "shoes",
        }
        original_category = product.get("category", "").lower()
        refitd_category = category_mapping.get(original_category, "top_base")

        async with ReFitdTagger() as tagger:
            console.print("[dim]Analyzing image with GPT-4o vision...[/dim]")

            # Generate AI sensor output
            ai_output = await tagger.tag_product(
                image_url=image_url,
                title=product.get("name", ""),
                category=refitd_category,
                description=product.get("description", ""),
                brand="Zara",
            )

            if not ai_output:
                console.print("[red]Failed to generate AI tags[/red]")
                return 1

            console.print("\n[bold]AI Sensor Output (with confidence):[/bold]")
            console.print_json(json.dumps(ai_output, indent=2))

            # Apply policy
            policy_result = apply_tag_policy(ai_output)

            console.print(f"\n[bold]Policy Result:[/bold]")
            console.print(f"Status: {policy_result.curation_status}")
            console.print(f"Reasons: {policy_result.curation_reasons}")

            console.print("\n[bold]Canonical Tags (for generator):[/bold]")
            console.print_json(json.dumps(policy_result.tags_final.to_dict(), indent=2))

            if policy_result.suppressed_tags:
                console.print("\n[yellow]Suppressed tags:[/yellow]")
                for s in policy_result.suppressed_tags:
                    console.print(
                        f"  - {s.field}: {s.tag} ({s.confidence:.2f}) - {s.reason}"
                    )

            if policy_result.defaults_applied:
                console.print("\n[yellow]Defaults applied:[/yellow]")
                for d in policy_result.defaults_applied:
                    console.print(f"  - {d.field}: {d.value} - {d.reason}")

            # Save to database
            try:
                update_data = {
                    "tags_ai_raw": json.dumps(ai_output),
                    "tags_final": policy_result.tags_final.to_dict(),
                    "curation_status": policy_result.curation_status,
                    "tag_policy_version": policy_result.tag_policy_version,
                }

                loader.client.table("products").update(update_data).eq(
                    "id", product_id
                ).execute()
                console.print("\n[green]✓ Tags saved to database[/green]")
            except Exception as e:
                console.print(f"\n[yellow]Could not save tags: {e}[/yellow]")

            return 0

    except ImportError as e:
        console.print(f"[red]Error importing modules: {e}[/red]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()
        return 1


async def sample_and_tag(
    categories: list[str] | None = None,
    skip_existing: bool = False,
    skip_tags: bool = False,
    max_retries: int = 3,
) -> int:
    """
    Sample one product from each category and generate AI tags.
    
    This is a streamlined workflow that:
    1. Scrapes exactly one product per category
    2. Saves to Supabase
    3. Generates ReFitd canonical tags for each product
    
    Args:
        categories: List of category keys to sample (None = all)
        skip_existing: Skip categories that already have products
        skip_tags: Skip AI tagging (only scrape)
        max_retries: Max retry attempts per category
    
    Returns:
        Exit code (0 = success, 1 = error)
    """
    import json
    import time
    from config.settings import config as pipeline_config
    from src.extractors.zara_extractor import ZaraExtractor
    from src.loaders.supabase_loader import SupabaseLoader
    
    # ANSI colors
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    
    print()
    print(f"{BOLD}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║         🛍️  SAMPLE & TAG WORKFLOW  🛍️               ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════╝{RESET}")
    
    # Get available categories from config
    all_categories = list(pipeline_config.scraper.categories.keys())
    
    # Filter to requested categories
    if categories:
        target_categories = [c for c in categories if c in all_categories]
        invalid = [c for c in categories if c not in all_categories]
        if invalid:
            print(f"{YELLOW}⚠ Unknown categories (skipping): {', '.join(invalid)}{RESET}")
    else:
        target_categories = all_categories
    
    print(f"\n{DIM}Categories:{RESET} {len(target_categories)}")
    print(f"{DIM}Skip existing:{RESET} {skip_existing}")
    print(f"{DIM}AI tagging:{RESET} {'Disabled' if skip_tags else 'Enabled'}")
    
    # Initialize
    loader = SupabaseLoader()
    supabase_url = os.getenv("SUPABASE_URL")
    bucket_name = "product-images"
    
    # Results tracking
    results = {
        "scraped": [],
        "tagged": [],
        "failed": [],
        "skipped": [],
    }
    
    # Category to ReFitd category mapping
    category_mapping = {
        "tshirts": "top_base",
        "shirts": "top_base",
        "polo-shirts": "top_base",
        "sweaters": "top_mid",
        "hoodies": "top_mid",
        "quarter-zip": "top_mid",
        "trousers": "bottom",
        "jeans": "bottom",
        "shorts": "bottom",
        "sweatsuits": "bottom",
        "jackets": "outerwear",
        "outerwear": "outerwear",
        "blazers": "outerwear",
        "suits": "outerwear",
        "leather": "outerwear",
        "overshirts": "outerwear",
        "shoes": "shoes",
        "boots": "shoes",
        "bags": "accessory",
        "accessories": "accessory",
        "colognes": "accessory",
    }
    
    print(f"\n{BOLD}Starting scraping...{RESET}\n")
    
    try:
        # Start browser for scraping
        scraper_config = pipeline_config.scraper
        scraper_config.products_per_category = 1
        
        async with ZaraExtractor(scraper_config=scraper_config) as extractor:
            for i, category in enumerate(target_categories):
                print(f"{CYAN}[{i+1}/{len(target_categories)}] {category}{RESET}")
                
                # Check if category already has products (if skip_existing)
                if skip_existing:
                    existing = loader.client.table("products").select("id").eq("category", category).limit(1).execute()
                    if existing.data:
                        print(f"  {DIM}⏭ Skipped (has existing products){RESET}")
                        results["skipped"].append(category)
                        continue
                
                # Scrape one product from this category
                start_time = time.time()
                product = None
                
                for attempt in range(1, max_retries + 1):
                    try:
                        # Get product URLs
                        urls = await extractor.get_category_product_urls(category, limit=5)
                        
                        if not urls:
                            print(f"  {YELLOW}No products found{RESET}")
                            break
                        
                        # Try to extract a product
                        for url in urls[:3]:  # Try up to 3 URLs
                            try:
                                products = await extractor.extract_products_by_color(url, category)
                                if products:
                                    product = products[0]
                                    break
                            except Exception:
                                continue
                        
                        if product:
                            break
                            
                    except Exception as e:
                        if attempt < max_retries:
                            print(f"  {DIM}Retry {attempt}/{max_retries}...{RESET}")
                            await asyncio.sleep(2 ** attempt)
                        else:
                            print(f"  {RED}✗ Failed: {str(e)[:50]}{RESET}")
                
                if not product:
                    results["failed"].append(category)
                    continue
                
                # Save to Supabase
                try:
                    saved_product = await save_product_to_supabase(loader, product, bucket_name)
                    duration = time.time() - start_time
                    print(f"  {GREEN}✓ {product.name[:45]}...{RESET} ({duration:.1f}s)")
                    results["scraped"].append({
                        "category": category,
                        "product_id": saved_product["id"],
                        "name": product.name,
                    })
                except Exception as e:
                    print(f"  {RED}✗ Save failed: {str(e)[:50]}{RESET}")
                    results["failed"].append(category)
    
    except Exception as e:
        print(f"\n{RED}Error during scraping: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return 1
    
    # AI Tagging phase
    if not skip_tags and results["scraped"]:
        print(f"\n{BOLD}Starting AI tagging...{RESET}\n")
        
        try:
            from src.ai import apply_tag_policy, ReFitdTagger
            
            async with ReFitdTagger() as tagger:
                for item in results["scraped"]:
                    product_id = item["product_id"]
                    category = item["category"]
                    name = item["name"]
                    
                    print(f"{CYAN}Tagging: {name[:45]}...{RESET}")
                    
                    try:
                        # Get product from database
                        response = loader.client.table("products").select("*").eq("id", product_id).single().execute()
                        product = response.data
                        
                        if not product:
                            print(f"  {YELLOW}Product not found in database{RESET}")
                            continue
                        
                        # Get image URL
                        image_paths = product.get("image_paths", [])
                        if image_paths and supabase_url:
                            image_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{image_paths[0]}"
                        else:
                            print(f"  {YELLOW}No image available{RESET}")
                            continue
                        
                        # Map category
                        refitd_category = category_mapping.get(category, "top_base")
                        
                        # Generate AI tags
                        ai_output = await tagger.tag_product(
                            image_url=image_url,
                            title=product.get("name", ""),
                            category=refitd_category,
                            description=product.get("description", ""),
                            brand="Zara",
                        )
                        
                        if not ai_output:
                            print(f"  {YELLOW}AI tagging failed{RESET}")
                            continue
                        
                        # Apply policy
                        policy_result = apply_tag_policy(ai_output)
                        
                        # Save to database
                        update_data = {
                            "tags_ai_raw": json.dumps(ai_output),
                            "tags_final": policy_result.tags_final.to_dict(),
                            "curation_status_refitd": policy_result.curation_status,
                            "tag_policy_version": policy_result.tag_policy_version,
                        }
                        
                        loader.client.table("products").update(update_data).eq("id", product_id).execute()
                        
                        # Show key tags
                        tags = policy_result.tags_final
                        style = ", ".join(tags.style_identity[:2]) if tags.style_identity else "—"
                        formality = tags.formality or "—"
                        print(f"  {GREEN}✓ Style: {style} | Formality: {formality}{RESET}")
                        results["tagged"].append(product_id)
                        
                    except Exception as e:
                        print(f"  {RED}✗ Error: {str(e)[:50]}{RESET}")
                        
        except ImportError as e:
            print(f"{RED}Error importing AI modules: {e}{RESET}")
        except Exception as e:
            print(f"{RED}Error during tagging: {e}{RESET}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print()
    print(f"{BOLD}╔══════════════════════════════════════════════════════╗{RESET}")
    print(f"{BOLD}║                    📊 SUMMARY                        ║{RESET}")
    print(f"{BOLD}╚══════════════════════════════════════════════════════╝{RESET}")
    print(f"\n  {GREEN}✓ Scraped:{RESET}  {len(results['scraped'])} products")
    print(f"  {GREEN}✓ Tagged:{RESET}   {len(results['tagged'])} products")
    print(f"  {YELLOW}⏭ Skipped:{RESET}  {len(results['skipped'])} categories")
    print(f"  {RED}✗ Failed:{RESET}   {len(results['failed'])} categories")
    
    if results["failed"]:
        print(f"\n  {DIM}Failed categories: {', '.join(results['failed'])}{RESET}")
    
    print()
    return 0 if not results["failed"] else 1


async def save_product_to_supabase(loader, product, bucket_name: str) -> dict:
    """Save a scraped product to Supabase with images."""
    import aiohttp
    from datetime import datetime
    
    supabase_url = os.getenv("SUPABASE_URL")
    
    # Download and upload images
    image_paths = []
    if product.image_urls and supabase_url:
        async with aiohttp.ClientSession() as session:
            for i, img_url in enumerate(product.image_urls[:5]):  # Max 5 images
                try:
                    async with session.get(img_url) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            
                            # Generate path
                            ext = "jpg"
                            if ".png" in img_url.lower():
                                ext = "png"
                            path = f"{product.category}/{product.product_id}/{i}.{ext}"
                            
                            # Upload to Supabase storage
                            loader.client.storage.from_(bucket_name).upload(
                                path,
                                image_data,
                                {"content-type": f"image/{ext}", "upsert": "true"}
                            )
                            image_paths.append(path)
                except Exception:
                    continue
    
    # Prepare product data
    product_data = {
        "product_id": product.product_id,
        "name": product.name,
        "url": product.url,
        "category": product.category,
        "price_current": product.price_current,
        "price_original": product.price_original,
        "currency": product.currency or "USD",
        "description": product.description,
        "colors": product.colors or [],
        "color": product.color,
        "sizes": product.sizes or [],
        "materials": product.materials or [],
        "composition": product.composition,
        "image_paths": image_paths,
        "scraped_at": product.scraped_at or datetime.utcnow().isoformat() + "Z",
        "brand": "zara",
    }
    
    # Upsert to database
    response = loader.client.table("products").upsert(
        product_data,
        on_conflict="product_id"
    ).execute()
    
    return response.data[0] if response.data else product_data


def create_config(args) -> PipelineConfig:
    """Create pipeline configuration from arguments."""
    # Build category dict based on selected categories
    all_categories = {k: v["url"] for k, v in AVAILABLE_CATEGORIES.items()}

    selected_categories = {
        k: v for k, v in all_categories.items() if k in args.categories
    }

    # Handle --all flag: use a very high number to effectively scrape all products
    # Handle --sample-all: scrape 1 product from each category
    if args.all:
        products_per_category = 9999
    elif args.sample_all:
        products_per_category = 1
    else:
        products_per_category = args.products

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
    expand_colors: bool = False,
) -> dict:
    """Run the ETL pipeline with given config."""
    pipeline = ZaraPipeline(
        config,
        force_rescrape=force_rescrape,
        use_supabase=use_supabase,
        save_local=save_local,
        expand_colors=expand_colors,
    )
    return await pipeline.run()


def main():
    """Main entry point."""
    args = parse_args()

    # Import tracker for stats and clear operations
    from src.tracking import ProductTracker

    tracker = ProductTracker()

    # Handle AI commands first (they exit after running)
    if args.ai_status:
        return asyncio.run(ai_status())

    if args.generate_tags:
        return asyncio.run(ai_generate_tags())

    if args.generate_embeddings:
        return asyncio.run(ai_generate_embeddings())

    if args.ai_chat:
        return asyncio.run(ai_chat())

    if args.tag_product:
        return asyncio.run(ai_tag_product(args.tag_product))

    if args.refitd_tags:
        return asyncio.run(ai_generate_refitd_tags())

    if args.refitd_tag_product:
        return asyncio.run(ai_refitd_tag_product(args.refitd_tag_product))

    # Handle --sample flag: sample one product from each category and tag
    if args.sample:
        categories = None
        if args.sample_categories:
            categories = [c.strip() for c in args.sample_categories.split(",")]
        return asyncio.run(sample_and_tag(
            categories=categories,
            skip_existing=args.sample_skip_existing,
            skip_tags=args.sample_no_tags,
        ))

    # Handle --stats flag: show tracking stats and exit
    if args.stats:
        console.print("\n[bold cyan]Tracking Database Statistics[/bold cyan]")
        tracker.print_stats()
        return 0

    # Handle --wipe flag: wipe all products and exit
    if args.wipe:
        console.print(
            "\n[bold red]⚠️  WARNING: This will DELETE ALL products from Supabase![/bold red]"
        )
        console.print(
            "[yellow]This will also clear the local tracking database.[/yellow]"
        )
        console.print("[yellow]This action cannot be undone.[/yellow]\n")

        confirm = input("Type 'DELETE ALL' to confirm: ")
        if confirm == "DELETE ALL":
            try:
                # Wipe Supabase
                from src.loaders.supabase_loader import SupabaseLoader

                loader = SupabaseLoader()
                deleted_count = loader.wipe_all()
                console.print(
                    f"\n[green]✓ Wiped {deleted_count} products from Supabase[/green]"
                )

                # Also clear the tracking database
                tracking_deleted = tracker.clear()
                console.print(
                    f"[green]✓ Cleared {tracking_deleted} records from tracking database[/green]"
                )

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
                expand_colors=not args.no_expand_colors,  # Default is True (expand colors)
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
