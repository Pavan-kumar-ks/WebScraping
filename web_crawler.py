# import json
# import re
# import time
# from urllib.parse import urlparse, urljoin
# import requests
# from bs4 import BeautifulSoup

# MAX_LINKS_PER_SITE = 20  # Maximum articles per site
# MAX_DEPTH = 4  # Increased depth for more recursive crawling
# MAX_URLS_PER_DEPTH = 20  # More URLs to crawl per depth level

# VISITED = set()
# ALL_ARTICLES = []  # Global list to collect all articles

# AI_ML_KEYWORDS = [
#     "artificial intelligence","machine learning","deep learning","neural",
#     "ai","ml","nlp","computer vision","automation","gpt","llm",
#     "transformer","model","data science","analytics","algorithm","prediction",
#     "classification","regression","clustering","supervised","unsupervised",
#     "reinforcement learning","chatbot","language model","bert","tensorflow",
#     "pytorch","keras","scikit-learn","neural network","cnn","rnn","lstm"
# ]


# # ------------------------
# # SIGNAL SCORING
# # ------------------------

# def ai_signal_score(text):
#     if not text:
#         return 0
#     t = text.lower()
#     return sum(1 for k in AI_ML_KEYWORDS if k in t)


# def detect_country(url):
#     """Detect country from URL domain"""
#     parsed = urlparse(url)
#     domain = parsed.netloc.lower()
    
#     # Country mapping based on TLD and domain patterns
#     country_mappings = {
#         ".in": "India",
#         ".gov.in": "India",
#         "indiaai": "India",
#         "timesofindia": "India",
#         "hindustantimes": "India",
#         "economictimes": "India",
#         "newsonair.gov.in": "India",
#         "newindianexpress": "India",
#         "thehindu": "India",
#         "indianexpress": "India",
#         "theprint": "India",
#         "analyticsindiamag": "India",
#         "aninews": "India",
#         "cmogujarat": "India",
#         ".uk": "United Kingdom",
#         ".us": "United States",
#         ".de": "Germany",
#         ".fr": "France",
#         ".jp": "Japan",
#         ".cn": "China",
#         ".au": "Australia",
#         ".ca": "Canada",
#     }
    
#     # Check domain patterns
#     for pattern, country in country_mappings.items():
#         if pattern in domain:
#             return country
    
#     # Default based on TLD
#     tld = domain.split('.')[-1]
#     if tld == "in":
#         return "India"
    
#     return "Unknown"


# def looks_like_article(url):
#     """Check if URL looks like content (more inclusive)"""
#     url_lower = url.lower()
    
#     # Exclude common non-content links
#     bad_patterns = [
#         "login", "signup", "register", "forgot", "reset",
#         "cart", "payment", "checkout",
#         ".jpg", ".png", ".gif", ".pdf", ".zip",
#         "privacy", "terms", "sitemap",
#         "/page-not-found", "/404"
#     ]
    
#     if any(bad in url_lower for bad in bad_patterns):
#         return False
    
#     # Include pages with good indicators
#     good_patterns = [
#         "article", "news", "press", "blog", "post", "story", "report",
#         "insight", "analysis", "interview", "case-study", "guide",
#         "tutorial", "how-to", "/tech/", "/tech-", "/ai-", "/ml-"
#     ]
    
#     if any(good in url_lower for good in good_patterns):
#         return True
    
#     # Include any path with reasonable depth and no query params
#     path = urlparse(url).path
#     if path.count("/") >= 2 and "?" not in url_lower:
#         return True
    
#     return False


# # ------------------------
# # CONTENT EXTRACTION
# # ------------------------

# # def extract_fields(result, url):
# #     meta = result.metadata or {}
# #     heading = meta.get("title")
# #     subheading = meta.get("description")
# #     date = meta.get("publishedTime")
# #     blocks = result.extracted_content or []
# #     for b in blocks[:5]:
# #         if not heading and b.get("title"):
# #             heading = b["title"]
# #         if not subheading and b.get("summary"):
# #             subheading = b["summary"]
# #     data = {
# #         "url": url,
# #         "heading": heading,
# #         "subheading": subheading,
# #         "date": date
# #     }
# #     return {k:v for k,v in data.items() if v}

