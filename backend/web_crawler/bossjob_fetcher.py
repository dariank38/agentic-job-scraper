"""Playwright-based fetcher for bossjob.com job listings."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def fetch_bossjob_posts(
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
    max_pages = 3
    jobs_per_page = min(batch_size, 10)

    try:
        for page_num in range(1, max_pages + 1):
            logger.info(f"[FETCH BOSSJOB] Page {page_num}/{max_pages}")
            await asyncio.sleep(4)

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
                                let parent = card.parentElement;
                                let isCompaniesSection = false;
                                while (parent) {
                                    if (parent.className && (parent.className.includes('companies') || parent.className.includes('style_companies'))) {
                                        isCompaniesSection = true;
                                        break;
                                    }
                                    parent = parent.parentElement;
                                }
                                if (isCompaniesSection) return;
                                const itemId = card.getAttribute('data-item-id');
                                const titleSelectors = ['h3[class*="jobHireTopTitle"]', 'h3 span', 'h3'];
                                let title = '';
                                for (const ts of titleSelectors) {
                                    const titleEl = card.querySelector(ts);
                                    if (titleEl) { title = titleEl.innerText?.trim() || ''; if (title) break; }
                                }
                                const companySelectors = ['[class*="jobHireRecruiterName"]', '[class*="company-name"]', '[class*="Company"]'];
                                let company = '';
                                for (const cs of companySelectors) {
                                    const companyEl = card.querySelector(cs);
                                    if (companyEl) { company = companyEl.innerText?.trim() || ''; if (company) break; }
                                }
                                if (itemId && title) {
                                    jobs.push({ item_id: itemId, title: title, company: company, card_index: index, card_selector: selector });
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

            for idx, job_data in enumerate(jobs_data[:jobs_per_page]):
                try:
                    title = job_data.get('title', '').strip()
                    company = job_data.get('company', '').strip()
                    item_id = job_data.get('item_id', '')
                    card_index = job_data.get('card_index', 0)
                    card_selector = job_data.get('card_selector', '')

                    if not title:
                        continue

                    logger.info(f"[FETCH BOSSJOB] Job {idx+1}/{len(jobs_data[:jobs_per_page])}: {title[:50]}... (item_id: {item_id})")
                    job_url = f"https://bossjob.com/en-us/job/{item_id}"

                    card_elements = await page.query_selector_all(card_selector)
                    if card_index < len(card_elements):
                        await card_elements[card_index].click()
                        await asyncio.sleep(2)
                    else:
                        logger.warning(f"[FETCH BOSSJOB] Card index {card_index} out of range, skipping")
                        continue

                    try:
                        await page.wait_for_selector("[class*='MainSection_pc_mainSection']", timeout=10000)
                    except Exception:
                        try:
                            await page.wait_for_selector("[class*='detail'], [class*='Detail'], [data-testid='job-detail'], .job-description, [class*='description'], [class*='Description']", timeout=5000)
                        except Exception:
                            pass

                    detail_data = await page.evaluate("""
                        () => {
                            const result = { description: '', requirements: '', location: '', salary: '' };
                            const mainSection = document.querySelector('[class*="MainSection_pc_mainSection"]');
                            const useMainSection = !!mainSection;
                            const isWarningText = (text) => {
                                const warningPhrases = ['mobile device', 'desktop browser', 'Download App', 'features may not work'];
                                return warningPhrases.some(phrase => text.toLowerCase().includes(phrase.toLowerCase()));
                            };
                            const isSimilarJobsSection = (el) => { let p = el.parentElement; while (p) { if (p.className && (p.className.includes('similarJobs') || p.className.includes('SimilarJobs'))) return true; p = p.parentElement; } return false; };
                            const isJobListSection = (el) => { let p = el.parentElement; while (p) { if (p.className && (p.className.includes('jobList') || p.className.includes('JobList'))) return true; p = p.parentElement; } return false; };
                            const isCompaniesSection = (el) => { let p = el.parentElement; while (p) { if (p.className && p.className.includes('companies')) return true; p = p.parentElement; } return false; };
                            const isUnwanted = (el) => isSimilarJobsSection(el) || isJobListSection(el) || isCompaniesSection(el);
                            const descSelectors = ['[class*="job-description"]','[class*="JobDescription"]','[data-testid="job-description"]','[class*="jobDetail"]','[class*="job-detail"]','[class*="detailContent"]','[class*="detail-content"]','[class*="Desc_pc_descContent"]'];
                            for (const sel of descSelectors) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwanted(el)) { const text = el.innerText?.trim() || ''; if (text.length > 50 && !isWarningText(text)) { result.description = text; break; } }
                            }
                            if (!result.description) {
                                for (const sel of ['.description','[class*="description"]','[class*="content"]','article','main']) {
                                    const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                    if (el && !isUnwanted(el)) { const text = el.innerText?.trim() || ''; if (text.length > 100 && !isWarningText(text)) { result.description = text; break; } }
                                }
                            }
                            for (const sel of ['[class*="requirement"]','[class*="Requirement"]','[class*="qualification"]','[class*="Qualification"]','[class*="skill"]','[class*="Skill"]']) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwanted(el)) { const text = el.innerText?.trim() || ''; if (text.length > 20 && !isWarningText(text)) { result.requirements = text; break; } }
                            }
                            for (const sel of ['[class*="location"]','[class*="Location"]','[data-testid="location"]','[class*="city"]','[class*="City"]']) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwanted(el)) { const text = el.innerText?.trim() || ''; if (text) { result.location = text; break; } }
                            }
                            for (const sel of ['[class*="salary"]','[class*="Salary"]','[data-testid="salary"]']) {
                                const el = useMainSection ? mainSection.querySelector(sel) : document.querySelector(sel);
                                if (el && !isUnwanted(el)) { const text = el.innerText?.trim() || ''; if (text) { result.salary = text; break; } }
                            }
                            return result;
                        }
                    """)

                    description = detail_data.get('description', '')
                    requirements = detail_data.get('requirements', '')
                    location = detail_data.get('location', '')
                    salary = detail_data.get('salary', '')

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

                    analysis_text = "\n\n".join(filter(None, [description, requirements]))

                    logger.info(f"[FETCH BOSSJOB] Analysis text length: {len(analysis_text)} chars")

                    post_id = item_id if item_id else f"bossjob_{page_num}_{idx}"
                    posts.append({
                        "id": post_id,
                        "title": title,
                        "url": job_url,
                        "company": company,
                        "date": datetime.now(timezone.utc),
                        "text": full_text,
                        "analysis_text": analysis_text,
                        "salary": salary,
                        "location": location,
                        "requirements": requirements,
                        "description": description,
                    })
                    logger.info(f"[FETCH BOSSJOB] ✓ Extracted: {title[:50]}... ({len(full_text)} chars)")

                    await page.keyboard.press('Escape')
                    await asyncio.sleep(batch_delay)

                except Exception as e:
                    logger.warning(f"[FETCH BOSSJOB] Error processing job {idx+1}: {e}")
                    try:
                        await page.keyboard.press('Escape')
                    except Exception:
                        pass
                    continue

            # Navigate to next page
            try:
                next_selectors = [
                    "[class*='Pagination_actionBtn'][style*='rotate(0deg)']",
                    "[class*='Pagination_actionBtn']:not([data-disabled='true'])",
                    "span[class*='Pagination_actionBtn']:last-child",
                    "[class*='Pagination_actionBtn']",
                    "button[class*='next']",
                    "a[class*='next']",
                ]
                next_button = None
                for selector in next_selectors:
                    next_button = await page.query_selector(selector)
                    if next_button:
                        break

                if next_button:
                    is_disabled = await next_button.get_attribute("data-disabled")
                    if is_disabled == "true":
                        logger.info("[FETCH BOSSJOB] Next button disabled, reached last page")
                        break
                    await next_button.click()
                    await asyncio.sleep(batch_delay + 1)
                else:
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
                        await page.click(f"[data-checked='false']:text('{next_page_num}')")
                        await asyncio.sleep(batch_delay + 1)
                    else:
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
