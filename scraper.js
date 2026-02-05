/**
 * Playwright-based Article Scraper
 * Auto-detects article containers without relying on hard-coded class names
 * Uses semantic and structural signals with fallback rules
 */

const { chromium } = require("playwright");
const fs = require("fs");

// Target URLs to scrape
const TARGET_URLS = [
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
];

// Configuration
const CONFIG = {
  navigationTimeout: 30000, // 30 seconds for page navigation
  waitTimeout: 15000, // 15 seconds for load state
  idleTimeout: 10000, // 10 seconds idle wait for dynamic content
  minArticles: 5, // Minimum articles for valid detection
  minTitleLength: 15, // Minimum title length to consider valid
  concurrency: 5, // Number of sites to process in parallel
  maxRetries: 2, // Maximum retries for failed pages
  retryDelay: 2000, // Delay between retries in ms
};

// Resources to block for faster loading
const BLOCKED_RESOURCES = ["image", "stylesheet", "font", "media", "other"];

/**
 * Extract hostname from URL for site identification
 */
function getHostname(url) {
  try {
    return new URL(url).hostname.replace("www.", "");
  } catch {
    return "unknown";
  }
}

/**
 * Auto-detect article containers using semantic and structural heuristics
 * Runs inside page.evaluate() context
 */