# def extract_content(soup):
#     """Extract full article body content - comprehensive extraction"""
    
#     # Remove unwanted elements
#     for element in soup(["script", "style", "nav", "footer", "header", "noscript", "meta", "link"]):
#         element.decompose()
    
#     content = ""
    
#     # Method 1: article tag (most reliable)
#     article = soup.find("article")
#     if article:
#         paragraphs = article.find_all("p")
#         if paragraphs:
#             content = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15])
#             if len(content) > 100:
#                 return content[:5000]
    
#     # Method 2: main content containers
#     content_selectors = [
#         "content", "article-content", "post-content", "main-content", 
#         "entry-content", "article-body", "story-body", "article-text",
#         "body-copy", "article-wrapper", "post-body", "news-body"
#     ]
    
#     for selector in content_selectors:
#         content_div = soup.find(["div", "section", "main"], class_=selector)
#         if content_div:
#             paragraphs = content_div.find_all("p")
#             if paragraphs:
#                 content = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15])
#                 if len(content) > 100:
#                     return content[:5000]
    
#     # Method 3: Find largest text block by ID
#     for elem_id in ["content", "article", "main", "post", "entry", "news"]:
#         content_elem = soup.find(id=elem_id)
#         if content_elem:
#             paragraphs = content_elem.find_all("p")
#             if paragraphs:
#                 content = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15])
#                 if len(content) > 100:
#                     return content[:5000]
    
#     # Method 4: Extract from main tag
#     main_tag = soup.find("main")
#     if main_tag:
#         paragraphs = main_tag.find_all("p")
#         if paragraphs:
#             content = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15])
#             if len(content) > 100:
#                 return content[:5000]
    
#     # Method 5: Get all paragraphs not in nav/footer
#     paragraphs = soup.find_all("p")
#     if paragraphs:
#         content = " ".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15])
#         if len(content) > 100:
#             return content[:5000]
    
#     return None


# def extract_heading(soup):
#     """Extract page/article heading"""
    
#     # Method 1: og:title
#     title_tag = soup.find("meta", {"property": "og:title"})
#     if title_tag and title_tag.get("content"):
#         return title_tag.get("content").strip()
    
#     # Method 2: title tag
#     title_tag = soup.find("title")
#     if title_tag and title_tag.string:
#         return title_tag.string.strip()
    
#     # Method 3: h1 tag
#     h1 = soup.find("h1")
#     if h1:
#         h1_text = h1.get_text(strip=True)
#         if h1_text and len(h1_text) > 5:
#             return h1_text
    
#     # Method 4: meta description as fallback
#     desc_tag = soup.find("meta", {"name": "description"})
#     if desc_tag and desc_tag.get("content"):
#         return desc_tag.get("content").strip()
    
#     return None


# def extract_fields(soup, url):
#     """Extract heading and content fields"""
    
#     heading = extract_heading(soup)
#     content = extract_content(soup)
#     country = detect_country(url)
    
#     # Only return if we have meaningful content
#     if heading and content and len(content) > 50:
#         return {
#             "url": url,
#             "heading": heading,
#             "content": content,
#             "country": country
#         }
    
#     return None


# # ------------------------
# # RECURSIVE CRAWL
# # ------------------------

# def crawl_recursive(url, base_domain, depth=0):
#     """Recursively crawl site for AI/ML content using requests + BeautifulSoup"""
#     if depth > MAX_DEPTH:
#         return []

#     if url in VISITED:
#         return []

#     VISITED.add(url)
#     print("  "*depth + f"[Depth {depth}] Scanning: {url}")

#     try:
#         headers = {
#             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#         }
        
#         response = requests.get(url, headers=headers, timeout=15)
#         response.raise_for_status()
#         response.encoding = 'utf-8'
        
#         soup = BeautifulSoup(response.content, 'html.parser')
        
#         found = []

#         # ---------- Extract article data if this page has content ----------
#         fields = extract_fields(soup, url)
        
