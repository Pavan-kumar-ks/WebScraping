# 🕷️ Web Scraping - AI/ML Articles Crawler

A powerful Python-based web crawler that intelligently extracts AI and Machine Learning related articles from Indian news sources and government websites. The crawler uses advanced scoring mechanisms to identify and collect high-quality content related to artificial intelligence and machine learning.

## ✨ Features

- **Intelligent Content Filtering**: Scores articles based on AI/ML keyword density to ensure relevance
- **Recursive Web Crawling**: Discovers and crawls multiple pages across domains (configurable depth)
- **Smart Article Extraction**: Extracts headings, content, and metadata from web pages
- **Country Detection**: Automatically identifies content origin by domain TLD
- **Duplicate Prevention**: Tracks visited URLs to avoid redundant scraping
- **Graceful Error Handling**: Handles network timeouts and parsing errors elegantly
- **JSON Export**: Saves results in structured JSON format with AI scoring

## 🎯 Use Cases

- Aggregating AI/ML news from multiple Indian sources
- Building datasets of AI-related articles for analysis
- Monitoring technology trends across government and media websites
- Content research for AI policy and industry insights

## 📋 Requirements

- Python 3.7+
- `requests` - HTTP library for fetching web pages
- `beautifulsoup4` - HTML parsing and content extraction

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/Pavan-kumar-ks/WebScraping.git
cd WebScraping
git checkout pavan
```

2. Install dependencies:
```bash
pip install requests beautifulsoup4
```

Or use the requirements file (if available):
```bash
pip install -r requirements.txt
```

## 💻 Usage

Run the crawler with:

```bash
python web_crawler.py
```

The script will:
1. Crawl through all configured websites
2. Extract AI/ML-related articles
3. Score each article based on keyword relevance
4. Save results to `ai_ml_articles_strict.json`

### Output Format

The script generates a JSON file with the following structure:

```json
[
  {
    "site": "https://example.com",
    "saved_articles": 5,
    "articles": [
      {
        "url": "https://example.com/article",
        "heading": "Article Title",
        "content": "Extracted article content...",
        "country": "India",
        "ai_score": 8
      }
    ]
  }
]
```

## ⚙️ Configuration

You can customize the crawler behavior by modifying these constants in `web_crawler.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `MAX_LINKS_PER_SITE` | 20 | Maximum articles to extract per website |
| `MAX_DEPTH` | 2 | Maximum recursion depth for crawling |
| `MAX_URLS_PER_DEPTH` | 20 | Maximum URLs to process per depth level |
| `MIN_AI_SCORE` | 4 | Minimum AI keyword score threshold |

### AI/ML Keywords

The crawler matches against 40+ AI/ML keywords including:
- Core concepts: `artificial intelligence`, `machine learning`, `deep learning`
- Technologies: `tensorflow`, `pytorch`, `keras`, `scikit-learn`
- Techniques: `nlp`, `computer vision`, `neural network`, `lstm`, `cnn`
- Models: `gpt`, `llm`, `bert`, `transformer`
- And more...

Edit the `AI_ML_KEYWORDS` list to customize keyword matching.

### Websites Included

The crawler targets 28+ Indian news sources and government sites:
- Government portals (IndiaAI, NEGD, CIO Economic Times)
- Major news outlets (Times of India, Hindustan Times, Indian Express)
- Tech-focused publications (Analytics India Mag, E-Government)
- And more...

Modify the `SITES` list to add or remove sources.

## 📁 Project Structure

```
WebScraping/
├── web_crawler.py              # Main crawler script
├── ai_ml_articles.json         # Scraped articles (basic)
├── ai_ml_articles_strict.json  # High-quality filtered articles
├── __pycache__/               # Python cache
└── README.md                   # This file
```

## 🔧 How It Works

### 1. **URL Filtering**
Excludes URLs containing: `login`, `signup`, `register`, `cart`, `checkout`, image/PDF files

### 2. **Content Extraction**
- Removes: scripts, styles, navigation, footers, headers
- Prioritizes: article tags and paragraph content
- Extracts: heading (Open Graph → H1 → Page Title)
- Limits: content to 6000 characters

### 3. **Scoring System**
Counts AI/ML keyword occurrences in:
- URL
- Article heading
- Article content

Only articles with score ≥ 4 are saved.

### 4. **Crawling Strategy**
- Starts from seed URL
- Discovers internal links
- Recursively crawls up to specified depth
- Respects visited URL tracking
- Adds 0.3s delay between requests

## 📊 Example Output

```json
{
  "site": "https://impact.indiaai.gov.in/",
  "saved_articles": 3,
  "articles": [
    {
      "url": "https://impact.indiaai.gov.in/ai-policy",
      "heading": "India's AI Strategy: Transforming the Future",
      "content": "Artificial intelligence is revolutionizing...",
      "country": "India",
      "ai_score": 12
    }
  ]
}
```

## ⚠️ Important Notes

- **Rate Limiting**: Includes 0.3s delay between requests to respect server resources
- **User Agent**: Sends standard Mozilla user agent to avoid blocking
- **Timeout**: 15-second timeout per request to handle slow servers
- **Robots.txt**: Respects website crawling policies
- **Error Handling**: Gracefully continues if individual pages fail

## 🤝 Contributing

Feel free to:
- Add new websites to crawl
- Enhance keyword detection
- Improve content extraction
- Fix bugs or edge cases

## 📝 License

This project is open source. Please ensure compliance with websites' Terms of Service and `robots.txt` when using this crawler.

## ⚡ Performance Tips

1. **Reduce crawl depth** if scraping is slow:
   ```python
   MAX_DEPTH = 1  # Only crawl main pages
   ```

2. **Adjust scoring threshold** to get more/fewer results:
   ```python
   MIN_AI_SCORE = 3  # Lower threshold for more results
   ```

3. **Filter websites** to speed up processing:
   ```python
   SITES = ["https://impact.indiaai.gov.in/"]  # Start with one
   ```

## 🐛 Troubleshooting

**Issue**: "Connection timeout" errors
- **Solution**: Increase timeout or reduce crawl depth

**Issue**: Few/no articles found
- **Solution**: Lower `MIN_AI_SCORE` or add more websites

**Issue**: Blocked by website
- **Solution**: Add delay, check robots.txt, or skip that site

## 📧 Support

For questions or issues, please open a GitHub issue on the repository.

---

**Built with ❤️ using Python, BeautifulSoup, and Requests**