function autoDetectArticles(baseUrl) {
  const results = [];

  // Helper: Check if element is visible
  function isVisible(el) {
    const style = window.getComputedStyle(el);
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      el.offsetWidth > 0 &&
      el.offsetHeight > 0
    );
  }

  // Helper: Get visible text content
  function getVisibleText(el) {
    return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
  }

  // Helper: Check for navigation/footer/pagination indicators
  function isPenaltyContent(el) {
    const text = getVisibleText(el).toLowerCase();
    const tagName = el.tagName.toLowerCase();
    const role = el.getAttribute("role") || "";

    // Check parent chain for nav/footer
    let parent = el;
    for (let i = 0; i < 3 && parent; i++) {
      const parentTag = parent.tagName?.toLowerCase();
      if (
        parentTag === "nav" ||
        parentTag === "footer" ||
        parentTag === "header"
      ) {
        return true;
      }
      parent = parent.parentElement;
    }

    // Check for pagination/navigation keywords
    const penaltyKeywords = [
      "next",
      "previous",
      "page",
      "pagination",
      "copyright",
      "subscribe",
      "newsletter",
      "follow us",
      "social",
      "menu",
      "navigation",
      "breadcrumb",
      "advertisement",
      "sponsored",
    ];
    if (penaltyKeywords.some((kw) => text.includes(kw)) && text.length < 100) {
      return true;
    }

    if (role === "navigation" || role === "banner" || role === "contentinfo") {
      return true;
    }

    return false;
  }

  // Helper: Score a candidate article container
  function scoreContainer(el) {
    let score = 0;
    const tagName = el.tagName.toLowerCase();

    // Bonus for article tag
    if (tagName === "article") score += 4;

    // Check for main heading (h1 or h2)
    const h1 = el.querySelector("h1");
    const h2 = el.querySelector("h2");
    if (h1 && getVisibleText(h1).length > 10) score += 4;
    else if (h2 && getVisibleText(h2).length > 10) score += 4;

    // Check for subheading
    const h3 = el.querySelector("h3");
    const h4 = el.querySelector("h4");
    const strong = el.querySelector("strong");
    if (h3 || h4 || strong) score += 2;

    // Check for link
    const link = el.querySelector("a[href]");
    if (link && link.href && !link.href.startsWith("javascript:")) score += 2;

    // Text length bonuses
    const text = getVisibleText(el);
    if (text.length > 60) score += 2;
    if (text.length > 150) score += 3;

    // Penalty for nav/footer/pagination content
    if (isPenaltyContent(el)) score -= 5;

    // Penalty for very short content
    if (text.length < 30) score -= 2;

    return score;
  }

  // Helper: Extract metadata from a container
  function extractMetadata(el) {
    // Main heading: Check multiple patterns
    // Pattern 1: a > h (link wrapping heading) - very common pattern
    // Pattern 2: h > a (heading containing link)
    // Pattern 3: standalone h tags
    // Pattern 4: a tags with substantial heading-like text
    let heading = null;
    let headingLink = null; // Track if heading came from a link

    // Declare h3 at function scope so it can be reused for subheading
    let h3 = null;

    // First check for links containing h1/h2/h3 (a > h pattern)
    const linkWithHeading = el.querySelector("a h1, a h2, a h3, a h4");
    if (linkWithHeading) {
      heading = getVisibleText(linkWithHeading);
      headingLink = linkWithHeading.closest("a");
    }

    // Then check for headings containing links (h > a pattern)
    if (!heading) {
      const headingWithLink = el.querySelector("h1 a, h2 a, h3 a, h4 a");
      if (headingWithLink) {
        heading = getVisibleText(headingWithLink);
        headingLink = headingWithLink;
      }
    }

    // Then check standalone h tags
    if (!heading) {
      const h1 = el.querySelector("h1");
      const h2 = el.querySelector("h2");
      h3 = el.querySelector("h3");

      if (h1) heading = getVisibleText(h1);
      else if (h2) heading = getVisibleText(h2);
      else if (h3) heading = getVisibleText(h3);
    } else {
      // Still query h3 for potential subheading use
      h3 = el.querySelector("h3");
    }

    // If no heading tags, try span with heading-like text (15-150 chars, no long paragraphs)
    if (!heading) {
      const spans = el.querySelectorAll("span");
      for (const span of spans) {
        const spanText = getVisibleText(span);
        if (spanText && spanText.length >= 15 && spanText.length <= 150) {
          // Skip date-like or category-like text
          if (
            !/^\d{1,2}[\s\/\-]|^(category|tag|by |author|posted|published|updated|read more)/i.test(
              spanText,
            )
          ) {
            heading = spanText;
            break;
          }
        }
      }
    }

    // Try p tag with heading-like text
    if (!heading) {
      const paragraphs = el.querySelectorAll("p");
      for (const p of paragraphs) {
        const pText = getVisibleText(p);
        if (pText && pText.length >= 15 && pText.length <= 150) {
          if (
            !/^(read more|click|share|comment|login|menu|subscribe)/i.test(
              pText,
            )
          ) {
            heading = pText;
            break;
          }
        }
      }
    }

    // Try div with heading-like text
    if (!heading) {
      const divs = el.querySelectorAll("div");
      for (const div of divs) {
        if (div.children.length <= 1) {
          const divText = getVisibleText(div);
          if (divText && divText.length >= 15 && divText.length <= 150) {
            if (
              !/^(read more|click|share|comment|login|menu|subscribe)/i.test(
                divText,
              )
            ) {
              heading = divText;
              break;
            }
          }
        }
      }
    }

    // Finally, try the first link with substantial text
    if (!heading) {
      const links = el.querySelectorAll("a[href]");
      for (const link of links) {
        const linkText = getVisibleText(link);
        if (linkText.length > 15) {
          heading = linkText;
          break;
        }
      }
    }

    // Subheading: Try multiple sources - h3, h4, h5, p (first short paragraph), figcaption, div with short text, strong, em, span
    let subheading = null;

    // Helper to check if text is valid subheading
    function isValidSubheading(text, heading) {
      if (!text) return false;
      text = text.trim();
      // Must be different from heading
      if (text === heading) return false;
      // Must be reasonable length (10-300 chars)
      if (text.length < 10 || text.length > 300) return false;
      // Avoid navigation/menu text
      const skipWords = [
        "read more",
        "click here",
        "learn more",
        "see more",
        "view all",
        "subscribe",
        "newsletter",
        "follow us",
        "share",
        "comments",
        "login",
        "sign in",
        "register",
      ];
      const lowerText = text.toLowerCase();
      if (
        skipWords.some((w) => lowerText === w || lowerText.startsWith(w + " "))
      )
        return false;
      return true;
    }

    // Try h3 first (if not already used as heading)
    // Note: h3 was already queried above, reuse if exists
    if (h3 && isValidSubheading(getVisibleText(h3), heading)) {
      subheading = getVisibleText(h3);
    }

    // Try h4
    if (!subheading) {
      const h4 = el.querySelector("h4");
      if (h4 && isValidSubheading(getVisibleText(h4), heading)) {
        subheading = getVisibleText(h4);
      }
    }

    // Try h5
    if (!subheading) {
      const h5 = el.querySelector("h5");
      if (h5 && isValidSubheading(getVisibleText(h5), heading)) {
        subheading = getVisibleText(h5);
      }
    }

    // Try figcaption (common for image-based articles)
    if (!subheading) {
      const figcaption = el.querySelector("figcaption");
      if (
        figcaption &&
        isValidSubheading(getVisibleText(figcaption), heading)
      ) {
        subheading = getVisibleText(figcaption);
      }
    }

    // Try first short paragraph (often used as description/excerpt)
    if (!subheading) {
      const paragraphs = el.querySelectorAll("p");
      for (const p of paragraphs) {
        const pText = getVisibleText(p);
        // Look for short paragraphs that might be descriptions (under 200 chars)
        if (
          pText &&
          pText !== heading &&
          pText.length >= 15 &&
          pText.length <= 200
        ) {
          subheading = pText;
          break;
        }
      }
    }

    // Try strong element
    if (!subheading) {
      const strongEl = el.querySelector("strong");
      if (strongEl && isValidSubheading(getVisibleText(strongEl), heading)) {
        subheading = getVisibleText(strongEl);
      }
    }

    // Try em element
    if (!subheading) {
      const emEl = el.querySelector("em");
      if (emEl && isValidSubheading(getVisibleText(emEl), heading)) {
        subheading = getVisibleText(emEl);
      }
    }

    // Try small element
    if (!subheading) {
      const smallEl = el.querySelector("small");
      if (smallEl && isValidSubheading(getVisibleText(smallEl), heading)) {
        subheading = getVisibleText(smallEl);
      }
    }

    // Try cite element (author attribution)
    if (!subheading) {
      const citeEl = el.querySelector("cite");
      if (citeEl && isValidSubheading(getVisibleText(citeEl), heading)) {
        subheading = getVisibleText(citeEl);
      }
    }

    // Try blockquote (sometimes used for excerpts)
    if (!subheading) {
      const blockquote = el.querySelector("blockquote");
      if (blockquote) {
        const bqText = getVisibleText(blockquote);
        if (
          bqText &&
          bqText !== heading &&
          bqText.length >= 15 &&
          bqText.length <= 250
        ) {
          subheading = bqText;
        }
      }
    }

    // Try span with substantial text
    if (!subheading) {
      const spans = el.querySelectorAll("span");
      for (const span of spans) {
        const spanText = getVisibleText(span);
        // Look for spans with description-like text (20-200 chars)
        if (
          spanText &&
          spanText !== heading &&
          spanText.length >= 20 &&
          spanText.length <= 200
        ) {
          // Skip if it looks like a date or category label
          if (
            !/^\d|^(category|tag|by|author|posted|published)/i.test(spanText)
          ) {
            subheading = spanText;
            break;
          }
        }
      }
    }

    // Try div with short descriptive text (last resort)
    if (!subheading) {
      const divs = el.querySelectorAll("div");
      for (const div of divs) {
        // Only consider divs that don't have many child elements (likely text containers)
        if (div.children.length <= 2) {
          const divText = getVisibleText(div);
          if (
            divText &&
            divText !== heading &&
            divText.length >= 20 &&
            divText.length <= 200
          ) {
            // Skip if it looks like navigation or metadata
            if (!/^(read more|click|share|comment|login|menu)/i.test(divText)) {
              subheading = divText;
              break;
            }
          }
        }
      }
    }

    // Publication date
    let date = null;

    // Date validation helper - ensure extracted text looks like a real date
    function looksLikeDate(text) {
      if (!text || text.length < 4 || text.length > 50) return false;
      // Must contain a digit
      if (!/\d/.test(text)) return false;
      // Must match at least one date-like pattern
      const dateIndicators = [
        /\d{4}/, // Year
        /\d{1,2}[\/\-]\d{1,2}/, // Numeric date
        /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i, // Month name
        /\b(?:hour|day|week|month|year|ago|yesterday|today)\b/i, // Relative time
      ];
      return dateIndicators.some((p) => p.test(text));
    }

    // Try <time datetime> first
    const timeEl = el.querySelector("time[datetime]");
    if (timeEl) {
      const dtAttr = timeEl.getAttribute("datetime");
      const timeText = getVisibleText(timeEl);
      if (dtAttr && looksLikeDate(dtAttr)) {
        date = dtAttr;
      } else if (timeText && looksLikeDate(timeText)) {
        date = timeText;
      }
    }

    // Try <time> without datetime attribute
    if (!date) {
      const timeElNoAttr = el.querySelector("time");
      if (timeElNoAttr) {
        const timeText = getVisibleText(timeElNoAttr);
        if (looksLikeDate(timeText)) {
          date = timeText;
        }
      }
    }

    // Extended date patterns including relative time
    const allDatePatterns = [
      /\d{4}-\d{2}-\d{2}(?:T[\d:]+)?/, // ISO date with optional time
      /\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\s+\d{4}/i, // DD Month YYYY
      /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\s+\d{1,2}[,.]?\s+\d{4}/i, // Month DD, YYYY
      /\d{1,2}\/\d{1,2}\/\d{2,4}/, // DD/MM/YYYY or MM/DD/YYYY
      /\d{1,2}-\d{1,2}-\d{2,4}/, // DD-MM-YYYY
      /\d{1,2}\.\d{1,2}\.\d{2,4}/, // DD.MM.YYYY
      /(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[,.]?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}/i,
      /\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago/i, // X time ago
      /(?:yesterday|today|just\s+now)/i, // Relative keywords
      /(?:posted|published|updated)[:\s]+.{5,25}/i, // Posted: date
    ];

    // Try spans that look like dates
    if (!date) {
      const spans = el.querySelectorAll("span");
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

    // Try divs that look like dates
    if (!date) {
      const divs = el.querySelectorAll("div");
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

    // Try to find date patterns in full text
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

    // Helper to normalize hostname (strip www and lowercase)
    function normalizeHostname(hostname) {
      return hostname.toLowerCase().replace(/^www\./, "");
    }

    // Helper to check if two hostnames are from the same domain
    function isSameDomain(host1, host2) {
      const h1 = normalizeHostname(host1);
      const h2 = normalizeHostname(host2);
      return h1 === h2 || h1.endsWith("." + h2) || h2.endsWith("." + h1);
    }

    // Article link: first valid <a href> from same domain only
    // If heading came from a link, prefer that link
    let link = null;
    const baseHostname = normalizeHostname(new URL(baseUrl).hostname);

    // First, check if heading came from a link (prioritize heading link)
    if (headingLink && headingLink.href) {
      try {
        const absoluteUrl = new URL(headingLink.href, baseUrl);
        if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
          link = absoluteUrl.href;
        }
      } catch {
        // Ignore parsing errors
      }
    }

    // If no link from heading, find first valid link
    if (!link) {
      const links = el.querySelectorAll("a[href]");
      for (const a of links) {
        const href = a.href;
        if (
          href &&
          !href.startsWith("javascript:") &&
          !href.startsWith("#") &&
          !href.includes("mailto:")
        ) {
          try {
            const absoluteUrl = new URL(href, baseUrl);
            if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
              link = absoluteUrl.href;
              break;
            }
          } catch {
            // If URL parsing fails, skip this link
          }
        }
      }
    }

    // Summary: first paragraph text
    let summary = null;
    const p = el.querySelector("p");
    if (p) {
      const pText = getVisibleText(p);
      if (pText.length > 20 && pText !== heading) {
        summary = pText.substring(0, 300); // Limit summary length
      }
    }

    return { heading, subheading, date, link, summary };
  }

  // Candidate parent elements to scan
  const parentSelectors = ["main", "section", "div"];
  const candidateGroups = [];

  for (const selector of parentSelectors) {
    const parents = document.querySelectorAll(selector);

    for (const parent of parents) {
      if (!isVisible(parent)) continue;

      // Get direct children
      const children = Array.from(parent.children);
      if (children.length < 5) continue;

      // Group children by tag name
      const tagGroups = {};
      for (const child of children) {
        if (!isVisible(child)) continue;
        const tag = child.tagName.toLowerCase();
        if (!tagGroups[tag]) tagGroups[tag] = [];
        tagGroups[tag].push(child);
      }

      // Find groups with 5+ elements of same tag
      for (const [tag, elements] of Object.entries(tagGroups)) {
        if (elements.length >= 5) {
          // Score each element in the group
          let totalScore = 0;
          const scoredElements = elements.map((el) => {
            const score = scoreContainer(el);
            totalScore += score;
            return { element: el, score };
          });

          // Average score for the group
          const avgScore = totalScore / elements.length;

          candidateGroups.push({
            parent,
            tag,
            elements: scoredElements,
            avgScore,
            totalScore,
          });
        }
      }
    }
  }

  // Select highest-scoring group
  if (candidateGroups.length > 0) {
    candidateGroups.sort((a, b) => b.avgScore - a.avgScore);
    const bestGroup = candidateGroups[0];

    // Extract metadata from each element in the best group
    for (const { element, score } of bestGroup.elements) {
      if (score > 0) {
        // Only include positively-scored elements
        const metadata = extractMetadata(element);
        if (metadata.heading || metadata.link) {
          results.push(metadata);
        }
      }
    }
  }

  return results;
}