#         if fields:
#             # Score based on AI/ML relevance
#             text_for_scoring = (fields.get("heading", "") + " " + fields.get("content", "")).lower()
#             score = ai_signal_score(text_for_scoring)
            
#             if score > 0:  # Accept any AI/ML mention
#                 fields["ai_score"] = score
#                 found.append(fields)
#                 print("  "*depth + f"✓ AI/ML content found (score: {score})")

#         # ---------- Discover and crawl all links ----------
#         discovered_links = []
        
#         for link in soup.find_all('a', href=True):
#             href = link.get('href', '').strip()
#             if not href:
#                 continue

#             # Skip anchor-only links
#             if href.startswith('#'):
#                 continue

#             full_url = urljoin(url, href)
            
#             # Remove fragments and query strings for cleaner URLs
#             parsed = urlparse(full_url)
#             clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
#             # Check if same domain
#             if base_domain not in parsed.netloc:
#                 continue

#             # Skip if already visited
#             if clean_url in VISITED:
#                 continue

#             # Include more URLs - relax the filtering
#             if looks_like_article(clean_url):
#                 discovered_links.append(clean_url)
#             elif depth < MAX_DEPTH - 1:
#                 # At shallower depths, also explore index pages
#                 path = parsed.path.lower()
#                 if not any(bad in path for bad in ['login', 'logout', 'signin', 'signup', 'admin', 'cart', 'checkout']):
#                     discovered_links.append(clean_url)

#         # Remove duplicates and limit
#         discovered_links = list(set(discovered_links))[:MAX_URLS_PER_DEPTH]
        
#         # Add delay to be respectful
#         time.sleep(0.3)

#         # ---------- Recursively crawl discovered links ----------
#         for next_url in discovered_links:
#             found.extend(crawl_recursive(next_url, base_domain, depth + 1))

#         return found

#     except requests.exceptions.Timeout:
#         print("  "*depth + "⏱ Timeout")
#         return []
#     except requests.exceptions.ConnectionError:
#         print("  "*depth + "❌ Connection error")
#         return []
#     except Exception as e:
#         print("  "*depth + f"⚠ Error: {str(e)[:60]}")
#         return []


# # ------------------------
# # MAIN
# # ------------------------

# SITES = [
#      "https://impact.indiaai.gov.in/",
#         "https://indiaai.gov.in/",
#         "https://negd.gov.in/",
#         "https://cio.economictimes.indiatimes.com/news/artificial-intelligence?utm_source=main_menu2&utm_medium=homepage",
#         "https://www.newsonair.gov.in/category/national/",
#         "https://cmogujarat.gov.in/en/news",
#         "https://timesofindia.indiatimes.com/technology/artificial-intelligence",
#         "https://www.hindustantimes.com/technology",
#         "https://economictimes.indiatimes.com/",
#         "https://www.rswebsols.com/category/technology/",
#         "https://globalvoices.org/-/topics/technology/",
#         "http://analyticsindiamag.com/ai-news",
#         "https://tele.net.in/",
#         "https://hubnetwork.in/",
#         "https://rajbhavan.mizoram.gov.in/",
#         "https://www.newindianexpress.com/search?q=artificial%20intelligence",
#         "https://www.visive.ai/_/search?query=Artificial%20Intelligence",
#         "https://nbbgc.org/",
#         "https://www.thehindu.com/sci-tech/technology/",
#         "https://www.communicationstoday.co.in/",
#         "https://www.eletimes.ai/?s=artificial+intelligence",
#         "https://www.databreachtoday.com/",
#         "https://indianexpress.com/section/technology/artificial-intelligence/?ref=technology_pg",
#         "https://www.news18.com/",
#         "https://theprint.in/?s=artificial+intelligence",
#         "https://www.aninews.in/",
#         "https://egov.eletsonline.com/"
# ]


# def main():
#     """Crawl all sites and extract AI/ML content"""
    
#     global VISITED, ALL_ARTICLES
    
#     all_results = []
#     total_articles_found = 0

#     for site_idx, site in enumerate(SITES, 1):
#         VISITED = set()  # Reset visited URLs for each site
        
#         domain = urlparse(site).netloc
#         print("\n" + "="*70)
#         print(f"[{site_idx}/{len(SITES)}] CRAWLING: {site}")
#         print("="*70)

