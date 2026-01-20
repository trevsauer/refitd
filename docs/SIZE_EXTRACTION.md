# Zara Size Extraction - Technical Solution

## Problem Statement

Zara's website uses sophisticated anti-bot detection that prevents automated browsers from accessing interactive features like the size selector dropdown. When clicking the "Add" button with Playwright, the size dropdown wouldn't open, even though it works perfectly in a real browser.

### What We Tried (And Failed)

1. **DOM Scraping** - Size buttons weren't rendered in the DOM
2. **Multiple Click Approaches** - Hover, force click, coordinate click, keyboard events
3. **Different Browsers** - Firefox, attempted Chromium
4. **Network Interception** - Captured only cookie consent data, not product APIs
5. **Checking `window.zara`** - Only contained config data, not product sizes

### Root Cause

Zara detects automated browsers and:
- Allows viewing product pages (when navigating from categories)
- **Blocks interactive features** like the size dropdown
- The "Add" button is visible but clicking doesn't trigger the size selector

---

## The Solution: Zara's ITXRest API

### Discovery

By analyzing Zara's website patterns, we discovered that Zara (owned by Inditex) exposes an internal REST API called **ITXRest** that returns complete product data including sizes.

### The API Endpoint

```
https://www.zara.com/itxrest/2/catalog/store/{store_id}/product/{product_id}
```

For the US store:
```
https://www.zara.com/itxrest/2/catalog/store/11719/product/02621421
```

### API Response Structure

```json
{
  "id": 499181503,
  "name": "PEARL KNIT T-SHIRT",
  "detail": {
    "colors": [
      {
        "id": "251",
        "name": "Oyster-white",
        "sizes": [
          {
            "name": "S",
            "availability": "in_stock",
            "price": 4990,
            "sku": 499181504
          },
          {
            "name": "M",
            "availability": "in_stock",
            "price": 4990,
            "sku": 499181505
          },
          {
            "name": "L",
            "availability": "in_stock",
            "price": 4990,
            "sku": 499181507
          },
          {
            "name": "XL",
            "availability": "low_on_stock",
            "price": 4990,
            "sku": 499181510
          }
        ]
      }
    ]
  }
}
```

### Key Data Available

| Field | Description |
|-------|-------------|
| `name` | Size label (S, M, L, XL, 30, 31, etc.) |
| `availability` | `in_stock`, `low_on_stock`, `out_of_stock` |
| `demand` | `DEMAND_REGULAR`, `DEMAND_RUNNING_OUT` |
| `sku` | SKU number for the specific size/color combo |
| `price` | Price in cents |

---

## Implementation

### Updated `_extract_sizes()` in `zara_extractor.py`

```python
async def _extract_sizes(self, page: Page) -> list[dict]:
    """Extract available sizes with availability status.

    Uses Zara's ITXRest API for reliable size data.
    """
    try:
        import httpx

        # Get product ID from current URL
        url = page.url
        product_id = self._extract_product_id(url)

        if not product_id:
            return []

        # Query Zara's ITXRest API directly using httpx (not browser)
        # This bypasses any browser-based bot detection
        api_url = f"https://www.zara.com/itxrest/2/catalog/store/11719/product/{product_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.zara.com/us/en/",
        }

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(api_url, headers=headers, timeout=10)

            if response.status_code != 200:
                return []

            data = response.json()
            sizes = []

            # Extract sizes from the first color variant
            if "detail" in data and "colors" in data["detail"]:
                colors = data["detail"]["colors"]
                if colors:
                    first_color = colors[0]
                    if "sizes" in first_color:
                        for size in first_color["sizes"]:
                            availability = size.get("availability", "unknown")
                            sizes.append({
                                "size": size.get("name", ""),
                                "available": availability in ("in_stock", "low_on_stock"),
                                "availability": availability,
                                "sku": size.get("sku")
                            })

            return sizes

    except Exception as e:
        return []
```

### Why This Works

1. **Bypasses Browser Detection** - Uses `httpx` (Python HTTP client) instead of making requests from within the browser context
2. **Simple HTTP Request** - No JavaScript execution needed
3. **Reliable Data** - API returns structured JSON with accurate stock information
4. **Fast** - No need to wait for page rendering or click interactions

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        SCRAPING FLOW                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Playwright loads product page                               │
│         ↓                                                       │
│  2. Extract product ID from URL (e.g., 02621421)                │
│         ↓                                                       │
│  3. Call ITXRest API via httpx (not browser)                    │
│     GET https://www.zara.com/itxrest/2/catalog/store/           │
│         11719/product/02621421                                  │
│         ↓                                                       │
│  4. Parse JSON response                                         │
│         ↓                                                       │
│  5. Extract sizes array from detail.colors[0].sizes             │
│         ↓                                                       │
│  6. Return: [{"size": "S", "available": true}, ...]             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Storage

Sizes are stored in two formats for flexibility:

### `sizes` column (simple list)
```json
["S", "M", "L", "XL"]
```

### `sizes_availability` column (JSONB with details)
```json
[
  {"size": "S", "available": true, "availability": "in_stock", "sku": 499181504},
  {"size": "M", "available": true, "availability": "in_stock", "sku": 499181505},
  {"size": "L", "available": true, "availability": "in_stock", "sku": 499181507},
  {"size": "XL", "available": true, "availability": "low_on_stock", "sku": 499181510}
]
```

---

## Viewer Display

The viewer shows sizes with availability styling:
- **Available sizes**: Normal display
- **Out of stock sizes**: Red background, strikethrough text

---

## Key Takeaways

1. **When DOM scraping fails, look for APIs** - Modern SPAs often have backend APIs that return the data you need
2. **Use HTTP clients outside the browser** - Bot detection often focuses on browser fingerprinting; direct API calls can bypass this
3. **Inditex/Zara uses ITXRest** - This API pattern may work for other Inditex brands (Massimo Dutti, Pull&Bear, etc.)
4. **Store ID matters** - The US store ID is `11719`; other countries have different IDs

---

## Files Modified

| File | Changes |
|------|---------|
| `src/extractors/zara_extractor.py` | Updated `_extract_sizes()` to use ITXRest API via httpx |
| `src/transformers/product_transformer.py` | Handle dict format sizes, extract string for validation |
| `src/loaders/supabase_loader.py` | Store both simple and detailed size formats |
| `supabase_schema.sql` | Added `sizes_availability` JSONB column |
| `viewer.py` | Display sizes with availability styling |