/**
 * Fallback detection using common selectors
 * Runs inside page.evaluate() context
 */
function fallbackDetection(baseUrl) {
  const results = [];

  // Helper functions (duplicated for evaluate context)
  function getVisibleText(el) {
    return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
  }

  function isVisible(el) {
    const style = window.getComputedStyle(el);
    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      el.offsetWidth > 0 &&
      el.offsetHeight > 0
    );
  }

  function extractMetadata(el) {
    // Main heading: Check multiple patterns for link-heading combinations
    let heading = null;
    let headingLink = null; // Track if heading came from a link

    // First check for links containing h1/h2/h3 (a > h pattern)
    const linkWithHeading = el.querySelector("a h1, a h2, a h3, a h4");
    if (linkWithHeading) {
      heading = getVisibleText(linkWithHeading);
      headingLink = linkWithHeading.closest("a");
    }

    // Then check for headings containing links (h > a pattern)
    if (!heading) {
      const headingWithLink = el.querySelector("h1 a, h2 a, h3 a, h4 a");
      if (headingWithLink) {
        heading = getVisibleText(headingWithLink);
        headingLink = headingWithLink;
      }
    }

    // Then check standalone h tags
    if (!heading) {
      const h1 = el.querySelector("h1");
      const h2 = el.querySelector("h2");
      const h3 = el.querySelector("h3");

      if (h1) heading = getVisibleText(h1);
      else if (h2) heading = getVisibleText(h2);
      else if (h3) heading = getVisibleText(h3);
    }

    // Try span with heading-like text
    if (!heading) {
      const spans = el.querySelectorAll("span");
      for (const span of spans) {
        const spanText = getVisibleText(span);
        if (spanText && spanText.length >= 15 && spanText.length <= 150) {
          if (
            !/^\d{1,2}[\s\/\-]|^(category|tag|by |author|posted|published|updated|read more)/i.test(
              spanText,
            )
          ) {
            heading = spanText;
            break;
          }
        }
      }
    }

    // Try p tag with heading-like text
    if (!heading) {
      const paragraphs = el.querySelectorAll("p");
      for (const p of paragraphs) {
        const pText = getVisibleText(p);
        if (pText && pText.length >= 15 && pText.length <= 150) {
          if (
            !/^(read more|click|share|comment|login|menu|subscribe)/i.test(
              pText,
            )
          ) {
            heading = pText;
            break;
          }
        }
      }
    }

    // Try div with heading-like text
    if (!heading) {
      const divs = el.querySelectorAll("div");
      for (const div of divs) {
        if (div.children.length <= 1) {
          const divText = getVisibleText(div);
          if (divText && divText.length >= 15 && divText.length <= 150) {
            if (
              !/^(read more|click|share|comment|login|menu|subscribe)/i.test(
                divText,
              )
            ) {
              heading = divText;
              break;
            }
          }
        }
      }
    }

    if (!heading) {
      const links = el.querySelectorAll("a[href]");
      for (const link of links) {
        const linkText = getVisibleText(link);
        if (linkText.length > 15) {
          heading = linkText;
          break;
        }
      }
    }

    // Subheading: Try multiple sources comprehensively
    let subheading = null;

    // Helper to check if text is valid subheading
    function isValidSubheading(text, heading) {
      if (!text) return false;
      text = text.trim();
      if (text === heading) return false;
      if (text.length < 10 || text.length > 300) return false;
      const skipWords = [
        "read more",
        "click here",
        "learn more",
        "see more",
        "view all",
        "subscribe",
        "newsletter",
        "follow us",
        "share",
        "comments",
        "login",
        "sign in",
        "register",
      ];
      const lowerText = text.toLowerCase();
      if (
        skipWords.some((w) => lowerText === w || lowerText.startsWith(w + " "))
      )
        return false;
      return true;
    }

    // Try h3 if heading came from h1/h2
    const h3Fall = el.querySelector("h3");
    if (h3Fall && isValidSubheading(getVisibleText(h3Fall), heading)) {
      subheading = getVisibleText(h3Fall);
    }

    // Try h4
    if (!subheading) {
      const h4Fall = el.querySelector("h4");
      if (h4Fall && isValidSubheading(getVisibleText(h4Fall), heading)) {
        subheading = getVisibleText(h4Fall);
      }
    }

    // Try h5
    if (!subheading) {
      const h5Fall = el.querySelector("h5");
      if (h5Fall && isValidSubheading(getVisibleText(h5Fall), heading)) {
        subheading = getVisibleText(h5Fall);
      }
    }

    // Try figcaption
    if (!subheading) {
      const figcaption = el.querySelector("figcaption");
      if (
        figcaption &&
        isValidSubheading(getVisibleText(figcaption), heading)
      ) {
        subheading = getVisibleText(figcaption);
      }
    }

    // Try first short paragraph (description/excerpt)
    if (!subheading) {
      const paragraphs = el.querySelectorAll("p");
      for (const p of paragraphs) {
        const pText = getVisibleText(p);
        if (
          pText &&
          pText !== heading &&
          pText.length >= 15 &&
          pText.length <= 200
        ) {
          subheading = pText;
          break;
        }
      }
    }

    // Try strong
    if (!subheading) {
      const strongFall = el.querySelector("strong");
      if (
        strongFall &&
        isValidSubheading(getVisibleText(strongFall), heading)
      ) {
        subheading = getVisibleText(strongFall);
      }
    }

    // Try em
    if (!subheading) {
      const emFall = el.querySelector("em");
      if (emFall && isValidSubheading(getVisibleText(emFall), heading)) {
        subheading = getVisibleText(emFall);
      }
    }

    // Try small
    if (!subheading) {
      const smallFall = el.querySelector("small");
      if (smallFall && isValidSubheading(getVisibleText(smallFall), heading)) {
        subheading = getVisibleText(smallFall);
      }
    }

    // Try cite
    if (!subheading) {
      const citeFall = el.querySelector("cite");
      if (citeFall && isValidSubheading(getVisibleText(citeFall), heading)) {
        subheading = getVisibleText(citeFall);
      }
    }

    // Try blockquote
    if (!subheading) {
      const blockquote = el.querySelector("blockquote");
      if (blockquote) {
        const bqText = getVisibleText(blockquote);
        if (
          bqText &&
          bqText !== heading &&
          bqText.length >= 15 &&
          bqText.length <= 250
        ) {
          subheading = bqText;
        }
      }
    }

    // Try span with substantial text
    if (!subheading) {
      const spans = el.querySelectorAll("span");
      for (const span of spans) {
        const spanText = getVisibleText(span);
        if (
          spanText &&
          spanText !== heading &&
          spanText.length >= 20 &&
          spanText.length <= 200
        ) {
          if (
            !/^\d|^(category|tag|by|author|posted|published)/i.test(spanText)
          ) {
            subheading = spanText;
            break;
          }
        }
      }
    }

    // Try div with short descriptive text
    if (!subheading) {
      const divs = el.querySelectorAll("div");
      for (const div of divs) {
        if (div.children.length <= 2) {
          const divText = getVisibleText(div);
          if (
            divText &&
            divText !== heading &&
            divText.length >= 20 &&
            divText.length <= 200
          ) {
            if (!/^(read more|click|share|comment|login|menu)/i.test(divText)) {
              subheading = divText;
              break;
            }
          }
        }
      }
    }

    let date = null;

    // Date validation helper
    function looksLikeDate(text) {
      if (!text || text.length < 4 || text.length > 50) return false;
      if (!/\d/.test(text)) return false;
      const dateIndicators = [
        /\d{4}/,
        /\d{1,2}[\/\-]\d{1,2}/,
        /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)/i,
        /\b(?:hour|day|week|month|year|ago|yesterday|today)\b/i,
      ];
      return dateIndicators.some((p) => p.test(text));
    }

    const timeEl = el.querySelector("time[datetime]");
    if (timeEl) {
      const dtAttr = timeEl.getAttribute("datetime");
      const timeText = getVisibleText(timeEl);
      if (dtAttr && looksLikeDate(dtAttr)) date = dtAttr;
      else if (timeText && looksLikeDate(timeText)) date = timeText;
    }

    // Try <time> without datetime attribute
    if (!date) {
      const timeElNoAttr = el.querySelector("time");
      if (timeElNoAttr) {
        const timeText = getVisibleText(timeElNoAttr);
        if (looksLikeDate(timeText)) {
          date = timeText;
        }
      }
    }

    // Extended date patterns
    const allDatePatterns = [
      /\d{4}-\d{2}-\d{2}(?:T[\d:]+)?/,
      /\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\s+\d{4}/i,
      /(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[,.]?\s+\d{1,2}[,.]?\s+\d{4}/i,
      /\d{1,2}\/\d{1,2}\/\d{2,4}/,
      /\d{1,2}-\d{1,2}-\d{2,4}/,
      /\d{1,2}\.\d{1,2}\.\d{2,4}/,
      /(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[,.]?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}/i,
      /\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago/i,
      /(?:yesterday|today|just\s+now)/i,
    ];

    // Try spans that look like dates
    if (!date) {
      const spans = el.querySelectorAll("span");
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

    // Try divs that look like dates
    if (!date) {
      const divs = el.querySelectorAll("div");
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

    // Helper to normalize hostname (strip www and lowercase)
    function normalizeHostname(hostname) {
      return hostname.toLowerCase().replace(/^www\./, "");
    }

    // Helper to check if two hostnames are from the same domain
    function isSameDomain(host1, host2) {
      const h1 = normalizeHostname(host1);
      const h2 = normalizeHostname(host2);
      return h1 === h2 || h1.endsWith("." + h2) || h2.endsWith("." + h1);
    }

    // Article link: same domain only, prioritize heading link
    let link = null;
    const baseHostname = normalizeHostname(new URL(baseUrl).hostname);

    // First, check if heading came from a link
    if (headingLink && headingLink.href) {
      try {
        const absoluteUrl = new URL(headingLink.href, baseUrl);
        if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
          link = absoluteUrl.href;
        }
      } catch {
        // Ignore parsing errors
      }
    }

    // If no link from heading, find first valid link
    if (!link) {
      const links = el.querySelectorAll("a[href]");
      for (const a of links) {
        const href = a.href;
        if (
          href &&
          !href.startsWith("javascript:") &&
          !href.startsWith("#") &&
          !href.includes("mailto:")
        ) {
          try {
            const absoluteUrl = new URL(href, baseUrl);
            if (isSameDomain(absoluteUrl.hostname, baseHostname)) {
              link = absoluteUrl.href;
              break;
            }
          } catch {
            // If URL parsing fails, skip this link
          }
        }
      }
    }

    let summary = null;
    const p = el.querySelector("p");
    if (p) {
      const pText = getVisibleText(p);
      if (pText.length > 20 && pText !== heading) {
        summary = pText.substring(0, 300);
      }
    }

    return { heading, subheading, date, link, summary };
  }

  // Fallback selectors in priority order
  const fallbackSelectors = [
    "article",
    "main article",
    '[role="article"]',
    "section > div",
    "main > div",
    ".post", // Generic class but commonly used
    ".article",
    ".entry",
    "li",
  ];

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

        if (results.length >= 5) {
          break; // Found enough articles with this selector
        }
      }
    } catch (e) {
      // Selector might be invalid, continue to next
    }
  }

  return results;
}