#         try:
#             articles = crawl_recursive(site, domain, depth=0)
            
#             # Sort articles by AI/ML score (relevance)
#             articles_sorted = sorted(
#                 articles,
#                 key=lambda x: -x.get("ai_score", 0)
#             )
            
#             # Limit but keep more articles per site
#             top_articles = articles_sorted[:MAX_LINKS_PER_SITE]
            
#             all_results.append({
#                 "site": site,
#                 "total_found": len(articles_sorted),
#                 "articles": top_articles
#             })
            
#             total_articles_found += len(articles_sorted)
            
#             print(f"\n✓ Found {len(articles_sorted)} AI/ML articles from {site}")
            
#         except Exception as e:
#             print(f"✗ Error processing {site}: {str(e)[:100]}")
#             continue

#     # Save results
#     output_file = "crawl_ai_ml_content.json"
#     with open(output_file, "w", encoding="utf-8") as f:
#         json.dump(all_results, f, indent=2, ensure_ascii=False)

#     # Print final summary
#     print("\n" + "="*70)
#     print("CRAWLING SUMMARY")
#     print("="*70)
#     print(f"Total sites crawled: {len(SITES)}")
#     print(f"Total AI/ML articles found: {total_articles_found}")
    
#     total_saved = sum(len(r["articles"]) for r in all_results)
#     print(f"Total articles saved: {total_saved}")
#     print(f"Output saved to: {output_file}")
    
#     # Show top sources
#     print("\nTop sources by article count:")
#     sorted_results = sorted(all_results, key=lambda x: len(x["articles"]), reverse=True)
#     for result in sorted_results[:10]:
#         print(f"  • {result['site']}: {len(result['articles'])} articles")
    
#     print("\n✓ Crawling complete!")


# if __name__ == "__main__":
#     main()
import json
import re
import time
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup

MAX_LINKS_PER_SITE = 20
MAX_DEPTH = 2
MAX_URLS_PER_DEPTH = 20
MIN_AI_SCORE = 4   # 🔥 ONLY KEEP AI SCORE > 3

VISITED = set()

AI_ML_KEYWORDS = [
    "artificial intelligence","machine learning","deep learning","neural",
    "ai","ml","nlp","computer vision","automation","gpt","llm",
    "transformer","model","data science","analytics","algorithm","prediction",
    "classification","regression","clustering","supervised","unsupervised",
    "reinforcement learning","chatbot","language model","bert","tensorflow",
    "pytorch","keras","scikit-learn","neural network","cnn","rnn","lstm"
]


# ------------------------
# AI SIGNAL SCORING
# ------------------------

def ai_signal_score(text):
    if not text:
        return 0
    t = text.lower()
    return sum(1 for k in AI_ML_KEYWORDS if k in t)


# ------------------------
# COUNTRY DETECTION
# ------------------------

def detect_country(url):
    domain = urlparse(url).netloc.lower()

    if ".in" in domain:
        return "India"
    if ".uk" in domain:
        return "United Kingdom"
    if ".us" in domain:
        return "United States"

    return "Unknown"


# ------------------------
# URL FILTER
# ------------------------

def looks_like_article(url):
    bad = ["login","signup","register","cart","checkout",".jpg",".png",".pdf"]
    if any(b in url.lower() for b in bad):
        return False
    return True


# ------------------------
# CONTENT EXTRACTION
# ------------------------

def extract_heading(soup):

    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)

    if soup.title:
        return soup.title.get_text(strip=True)

    return None


def extract_content(soup):

    for bad in soup(["script","style","nav","footer","header"]):
        bad.decompose()

    article = soup.find("article")
    if article:
        ps = article.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in ps if len(p.get_text()) > 40)
        if len(text) > 200:
            return text[:6000]

    ps = soup.find_all("p")
    text = " ".join(p.get_text(strip=True) for p in ps if len(p.get_text()) > 40)
    if len(text) > 200:
        return text[:6000]

    return None


