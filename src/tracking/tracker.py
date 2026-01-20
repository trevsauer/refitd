"""
SQLite-based product tracking to avoid re-scraping the same products.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console

console = Console()


@dataclass
class TrackedProduct:
    """Record of a previously scraped product."""

    product_id: str
    url: str
    category: str
    name: str
    scraped_at: str
    price: Optional[float] = None


class ProductTracker:
    """
    Tracks scraped products in a SQLite database to avoid re-processing.

    The database stores minimal information needed to identify products
    and when they were last scraped.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the product tracker.

        Args:
            db_path: Path to the SQLite database file. Defaults to data/tracking.db
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "tracking.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS scraped_products (
                    product_id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    category TEXT NOT NULL,
                    name TEXT NOT NULL,
                    price REAL,
                    scraped_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_category ON scraped_products(category)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_scraped_at ON scraped_products(scraped_at)
            """
            )
            conn.commit()

    def is_scraped(self, product_id: str) -> bool:
        """
        Check if a product has already been scraped.

        Args:
            product_id: The product ID to check

        Returns:
            True if the product exists in the tracking database
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM scraped_products WHERE product_id = ?", (product_id,)
            )
            return cursor.fetchone() is not None

    def get_scraped_ids(self, category: Optional[str] = None) -> set[str]:
        """
        Get all product IDs that have been scraped.

        Args:
            category: Optional category filter

        Returns:
            Set of product IDs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT product_id FROM scraped_products WHERE category = ?",
                    (category,),
                )
            else:
                cursor.execute("SELECT product_id FROM scraped_products")
            return {row["product_id"] for row in cursor.fetchall()}

    def mark_scraped(
        self,
        product_id: str,
        url: str,
        category: str,
        name: str,
        price: Optional[float] = None,
    ) -> None:
        """
        Mark a product as scraped in the tracking database.

        Args:
            product_id: Unique product identifier
            url: Product page URL
            category: Product category
            name: Product name
            price: Current price (optional)
        """
        now = datetime.utcnow().isoformat() + "Z"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO scraped_products (product_id, url, category, name, price, scraped_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    url = excluded.url,
                    category = excluded.category,
                    name = excluded.name,
                    price = excluded.price,
                    updated_at = excluded.updated_at
            """,
                (product_id, url, category, name, price, now, now),
            )
            conn.commit()

    def get_product(self, product_id: str) -> Optional[TrackedProduct]:
        """
        Get tracking info for a specific product.

        Args:
            product_id: The product ID to look up

        Returns:
            TrackedProduct if found, None otherwise
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scraped_products WHERE product_id = ?", (product_id,)
            )
            row = cursor.fetchone()
            if row:
                return TrackedProduct(
                    product_id=row["product_id"],
                    url=row["url"],
                    category=row["category"],
                    name=row["name"],
                    scraped_at=row["scraped_at"],
                    price=row["price"],
                )
            return None

    def get_stats(self) -> dict:
        """
        Get tracking statistics.

        Returns:
            Dictionary with tracking stats
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM scraped_products")
            total = cursor.fetchone()["total"]

            cursor.execute(
                """
                SELECT category, COUNT(*) as count
                FROM scraped_products
                GROUP BY category
            """
            )
            by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT MIN(scraped_at) as first, MAX(scraped_at) as last FROM scraped_products"
            )
            row = cursor.fetchone()
            first_scraped = row["first"]
            last_scraped = row["last"]

            return {
                "total_products": total,
                "by_category": by_category,
                "first_scraped": first_scraped,
                "last_scraped": last_scraped,
            }

    def clear(self, category: Optional[str] = None) -> int:
        """
        Clear tracking records.

        Args:
            category: If provided, only clear records for this category.
                     If None, clears all records.

        Returns:
            Number of records deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "DELETE FROM scraped_products WHERE category = ?", (category,)
                )
            else:
                cursor.execute("DELETE FROM scraped_products")
            deleted = cursor.rowcount
            conn.commit()
            return deleted

    def remove_product(self, product_id: str) -> bool:
        """
        Remove a single product from the tracking database.

        Args:
            product_id: The product ID to remove

        Returns:
            True if the product was removed, False if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM scraped_products WHERE product_id = ?", (product_id,)
            )
            deleted = cursor.rowcount > 0
            conn.commit()
            return deleted

    def print_stats(self) -> None:
        """Print tracking statistics to console."""
        stats = self.get_stats()

        if stats["total_products"] == 0:
            console.print("[dim]No products tracked yet.[/dim]")
            return

        console.print(f"\n[bold cyan]Tracking Database Stats[/bold cyan]")
        console.print(f"  Total products: [green]{stats['total_products']}[/green]")

        if stats["by_category"]:
            console.print("  By category:")
            for cat, count in stats["by_category"].items():
                console.print(f"    • {cat}: {count}")

        if stats["first_scraped"]:
            console.print(f"  First scraped: {stats['first_scraped']}")
        if stats["last_scraped"]:
            console.print(f"  Last scraped: {stats['last_scraped']}")