/**
 * Main scraping function - reusable for any page/URL
 * @param {Page} page - Playwright page instance
 * @param {string} url - URL to scrape
 * @param {number} retryCount - Current retry attempt
 * @returns {Promise<Array>} - Array of article metadata objects
 */
async function scrapeArticles(page, url, retryCount = 0) {
  const site = getHostname(url);
  const articles = [];

  // Block heavy resources for faster loading
  await page.route("**/*", (route) => {
    const resourceType = route.request().resourceType();
    if (BLOCKED_RESOURCES.includes(resourceType)) {
      route.abort();
    } else {
      route.continue();
    }
  });

  try {
    // Navigate to the page with timeout
    await page.goto(url, {
      timeout: CONFIG.navigationTimeout,
      waitUntil: "domcontentloaded",
    });

    // Wait for network to be mostly idle (with timeout safety)
    try {
      await page.waitForLoadState("networkidle", {
        timeout: CONFIG.idleTimeout,
      });
    } catch {
      // Network didn't become idle, continue anyway
    }

    // Scroll down to trigger lazy loading
    await page.evaluate(async () => {
      const scrollStep = 500;
      const maxScrolls = 3;
      for (let i = 0; i < maxScrolls; i++) {
        window.scrollBy(0, scrollStep);
        await new Promise((r) => setTimeout(r, 300));
      }
      window.scrollTo(0, 0); // Scroll back to top
    });

    // Small delay to let dynamic content render
    await page.waitForTimeout(1500);

    // Try auto-detection first
    let rawArticles = await page.evaluate(autoDetectArticles, url);

    // If auto-detection found very few articles, try scrolling more
    if (!rawArticles || rawArticles.length < 3) {
      // Scroll down more aggressively
      await page.evaluate(async () => {
        for (let i = 0; i < 5; i++) {
          window.scrollBy(0, window.innerHeight);
          await new Promise((r) => setTimeout(r, 400));
        }
      });
      await page.waitForTimeout(1000);
      rawArticles = await page.evaluate(autoDetectArticles, url);
    }

    // If auto-detection failed, try fallback
    if (!rawArticles || rawArticles.length < CONFIG.minArticles) {
      console.log(
        `  [${site}] Auto-detection found ${rawArticles?.length || 0} articles, trying fallback...`,
      );
      const fallbackArticles = await page.evaluate(fallbackDetection, url);

      if (fallbackArticles && fallbackArticles.length > rawArticles?.length) {
        rawArticles = fallbackArticles;
        console.log(
          `  [${site}] Fallback found ${rawArticles.length} articles`,
        );
      }
    }

    // Process and filter articles
    const seenUrls = new Set();

    for (const article of rawArticles || []) {
      // Skip if no link or heading
      if (!article.link || !article.heading) continue;

      // Skip if title too short
      if (article.heading.length < CONFIG.minTitleLength) continue;

      // Deduplicate by URL
      if (seenUrls.has(article.link)) continue;
      seenUrls.add(article.link);

      // Add site info and normalize
      articles.push({
        site,
        heading: article.heading.trim(),
        subheading: article.subheading?.trim() || null,
        date: article.date?.trim() || null,
        link: article.link,
        summary: article.summary?.trim() || null,
      });
    }
  } catch (error) {
    // Retry logic for transient failures
    if (retryCount < CONFIG.maxRetries) {
      console.log(
        `  [${site}] Retrying (${retryCount + 1}/${CONFIG.maxRetries})...`,
      );
      await new Promise((resolve) => setTimeout(resolve, CONFIG.retryDelay));
      return scrapeArticles(page, url, retryCount + 1);
    }
    console.error(`  [${site}] Error: ${error.message}`);
    // Return empty array on error - don't throw
  }

  return articles;
}

