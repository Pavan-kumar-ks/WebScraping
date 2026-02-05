# AI/ML Article Scraper - Complete Workflow

## Overview
This system automatically discovers and scrapes AI and Machine Learning related articles from multiple websites. It consists of three main components that work together:

1. **ml_link_finder.py** - Discovers AI/ML related links from source websites
2. **scraper.py** - Scrapes article content (headings and paragraphs) from discovered links
3. **ai_ml_scraper_workflow.py** - Orchestrates the complete workflow

## How It Works

### Workflow Steps:
1. **Link Discovery**: The system takes URLs from `scraper.py` and searches each website for links containing AI/ML related keywords
2. **Filtering**: Links are filtered based on relevance using keywords like "artificial intelligence", "machine learning", "deep learning", etc.
3. **Content Scraping**: The filtered links are then scraped to extract article headings and full paragraph content
4. **Output**: Results are saved to JSON files with metadata about the scraping process

## Installation

Make sure you have the required dependencies installed:

```bash
pip install playwright
python -m playwright install chromium
```

## Usage

### Option 1: Run the Complete Workflow (Recommended)
This runs both link discovery and article scraping in one go:

```bash
python ai_ml_scraper_workflow.py
```

**Output Files:**
- `ai_ml_links.json` - All discovered AI/ML related links
- `ai_ml_articles.json` - Scraped article content with headings and paragraphs

### Option 2: Run Components Separately

#### Step 1: Find AI/ML Links
```bash
python ml_link_finder.py
```
This will create `ai_ml_links.json` with all discovered AI/ML related links.

#### Step 2: Scrape Articles (Manual)
After discovering links, you can use the scraper functions programmatically:

```python
import asyncio
import json
from scraper import scrape_from_links

# Load discovered links
with open('ai_ml_links.json', 'r') as f:
    data = json.load(f)
    links = [item['url'] for item in data['ai_ml_links']]

# Scrape articles
result = asyncio.run(scrape_from_links(links))

# Save results
with open('ai_ml_articles.json', 'w') as f:
    json.dump(result, f, indent=2)
```

## Configuration

### AI/ML Keywords
You can customize the keywords used for filtering in `ml_link_finder.py`:

```python
AI_ML_KEYWORDS = [
    'artificial intelligence', 'machine learning', 'deep learning',
    'neural network', 'ai', 'ml', 'nlp', 'computer vision',
    # Add more keywords as needed
]
```

### Performance Settings
Adjust concurrency and limits in both scripts:

```python
CONFIG = {
    "concurrency": 5,  # Number of pages to process simultaneously
    "max_links_per_site": 50,  # Maximum AI/ML links per source site
    "navigation_timeout": 30000,  # Page load timeout in ms
}
```

## Output Format

### ai_ml_links.json
```json
{
  "metadata": {
    "discoveredAt": "2024-01-01T12:00:00",
    "totalLinksFound": 250,
    "totalSources": 27,
    "successfulSites": 25
  },
  "ai_ml_links": [
    {
      "url": "https://example.com/ai-article",
      "text": "Machine Learning Breakthrough",
      "relevance_score": 3,
      "site": "example.com"
    }
  ]
}
```

### ai_ml_articles.json
```json
{
  "metadata": {
    "scrapedAt": "2024-01-01T12:30:00",
    "totalLinks": 250,
    "successfulScrapes": 235,
    "failedScrapes": 15
  },
  "articles": [
    {
      "url": "https://example.com/ai-article",
      "heading": "Machine Learning Breakthrough",
      "content": "Full article text with all paragraphs combined...",
      "paragraphCount": 12,
      "scraped": true
    }
  ]
}
```

## Features

✓ Automatic AI/ML keyword detection
✓ Smart link filtering (same domain only)
✓ Relevance scoring for discovered links
✓ Full article content extraction (headings + paragraphs)
✓ Parallel processing for faster scraping
✓ Detailed metadata and statistics
✓ Error handling and retry logic
✓ Resource optimization (blocks images, fonts, etc.)

## Source URLs

The system uses URLs defined in `scraper.py`:
- Government AI portals (IndiaAI, NEGD, etc.)
- Technology news sites
- AI-focused publications
- General tech news with AI coverage

You can modify the `TARGET_URLS` list in `scraper.py` to add or remove sources.

## Troubleshooting

### No links found
- Check if the source websites are accessible
- Try increasing the navigation timeout
- Verify that the keywords match the content on those sites

### Scraping failures
- Some sites may have anti-bot protection
- Increase timeout values in CONFIG
- Check if the sites require JavaScript rendering (already handled by Playwright)

### Memory issues
- Reduce the `concurrency` value
- Process fewer links at a time
- Use `max_links_per_site` to limit results

## Notes

- The scraper respects robots.txt implicitly through Playwright
- Resource-heavy assets (images, fonts) are blocked for faster performance
- All operations are asynchronous for optimal speed
- Same-domain restriction ensures focused content discovery