def extract_fields(soup, url):

    heading = extract_heading(soup)
    content = extract_content(soup)

    if not heading or not content:
        return None

    return {
        "url": url,
        "heading": heading,
        "content": content,
        "country": detect_country(url)
    }


# ------------------------
# RECURSIVE CRAWLER
# ------------------------

def crawl_recursive(url, base_domain, depth=0):

    if depth > MAX_DEPTH:
        return []

    if url in VISITED:
        return []

    VISITED.add(url)
    print("  "*depth + f"[D{depth}] {url}")

    try:
        r = requests.get(
            url,
            headers={"User-Agent":"Mozilla/5.0"},
            timeout=15
        )

        soup = BeautifulSoup(r.text, "html.parser")

        found = []

        # -------- extract article --------
        fields = extract_fields(soup, url)

        if fields:
            score = (
                ai_signal_score(fields["heading"]) +
                ai_signal_score(fields["content"]) +
                ai_signal_score(url)
            )

            if score >= MIN_AI_SCORE:
                fields["ai_score"] = score
                found.append(fields)
                print("  "*depth + f"✓ SAVED (score={score})")

        # -------- discover links --------
        links = set()

        for a in soup.find_all("a", href=True):

            full = urljoin(url, a["href"])
            parsed = urlparse(full)

            if base_domain not in parsed.netloc:
                continue

            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

            if clean in VISITED:
                continue

            if not looks_like_article(clean):
                continue

            links.add(clean)

        links = list(links)[:MAX_URLS_PER_DEPTH]

        time.sleep(0.3)

        for nxt in links:
            found.extend(
                crawl_recursive(nxt, base_domain, depth+1)
            )

        return found

    except Exception as e:
        print("  "*depth + "ERR:", str(e)[:60])
        return []


# ------------------------
# SITES
# ------------------------

SITES = [
    "https://impact.indiaai.gov.in/",
        "https://indiaai.gov.in/",
        "https://negd.gov.in/",
        "https://cio.economictimes.indiatimes.com/news/artificial-intelligence?utm_source=main_menu2&utm_medium=homepage",
        "https://www.newsonair.gov.in/category/national/",
        "https://cmogujarat.gov.in/en/news",
        "https://timesofindia.indiatimes.com/technology/artificial-intelligence",
        "https://www.hindustantimes.com/technology",
        "https://economictimes.indiatimes.com/",
        "https://www.rswebsols.com/category/technology/",
        "https://globalvoices.org/-/topics/technology/",
        "http://analyticsindiamag.com/ai-news",
        "https://tele.net.in/",
        "https://hubnetwork.in/",
        "https://rajbhavan.mizoram.gov.in/",
        "https://www.newindianexpress.com/search?q=artificial%20intelligence",
        "https://www.visive.ai/_/search?query=Artificial%20Intelligence",
        "https://nbbgc.org/",
        "https://www.thehindu.com/sci-tech/technology/",
        "https://www.communicationstoday.co.in/",
        "https://www.eletimes.ai/?s=artificial+intelligence",
        "https://www.databreachtoday.com/",
        "https://indianexpress.com/section/technology/artificial-intelligence/?ref=technology_pg",
        "https://www.news18.com/",
        "https://theprint.in/?s=artificial+intelligence",
        "https://www.aninews.in/",
        "https://egov.eletsonline.com/"
]


# ------------------------
# MAIN
# ------------------------

def main():

    results = []
    total_saved = 0

    for site in SITES:

        global VISITED
        VISITED = set()

        print("\n"+"="*70)
        print("SITE:", site)

        domain = urlparse(site).netloc

        articles = crawl_recursive(site, domain)

        articles = sorted(
            articles,
            key=lambda x: -x["ai_score"]
        )[:MAX_LINKS_PER_SITE]

        total_saved += len(articles)

        results.append({
            "site": site,
            "saved_articles": len(articles),
            "articles": articles
        })

    with open("ai_ml_articles_strict.json","w",encoding="utf-8") as f:
        json.dump(results,f,indent=2,ensure_ascii=False)

    print("\n"+"="*70)
    print("DONE")
    print("Saved:", total_saved)
    print("File: ai_ml_articles_strict.json")


if __name__ == "__main__":
    main()
