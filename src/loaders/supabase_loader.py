"""
Supabase loader for storing product metadata and images.

Stores product metadata in PostgreSQL and images in Supabase Storage.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from rich.console import Console
from supabase import Client, create_client

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent.parent / ".env")

console = Console()


class SupabaseLoader:
    """
    Loads scraped product data into Supabase.

    - Product metadata -> PostgreSQL database
    - Product images -> Supabase Storage bucket
    """

    def __init__(
        self,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
        bucket_name: str = "product-images",
    ):
        """
        Initialize the Supabase loader.

        Args:
            supabase_url: Supabase project URL (or set SUPABASE_URL env var)
            supabase_key: Supabase anon/service key (or set SUPABASE_KEY env var)
            bucket_name: Name of the storage bucket for images
        """
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Supabase credentials required. Set SUPABASE_URL and SUPABASE_KEY "
                "environment variables or pass them to the constructor."
            )

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.bucket_name = bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Check if the storage bucket exists (creation requires service_role key)."""
        try:
            # Try to list files in the bucket to verify it exists
            # Note: Creating buckets requires service_role key, not anon key
            self.client.storage.from_(self.bucket_name).list(limit=1)
            console.print(
                f"[dim]✓ Storage bucket '{self.bucket_name}' accessible[/dim]"
            )
        except Exception as e:
            # Bucket might not exist or we don't have permissions
            console.print(
                f"[yellow]Warning: Could not access bucket '{self.bucket_name}'. "
                f"Make sure it exists in Supabase Storage.[/yellow]"
            )

    async def save_product(
        self,
        product_id: str,
        name: str,
        category: str,
        url: str,
        price_current: Optional[float] = None,
        price_original: Optional[float] = None,
        currency: str = "USD",
        description: Optional[str] = None,
        colors: Optional[list[str]] = None,
        sizes: Optional[list[str]] = None,
        materials: Optional[list[str]] = None,
        fit: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
    ) -> dict:
        """
        Save a product to Supabase.

        Args:
            product_id: Unique product identifier
            name: Product name
            category: Product category
            url: Source URL
            price_current: Current price
            price_original: Original price (if on sale)
            currency: Currency code
            description: Product description
            colors: Available colors
            sizes: Available sizes
            materials: Material composition
            fit: Fit type (slim, regular, etc.)
            image_urls: List of image URLs to download and store

        Returns:
            Dict with saved product info including storage paths
        """
        console.print(f"[cyan]Saving product to Supabase: {name} ({product_id})[/cyan]")

        # Upload images first and get storage paths
        image_paths = []
        if image_urls:
            image_paths = await self._upload_images(product_id, category, image_urls)

        # Prepare product record
        product_data = {
            "product_id": product_id,
            "name": name,
            "category": category,
            "url": url,
            "price_current": price_current,
            "price_original": price_original,
            "currency": currency,
            "description": description,
            "colors": colors or [],
            "sizes": sizes or [],
            "materials": materials or [],
            "fit": fit,
            "image_paths": image_paths,
            "image_count": len(image_paths),
            "scraped_at": datetime.utcnow().isoformat() + "Z",
        }

        # Upsert to database (insert or update if exists)
        result = (
            self.client.table("products")
            .upsert(product_data, on_conflict="product_id")
            .execute()
        )

        console.print(f"[green]✓ Saved: {name} ({len(image_paths)} images)[/green]")

        return {
            "product_id": product_id,
            "name": name,
            "image_paths": image_paths,
            "db_record": result.data[0] if result.data else None,
        }

    async def _upload_images(
        self, product_id: str, category: str, image_urls: list[str]
    ) -> list[str]:
        """
        Download and upload images to Supabase Storage.

        Args:
            product_id: Product ID for organizing images
            category: Category for path organization
            image_urls: URLs of images to download

        Returns:
            List of storage paths for uploaded images
        """
        storage_paths = []

        async with httpx.AsyncClient() as http_client:
            for i, url in enumerate(image_urls):
                try:
                    # Download image
                    response = await http_client.get(url, timeout=30.0)
                    response.raise_for_status()
                    image_data = response.content

                    # Determine file extension from URL or content-type
                    content_type = response.headers.get("content-type", "image/jpeg")
                    ext = self._get_extension(url, content_type)

                    # Create storage path: category/product_id/image_0.jpg
                    storage_path = f"{category}/{product_id}/image_{i}{ext}"

                    # Upload to Supabase Storage
                    self.client.storage.from_(self.bucket_name).upload(
                        storage_path,
                        image_data,
                        {"content-type": content_type, "upsert": "true"},
                    )

                    storage_paths.append(storage_path)
                    console.print(f"[dim]  Uploaded: {storage_path}[/dim]")

                except Exception as e:
                    console.print(
                        f"[yellow]  Warning: Failed to upload image {i}: {e}[/yellow]"
                    )

                # Small delay between uploads
                await asyncio.sleep(0.2)

        return storage_paths

    def _get_extension(self, url: str, content_type: str) -> str:
        """Get file extension from URL or content-type."""
        # Try URL first
        url_lower = url.lower()
        if ".jpg" in url_lower or ".jpeg" in url_lower:
            return ".jpg"
        elif ".png" in url_lower:
            return ".png"
        elif ".webp" in url_lower:
            return ".webp"
        elif ".gif" in url_lower:
            return ".gif"

        # Fall back to content-type
        if "png" in content_type:
            return ".png"
        elif "webp" in content_type:
            return ".webp"
        elif "gif" in content_type:
            return ".gif"

        return ".jpg"

    def get_image_url(self, storage_path: str) -> str:
        """
        Get the public URL for an image in storage.

        Args:
            storage_path: Path within the storage bucket

        Returns:
            Public URL for the image
        """
        return self.client.storage.from_(self.bucket_name).get_public_url(storage_path)

    def get_products(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Retrieve products from the database.

        Args:
            category: Filter by category (optional)
            limit: Maximum number of products to return

        Returns:
            List of product records
        """
        query = self.client.table("products").select("*").limit(limit)

        if category:
            query = query.eq("category", category)

        result = query.execute()
        return result.data

    def get_product(self, product_id: str) -> Optional[dict]:
        """
        Get a single product by ID.

        Args:
            product_id: Product ID to retrieve

        Returns:
            Product record or None if not found
        """
        result = (
            self.client.table("products")
            .select("*")
            .eq("product_id", product_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def delete_product(self, product_id: str) -> bool:
        """
        Delete a product and its images.

        Args:
            product_id: Product ID to delete

        Returns:
            True if deleted successfully
        """
        # Get product to find image paths
        product = self.get_product(product_id)
        if not product:
            return False

        # Delete images from storage
        image_paths = product.get("image_paths", [])
        if image_paths:
            try:
                self.client.storage.from_(self.bucket_name).remove(image_paths)
            except Exception as e:
                console.print(f"[yellow]Warning: Could not delete images: {e}[/yellow]")

        # Delete from database
        self.client.table("products").delete().eq("product_id", product_id).execute()

        console.print(f"[green]Deleted product: {product_id}[/green]")
        return True

    def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dict with product counts and categories
        """
        # Total count
        total_result = (
            self.client.table("products").select("product_id", count="exact").execute()
        )
        total = total_result.count or 0

        # Count by category
        all_products = self.client.table("products").select("category").execute()
        by_category = {}
        for p in all_products.data:
            cat = p.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_products": total,
            "by_category": by_category,
        }
