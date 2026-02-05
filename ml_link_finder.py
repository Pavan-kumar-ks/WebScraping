"""
ML Link Finder - Discovers AI/ML related links from websites
Searches websites for AI and Machine Learning related content and returns filtered links
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Set
from urllib.parse import urljoin, urlparse

from playwright.async_api import BrowserContext, Page, async_playwright

# AI/ML related keywords - grouped by specificity
# High-confidence keywords that strongly indicate AI/ML content
HIGH_CONFIDENCE_AI_ML_KEYWORDS = [
    'artificial intelligence', 'machine learning', 'deep learning', 'neural network',
    'generative ai', 'large language model', 'computer vision', 'natural language processing',
    'reinforcement learning', 'supervised learning', 'unsupervised learning',
    'convolutional neural', 'recurrent neural', 'transformer model', 'llm',
    'gpt', 'bert', 'stable diffusion', 'diffusion model', 'gan', 'generative adversarial'
]

# Medium-confidence keywords that may indicate AI/ML (require additional context)
MEDIUM_CONFIDENCE_AI_ML_KEYWORDS = [
    'chatbot', 'predictive analytics', 'data science', 'sentiment analysis',
    'recommendation system', 'classification model', 'regression model',
    'training data', 'model training', 'inference', 'embedding'
]

# Negative keywords that indicate non-AI content
NEGATIVE_KEYWORDS = [
    'phone launch', 'price cut', 'deal', 'offer', 'discount', 'sale',
    'customs', 'duty', 'prepaid', 'postpaid', 'banking', 'loan',
    'hdmi', 'cable', 'charger', 'battery', 'screen', 'display',
    'iphone', 'samsung', 'vivo', 'oppo', 'xiaomi', 'redmi', 'oneplus',
    'airtel', 'jio', 'vodafone', 'telecom operator', 'recharge'
]

CONFIG = {
    "navigation_timeout": 30000,
    "concurrency": 5,
    "max_links_per_site": 50,
}

BLOCKED_RESOURCES = ["image", "stylesheet", "font", "media", "other"]


def get_hostname(url: str) -> str:
    """Extract hostname from URL"""
    try:
        return urlparse(url).hostname.replace("www.", "") if urlparse(url).hostname else "unknown"
    except:
        return "unknown"


def normalize_url(url: str, base_url: str) -> str:
    """Normalize and make URL absolute"""
    try:
        return urljoin(base_url, url)
    except:
        return url


def is_ai_ml_related(text: str) -> bool:
    """
    Check if text contains AI/ML related keywords using strict filtering.

    Returns True only if:
    1. No negative keywords are present, AND
    2. At least one high-confidence keyword is present, OR
    3. At least two medium-confidence keywords are present
    """
    if not text:
        return False

    text_lower = text.lower()

    # First check for negative keywords - if found, reject immediately
    for neg_kw in NEGATIVE_KEYWORDS:
        if neg_kw in text_lower:
            return False

    # Check for high-confidence AI/ML keywords
    high_confidence_matches = 0
    for keyword in HIGH_CONFIDENCE_AI_ML_KEYWORDS:
        if keyword in text_lower:
            high_confidence_matches += 1

    # If we have at least one high-confidence match, accept it
    if high_confidence_matches > 0:
        return True

    # Check for medium-confidence keywords
    medium_confidence_matches = 0
    for keyword in MEDIUM_CONFIDENCE_AI_ML_KEYWORDS:
        if keyword in text_lower:
            medium_confidence_matches += 1

    # Require at least 2 medium-confidence matches to accept
    if medium_confidence_matches >= 2:
        return True

    return False


def normalize_hostname(hostname: str) -> str:
    """Normalize hostname"""
    return hostname.lower().replace("www.", "").lstrip(".")


def is_same_domain(host1: str, host2: str) -> bool:
    """Check if two hostnames are from the same domain"""
    h1 = normalize_hostname(host1)
    h2 = normalize_hostname(host2)
    return h1 == h2 or h1.endswith("." + h2) or h2.endswith("." + h1)


# Article detection script - finds article containers and extracts their links
# This is adapted from scraper.py's AUTO_DETECT_SCRIPT
FIND_ARTICLE_LINKS_SCRIPT = """
(baseUrl) => {
    const results = [];

    function isVisible(el) {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0 && el.offsetHeight > 0;
    }

    function getVisibleText(el) {
        return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
    }

    function isPenaltyContent(el) {
        const text = getVisibleText(el).toLowerCase();
        const role = el.getAttribute('role') || '';

        let parent = el;
        for (let i = 0; i < 3 && parent; i++) {
            const parentTag = parent.tagName?.toLowerCase();
            if (parentTag === 'nav' || parentTag === 'footer' || parentTag === 'header') return true;
            parent = parent.parentElement;
        }

        const penaltyKeywords = ['next', 'previous', 'page', 'pagination', 'copyright', 'subscribe',
            'newsletter', 'follow us', 'social', 'menu', 'navigation', 'breadcrumb', 'advertisement', 'sponsored'];
        if (penaltyKeywords.some(kw => text.includes(kw)) && text.length < 100) return true;
        if (role === 'navigation' || role === 'banner' || role === 'contentinfo') return true;
        return false;
    }

    function scoreContainer(el) {
        let score = 0;
        const tagName = el.tagName.toLowerCase();

        if (tagName === 'article') score += 4;

        const h1 = el.querySelector('h1');
        const h2 = el.querySelector('h2');
        if (h1 && getVisibleText(h1).length > 10) score += 4;
        else if (h2 && getVisibleText(h2).length > 10) score += 4;

        const h3 = el.querySelector('h3');
        const h4 = el.querySelector('h4');
        const strong = el.querySelector('strong');
        if (h3 || h4 || strong) score += 2;

        const link = el.querySelector('a[href]');
        if (link && link.href && !link.href.startsWith('javascript:')) score += 2;

        const text = getVisibleText(el);
        if (text.length > 60) score += 2;
        if (text.length > 150) score += 3;
        if (isPenaltyContent(el)) score -= 5;
        if (text.length < 30) score -= 2;

        return score;
    }

    function looksLikeDate(text) {
        if (!text || text.length < 4 || text.length > 50) return false;
        if (!/\\d/.test(text)) return false;
        const dateIndicators = [/\\d{4}/, /\\d{1,2}[\\/\\-]\\d{1,2}/,
            /\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i,
            /\\b(?:hour|day|week|month|year|ago|yesterday|today)\\b/i];
        return dateIndicators.some(p => p.test(text));
    }

    function normalizeHostname(hostname) {
        return hostname.toLowerCase().replace(/^www\\./, '');
    }

    function isSameDomain(host1, host2) {
        const h1 = normalizeHostname(host1);
        const h2 = normalizeHostname(host2);
        return h1 === h2 || h1.endsWith('.' + h2) || h2.endsWith('.' + h1);
    }

    function extractArticleMetadata(el) {
        let heading = null;
        let headingLink = null;

        // Try to find heading with link
        const linkWithHeading = el.querySelector('a h1, a h2, a h3, a h4');
        if (linkWithHeading) {
            heading = getVisibleText(linkWithHeading);
            headingLink = linkWithHeading.closest('a');
        }

        if (!heading) {
            const headingWithLink = el.querySelector('h1 a, h2 a, h3 a, h4 a');
            if (headingWithLink) {
                heading = getVisibleText(headingWithLink);
                headingLink = headingWithLink;
            }
        }

        if (!heading) {
            const h1 = el.querySelector('h1');
            const h2 = el.querySelector('h2');
            const h3 = el.querySelector('h3');
            if (h1) heading = getVisibleText(h1);
            else if (h2) heading = getVisibleText(h2);
            else if (h3) heading = getVisibleText(h3);
        }

        if (!heading) {
            const spans = el.querySelectorAll('span');
            for (const span of spans) {
                const spanText = getVisibleText(span);
                if (spanText && spanText.length >= 15 && spanText.length <= 150) {
                    if (!/^\\d{1,2}[\\s\\/\\-]|^(category|tag|by |author|posted|published|updated|read more)/i.test(spanText)) {
                        heading = spanText;
                        break;
                    }
                }
            }
        }

        // Extract date
        let date = null;
        const timeEl = el.querySelector('time[datetime]');
        if (timeEl) {
            const dtAttr = timeEl.getAttribute('datetime');
            const timeText = getVisibleText(timeEl);
            if (dtAttr && looksLikeDate(dtAttr)) date = dtAttr;
            else if (timeText && looksLikeDate(timeText)) date = timeText;
        }

        if (!date) {
            const allDatePatterns = [
                /\\d{4}-\\d{2}-\\d{2}(?:T[\\d:]+)?/,
                /\\d{1,2}\\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{4}/i,
                /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{1,2}[,.]?\\s+\\d{4}/i,
                /\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/,
                /\\d{1,2}-\\d{1,2}-\\d{2,4}/
            ];

            const fullText = getVisibleText(el);
            for (const pattern of allDatePatterns) {
                const match = fullText.match(pattern);
                if (match && looksLikeDate(match[0])) {
                    date = match[0];
                    break;
                }
            }
        }

        // Extract link
        let link = null;
        const baseHostname = normalizeHostname(new URL(baseUrl).hostname);

        if (headingLink && headingLink.href) {
            try {
                const absoluteUrl = new URL(headingLink.href, baseUrl);
                if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
                    link = absoluteUrl.href.split('#')[0];
                }
            } catch {}
        }

        if (!link) {
            const links = el.querySelectorAll('a[href]');
            for (const a of links) {
                const href = a.href;
                if (href && !href.startsWith('javascript:') && !href.startsWith('#') && !href.includes('mailto:')) {
                    try {
                        const absoluteUrl = new URL(href, baseUrl);
                        if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
                            link = absoluteUrl.href.split('#')[0];
                            break;
                        }
                    } catch {}
                }
            }
        }

        // Extract summary/subheading
        let summary = null;
        const p = el.querySelector('p');
        if (p) {
            const pText = getVisibleText(p);
            if (pText.length > 20 && pText !== heading) {
                summary = pText.substring(0, 300);
            }
        }

        return { heading, date, link, summary };
    }

    // Find article containers
    const parentSelectors = ['main', 'section', 'div'];
    const candidateGroups = [];

    for (const selector of parentSelectors) {
        const parents = document.querySelectorAll(selector);
        for (const parent of parents) {
            if (!isVisible(parent)) continue;
            const children = Array.from(parent.children);
            if (children.length < 5) continue;

            const tagGroups = {};
            for (const child of children) {
                if (!isVisible(child)) continue;
                const tag = child.tagName.toLowerCase();
                if (!tagGroups[tag]) tagGroups[tag] = [];
                tagGroups[tag].push(child);
            }

            for (const [tag, elements] of Object.entries(tagGroups)) {
                if (elements.length >= 5) {
                    let totalScore = 0;
                    const scoredElements = elements.map(el => {
                        const score = scoreContainer(el);
                        totalScore += score;
                        return { element: el, score };
                    });
                    const avgScore = totalScore / elements.length;
                    candidateGroups.push({ parent, tag, elements: scoredElements, avgScore, totalScore });
                }
            }
        }
    }

    if (candidateGroups.length > 0) {
        candidateGroups.sort((a, b) => b.avgScore - a.avgScore);
        const bestGroup = candidateGroups[0];
        for (const { element, score } of bestGroup.elements) {
            if (score > 0) {
                const metadata = extractArticleMetadata(element);
                if (metadata.heading && metadata.link) {
                    results.push(metadata);
                }
            }
        }
    }

    return results;
}
"""

# Fallback script for when auto-detection doesn't find enough articles
FALLBACK_ARTICLE_LINKS_SCRIPT = """
(baseUrl) => {
    const results = [];

    function getVisibleText(el) {
        return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
    }

    function isVisible(el) {
        const style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0 && el.offsetHeight > 0;
    }

    function looksLikeDate(text) {
        if (!text || text.length < 4 || text.length > 50) return false;
        if (!/\\d/.test(text)) return false;
        const dateIndicators = [/\\d{4}/, /\\d{1,2}[\\/\\-]\\d{1,2}/,
            /\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i];
        return dateIndicators.some(p => p.test(text));
    }

    function normalizeHostname(hostname) {
        return hostname.toLowerCase().replace(/^www\\./, '');
    }

    function isSameDomain(host1, host2) {
        const h1 = normalizeHostname(host1);
        const h2 = normalizeHostname(host2);
        return h1 === h2 || h1.endsWith('.' + h2) || h2.endsWith('.' + h1);
    }

    function extractArticleMetadata(el) {
        let heading = null;
        let headingLink = null;

        const linkWithHeading = el.querySelector('a h1, a h2, a h3, a h4');
        if (linkWithHeading) {
            heading = getVisibleText(linkWithHeading);
            headingLink = linkWithHeading.closest('a');
        }

        if (!heading) {
            const headingWithLink = el.querySelector('h1 a, h2 a, h3 a, h4 a');
            if (headingWithLink) {
                heading = getVisibleText(headingWithLink);
                headingLink = headingWithLink;
            }
        }

        if (!heading) {
            const h1 = el.querySelector('h1');
            const h2 = el.querySelector('h2');
            const h3 = el.querySelector('h3');
            if (h1) heading = getVisibleText(h1);
            else if (h2) heading = getVisibleText(h2);
            else if (h3) heading = getVisibleText(h3);
        }

        let date = null;
        const timeEl = el.querySelector('time[datetime]');
        if (timeEl) {
            const dtAttr = timeEl.getAttribute('datetime');
            if (dtAttr && looksLikeDate(dtAttr)) date = dtAttr;
        }

        let link = null;
        const baseHostname = normalizeHostname(new URL(baseUrl).hostname);

        if (headingLink && headingLink.href) {
            try {
                const absoluteUrl = new URL(headingLink.href, baseUrl);
                if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
                    link = absoluteUrl.href.split('#')[0];
                }
            } catch {}
        }

        if (!link) {
            const links = el.querySelectorAll('a[href]');
            for (const a of links) {
                const href = a.href;
                if (href && !href.startsWith('javascript:') && !href.startsWith('#') && !href.includes('mailto:')) {
                    try {
                        const absoluteUrl = new URL(href, baseUrl);
                        if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
                            link = absoluteUrl.href.split('#')[0];
                            break;
                        }
                    } catch {}
                }
            }
        }

        let summary = null;
        const p = el.querySelector('p');
        if (p) {
            const pText = getVisibleText(p);
            if (pText.length > 20 && pText !== heading) {
                summary = pText.substring(0, 300);
            }
        }

        return { heading, date, link, summary };
    }

    const fallbackSelectors = ['article', 'main article', '[role="article"]', 'section > div',
        'main > div', '.post', '.article', '.entry', 'li'];

    for (const selector of fallbackSelectors) {
        try {
            const elements = document.querySelectorAll(selector);
            const visibleElements = Array.from(elements).filter(isVisible);

            if (visibleElements.length >= 5) {
                for (const el of visibleElements) {
                    const metadata = extractArticleMetadata(el);
                    if (metadata.heading && metadata.link) {
                        results.push(metadata);
                    }
                }
                if (results.length >= 5) break;
            }
        } catch (e) {}
    }

    return results;
}
"""


async def find_ai_ml_links(page: Page, url: str) -> List[Dict]:
    """Find AI/ML related article links from a webpage"""
    site = get_hostname(url)
    ai_ml_links = []

    # Block heavy resources
    await page.route("**/*", lambda route: (
        route.abort() if route.request.resource_type in BLOCKED_RESOURCES else route.continue_()
    ))

    try:
        # Navigate to page
        await page.goto(url, timeout=CONFIG["navigation_timeout"], wait_until="domcontentloaded")

        # Wait for network idle
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        # Try to find article links using auto-detection
        article_links = await page.evaluate(FIND_ARTICLE_LINKS_SCRIPT, url)

        # If few articles found, try fallback
        if not article_links or len(article_links) < 3:
            print(f"  [{site}] Auto-detection found {len(article_links) if article_links else 0} articles, trying fallback...")
            fallback_articles = await page.evaluate(FALLBACK_ARTICLE_LINKS_SCRIPT, url)

            if fallback_articles and len(fallback_articles) > (len(article_links) if article_links else 0):
                article_links = fallback_articles
                print(f"  [{site}] Fallback found {len(article_links)} articles")

        # Filter AI/ML related article links
        seen_urls = set()

        for article_data in (article_links or []):
            link_url = article_data.get('link', '')
            heading = article_data.get('heading', '')
            summary = article_data.get('summary', '')
            date = article_data.get('date', '')

            # Skip if no link or already seen
            if not link_url or link_url in seen_urls:
                continue

            # Check if article is AI/ML related
            combined_text = f"{heading} {summary}"
            if is_ai_ml_related(combined_text):
                seen_urls.add(link_url)

                # Calculate relevance score based on keyword matches
                combined_text_lower = combined_text.lower()
                high_conf_score = sum(2 for kw in HIGH_CONFIDENCE_AI_ML_KEYWORDS if kw in combined_text_lower)
                medium_conf_score = sum(1 for kw in MEDIUM_CONFIDENCE_AI_ML_KEYWORDS if kw in combined_text_lower)
                relevance_score = high_conf_score + medium_conf_score

                ai_ml_links.append({
                    'url': link_url,
                    'text': heading.strip(),
                    'date': date.strip() if date else None,
                    'relevance_score': relevance_score,
                    'site': site
                })

                if len(ai_ml_links) >= CONFIG["max_links_per_site"]:
                    break

        # Sort by relevance score
        ai_ml_links.sort(key=lambda x: x['relevance_score'], reverse=True)

    except Exception as e:
        print(f"  [{site}] Error finding links: {e}")

    return ai_ml_links


async def process_site_for_links(context: BrowserContext, url: str, index: int, total: int) -> Dict:
    """Process a single site to find AI/ML links"""
    site = get_hostname(url)
    print(f"\n[{index + 1}/{total}] Finding AI/ML links: {site}")
    print(f"  URL: {url}")
    
    page = await context.new_page()
    links = []
    
    try:
        links = await find_ai_ml_links(page, url)
        
        if links:
            print(f"  [OK] Found {len(links)} AI/ML related links")
        else:
            print(f"  [X] No AI/ML links found")
    except Exception as e:
        print(f"  [X] Failed: {e}")
    finally:
        await page.close()
    
    return {"site": site, "source_url": url, "links": links}


async def discover_ai_ml_links(source_urls: List[str]) -> Dict:
    """Main function to discover AI/ML links from source URLs"""
    start_time = datetime.now()
    
    print("=" * 60)
    print("AI/ML Link Finder - Starting")
    print("=" * 60)
    print(f"Source URLs: {len(source_urls)}")
    print(f"Concurrency: {CONFIG['concurrency']}")
    print(f"Started at: {start_time.isoformat()}")
    print("=" * 60)
    
    all_links = []
    stats = {
        "total_sources": len(source_urls),
        "success": 0,
        "failed": 0,
        "total_links_found": 0,
        "per_site": {}
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        
        try:
            results = []
            
            # Process URLs in parallel batches
            for i in range(0, len(source_urls), CONFIG["concurrency"]):
                batch = source_urls[i:i + CONFIG["concurrency"]]
                batch_tasks = [
                    process_site_for_links(context, url, i + idx, len(source_urls))
                    for idx, url in enumerate(batch)
                ]
                
                batch_results = await asyncio.gather(*batch_tasks)
                results.extend(batch_results)
                
                # Progress update
                processed = min(i + CONFIG["concurrency"], len(source_urls))
                print(f"\n--- Progress: {processed}/{len(source_urls)} ---")
            
            # Aggregate results
            for result in results:
                site = result["site"]
                links = result["links"]
                
                if links:
                    all_links.extend(links)
                    stats["success"] += 1
                    stats["total_links_found"] += len(links)
                    stats["per_site"][site] = len(links)
                else:
                    stats["failed"] += 1
                    stats["per_site"][site] = 0
        
        finally:
            await browser.close()
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    # Create output
    output = {
        "metadata": {
            "discoveredAt": datetime.now().isoformat(),
            "totalTime": f"{total_time:.2f}s",
            "totalSources": stats["total_sources"],
            "successfulSites": stats["success"],
            "failedSites": stats["failed"],
            "totalLinksFound": stats["total_links_found"],
            "perSite": stats["per_site"],
        },
        "ai_ml_links": all_links
    }
    
    # Print summary
    print("\n" + "=" * 60)
    print("AI/ML LINK DISCOVERY COMPLETE - SUMMARY")
    print("=" * 60)
    print(f"Total time: {total_time:.2f}s")
    print(f"Total sources processed: {stats['total_sources']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed/Empty: {stats['failed']}")
    print(f"Total AI/ML links found: {stats['total_links_found']}")
    print("\nLinks per site:")
    
    for site, count in sorted(stats["per_site"].items(), key=lambda x: -x[1]):
        status = "[OK]" if count > 0 else "[X]"
        print(f"  {status} {site}: {count}")
    
    print("=" * 60)
    
    return output


async def main():
    """Run the link finder with URLs from scraper.py"""
    # Import URLs from scraper.py
    from scraper import TARGET_URLS

    # Find AI/ML related links
    result = await discover_ai_ml_links(TARGET_URLS)
    
    # Save discovered links
    output_path = "ai_ml_links.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\nAI/ML links saved to: {output_path}")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())
