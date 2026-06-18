"""Website post fetcher using Playwright for dynamic sites."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from playwright.async_api import async_playwright, Browser, Page

from web_crawler.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_BATCH_DELAY,
    HEADLESS,
    TIMEOUT,
    USER_AGENT,
)

logger = logging.getLogger(__name__)


async def fetch_posts(
    url: str,
    site_type: str,
    days_back: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
    batch_delay: float = DEFAULT_BATCH_DELAY,
    cookies: list[dict] | None = None,
) -> list[dict[str, Any]]:
    """Fetch posts from a website with batch processing.

    Args:
        url: The website URL to fetch from.
        site_type: The site type (e.g., 'v2ex', 'eleduck') for parser selection.
        days_back: Extra days before today to include (0 = today only).
        batch_size: Posts per page/batch (default: 20).
        batch_delay: Seconds to wait between batches (default: 2.0).
        cookies: Optional list of cookies for authenticated requests.

    Returns:
        List of post dictionaries.
    """
    posts: list[dict[str, Any]] = []

    today_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    cutoff_date = today_midnight - timedelta(days=days_back)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1920, "height": 1080},
            )

            # Add cookies if provided (for authenticated sites)
            if cookies:
                await context.add_cookies(cookies)
                logger.info(f"[FETCH] Added {len(cookies)} cookies for authentication")

            page = await context.new_page()
            # Set longer timeout for bossjob (slow site with many ads)
            page_timeout = 120000 if site_type == "bossjob" else TIMEOUT
            page.set_default_timeout(page_timeout)

            # Navigate to the URL
            logger.info(f"[FETCH] Navigating to {url}")
            # Use less strict wait for bossjob (has lots of ads/analytics)
            wait_until = "commit" if site_type == "bossjob" else "networkidle"
            await page.goto(url, wait_until=wait_until, timeout=page_timeout)

            # Site-specific parsing
            if site_type == "v2ex":
                posts = await _fetch_v2ex_posts(page, cutoff_date, batch_size, batch_delay)
            elif site_type == "eleduck":
                posts = await _fetch_eleduck_posts(page, cutoff_date, batch_size, batch_delay)
            elif site_type == "bossjob":
                posts = await _fetch_bossjob_posts(page, cutoff_date, batch_size, batch_delay)
            else:
                logger.error(f"[FETCH] Unknown site type: {site_type}")

            await context.close()
            await browser.close()

    except Exception as e:
        logger.error(f"[FETCH] Error fetching from {url}: {e}", exc_info=True)

    return posts


async def _fetch_v2ex_posts(
    page: Page,
    cutoff_date: datetime,
    batch_size: int,
    batch_delay: float,
) -> list[dict[str, Any]]:
    """Fetch posts from V2EX.

    Args:
        page: Playwright page instance.
        cutoff_date: Date cutoff for posts.
        batch_size: Posts per page.
        batch_delay: Delay between pages.

    Returns:
        List of post dictionaries.
    """
    posts: list[dict[str, Any]] = []
    page_num = 1
    reached_cutoff = False

    try:
        while not reached_cutoff:
            logger.info(f"[FETCH V2EX] Page {page_num}")

            # Wait for posts to load
            await page.wait_for_selector(".item", timeout=10000)

            # Extract posts
            post_elements = await page.query_selector_all(".item")
            batch_count = 0

            for element in post_elements:
                if batch_count >= batch_size:
                    break

                try:
                    # Extract post data
                    title_elem = await element.query_selector(".topic-link")
                    post_id = await element.get_attribute("data-id")
                    title = await title_elem.inner_text() if title_elem else None

                    # Extract date
                    date_elem = await element.query_selector(".ago")
                    date_text = await date_elem.inner_text() if date_elem else None
                    post_date = _parse_v2ex_date(date_text) if date_text else None

                    # Extract author
                    author_elem = await element.query_selector(".user-name")
                    author = await author_elem.inner_text() if author_elem else None

                    # Extract URL
                    post_url = await title_elem.get_attribute("href") if title_elem else None
                    if post_url and not post_url.startswith("http"):
                        post_url = f"https://v2ex.com{post_url}"

                    # Check cutoff
                    if post_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break

                    if title and post_id:
                        posts.append({
                            "id": post_id,
                            "title": title,
                            "url": post_url,
                            "author": author,
                            "date": post_date,
                            "text": title,  # V2EX posts need detail page fetch for full text
                        })
                        batch_count += 1

                except Exception as e:
                    logger.warning(f"[FETCH V2EX] Error parsing post: {e}")
                    continue

            # Check if we need to go to next page
            if batch_count < batch_size or reached_cutoff:
                break

            # Look for next page button
            next_button = await page.query_selector(".page_normal:last-child")
            if next_button:
                await next_button.click()
                await asyncio.sleep(batch_delay)
                page_num += 1
            else:
                break

    except Exception as e:
        logger.error(f"[FETCH V2EX] Error: {e}", exc_info=True)

    return posts


async def _fetch_eleduck_posts(
    page: Page,
    cutoff_date: datetime,
    batch_size: int,
    batch_delay: float,
) -> list[dict[str, Any]]:
    """Fetch posts from 电鸭社区.

    Args:
        page: Playwright page instance.
        cutoff_date: Date cutoff for posts.
        batch_size: Posts per page.
        batch_delay: Delay between pages.

    Returns:
        List of post dictionaries.
    """
    posts: list[dict[str, Any]] = []
    page_num = 1
    reached_cutoff = False

    try:
        while not reached_cutoff:
            logger.info(f"[FETCH ELEDUCK] Page {page_num}")

            # Wait for posts to load
            await page.wait_for_selector(".post-item", timeout=10000)

            # Extract posts
            post_elements = await page.query_selector_all(".post-item")
            batch_count = 0

            for element in post_elements:
                if batch_count >= batch_size:
                    break

                try:
                    # Extract post data
                    title_elem = await element.query_selector(".post-title a")
                    title = await title_elem.inner_text() if title_elem else None

                    # Extract post ID from URL
                    post_url = await title_elem.get_attribute("href") if title_elem else None
                    post_id = post_url.split("/")[-1] if post_url else None

                    # Extract date
                    date_elem = await element.query_selector(".post-meta .time")
                    date_text = await date_elem.inner_text() if date_elem else None
                    post_date = _parse_eleduck_date(date_text) if date_text else None

                    # Extract author
                    author_elem = await element.query_selector(".post-meta .author")
                    author = await author_elem.inner_text() if author_elem else None

                    # Check cutoff
                    if post_date and post_date < cutoff_date:
                        reached_cutoff = True
                        break

                    if title and post_id:
                        posts.append({
                            "id": post_id,
                            "title": title,
                            "url": post_url,
                            "author": author,
                            "date": post_date,
                            "text": title,  # 电鸭 posts need detail page fetch for full text
                        })
                        batch_count += 1

                except Exception as e:
                    logger.warning(f"[FETCH ELEDUCK] Error parsing post: {e}")
                    continue

            # Check if we need to go to next page
            if batch_count < batch_size or reached_cutoff:
                break

            # Look for next page button
            next_button = await page.query_selector(".pagination .next")
            if next_button:
                await next_button.click()
                await asyncio.sleep(batch_delay)
                page_num += 1
            else:
                break

    except Exception as e:
        logger.error(f"[FETCH ELEDUCK] Error: {e}", exc_info=True)

    return posts


def _parse_v2ex_date(date_text: str) -> datetime:
    """Parse V2EX date string (e.g., "2小时前", "3天前").

    Args:
        date_text: Date string from V2EX.

    Returns:
        Datetime object.
    """
    now = datetime.now(timezone.utc)

    if "分钟前" in date_text:
        minutes = int(date_text.replace("分钟前", ""))
        return now - timedelta(minutes=minutes)
    elif "小时前" in date_text:
        hours = int(date_text.replace("小时前", ""))
        return now - timedelta(hours=hours)
    elif "天前" in date_text:
        days = int(date_text.replace("天前", ""))
        return now - timedelta(days=days)
    else:
        # Try to parse as regular date
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except:
            return now


def _parse_eleduck_date(date_text: str) -> datetime:
    """Parse 电鸭 date string (e.g., "2小时前", "3天前").

    Args:
        date_text: Date string from 电鸭.

    Returns:
        Datetime object.
    """
    now = datetime.now(timezone.utc)

    if "分钟前" in date_text:
        minutes = int(date_text.replace("分钟前", ""))
        return now - timedelta(minutes=minutes)
    elif "小时前" in date_text:
        hours = int(date_text.replace("小时前", ""))
        return now - timedelta(hours=hours)
    elif "天前" in date_text:
        days = int(date_text.replace("天前", ""))
        return now - timedelta(days=days)
    else:
        # Try to parse as regular date
        try:
            return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except:
            return now


async def _fetch_bossjob_posts(
    page: Page,
    cutoff_date: datetime,
    batch_size: int,
    batch_delay: float,
) -> list[dict[str, Any]]:
    """Fetch job posts from bossjob.com with detail page scraping.

    Uses JavaScript extraction via page.evaluate() to avoid stale element handles.
    First extracts all job data (title, company, item_id) from listing page,
    then navigates to each job's detail page individually.

    Args:
        page: Playwright page instance.
        cutoff_date: Date cutoff for posts (not used for bossjob, always fetch).
        batch_size: Posts per page (used as max jobs per page).
        batch_delay: Delay between job detail fetches.

    Returns:
        List of post dictionaries with full job details.
    """
    posts: list[dict[str, Any]] = []
    max_pages = 10
    jobs_per_page = min(batch_size, 10)  # Bossjob shows ~10 jobs per page

    try:
        for page_num in range(1, max_pages + 1):
            logger.info(f"[FETCH BOSSJOB] Page {page_num}/{max_pages}")

            # Wait for job cards to load
            await asyncio.sleep(4)

            # Extract job data using JavaScript (returns plain dicts with card index)
            jobs_data = await page.evaluate("""
                () => {
                    const jobs = [];
                    const selectors = [
                        '.yolo-technology-jobCard',
                        '[class*="index_pc_listItem"]',
                        '[data-sentry-component="JobCardPc"]',
                        '[class*="JobCard"]',
                        '.job-card'
                    ];
                    
                    for (const selector of selectors) {
                        const cards = document.querySelectorAll(selector);
                        if (cards.length > 0) {
                            cards.forEach((card, index) => {
                                // Skip cards from 'Top Web3 Companies' section
                                let parent = card.parentElement;
                                let isCompaniesSection = false;
                                while (parent) {
                                    if (parent.className && (parent.className.includes('companies') || parent.className.includes('style_companies'))) {
                                        isCompaniesSection = true;
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                                if (isCompaniesSection) {
                                    return; // Skip this card (return from forEach iteration)
                                }

                                const itemId = card.getAttribute('data-item-id');

                                // Try multiple title selectors
                                const titleSelectors = [
                                    'h3[class*="jobHireTopTitle"]',
                                    'h3 span',
                                    'h3'
                                ];
                                let title = '';
                                for (const ts of titleSelectors) {
                                    const titleEl = card.querySelector(ts);
                                    if (titleEl) {
                                        title = titleEl.innerText?.trim() || '';
                                        if (title) break;
                                    }
                                }
                                
                                // Try multiple company selectors
                                const companySelectors = [
                                    '[class*="jobHireRecruiterName"]',
                                    '[class*="company-name"]',
                                    '[class*="Company"]'
                                ];
                                let company = '';
                                for (const cs of companySelectors) {
                                    const companyEl = card.querySelector(cs);
                                    if (companyEl) {
                                        company = companyEl.innerText?.trim() || '';
                                        if (company) break;
                                    }
                                }
                                
                                if (itemId && title) {
                                    jobs.push({
                                        item_id: itemId,
                                        title: title,
                                        company: company,
                                        card_index: index,
                                        card_selector: selector
                                    });
                                }
                            });
                            break;
                        }
                    }
                    return jobs;
                }
            """)

            if not jobs_data:
                logger.warning(f"[FETCH BOSSJOB] No job cards found on page {page_num}, stopping")
                break

            logger.info(f"[FETCH BOSSJOB] Found {len(jobs_data)} jobs on page {page_num}")

            # Iterate through extracted job data (plain Python dicts, no stale handles)
            for idx, job_data in enumerate(jobs_data[:jobs_per_page]):
                try:
                    title = job_data.get('title', '').strip()
                    company = job_data.get('company', '').strip()
                    item_id = job_data.get('item_id', '')
                    card_index = job_data.get('card_index', 0)
                    card_selector = job_data.get('card_selector', '')

                    if not title:
                        continue

                    logger.info(f"[FETCH BOSSJOB] -------------------------------")
                    logger.info(f"[FETCH BOSSJOB] Job {idx+1}/{len(jobs_data[:jobs_per_page])}: {title[:50]}... (item_id: {item_id})")

                    # Construct job URL for reference
                    job_url = f"https://bossjob.com/en-us/job/{item_id}"

                    # Click the job card to open modal/sidebar
                    card_elements = await page.query_selector_all(card_selector)
                    if card_index < len(card_elements):
                        await card_elements[card_index].click()
                        await asyncio.sleep(2)  # Wait for modal to load
                    else:
                        logger.warning(f"[FETCH BOSSJOB] Card index {card_index} out of range, skipping")
                        continue

                    # Wait for detail page content - wait for MainSection specifically
                    try:
                        await page.wait_for_selector("[class*='MainSection_pc_mainSection']", timeout=10000)
                    except Exception:
                        # If MainSection not found, try fallback selectors
                        try:
                            await page.wait_for_selector("[class*='detail'], [class*='Detail'], [data-testid='job-detail'], .job-description, [class*='description'], [class*='Description']", timeout=5000)
                        except Exception:
                            pass  # Continue even if detail selector not found

                    # Extract full details from detail page using JavaScript
                    detail_data = await page.evaluate("""
                        () => {
                            const result = {
                                description: '',
                                requirements: '',
                                location: '',
                                salary: ''
                            };

                            // Target the main job detail section
                            const mainSection = document.querySelector('[class*="MainSection_pc_mainSection"]');
                            const useMainSection = !!mainSection;

                            // Filter out warning messages
                            const isWarningText = (text) => {
                                const warningPhrases = ['mobile device', 'desktop browser', 'Download App', 'features may not work'];
                                return warningPhrases.some(phrase => text.toLowerCase().includes(phrase.toLowerCase()));
                            };

                            // Check if element is inside Similar Jobs section
                            const isSimilarJobsSection = (el) => {
                                let parent = el.parentElement;
                                while (parent) {
                                    if (parent.className && (parent.className.includes('similarJobs') || parent.className.includes('SimilarJobs'))) {
                                        return true;
                                    }
                                    parent = parent.parentElement;
                                }
                                return false;
                            };

                            // Check if element is inside Job List section
                            const isJobListSection = (el) => {
                                let parent = el.parentElement;
                                while (parent) {
                                    if (parent.className && (parent.className.includes('jobList') || parent.className.includes('JobList'))) {
                                        return true;
                                    }
                                    parent = parent.parentElement;
                                }
                                return false;
                            };

                            // Check if element is inside Top Web3 Companies section
                            const isCompaniesSection = (el) => {
                                let parent = el.parentElement;
                                while (parent) {
                                    if (parent.className && parent.className.includes('companies')) {
                                        return true;
                                    }
                                    parent = parent.parentElement;
                                }
                                return false;
                            };

                            // Combined filter for all unwanted sections
                            const isUnwantedSection = (el) => {
                                return isSimilarJobsSection(el) || isJobListSection(el) || isCompaniesSection(el);
                            };

                            // Description - use more specific selectors
                            const descSelectors = [
                                '[class*="job-description"]',
                                '[class*="JobDescription"]',
                                '[data-testid="job-description"]',
                                '[class*="jobDetail"]',
                                '[class*="job-detail"]',
                                '[class*="detailContent"]',
                                '[class*="detail-content"]',
                                '[class*="Desc_pc_descContent"]'
                            ];
                            for (const sel of descSelectors) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwantedSection(el)) {
                                    const text = el.innerText?.trim() || '';
                                    if (text.length > 50 && !isWarningText(text)) {
                                        result.description = text;
                                        break;
                                    }
                                }
                            }
                            
                            // If no description found, try broader selectors but filter warnings
                            if (!result.description) {
                                const broadDescSelectors = [
                                    '.description',
                                    '[class*="description"]',
                                    '[class*="content"]',
                                    'article',
                                    'main'
                                ];
                                for (const sel of broadDescSelectors) {
                                    const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                    if (el && !isUnwantedSection(el)) {
                                        const text = el.innerText?.trim() || '';
                                        if (text.length > 100 && !isWarningText(text)) {
                                            result.description = text;
                                            break;
                                        }
                                    }
                                }
                            }
                            
                            // Requirements
                            const reqSelectors = [
                                '[class*="requirement"]',
                                '[class*="Requirement"]',
                                '[class*="qualification"]',
                                '[class*="Qualification"]',
                                '[class*="skill"]',
                                '[class*="Skill"]'
                            ];
                            for (const sel of reqSelectors) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwantedSection(el)) {
                                    const text = el.innerText?.trim() || '';
                                    if (text.length > 20 && !isWarningText(text)) {
                                        result.requirements = text;
                                        break;
                                    }
                                }
                            }
                            
                            // Location
                            const locSelectors = [
                                '[class*="location"]',
                                '[class*="Location"]',
                                '[data-testid="location"]',
                                '[class*="city"]',
                                '[class*="City"]'
                            ];
                            for (const sel of locSelectors) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwantedSection(el)) {
                                    const text = el.innerText?.trim() || '';
                                    if (text) {
                                        result.location = text;
                                        break;
                                    }
                                }
                            }
                            
                            // Salary
                            const salSelectors = [
                                '[class*="salary"]',
                                '[class*="Salary"]',
                                '[data-testid="salary"]'
                            ];
                            for (const sel of salSelectors) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwantedSection(el)) {
                                    const text = el.innerText?.trim() || '';
                                    if (text) {
                                        result.salary = text;
                                        break;
                                    }
                                }
                            }
                            
                            return result;
                        }
                    """)

                    description = detail_data.get('description', '')
                    requirements = detail_data.get('requirements', '')
                    location = detail_data.get('location', '')
                    salary = detail_data.get('salary', '')

                    # Construct full text
                    full_text_parts = [title]
                    if company:
                        full_text_parts.append(f"Company: {company}")
                    if salary:
                        full_text_parts.append(f"Salary: {salary}")
                    if location:
                        full_text_parts.append(f"Location: {location}")
                    if requirements:
                        full_text_parts.append(f"Requirements: {requirements}")
                    if description:
                        full_text_parts.append(f"Description: {description}")

                    full_text = "\n\n".join(full_text_parts)

                    # Create analysis text with only description + requirements for Ollama
                    analysis_parts = []
                    if description:
                        analysis_parts.append(description)
                    if requirements:
                        analysis_parts.append(requirements)
                    analysis_text = "\n\n".join(analysis_parts)

                    logger.info(f"[FETCH BOSSJOB] Full text:\n{full_text}")
                    logger.info(f"[FETCH BOSSJOB] Analysis text length: {len(analysis_text)} chars")

                    # Create post entry
                    post_id = item_id if item_id else f"bossjob_{page_num}_{idx}"
                    posts.append({
                        "id": post_id,
                        "title": title,
                        "url": job_url,
                        "company": company,
                        "date": datetime.now(),
                        "text": full_text,
                        "analysis_text": analysis_text,  # For Ollama analysis
                        "salary": salary,
                        "location": location,
                        "requirements": requirements,
                        "description": description,
                    })

                    logger.info(f"[FETCH BOSSJOB] ✓ Extracted: {title[:50]}... ({len(full_text)} chars)")

                    # Close modal by pressing Escape
                    await page.keyboard.press('Escape')
                    await asyncio.sleep(batch_delay)

                except Exception as e:
                    logger.warning(f"[FETCH BOSSJOB] Error processing job {idx+1}: {e}")
                    # Try to close modal in case we're stuck
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    continue

            # Check if there's a next page button
            try:
                # Bossjob pagination: next button is a span with Pagination_actionBtn class
                # Use partial class matching for Next.js hash classnames
                next_selectors = [
                    "[class*='Pagination_actionBtn'][style*='rotate(0deg)']",
                    "[class*='Pagination_actionBtn']:not([data-disabled='true'])",
                    "span[class*='Pagination_actionBtn']:last-child",
                    "[class*='Pagination_actionBtn']",
                    "button[class*='next']",
                    "a[class*='next']"
                ]
                next_button = None
                for selector in next_selectors:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        break

                if next_button:
                    # Check data-disabled attribute (Bossjob uses this instead of disabled)
                    is_disabled = await next_button.get_attribute("data-disabled")
                    if is_disabled == "true":
                        logger.info("[FETCH BOSSJOB] Next button disabled, reached last page")
                        break

                    # Click next page
                    await next_button.click()
                    await asyncio.sleep(batch_delay + 1)
                else:
                    # Alternative: click the next page number
                    next_page_num = await page.evaluate("""
                        () => {
                            const currentPage = document.querySelector('[data-checked="true"]');
                            if (currentPage) {
                                const nextSibling = currentPage.nextElementSibling;
                                if (nextSibling && nextSibling.getAttribute('data-checked') === 'false') {
                                    return nextSibling.innerText.trim();
                                }
                            }
                            return null;
                        }
                    """)
                    if next_page_num:
                        logger.info(f"[FETCH BOSSJOB] Clicking page number: {next_page_num}")
                        await page.click(f"[data-checked='false']:text('{next_page_num}')")
                        await asyncio.sleep(batch_delay + 1)
                    else:
                        # Fallback: try to increment page number in URL
                        current_url = page.url
                        if "page=" in current_url:
                            current_page = int(current_url.split("page=")[1].split("&")[0])
                            next_url = current_url.replace(f"page={current_page}", f"page={current_page + 1}")
                            await page.goto(next_url, wait_until="domcontentloaded")
                            await asyncio.sleep(batch_delay)
                        else:
                            logger.info("[FETCH BOSSJOB] No next button found, stopping")
                            break
            except Exception as e:
                logger.warning(f"[FETCH BOSSJOB] Error navigating to next page: {e}")
                break

    except Exception as e:
        logger.error(f"[FETCH BOSSJOB] Error: {e}", exc_info=True)

    logger.info(f"[FETCH BOSSJOB] Total jobs fetched: {len(posts)}")
    return posts
