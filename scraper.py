"""
Playwright-based Article Scraper (Python version)
Auto-detects article containers without relying on hard-coded class names
Uses semantic and structural signals with fallback rules
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, Page, async_playwright

# Target URLs to scrape
TARGET_URLS = [
    "https://impact.indiaai.gov.in/media-resources?tab=press",
    "https://indiaai.gov.in/articles/all",
    "https://negd.gov.in/press-release/",
    "https://cio.economictimes.indiatimes.com/news/artificial-intelligence",
    "https://www.newsonair.gov.in/category/national/",
    "https://cmogujarat.gov.in/en/news",
    "https://timesofindia.indiatimes.com/technology/artificial-intelligence",
    "https://www.hindustantimes.com/technology",
    "https://ai.economictimes.com/",
    "https://www.rswebsols.com/category/technology/",
    "https://globalvoices.org/-/topics/technology/",
    "http://analyticsindiamag.com/ai-news",
    "https://tele.net.in/category/artificial-intelligence/",
    "https://hubnetwork.in/?s=artificial+intelligence",
    "https://rajbhavan.mizoram.gov.in/?s=artificial+intelligence",
    "https://www.newindianexpress.com/search?q=artificial%20intelligence",
    "https://www.visive.ai/_/search?query=Artificial%20Intelligence",
    "https://nbbgc.org/?s=artificial+intelligence",
    "https://www.thehindu.com/sci-tech/technology/",
    "https://www.communicationstoday.co.in/?s=artificial+intelligence",
    "https://www.eletimes.ai/?s=artificial+intelligence",
    "https://www.databreachtoday.com/latest-news",
    "https://indianexpress.com/section/technology/artificial-intelligence/",
    "https://www.news18.com/tech/",
    "https://theprint.in/?s=artificial+intelligence",
    "https://www.aninews.in/search/?query=artificial+intelligence",
    "https://egov.eletsonline.com/?s=artificial%20intelligence",
]

# Configuration
CONFIG = {
    "navigation_timeout": 30000,  # 30 seconds for page navigation
    "wait_timeout": 15000,  # 15 seconds for load state
    "idle_timeout": 10000,  # 10 seconds idle wait for dynamic content
    "min_articles": 5,  # Minimum articles for valid detection
    "min_title_length": 15,  # Minimum title length to consider valid
    "concurrency": 5,  # Number of sites to process in parallel
    "max_retries": 2,  # Maximum retries for failed pages
    "retry_delay": 2000,  # Delay between retries in ms
}

# Resources to block for faster loading
BLOCKED_RESOURCES = ["image", "stylesheet", "font", "media", "other"]


def get_hostname(url: str) -> str:
    """Extract hostname from URL for site identification"""
    try:
        return urlparse(url).hostname.replace("www.", "")
    except:
        return "unknown"


def detect_country_from_domain(url: str) -> str:
    """Detect country from domain URL"""
    try:
        hostname = urlparse(url).hostname
        if not hostname:
            return "Unknown"

        hostname = hostname.lower()

        # Country-specific domain mappings
        country_domains = {
            # Indian domains
            '.gov.in': 'India',
            '.in': 'India',
            '.co.in': 'India',
            '.ac.in': 'India',
            '.edu.in': 'India',
            '.nic.in': 'India',
            # US domains
            '.gov': 'United States',
            '.us': 'United States',
            # UK domains
            '.uk': 'United Kingdom',
            '.co.uk': 'United Kingdom',
            '.gov.uk': 'United Kingdom',
            '.ac.uk': 'United Kingdom',
            # Australian domains
            '.au': 'Australia',
            '.com.au': 'Australia',
            '.gov.au': 'Australia',
            # Canadian domains
            '.ca': 'Canada',
            '.gc.ca': 'Canada',
            # Chinese domains
            '.cn': 'China',
            '.com.cn': 'China',
            # Japanese domains
            '.jp': 'Japan',
            '.co.jp': 'Japan',
            # German domains
            '.de': 'Germany',
            # French domains
            '.fr': 'France',
            # Singapore domains
            '.sg': 'Singapore',
            '.gov.sg': 'Singapore',
            # UAE domains
            '.ae': 'United Arab Emirates',
            # Saudi Arabia
            '.sa': 'Saudi Arabia',
            # European Union
            '.eu': 'European Union',
        }

        # Check for country-specific domains
        for domain_suffix, country in country_domains.items():
            if hostname.endswith(domain_suffix):
                return country

        # Check for known Indian state/regional domains
        indian_regional_keywords = [
            'india', 'gujarat', 'maharashtra', 'delhi', 'karnataka', 'tamil',
            'telangana', 'punjab', 'rajasthan', 'mizoram', 'bengal', 'kerala'
        ]
        for keyword in indian_regional_keywords:
            if keyword in hostname:
                return 'India'

        # For generic .com, .org, .net domains, try to infer from domain name
        if hostname.endswith(('.com', '.org', '.net', '.io', '.ai')):
            # Check for country indicators in domain name
            if any(keyword in hostname for keyword in ['india', 'indiaai', 'analyticsindiamag']):
                return 'India'
            if 'global' in hostname:
                return 'International'

        # Default to International for generic TLDs
        if hostname.endswith(('.com', '.org', '.net', '.io', '.ai', '.tech')):
            return 'International'

        return 'Unknown'

    except Exception:
        return 'Unknown'


def normalize_hostname(hostname: str) -> str:
    """Normalize hostname (strip www and lowercase)"""
    return hostname.lower().replace("www.", "").lstrip(".")


def is_same_domain(host1: str, host2: str) -> bool:
    """Check if two hostnames are from the same domain"""
    h1 = normalize_hostname(host1)
    h2 = normalize_hostname(host2)
    return h1 == h2 or h1.endswith("." + h2) or h2.endswith("." + h1)


# JavaScript functions to run in browser context
AUTO_DETECT_SCRIPT = """
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

    function extractMetadata(el) {
        let heading = null;
        let headingLink = null;
        let h3 = null;

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
            h3 = el.querySelector('h3');
            if (h1) heading = getVisibleText(h1);
            else if (h2) heading = getVisibleText(h2);
            else if (h3) heading = getVisibleText(h3);
        } else {
            h3 = el.querySelector('h3');
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

        if (!heading) {
            const paragraphs = el.querySelectorAll('p');
            for (const p of paragraphs) {
                const pText = getVisibleText(p);
                if (pText && pText.length >= 15 && pText.length <= 150) {
                    if (!/^(read more|click|share|comment|login|menu|subscribe)/i.test(pText)) {
                        heading = pText;
                        break;
                    }
                }
            }
        }

        if (!heading) {
            const divs = el.querySelectorAll('div');
            for (const div of divs) {
                if (div.children.length <= 1) {
                    const divText = getVisibleText(div);
                    if (divText && divText.length >= 15 && divText.length <= 150) {
                        if (!/^(read more|click|share|comment|login|menu|subscribe)/i.test(divText)) {
                            heading = divText;
                            break;
                        }
                    }
                }
            }
        }

        if (!heading) {
            const links = el.querySelectorAll('a[href]');
            for (const link of links) {
                const linkText = getVisibleText(link);
                if (linkText.length > 15) {
                    heading = linkText;
                    break;
                }
            }
        }

        let subheading = null;
        
        function isValidSubheading(text, heading) {
            if (!text) return false;
            text = text.trim();
            if (text === heading) return false;
            if (text.length < 10 || text.length > 300) return false;
            const skipWords = ['read more', 'click here', 'learn more', 'see more', 'view all', 
                'subscribe', 'newsletter', 'follow us', 'share', 'comments', 'login', 'sign in', 'register'];
            const lowerText = text.toLowerCase();
            if (skipWords.some(w => lowerText === w || lowerText.startsWith(w + ' '))) return false;
            return true;
        }

        if (h3 && isValidSubheading(getVisibleText(h3), heading)) {
            subheading = getVisibleText(h3);
        }

        if (!subheading) {
            const h4 = el.querySelector('h4');
            if (h4 && isValidSubheading(getVisibleText(h4), heading)) subheading = getVisibleText(h4);
        }

        if (!subheading) {
            const h5 = el.querySelector('h5');
            if (h5 && isValidSubheading(getVisibleText(h5), heading)) subheading = getVisibleText(h5);
        }

        if (!subheading) {
            const figcaption = el.querySelector('figcaption');
            if (figcaption && isValidSubheading(getVisibleText(figcaption), heading)) {
                subheading = getVisibleText(figcaption);
            }
        }

        if (!subheading) {
            const paragraphs = el.querySelectorAll('p');
            for (const p of paragraphs) {
                const pText = getVisibleText(p);
                if (pText && pText !== heading && pText.length >= 15 && pText.length <= 200) {
                    subheading = pText;
                    break;
                }
            }
        }

        if (!subheading) {
            const strongEl = el.querySelector('strong');
            if (strongEl && isValidSubheading(getVisibleText(strongEl), heading)) {
                subheading = getVisibleText(strongEl);
            }
        }

        if (!subheading) {
            const spans = el.querySelectorAll('span');
            for (const span of spans) {
                const spanText = getVisibleText(span);
                if (spanText && spanText !== heading && spanText.length >= 20 && spanText.length <= 200) {
                    if (!/^\\d|^(category|tag|by|author|posted|published)/i.test(spanText)) {
                        subheading = spanText;
                        break;
                    }
                }
            }
        }

        let date = null;
        const timeEl = el.querySelector('time[datetime]');
        if (timeEl) {
            const dtAttr = timeEl.getAttribute('datetime');
            const timeText = getVisibleText(timeEl);
            if (dtAttr && looksLikeDate(dtAttr)) date = dtAttr;
            else if (timeText && looksLikeDate(timeText)) date = timeText;
        }

        if (!date) {
            const timeElNoAttr = el.querySelector('time');
            if (timeElNoAttr) {
                const timeText = getVisibleText(timeElNoAttr);
                if (looksLikeDate(timeText)) date = timeText;
            }
        }

        const allDatePatterns = [
            /\\d{4}-\\d{2}-\\d{2}(?:T[\\d:]+)?/,
            /\\d{1,2}\\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{4}/i,
            /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{1,2}[,.]?\\s+\\d{4}/i,
            /\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/,
            /\\d{1,2}-\\d{1,2}-\\d{2,4}/,
            /\\d{1,2}\\.\\d{1,2}\\.\\d{2,4}/,
            /\\d+\\s+(?:second|minute|hour|day|week|month|year)s?\\s+ago/i,
            /(?:yesterday|today|just\\s+now)/i
        ];

        if (!date) {
            const spans = el.querySelectorAll('span');
            for (const span of spans) {
                const spanText = getVisibleText(span);
                if (spanText && spanText.length < 60) {
                    for (const pattern of allDatePatterns) {
                        const match = spanText.match(pattern);
                        if (match && looksLikeDate(match[0])) {
                            date = match[0];
                            break;
                        }
                    }
                    if (date) break;
                }
            }
        }

        if (!date) {
            const divs = el.querySelectorAll('div');
            for (const div of divs) {
                if (div.children.length <= 1) {
                    const divText = getVisibleText(div);
                    if (divText && divText.length < 60) {
                        for (const pattern of allDatePatterns) {
                            const match = divText.match(pattern);
                            if (match && looksLikeDate(match[0])) {
                                date = match[0];
                                break;
                            }
                        }
                        if (date) break;
                    }
                }
            }
        }

        if (!date) {
            const fullText = getVisibleText(el);
            for (const pattern of allDatePatterns) {
                const match = fullText.match(pattern);
                if (match && looksLikeDate(match[0])) {
                    date = match[0];
                    break;
                }
            }
        }

        let link = null;
        const baseHostname = normalizeHostname(new URL(baseUrl).hostname);

        if (headingLink && headingLink.href) {
            try {
                const absoluteUrl = new URL(headingLink.href, baseUrl);
                if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
                    link = absoluteUrl.href;
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
                            link = absoluteUrl.href;
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

        return { heading, subheading, date, link, summary };
    }

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
                const metadata = extractMetadata(element);
                if (metadata.heading || metadata.link) {
                    results.push(metadata);
                }
            }
        }
    }

    return results;
}
"""

FALLBACK_SCRIPT = """
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

    function extractMetadata(el) {
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

        if (!heading) {
            const links = el.querySelectorAll('a[href]');
            for (const link of links) {
                const linkText = getVisibleText(link);
                if (linkText.length > 15) {
                    heading = linkText;
                    break;
                }
            }
        }

        let subheading = null;
        function isValidSubheading(text, heading) {
            if (!text) return false;
            text = text.trim();
            if (text === heading) return false;
            if (text.length < 10 || text.length > 300) return false;
            const skipWords = ['read more', 'click here', 'learn more', 'see more', 'view all'];
            const lowerText = text.toLowerCase();
            if (skipWords.some(w => lowerText === w || lowerText.startsWith(w + ' '))) return false;
            return true;
        }

        const h3Fall = el.querySelector('h3');
        if (h3Fall && isValidSubheading(getVisibleText(h3Fall), heading)) {
            subheading = getVisibleText(h3Fall);
        }

        if (!subheading) {
            const paragraphs = el.querySelectorAll('p');
            for (const p of paragraphs) {
                const pText = getVisibleText(p);
                if (pText && pText !== heading && pText.length >= 15 && pText.length <= 200) {
                    subheading = pText;
                    break;
                }
            }
        }

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
                /\\d+\\s+(?:second|minute|hour|day|week|month|year)s?\\s+ago/i
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

        let link = null;
        const baseHostname = normalizeHostname(new URL(baseUrl).hostname);

        if (headingLink && headingLink.href) {
            try {
                const absoluteUrl = new URL(headingLink.href, baseUrl);
                if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
                    link = absoluteUrl.href;
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
                            link = absoluteUrl.href;
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

        return { heading, subheading, date, link, summary };
    }

    const fallbackSelectors = ['article', 'main article', '[role="article"]', 'section > div', 
        'main > div', '.post', '.article', '.entry', 'li'];

    for (const selector of fallbackSelectors) {
        try {
            const elements = document.querySelectorAll(selector);
            const visibleElements = Array.from(elements).filter(isVisible);

            if (visibleElements.length >= 5) {
                for (const el of visibleElements) {
                    const metadata = extractMetadata(el);
                    if (metadata.heading || metadata.link) {
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

SCROLL_SCRIPT = """
async () => {
    const scrollStep = 500;
    const maxScrolls = 3;
    for (let i = 0; i < maxScrolls; i++) {
        window.scrollBy(0, scrollStep);
        await new Promise(r => setTimeout(r, 300));
    }
    window.scrollTo(0, 0);
}
"""

AGGRESSIVE_SCROLL_SCRIPT = """
async () => {
    for (let i = 0; i < 5; i++) {
        window.scrollBy(0, window.innerHeight);
        await new Promise(r => setTimeout(r, 400));
    }
}
"""


async def scrape_articles(page: Page, url: str, retry_count: int = 0) -> List[Dict]:
    """Main scraping function for a single URL"""
    site = get_hostname(url)
    articles = []

    # Block heavy resources
    await page.route("**/*", lambda route: (
        route.abort() if route.request.resource_type in BLOCKED_RESOURCES else route.continue_()
    ))

    try:
        # Navigate to page
        await page.goto(url, timeout=CONFIG["navigation_timeout"], wait_until="domcontentloaded")

        # Wait for network idle
        try:
            await page.wait_for_load_state("networkidle", timeout=CONFIG["idle_timeout"])
        except:
            pass  # Network didn't become idle, continue anyway

        # Scroll to trigger lazy loading
        await page.evaluate(SCROLL_SCRIPT)
        await page.wait_for_timeout(1500)

        # Try auto-detection first
        raw_articles = await page.evaluate(AUTO_DETECT_SCRIPT, url)

        # If few articles, try scrolling more aggressively
        if not raw_articles or len(raw_articles) < 3:
            await page.evaluate(AGGRESSIVE_SCROLL_SCRIPT)
            await page.wait_for_timeout(1000)
            raw_articles = await page.evaluate(AUTO_DETECT_SCRIPT, url)

        # If auto-detection failed, try fallback
        if not raw_articles or len(raw_articles) < CONFIG["min_articles"]:
            print(f"  [{site}] Auto-detection found {len(raw_articles) if raw_articles else 0} articles, trying fallback...")
            fallback_articles = await page.evaluate(FALLBACK_SCRIPT, url)

            if fallback_articles and len(fallback_articles) > (len(raw_articles) if raw_articles else 0):
                raw_articles = fallback_articles
                print(f"  [{site}] Fallback found {len(raw_articles)} articles")

        # Process and filter articles
        seen_urls: Set[str] = set()

        for article in (raw_articles or []):
            if not article.get("link") or not article.get("heading"):
                continue

            heading = article["heading"]
            if len(heading) < CONFIG["min_title_length"]:
                continue

            link = article["link"]
            if link in seen_urls:
                continue
            seen_urls.add(link)

            articles.append({
                "site": site,
                "heading": heading.strip(),
                "subheading": (article.get("subheading") or "").strip() or None,
                "date": (article.get("date") or "").strip() or None,
                "link": link,
                "summary": (article.get("summary") or "").strip() or None,
            })

    except Exception as e:
        # Retry logic
        if retry_count < CONFIG["max_retries"]:
            print(f"  [{site}] Retrying ({retry_count + 1}/{CONFIG['max_retries']})...")
            await asyncio.sleep(CONFIG["retry_delay"] / 1000)
            return await scrape_articles(page, url, retry_count + 1)
        print(f"  [{site}] Error: {e}")

    return articles


async def process_site(context: BrowserContext, url: str, index: int, total: int) -> Dict:
    """Process a single site (for parallel execution)"""
    site = get_hostname(url)
    print(f"\n[{index + 1}/{total}] Scraping: {site}")
    print(f"  URL: {url}")

    page = await context.new_page()
    articles = []

    try:
        articles = await scrape_articles(page, url)

        if articles:
            print(f"  [OK] Found {len(articles)} articles")
        else:
            print(f"  [X] No valid articles found")
    except Exception as e:
        print(f"  [X] Failed: {e}")
    finally:
        await page.close()

    return {"site": site, "articles": articles, "url": url}


async def main():
    """Main execution function with parallel processing"""
    start_time = datetime.now()

    print("=" * 60)
    print("Playwright Article Scraper (Python) - Starting")
    print("=" * 60)
    print(f"Target URLs: {len(TARGET_URLS)}")
    print(f"Concurrency: {CONFIG['concurrency']} sites in parallel")
    print(f"Started at: {start_time.isoformat()}")
    print("=" * 60)

    all_articles = []
    stats = {
        "total": len(TARGET_URLS),
        "success": 0,
        "failed": 0,
        "per_site": {},
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )

        try:
            results = []

            # Process URLs in parallel batches
            for i in range(0, len(TARGET_URLS), CONFIG["concurrency"]):
                batch = TARGET_URLS[i:i + CONFIG["concurrency"]]
                batch_tasks = [
                    process_site(context, url, i + idx, len(TARGET_URLS))
                    for idx, url in enumerate(batch)
                ]

                batch_results = await asyncio.gather(*batch_tasks)
                results.extend(batch_results)

                # Progress update
                processed = min(i + CONFIG["concurrency"], len(TARGET_URLS))
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = processed / elapsed if elapsed > 0 else 1
                remaining = (len(TARGET_URLS) - processed) / rate if rate > 0 else 0
                print(f"\n--- Progress: {processed}/{len(TARGET_URLS)} ({int(remaining)}s remaining) ---")

            # Aggregate results
            for result in results:
                site = result["site"]
                articles = result["articles"]

                if articles:
                    all_articles.extend(articles)
                    stats["success"] += 1
                    stats["per_site"][site] = stats["per_site"].get(site, 0) + len(articles)
                else:
                    stats["failed"] += 1
                    stats["per_site"][site] = stats["per_site"].get(site, 0)

        finally:
            await browser.close()

    total_time = (datetime.now() - start_time).total_seconds()

    # Create output with metadata
    output = {
        "metadata": {
            "scrapedAt": datetime.now().isoformat(),
            "totalTime": f"{total_time:.2f}s",
            "totalUrls": stats["total"],
            "successfulSites": stats["success"],
            "failedSites": stats["failed"],
            "totalArticles": len(all_articles),
            "perSite": stats["per_site"],
        },
        "articles": all_articles,
    }

    # Write results to JSON file
    output_path = "results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE - SUMMARY")
    print("=" * 60)
    print(f"Finished at: {datetime.now().isoformat()}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Total URLs processed: {stats['total']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed/Empty: {stats['failed']}")
    print(f"Total articles scraped: {len(all_articles)}")
    print("\nArticles per site:")

    for site, count in sorted(stats["per_site"].items(), key=lambda x: -x[1]):
        status = "[OK]" if count > 0 else "[X]"
        print(f"  {status} {site}: {count}")

    print(f"\nResults saved to: {output_path}")
    print("=" * 60)

    return all_articles


async def scrape_article_content(page: Page, url: str) -> Dict:
    """Scrape full article content (heading, date, and paragraphs) from a single article URL"""
    try:
        # Block heavy resources
        await page.route("**/*", lambda route: (
            route.abort() if route.request.resource_type in BLOCKED_RESOURCES else route.continue_()
        ))

        await page.goto(url, timeout=CONFIG["navigation_timeout"], wait_until="domcontentloaded")

        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass

        # Extract article content including date
        article_data = await page.evaluate("""
            () => {
                function getVisibleText(el) {
                    return (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                }

                function looksLikeDate(text) {
                    if (!text || text.length < 4 || text.length > 50) return false;
                    if (!/\\d/.test(text)) return false;
                    const dateIndicators = [/\\d{4}/, /\\d{1,2}[\\/\\-]\\d{1,2}/,
                        /\\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i,
                        /\\b(?:hour|day|week|month|year|ago|yesterday|today)\\b/i];
                    return dateIndicators.some(p => p.test(text));
                }

                // Find main heading
                let heading = '';
                const h1 = document.querySelector('h1');
                if (h1) {
                    heading = getVisibleText(h1);
                }

                // Find publication date
                let date = null;

                // Try <time> element with datetime attribute first
                const timeEl = document.querySelector('time[datetime]');
                if (timeEl) {
                    const dtAttr = timeEl.getAttribute('datetime');
                    const timeText = getVisibleText(timeEl);
                    if (dtAttr && looksLikeDate(dtAttr)) date = dtAttr;
                    else if (timeText && looksLikeDate(timeText)) date = timeText;
                }

                // Try <time> element without datetime attribute
                if (!date) {
                    const timeElNoAttr = document.querySelector('time');
                    if (timeElNoAttr) {
                        const timeText = getVisibleText(timeElNoAttr);
                        if (looksLikeDate(timeText)) date = timeText;
                    }
                }

                // Try common date patterns in the document
                if (!date) {
                    const allDatePatterns = [
                        /\\d{4}-\\d{2}-\\d{2}(?:T[\\d:]+)?/,
                        /\\d{1,2}\\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{4}/i,
                        /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{1,2}[,.]?\\s+\\d{4}/i,
                        /\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/,
                        /\\d{1,2}-\\d{1,2}-\\d{2,4}/,
                        /\\d{1,2}\\.\\d{1,2}\\.\\d{2,4}/,
                        /\\d+\\s+(?:second|minute|hour|day|week|month|year)s?\\s+ago/i,
                        /(?:yesterday|today|just\\s+now)/i
                    ];

                    // Try to find date in common containers first
                    const dateContainers = document.querySelectorAll('span, div, p');
                    for (const container of dateContainers) {
                        if (container.children.length <= 1) {
                            const containerText = getVisibleText(container);
                            if (containerText && containerText.length < 60) {
                                for (const pattern of allDatePatterns) {
                                    const match = containerText.match(pattern);
                                    if (match && looksLikeDate(match[0])) {
                                        date = match[0];
                                        break;
                                    }
                                }
                                if (date) break;
                            }
                        }
                    }
                }

                // Last resort: search entire article body
                if (!date) {
                    const articleSelectors = ['article', 'main', '[role="main"]', '.article-content', '.post-content'];
                    let articleBody = null;
                    for (const selector of articleSelectors) {
                        articleBody = document.querySelector(selector);
                        if (articleBody) break;
                    }

                    if (articleBody) {
                        const bodyText = getVisibleText(articleBody);
                        const allDatePatterns = [
                            /\\d{4}-\\d{2}-\\d{2}(?:T[\\d:]+)?/,
                            /\\d{1,2}\\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{4}/i,
                            /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\\s+\\d{1,2}[,.]?\\s+\\d{4}/i,
                            /\\d{1,2}\\/\\d{1,2}\\/\\d{2,4}/,
                            /\\d+\\s+(?:second|minute|hour|day|week|month|year)s?\\s+ago/i
                        ];

                        for (const pattern of allDatePatterns) {
                            const match = bodyText.match(pattern);
                            if (match && looksLikeDate(match[0])) {
                                date = match[0];
                                break;
                            }
                        }
                    }
                }

                // Find article body and collect all paragraphs
                let paragraphs = [];
                const articleSelectors = ['article', 'main', '[role="main"]', '.article-content', '.post-content', '.entry-content'];

                let articleBody = null;
                for (const selector of articleSelectors) {
                    articleBody = document.querySelector(selector);
                    if (articleBody) break;
                }

                if (!articleBody) {
                    articleBody = document.body;
                }

                // Get all paragraphs
                const pElements = articleBody.querySelectorAll('p');
                for (const p of pElements) {
                    const text = getVisibleText(p);
                    if (text && text.length > 30) {
                        paragraphs.push(text);
                    }
                }

                // Combine all paragraphs
                const fullContent = paragraphs.join(' ');

                return {
                    heading: heading,
                    date: date,
                    content: fullContent,
                    paragraphCount: paragraphs.length
                };
            }
        """)

        return {
            'url': url,
            'heading': article_data.get('heading', ''),
            'date': article_data.get('date', ''),
            'content': article_data.get('content', ''),
            'country': detect_country_from_domain(url),
            'paragraphCount': article_data.get('paragraphCount', 0),
            'scraped': True
        }

    except Exception as e:
        return {
            'url': url,
            'heading': '',
            'date': '',
            'content': '',
            'country': detect_country_from_domain(url),
            'error': str(e),
            'scraped': False
        }


async def scrape_from_links(links: List[str]) -> Dict:
    """Scrape article content from a list of AI/ML related links"""
    start_time = datetime.now()
    
    print("=" * 60)
    print("Scraping AI/ML Articles from Links")
    print("=" * 60)
    print(f"Total links to scrape: {len(links)}")
    print(f"Concurrency: {CONFIG['concurrency']}")
    print(f"Started at: {start_time.isoformat()}")
    print("=" * 60)
    
    all_articles = []
    stats = {
        "total_links": len(links),
        "success": 0,
        "failed": 0,
    }
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        
        try:
            # Process links in batches
            for i in range(0, len(links), CONFIG["concurrency"]):
                batch = links[i:i + CONFIG["concurrency"]]
                batch_tasks = []
                
                for idx, url in enumerate(batch):
                    page = await context.new_page()
                    
                    async def scrape_wrapper(p, u):
                        try:
                            result = await scrape_article_content(p, u)
                            return result
                        finally:
                            await p.close()
                    
                    batch_tasks.append(scrape_wrapper(page, url))
                
                batch_results = await asyncio.gather(*batch_tasks)
                
                for result in batch_results:
                    if result.get('scraped'):
                        all_articles.append(result)
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                
                # Progress update
                processed = min(i + CONFIG["concurrency"], len(links))
                print(f"Progress: {processed}/{len(links)} articles scraped")
        
        finally:
            await browser.close()
    
    total_time = (datetime.now() - start_time).total_seconds()
    
    # Create output
    output = {
        "metadata": {
            "scrapedAt": datetime.now().isoformat(),
            "totalTime": f"{total_time:.2f}s",
            "totalLinks": stats["total_links"],
            "successfulScrapes": stats["success"],
            "failedScrapes": stats["failed"],
        },
        "articles": all_articles
    }
    
    # Print summary
    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE - SUMMARY")
    print("=" * 60)
    print(f"Total time: {total_time:.2f}s")
    print(f"Total links: {stats['total_links']}")
    print(f"Successful: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print("=" * 60)
    
    return output


if __name__ == "__main__":
    asyncio.run(main())
