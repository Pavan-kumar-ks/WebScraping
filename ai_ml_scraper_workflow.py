"""
Integrated AI/ML Article Scraper Workflow
This script orchestrates the complete workflow:
1. Takes URLs from scraper.py
2. Finds AI/ML related links using ml_link_finder.py
3. Scrapes article content (heading, date, paragraphs, country) from those links
4. Organizes and saves results by country in separate folders
"""

import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from ml_link_finder import discover_ai_ml_links
from scraper import TARGET_URLS, scrape_from_links


async def run_integrated_workflow():
    """Run the complete AI/ML article scraping workflow"""
    workflow_start = datetime.now()
    
    print("=" * 70)
    print(" AI/ML ARTICLE SCRAPER - INTEGRATED WORKFLOW")
    print("=" * 70)
    print(f"Started at: {workflow_start.isoformat()}")
    print(f"Source URLs: {len(TARGET_URLS)}")
    print("=" * 70)
    
    # Step 1: Discover AI/ML related links
    print("\n" + "=" * 70)
    print("STEP 1: Discovering AI/ML Related Links")
    print("=" * 70)
    
    link_discovery_result = await discover_ai_ml_links(TARGET_URLS)
    
    # Save link discovery results
    with open("ai_ml_links.json", "w", encoding="utf-8") as f:
        json.dump(link_discovery_result, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Link discovery complete. Found {link_discovery_result['metadata']['totalLinksFound']} AI/ML links")
    print(f"  Results saved to: ai_ml_links.json")
    
    # Extract URLs from discovered links
    ai_ml_urls = [link['url'] for link in link_discovery_result['ai_ml_links']]
    
    if not ai_ml_urls:
        print("\n[WARNING] No AI/ML links found. Workflow complete.")
        return
    
    # Step 2: Scrape article content from AI/ML links
    print("\n" + "=" * 70)
    print("STEP 2: Scraping Article Content from AI/ML Links")
    print("=" * 70)
    
    scraping_result = await scrape_from_links(ai_ml_urls)

    # Save final results organized by country
    print(f"\n[OK] Article scraping complete")
    print(f"  Organizing articles by country...")

    # Group articles by country
    articles_by_country = defaultdict(list)
    for article in scraping_result['articles']:
        country = article.get('country', 'Unknown')
        articles_by_country[country].append(article)

    # Create articles folder if it doesn't exist
    articles_folder = "articles"
    os.makedirs(articles_folder, exist_ok=True)

    # Save articles organized by country
    country_files = {}
    for country, articles in articles_by_country.items():
        # Create country folder
        country_folder = os.path.join(articles_folder, country.replace(' ', '_'))
        os.makedirs(country_folder, exist_ok=True)

        # Save articles to country-specific JSON file
        country_file_path = os.path.join(country_folder, "articles.json")

        country_output = {
            "metadata": {
                "country": country,
                "totalArticles": len(articles),
                "scrapedAt": datetime.now().isoformat()
            },
            "articles": articles
        }

        with open(country_file_path, "w", encoding="utf-8") as f:
            json.dump(country_output, f, indent=2, ensure_ascii=False)

        country_files[country] = country_file_path
        print(f"  [OK] {country}: {len(articles)} articles -> {country_file_path}")

    # Also save a combined file for reference
    combined_output_path = "ai_ml_articles_combined.json"
    with open(combined_output_path, "w", encoding="utf-8") as f:
        json.dump(scraping_result, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Combined results also saved to: {combined_output_path}")
    
    # Step 3: Create summary report
    workflow_end = datetime.now()
    total_workflow_time = (workflow_end - workflow_start).total_seconds()
    
    print("\n" + "=" * 70)
    print(" WORKFLOW COMPLETE - FINAL SUMMARY")
    print("=" * 70)
    print(f"Total workflow time: {total_workflow_time:.2f}s")
    print(f"\nPhase 1 - Link Discovery:")
    print(f"  • Source URLs processed: {link_discovery_result['metadata']['totalSources']}")
    print(f"  • AI/ML links found: {link_discovery_result['metadata']['totalLinksFound']}")
    print(f"  • Time taken: {link_discovery_result['metadata']['totalTime']}")
    print(f"\nPhase 2 - Article Scraping:")
    print(f"  • Links scraped: {scraping_result['metadata']['totalLinks']}")
    print(f"  • Successful scrapes: {scraping_result['metadata']['successfulScrapes']}")
    print(f"  • Failed scrapes: {scraping_result['metadata']['failedScrapes']}")
    print(f"  • Time taken: {scraping_result['metadata']['totalTime']}")
    print(f"\nArticles by Country:")
    for country, articles in sorted(articles_by_country.items(), key=lambda x: -len(x[1])):
        print(f"  • {country}: {len(articles)} articles")
    print(f"\nOutput Files:")
    print(f"  • AI/ML Links: ai_ml_links.json")
    print(f"  • Combined Articles: {combined_output_path}")
    print(f"  • By Country: articles/{{country}}/articles.json")
    print("=" * 70)
    
    # Display sample articles
    if scraping_result['articles']:
        print("\n" + "=" * 70)
        print(" SAMPLE ARTICLES (First 3)")
        print("=" * 70)
        
        for i, article in enumerate(scraping_result['articles'][:3], 1):
            print(f"\n{i}. {article.get('heading', 'No heading')}")
            print(f"   URL: {article.get('url', '')}")
            print(f"   Paragraphs: {article.get('paragraphCount', 0)}")
            content_preview = article.get('content', '')[:200]
            print(f"   Preview: {content_preview}...")
        
        print("\n" + "=" * 70)


def main():
    """Entry point for the integrated workflow"""
    asyncio.run(run_integrated_workflow())


if __name__ == "__main__":
    main()
