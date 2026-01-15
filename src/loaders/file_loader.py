"""
File loader for saving product data and images to organized directory structure.
"""

import asyncio
import json
import re
import ssl
import sys
from pathlib import Path
from typing import Optional

import aiofiles
import aiohttp
from rich.console import Console
from rich.progress import Progress, TaskID

sys.path.insert(0, str(__file__).rsplit("/", 3)[0])
from config.settings import config, StorageConfig
from src.transformers.product_transformer import ProductMetadata

console = Console()


class FileLoader:
    """Saves product data and images to organized directory structure."""

    def __init__(self, storage_config: Optional[StorageConfig] = None):
        self.config = storage_config or config.storage
        self.config.ensure_dirs()

    def _sanitize_filename(self, name: str) -> str:
        """Create a safe filename from product name."""
        # Remove special characters, replace spaces with underscores
        name = re.sub(r"[^\w\s-]", "", name.lower())
        name = re.sub(r"[\s]+", "_", name)
        return name[:50]  # Limit length

    def _get_product_dir(self, product: ProductMetadata) -> Path:
        """Get the directory path for a product."""
        # Use category/product_id structure
        category_dir = product.subcategory or product.category
        safe_category = self._sanitize_filename(category_dir)
        product_dir = self.config.output_dir / safe_category / product.product_id
        product_dir.mkdir(parents=True, exist_ok=True)
        return product_dir

    async def download_image(
        self,
        url: str,
        save_path: Path,
        session: aiohttp.ClientSession,
        delay: float = 1.0,
    ) -> bool:
        """
        Download a single image.

        Args:
            url: Image URL
            save_path: Path to save the image
            session: aiohttp session
            delay: Delay after download (rate limiting)

        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": "https://www.zara.com/",
            }

            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                    async with aiofiles.open(save_path, "wb") as f:
                        await f.write(content)
                    await asyncio.sleep(delay)
                    return True
                else:
                    console.print(
                        f"[yellow]Failed to download {url}: HTTP {response.status}[/yellow]"
                    )
                    return False

        except Exception as e:
            console.print(f"[red]Error downloading {url}: {e}[/red]")
            return False

    async def download_product_images(
        self,
        product: ProductMetadata,
        image_urls: list[str],
        product_dir: Path,
    ) -> list[str]:
        """
        Download all images for a product.

        Args:
            product: Product metadata
            image_urls: List of image URLs
            product_dir: Directory to save images

        Returns:
            List of saved image filenames
        """
        saved_images = []

        if not image_urls:
            console.print(f"[yellow]No images to download for {product.name}[/yellow]")
            return saved_images

        # Create SSL context that doesn't verify certificates (for macOS compatibility)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            for i, url in enumerate(image_urls[: self.config.max_images_per_product]):
                # Generate filename
                extension = self.config.image_format
                # Try to get extension from URL
                if ".jpg" in url.lower() or ".jpeg" in url.lower():
                    extension = "jpg"
                elif ".png" in url.lower():
                    extension = "png"
                elif ".webp" in url.lower():
                    extension = "webp"

                filename = f"image_{i+1:02d}.{extension}"
                save_path = product_dir / filename

                success = await self.download_image(
                    url,
                    save_path,
                    session,
                    delay=self.config.image_format == "jpg" and 1.0 or 0.5,
                )

                if success:
                    saved_images.append(filename)
                    console.print(f"  [green]✓[/green] {filename}")

        return saved_images

    async def save_product(
        self,
        product: ProductMetadata,
        image_urls: list[str],
    ) -> Optional[Path]:
        """
        Save product metadata and images to disk.

        Args:
            product: Product metadata
            image_urls: Original image URLs from extraction

        Returns:
            Path to product directory if successful, None otherwise
        """
        try:
            product_dir = self._get_product_dir(product)
            console.print(f"\n[cyan]Saving {product.name} to {product_dir}[/cyan]")

            # Download images
            if self.config.download_images:
                saved_images = await self.download_product_images(
                    product, image_urls, product_dir
                )
                # Update product with local image filenames
                product.images = saved_images

            # Save metadata as JSON
            metadata_path = product_dir / "metadata.json"
            metadata_dict = product.model_dump(mode="json")

            async with aiofiles.open(metadata_path, "w") as f:
                await f.write(json.dumps(metadata_dict, indent=2))

            console.print(f"  [green]✓[/green] metadata.json")
            console.print(
                f"[green]✓ Saved {product.name} ({len(product.images)} images)[/green]"
            )

            return product_dir

        except Exception as e:
            console.print(
                f"[bold red]Error saving product {product.product_id}: {e}[/bold red]"
            )
            return None

    async def save_all_products(
        self,
        products: list[ProductMetadata],
        image_urls_map: dict[str, list[str]],
    ) -> list[Path]:
        """
        Save all products to disk.

        Args:
            products: List of ProductMetadata objects
            image_urls_map: Dict mapping product_id to list of image URLs

        Returns:
            List of saved product directory paths
        """
        saved_paths = []

        console.print(
            f"\n[bold magenta]Saving {len(products)} products...[/bold magenta]"
        )

        for product in products:
            image_urls = image_urls_map.get(product.product_id, [])
            path = await self.save_product(product, image_urls)
            if path:
                saved_paths.append(path)

        console.print(
            f"\n[bold green]Successfully saved {len(saved_paths)}/{len(products)} products[/bold green]"
        )
        return saved_paths

    def generate_summary(self, products: list[ProductMetadata]) -> dict:
        """Generate a summary of all scraped products."""
        summary = {
            "total_products": len(products),
            "categories": {},
            "price_range": {"min": None, "max": None},
            "products": [],
        }

        for product in products:
            # Count by category
            cat = product.subcategory or product.category
            summary["categories"][cat] = summary["categories"].get(cat, 0) + 1

            # Track price range
            if product.price.current:
                if (
                    summary["price_range"]["min"] is None
                    or product.price.current < summary["price_range"]["min"]
                ):
                    summary["price_range"]["min"] = product.price.current
                if (
                    summary["price_range"]["max"] is None
                    or product.price.current > summary["price_range"]["max"]
                ):
                    summary["price_range"]["max"] = product.price.current

            # Add product summary
            summary["products"].append(
                {
                    "id": product.product_id,
                    "name": product.name,
                    "category": cat,
                    "price": product.price.current,
                    "images_count": len(product.images),
                }
            )

        return summary

    async def save_summary(self, products: list[ProductMetadata]) -> Path:
        """Save a summary JSON file."""
        summary = self.generate_summary(products)
        summary_path = self.config.output_dir / "summary.json"

        async with aiofiles.open(summary_path, "w") as f:
            await f.write(json.dumps(summary, indent=2))

        console.print(f"\n[cyan]Summary saved to {summary_path}[/cyan]")
        return summary_path