/**
 * Process a single site (for parallel execution)
 */
async function processSite(context, url, index, total) {
  const site = getHostname(url);
  console.log(`\n[${index + 1}/${total}] Scraping: ${site}`);
  console.log(`  URL: ${url}`);

  const page = await context.newPage();
  let articles = [];

  try {
    articles = await scrapeArticles(page, url);

    if (articles.length > 0) {
      console.log(`  ✓ Found ${articles.length} articles`);
    } else {
      console.log(`  ✗ No valid articles found`);
    }
  } catch (error) {
    console.error(`  ✗ Failed: ${error.message}`);
  } finally {
    await page.close();
  }

  return { site, articles, url };
}

/**
 * Main execution function with parallel processing
 */
async function main() {
  const startTime = Date.now();

  console.log("=".repeat(60));
  console.log("Playwright Article Scraper - Starting");
  console.log("=".repeat(60));
  console.log(`Target URLs: ${TARGET_URLS.length}`);
  console.log(`Concurrency: ${CONFIG.concurrency} sites in parallel`);
  console.log(`Started at: ${new Date().toISOString()}`);
  console.log("=".repeat(60));

  const allArticles = [];
  const stats = {
    total: TARGET_URLS.length,
    success: 0,
    failed: 0,
    perSite: {},
  };

  // Launch browser
  const browser = await chromium.launch({
    headless: true,
  });

  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    viewport: { width: 1920, height: 1080 },
    ignoreHTTPSErrors: true,
  });

  try {
    // Process URLs in parallel batches
    const results = [];

    for (let i = 0; i < TARGET_URLS.length; i += CONFIG.concurrency) {
      const batch = TARGET_URLS.slice(i, i + CONFIG.concurrency);
      const batchPromises = batch.map((url, batchIndex) =>
        processSite(context, url, i + batchIndex, TARGET_URLS.length),
      );

      const batchResults = await Promise.all(batchPromises);
      results.push(...batchResults);

      // Progress update
      const processed = Math.min(i + CONFIG.concurrency, TARGET_URLS.length);
      const elapsed = (Date.now() - startTime) / 1000;
      const rate = processed / elapsed;
      const remaining = (TARGET_URLS.length - processed) / rate;
      console.log(
        `\n--- Progress: ${processed}/${TARGET_URLS.length} (${Math.round(remaining)}s remaining) ---`,
      );
    }

    // Aggregate results
    for (const { site, articles } of results) {
      if (articles.length > 0) {
        allArticles.push(...articles);
        stats.success++;
        stats.perSite[site] = (stats.perSite[site] || 0) + articles.length;
      } else {
        stats.failed++;
        stats.perSite[site] = stats.perSite[site] || 0;
      }
    }
  } finally {
    await browser.close();
  }

  const totalTime = ((Date.now() - startTime) / 1000).toFixed(2);

  // Create output with metadata
  const output = {
    metadata: {
      scrapedAt: new Date().toISOString(),
      totalTime: `${totalTime}s`,
      totalUrls: stats.total,
      successfulSites: stats.success,
      failedSites: stats.failed,
      totalArticles: allArticles.length,
      perSite: stats.perSite,
    },
    articles: allArticles,
  };

  // Write results to JSON file
  const outputPath = "results.json";
  fs.writeFileSync(outputPath, JSON.stringify(output, null, 2), "utf8");

  // Print summary
  console.log("\n" + "=".repeat(60));
  console.log("SCRAPING COMPLETE - SUMMARY");
  console.log("=".repeat(60));
  console.log(`Finished at: ${new Date().toISOString()}`);
  console.log(`Total time: ${totalTime}s`);
  console.log(`Total URLs processed: ${stats.total}`);
  console.log(`Successful: ${stats.success}`);
  console.log(`Failed/Empty: ${stats.failed}`);
  console.log(`Total articles scraped: ${allArticles.length}`);
  console.log("\nArticles per site:");

  Object.entries(stats.perSite)
    .sort((a, b) => b[1] - a[1])
    .forEach(([site, count]) => {
      const status = count > 0 ? "✓" : "✗";
      console.log(`  ${status} ${site}: ${count}`);
    });

  console.log(`\nResults saved to: ${outputPath}`);
  console.log("=".repeat(60));

  return allArticles;
}

// Run the scraper
main().catch(console.error);
