"""
Configuration settings for Zara scraper ETL pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ScraperConfig:
    """Configuration for the web scraper."""

    # Base URLs
    base_url: str = "https://www.zara.com"
    country: str = "us"
    language: str = "en"

    # Category URLs for Men's clothing
    categories: dict = field(
        default_factory=lambda: {
            "tshirts": "/us/en/man-tshirts-l855.html",
            "pants": "/us/en/man-trousers-l838.html",
            "jackets": "/us/en/man-jackets-l640.html",
        }
    )

    # Scraping limits
    products_per_category: int = 2  # 2 products per category = 6 total
    max_retries: int = 3

    # Rate limiting (be respectful)
    page_delay_seconds: float = 3.0  # Delay between page loads
    image_delay_seconds: float = 1.0  # Delay between image downloads

    # Browser settings
    headless: bool = True  # Set to False for debugging
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout_ms: int = 30000

    # User agents to rotate
    user_agents: list = field(
        default_factory=lambda: [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        ]
    )


@dataclass
class StorageConfig:
    """Configuration for data storage."""

    # Base data directory
    base_dir: Path = field(
        default_factory=lambda: Path(__file__).parent.parent / "data"
    )

    # Directory structure
    brand: str = "zara"
    gender: str = "mens"

    # Image settings
    download_images: bool = True
    image_format: str = "jpg"
    max_images_per_product: int = 5  # Limit to primary images

    @property
    def output_dir(self) -> Path:
        """Get the output directory for scraped data."""
        return self.base_dir / self.brand / self.gender

    def get_product_dir(self, product_id: str, category: str) -> Path:
        """Get the directory for a specific product."""
        return self.output_dir / category / product_id

    def ensure_dirs(self) -> None:
        """Create necessary directories if they don't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class LoggingConfig:
    """Configuration for logging."""

    log_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "logs")
    log_level: str = "INFO"
    log_to_file: bool = True
    log_to_console: bool = True

    def ensure_dirs(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class PipelineConfig:
    """Main configuration combining all settings."""

    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self):
        """Ensure all necessary directories exist."""
        self.storage.ensure_dirs()
        self.logging.ensure_dirs()


# Default configuration instance
config = PipelineConfig()
