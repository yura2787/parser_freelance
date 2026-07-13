#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import gzip
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from bs4 import BeautifulSoup
except ImportError as exc:
    raise SystemExit("Install dependencies first: pip install -r requirements.txt") from exc

try:
    from telethon import TelegramClient
except ImportError:
    TelegramClient = None


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
SEEN_PATH = OUTPUT_DIR / "seen.json"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    kind: str
    url: str
    enabled: bool = True
    query: str = ""
    quality: str = "A"
    note: str = ""


@dataclass
class Deal:
    title: str
    source: str
    url: str
    budget: str = ""
    description: str = ""
    source_id: str = ""
    posted_hint: str = ""
    tags: list[str] = field(default_factory=list)
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_step: str = ""


SOURCES: list[Source] = [
    Source("freelancer_scraping", "Freelancer.com - scraping", "freelancer_api", "https://www.freelancer.com/api/projects/0.1/projects/active/", query="web scraping data extraction python"),
    Source("freelancer_telegram", "Freelancer.com - bot/API projects", "freelancer_api", "https://www.freelancer.com/api/projects/0.1/projects/active/", query="telegram bot bot api"),
    Source("freelancer_automation", "Freelancer.com - automation/API", "freelancer_api", "https://www.freelancer.com/api/projects/0.1/projects/active/", query="automation api integration zapier make n8n"),
    Source("freelancer_ai", "Freelancer.com - AI agents", "freelancer_api", "https://www.freelancer.com/api/projects/0.1/projects/active/", query="openai chatgpt llm ai agent"),
    Source("freelancer_chrome", "Freelancer.com - Chrome extensions", "freelancer_api", "https://www.freelancer.com/api/projects/0.1/projects/active/", query="chrome extension browser automation"),
    Source("freelancer_dashboard", "Freelancer.com - dashboards/CRM", "freelancer_api", "https://www.freelancer.com/api/projects/0.1/projects/active/", query="crm dashboard automation"),
    Source("pph_tech", "PeoplePerHour - Technology", "peopleperhour", "https://www.peopleperhour.com/freelance-jobs/technology-programming"),
    Source("pph_coding", "PeoplePerHour - Programming & Coding", "peopleperhour", "https://www.peopleperhour.com/freelance-jobs/technology-programming/programming-coding"),
    Source("pph_data", "PeoplePerHour - Data Science", "peopleperhour", "https://www.peopleperhour.com/freelance-jobs/technology-programming/data-science-analysis"),
    Source("pph_web", "PeoplePerHour - Website Development", "peopleperhour", "https://www.peopleperhour.com/freelance-jobs/technology-programming/website-development"),
    Source("algora", "Algora bounties", "generic_cards", "https://algora.io/bounties"),
    Source("tg_freelanceroff", "Telegram - Freelancer.com live projects", "telegram_web", "https://t.me/s/Freelanceroff", note="unofficial Freelancer.com project feed"),
    Source("tg_react_upwork", "Telegram - React/Next.js Upwork Jobs", "telegram_web", "https://t.me/s/ReactUpworkJobs", note="Upwork-like project posts, good dev fit"),
    Source("tg_react_gigs", "Telegram - React Freelance Jobs/Gigs", "telegram_web", "https://t.me/s/applyfirst_to_reactjs_jobs", note="React/Node project posts"),
    Source("tg_upwork_projects", "Telegram - Upwork Projects", "telegram_web", "https://t.me/s/upWorkPojects", note="Upwork project feed"),
    Source("tg_upwork_webdev", "Telegram - Upwork WebDev Projects", "telegram_web", "https://t.me/s/upworkwd", note="Web-dev Upwork project feed"),
    Source("tg_freelancermap", "Telegram - Freelancermap IT projects", "telegram_web", "https://t.me/s/freelancermap", note="IT projects, often contract-heavy"),
    Source("laborx_tg", "Telegram - LaborX Web3 Jobs", "telegram_web", "https://t.me/s/laborxWeb3Jobs", enabled=False, quality="C", note="web3/crypto; disabled — off your Python stack"),
    Source("remoteweb3_tg", "Telegram - Remote Web3/AI Jobs", "telegram_web", "https://t.me/s/remoteweb3jobs", enabled=False, quality="C", note="mostly jobs; disabled by default"),
    Source("unicast_tg", "Telegram - Unicast Web3 Jobs", "telegram_web", "https://t.me/s/unicastjobs", enabled=False, quality="C", note="mostly jobs; disabled by default"),
    Source("bossjob_tg", "Telegram - Bossjob Remote/Web3", "telegram_web", "https://t.me/s/jobs", enabled=False, quality="C", note="mostly jobs; disabled by default"),
    Source("ddevjobs_tg", "Telegram - Web3 Developer Jobs", "telegram_web", "https://t.me/s/ddevjobs", enabled=False, quality="C", note="mostly jobs; disabled by default"),
    Source("cryptojobslist_tg", "Telegram - CryptoJobsList", "telegram_web", "https://t.me/s/CryptoJobsList", enabled=False, quality="C", note="mostly jobs; disabled by default"),
    Source("remotecrypto_tg", "Telegram - Remote Crypto Jobs", "telegram_web", "https://t.me/s/remotejobshg", enabled=False, quality="C", note="mostly jobs; disabled by default"),
    Source("remotejobs_tg", "Telegram - Remote Jobs", "telegram_web", "https://t.me/s/RemoteJobss", enabled=False, quality="C", note="broad remote jobs; disabled by default"),
    Source("jobicy_tg", "Telegram - Jobicy", "telegram_web", "https://t.me/s/jobicy", enabled=False, quality="C", note="remote jobs; disabled by default"),
    # Good watchlist, but not enabled for demo until a dedicated parser/login flow exists.
    Source("twine", "Twine freelance jobs", "generic_cards", "https://www.twine.net/jobs", enabled=False, quality="B", note="good marketplace, parser needs more tuning"),
    Source("workana", "Workana IT projects", "generic_cards", "https://www.workana.com/jobs?category=it-programming", enabled=False, quality="B", note="good projects, multilingual noise"),
    Source("guru", "Guru programming projects", "generic_cards", "https://www.guru.com/d/jobs/c/programming-development/", enabled=False, quality="B", note="old-school marketplace, parser needs tuning"),
    Source("contra", "Contra opportunities", "manual", "https://contra.com/features/find-freelance-jobs", enabled=False, quality="A", note="high quality, account/login; manual or browser flow"),
    Source("braintrust", "Braintrust freelance contracts", "manual", "https://www.usebraintrust.com/test-product-form", enabled=False, quality="A", note="high-ticket contracts, not quick scraping"),
    Source("dework", "Dework bounties", "generic_cards", "https://dework.xyz/explore", enabled=False, quality="B", note="dynamic app; likely needs API/browser"),
    Source("gitcoin", "Gitcoin bounties", "manual", "https://gitcoin.co/mechanisms/bounties", enabled=False, quality="B", note="bounty concept, discovery needs separate flow"),
    Source("onlydust", "OnlyDust rewards", "manual", "https://www.onlydust.com/", enabled=False, quality="B", note="OSS rewards, not always direct freelance"),
    Source("github_bounties", "GitHub bounty issues", "manual", "https://api.github.com/search/issues", enabled=False, quality="B", note="needs curated repo list"),
    Source("malt", "Malt freelance", "manual", "https://www.malt.com/", enabled=False, quality="B", note="good EU marketplace, login/geography"),
    Source("yuno_juno", "YunoJuno freelance", "manual", "https://www.yunojuno.com/", enabled=False, quality="B", note="good marketplace, mostly account flow"),
]


RELEVANT_TERMS = {
    # AI / automation — strong freelance fit
    "ai": 2,
    "ai agent": 10,
    "automation": 10,
    "automate": 8,
    "api": 8,
    "integration": 7,
    "webhook": 8,
    # Scraping / data collection
    "web scraping": 10,
    "scraper": 10,
    "data extraction": 10,
    # Telegram bots
    "telegram bot": 12,
    "bot": 6,
    # Python backend stack — your core
    "python": 8,
    "django": 10,
    "fastapi": 10,
    "drf": 6,
    "celery": 8,
    "redis": 6,
    "rabbitmq": 6,
    "postgres": 6,
    "websocket": 7,
    "backend": 6,
    "full stack": 5,
    "microservice": 6,
    "node": 5,
    # Integrations you list on your resume
    "google sheets": 8,
    "notion": 6,
    "slack": 6,
    "stripe": 7,
    # Product types you build
    "chrome extension": 8,
    "browser extension": 8,
    "dashboard": 8,
    "crm": 7,
    "web app": 7,
    "e-commerce": 6,
    "ecommerce": 6,
    "shopify": 5,
    "website": 4,
    "html": 3,
    "mvp": 8,
    "saas": 8,
    # LLM providers
    "openai": 8,
    "llm": 8,
    # No-code automation platforms
    "make.com": 8,
    "zapier": 8,
    "n8n": 8,
    # Infra / cloud / deploy
    "docker": 5,
    "devops": 5,
    "aws": 5,
    "gcp": 5,
    "cloud": 4,
    "nginx": 5,
    "ci/cd": 5,
    "github actions": 5,
    "developer": 4,
    # Email / notifications / real-time messaging
    "email": 4,
    "smtp": 6,
    "mailing": 5,
    "newsletter": 5,
    "notification": 5,
    "chat": 4,
    "real-time": 5,
    "realtime": 5,
    # Scraping tools
    "selenium": 7,
    "playwright": 7,
    "puppeteer": 6,
    # Scheduling / reports
    "cron": 6,
    "schedule": 5,
    "report": 4,
    # Payments (beyond stripe)
    "payment": 5,
    "paypal": 6,
    "checkout": 5,
    # Databases
    "sql": 4,
    "database": 4,
}

CORE_TERMS = {
    "ai agent",
    "automation",
    "automate",
    "api",
    "integration",
    "webhook",
    "web scraping",
    "scraper",
    "data extraction",
    "telegram bot",
    "bot",
    "python",
    "django",
    "fastapi",
    "drf",
    "celery",
    "redis",
    "rabbitmq",
    "postgres",
    "websocket",
    "backend",
    "full stack",
    "microservice",
    "node",
    "google sheets",
    "notion",
    "slack",
    "stripe",
    "developer",
    "chrome extension",
    "browser extension",
    "dashboard",
    "crm",
    "web app",
    "e-commerce",
    "ecommerce",
    "shopify",
    "website",
    "html",
    "devops",
    "mvp",
    "saas",
    "openai",
    "llm",
    "make.com",
    "zapier",
    "n8n",
    "docker",
    "aws",
    "gcp",
    "nginx",
    "ci/cd",
    "github actions",
    "smtp",
    "newsletter",
    "notification",
    "real-time",
    "selenium",
    "playwright",
    "puppeteer",
    "cron",
    "schedule",
    "payment",
    "paypal",
    "checkout",
    "database",
}

PROJECT_TERMS = [
    "freelance opportunity",
    "freelance",
    "contract",
    "fixed",
    "fixed price",
    "hourly",
    "budget",
    "bounty",
    "project",
    "proposal",
    "remote",
]

HARD_REJECT = [
    "full time",
    "full-time",
    "office",
    "onsite",
    "on-site",
    "hybrid",
    "internship",
    "recruiter",
    "recruiters needed",
    "voice recording",
    "record voice",
    "voice talent",
    "video editing",
    "video editor",
    "youtube-ready",
    "graphic designer",
    "logo",
    "ebook",
    "translation",
    "translator",
    "typing",
    "retyping",
    "ms word",
    "copywriting",
    "article writing",
    "followers",
    "buy facebook",
    "buy usa facebook",
    "selling",
    "sell seconds",
    "token for sale",
    "onlyfans",
    "adult",
    "casino",
    "gambling",
    "sniper bot",
    "trading bot",
    "pump.fun",
    "hacker",
    "fashion",
    "beachwear",
    "designer needed",
    "ios",
    "swift",
    "testflight",
    "roomplan",
    "arkit",
    "native ios",
    "join our team",
    "long term partnership",
    "senior professional",
    "technical leadership",
    "team coordination",
]

LOW_VALUE_TERMS = [
    "elementor",
    "wordpress bug",
    "portfolio made",
    "bug fixing",
    "small fix",
    "consultation",
]


def load_env(path: str | None = None) -> None:
    env_path = Path(path).expanduser() if path else ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", clean(text).lower()).strip()


def has(text: str, term: str) -> bool:
    return term in text


def fetch_text(url: str, timeout: int = 20, retries: int = 2) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/json,*/*",
        "Accept-Encoding": "gzip",
    }
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            # 4xx = the page is gone/blocked; retrying wastes time, fail fast.
            if 400 <= exc.code < 500:
                raise
            last_error = exc
        except Exception as exc:  # noqa: BLE001 - retry any transient network error
            last_error = exc
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise last_error if last_error else RuntimeError(f"failed to fetch {url}")


_CURRENCY_CODES = "usd|eur|gbp|inr|aud|cad|sgd"
BUDGET_RE_LABELED = re.compile(
    rf"(?:budget|pay|reward|bounty|💰)\s*(?:range)?\s*:?\s*"
    rf"([£€$₹]?\s?[0-9][0-9,.kK]*(?:\s?(?:{_CURRENCY_CODES}))?"
    rf"(?:\s?[-–]\s?[£€$₹]?\s?[0-9][0-9,.kK]*(?:\s?(?:{_CURRENCY_CODES}))?)?)",
    re.I,
)
BUDGET_RE_BARE = re.compile(
    rf"([£€$₹]\s?[0-9][0-9,.kK]*(?:\s?[-–]\s?[£€$₹]?\s?[0-9][0-9,.kK]*)?"
    rf"|[0-9][0-9,.kK]*\s?(?:{_CURRENCY_CODES})(?:\s?[-–]\s?[0-9][0-9,.kK]*\s?(?:{_CURRENCY_CODES}))?)",
    re.I,
)


def extract_budget(text: str) -> str:
    match = BUDGET_RE_LABELED.search(text) or BUDGET_RE_BARE.search(text)
    return clean(match.group(1)) if match else ""


def fetch_freelancer(source: Source, per_source: int) -> list[Deal]:
    params = {
        "query": source.query,
        "limit": str(per_source),
        "full_description": "true",
        "job_details": "true",
    }
    data = json.loads(fetch_text(f"{source.url}?{urllib.parse.urlencode(params)}"))
    deals: list[Deal] = []
    for project in data.get("result", {}).get("projects", []):
        currency = project.get("currency") or {}
        budget = project.get("budget") or {}
        sign = clean(currency.get("sign") or currency.get("code"))
        minimum = budget.get("minimum")
        maximum = budget.get("maximum")
        project_type = clean(project.get("type") or "project")
        money = ""
        if minimum is not None or maximum is not None:
            money = f"{sign}{minimum or '?'}-{maximum or '?'} {project_type}".strip()
        if project.get("hourly_project_info"):
            money = f"{money} hourly".strip()
        tags = [clean(job.get("name")) for job in project.get("jobs") or [] if isinstance(job, dict)]
        bid_stats = project.get("bid_stats") or {}
        if bid_stats.get("bid_count") is not None:
            tags.append(f"{bid_stats['bid_count']} bids")
        seo_url = clean(project.get("seo_url"))
        url = f"https://www.freelancer.com/projects/{seo_url}" if seo_url else "https://www.freelancer.com/projects/"
        deals.append(
            Deal(
                title=clean(project.get("title")),
                source=source.name,
                source_id=source.id,
                url=url,
                budget=money,
                description=clean(project.get("description") or project.get("preview_description")),
                tags=[tag for tag in tags if tag],
            )
        )
    return deals


def fetch_peopleperhour(source: Source, per_source: int) -> list[Deal]:
    soup = BeautifulSoup(fetch_text(source.url), "html.parser")
    deals: list[Deal] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        title = clean(anchor.get_text(" ", strip=True))
        if "peopleperhour.com/freelance-jobs/" not in href:
            continue
        if len(title) < 18 or title.lower() in {"technology & programming"}:
            continue
        if href in seen:
            continue
        seen.add(href)
        card = anchor
        for parent in anchor.parents:
            classes = " ".join(parent.get("class", []))
            if parent.name == "li" or "item--container" in classes:
                card = parent
                break
        card_text = clean(card.get_text(" ", strip=True))
        budget_match = re.search(r"([£€$]\s?[0-9][0-9,.]*(?:\s?[/a-zA-Z]+)?)", card_text)
        deals.append(
            Deal(
                title=title,
                source=source.name,
                source_id=source.id,
                url=href,
                budget=clean(budget_match.group(1)) if budget_match else "",
                description=card_text,
            )
        )
        if len(deals) >= per_source:
            break
    return deals


def fetch_telegram_web(source: Source, per_source: int) -> list[Deal]:
    soup = BeautifulSoup(fetch_text(source.url), "html.parser")
    deals: list[Deal] = []
    for message in soup.select(".tgme_widget_message")[-per_source * 2 :]:
        text_node = message.select_one(".tgme_widget_message_text")
        if not text_node:
            continue
        text = clean(text_node.get_text(" ", strip=True))
        if not text:
            continue
        title = text.split("💰")[0].split("\n")[0][:140].strip(" -")
        link_node = message.select_one("a.tgme_widget_message_date")
        deals.append(
            Deal(
                title=title or source.name,
                source=source.name,
                source_id=source.id,
                url=link_node["href"] if link_node and link_node.has_attr("href") else source.url,
                budget=extract_budget(text),
                description=text,
            )
        )
    return deals[:per_source]


def source_to_telegram_handle(source: Source) -> str:
    parsed = urllib.parse.urlparse(source.url)
    handle = parsed.path.strip("/").split("/")[-1]
    if handle == "s":
        return ""
    return handle.removeprefix("@")


async def fetch_telegram_session_sources(sources: list[Source], per_source: int) -> list[Deal]:
    if TelegramClient is None:
        raise RuntimeError("Telethon is not installed. Run: pip install -r requirements.txt")

    api_id_raw = env_first("TELEGRAM_API_ID", "API_ID")
    api_hash = env_first("TELEGRAM_API_HASH", "API_HASH")
    if not api_id_raw or not api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required for --use-telegram-session")

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise RuntimeError("TELEGRAM_API_ID must be an integer") from exc

    session_path = Path(env_first("TELEGRAM_SESSION_PATH", "USER_SESSION_PATH") or "sessions/freelance_user")
    if not session_path.is_absolute():
        session_path = ROOT / session_path
    session_path.parent.mkdir(parents=True, exist_ok=True)

    phone = env_first("TELEGRAM_PHONE", "PHONE") or None
    client = TelegramClient(str(session_path), api_id, api_hash)
    await client.start(phone=phone)

    deals: list[Deal] = []
    try:
        for source in sources:
            handle = source_to_telegram_handle(source)
            if not handle:
                continue
            print(f"[source] {source.name} (telegram session)", file=sys.stderr)
            try:
                entity = await client.get_entity(handle)
            except Exception as exc:
                print(f"[warn] {source.id}: could not resolve @{handle}: {exc}", file=sys.stderr)
                continue

            async for message in client.iter_messages(entity, limit=per_source):
                text = clean(getattr(message, "message", "") or "")
                if not text:
                    continue
                title = text.split("💰")[0].split("\n")[0][:140].strip(" -")
                deals.append(
                    Deal(
                        title=title or source.name,
                        source=source.name,
                        source_id=source.id,
                        url=f"https://t.me/{handle}/{message.id}",
                        budget=extract_budget(text),
                        description=text,
                    )
                )
    finally:
        await client.disconnect()
    return deals


def fetch_generic_cards(source: Source, per_source: int) -> list[Deal]:
    soup = BeautifulSoup(fetch_text(source.url), "html.parser")
    deals: list[Deal] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        title = clean(anchor.get_text(" ", strip=True))
        if len(title) < 18 or len(title) > 170:
            continue
        href = urllib.parse.urljoin(source.url, anchor["href"])
        if href in seen:
            continue
        seen.add(href)
        card = anchor
        for _ in range(4):
            if card.parent is None:
                break
            card = card.parent
        text = clean(card.get_text(" ", strip=True))
        budget_match = re.search(r"([£€$][0-9][0-9,.kK]*)", text)
        deals.append(
            Deal(
                title=title,
                source=source.name,
                source_id=source.id,
                url=href,
                budget=budget_match.group(1) if budget_match else "",
                description=text,
            )
        )
        if len(deals) >= per_source:
            break
    return deals


FETCHERS = {
    "freelancer_api": fetch_freelancer,
    "peopleperhour": fetch_peopleperhour,
    "telegram_web": fetch_telegram_web,
    "generic_cards": fetch_generic_cards,
}


def budget_usd_estimate(budget: str) -> float | None:
    if not budget:
        return None
    lower = budget.lower()
    symbol_rates = {"$": 1.0, "€": 1.08, "£": 1.27, "₹": 0.012}
    code_rates = {"usd": 1.0, "eur": 1.08, "gbp": 1.27, "inr": 0.012, "aud": 0.66, "cad": 0.73, "sgd": 0.75}
    symbol_match = re.search(r"([£€$₹])", budget)
    if symbol_match:
        amounts = [float(value.replace(",", "")) for value in re.findall(r"[0-9][0-9,.]*", budget)]
        if not amounts:
            return None
        return max(amounts) * symbol_rates.get(symbol_match.group(1), 1.0)
    code_match = re.search(r"\b(usd|eur|gbp|inr|aud|cad|sgd)\b", lower)
    if code_match:
        amounts = [float(value.replace(",", "")) for value in re.findall(r"[0-9][0-9,.]*", lower)]
        if not amounts:
            return None
        return max(amounts) * code_rates.get(code_match.group(1), 1.0)
    return None


def score_deal(deal: Deal) -> Deal:
    text = norm(" ".join([deal.title, deal.budget, deal.description, " ".join(deal.tags)]))
    reject_hits = [term for term in HARD_REJECT if has(text, term)]
    relevant_hits = [term for term, _ in RELEVANT_TERMS.items() if has(text, term)]
    core_hits = [term for term in CORE_TERMS if has(text, term)]
    project_hits = [term for term in PROJECT_TERMS if has(text, term)]
    low_hits = [term for term in LOW_VALUE_TERMS if has(text, term)]
    budget_estimate = budget_usd_estimate(deal.budget)

    score = 20
    score += sum(RELEVANT_TERMS[term] for term in relevant_hits)
    score += min(14, len(project_hits) * 4)
    if deal.budget:
        score += 18
    if budget_estimate is not None:
        if budget_estimate >= 500:
            score += 18
        elif budget_estimate >= 150:
            score += 10
        elif budget_estimate >= 100:
            score += 8
        elif budget_estimate >= 50:
            score += 3
        elif budget_estimate < 40:
            score -= 18
            deal.risks.append("low budget")
    score -= len(reject_hits) * 60
    score -= len(low_hits) * 12
    if not relevant_hits:
        score -= 35
    if not core_hits:
        score -= 50
        deal.risks.append("weak relevance")
    if not project_hits and deal.source_id not in {"algora"}:
        score -= 25

    deal.reasons = sorted(set(core_hits + project_hits[:4]))[:8]
    deal.risks.extend(reject_hits[:6])
    if low_hits:
        deal.risks.extend(low_hits[:3])
    deal.score = max(0, min(100, score))
    deal.next_step = next_step_for(deal, text)
    return deal


def next_step_for(deal: Deal, text: str) -> str:
    if any(term in text for term in ["web scraping", "scraper", "data extraction"]):
        return "Зайти с мини-планом: источник данных -> частота -> формат результата -> быстрый PoC за 1 день."
    if any(term in text for term in ["automation", "api", "integration", "make.com", "zapier", "n8n"]):
        return "Предложить discovery: какие API есть, какой ручной процесс убираем, какой первый результат за 24-48 часов."
    if any(term in text for term in ["telegram bot", "bot", "mini app"]):
        return "Спросить сценарий, роли пользователей, команды бота и предложить короткую схему MVP."
    if any(term in text for term in ["dashboard", "power bi", "crm"]):
        return "Показать структуру дашборда: источники данных, метрики, обновление, роли, первый экран."
    return "Открыть оригинал, проверить клиента/бюджет и написать персональный отклик без авто-спама."


def collect(sources: list[Source], per_source: int, workers: int = 8) -> list[Deal]:
    active = [s for s in sources if s.enabled and s.kind in FETCHERS]

    def work(source: Source) -> list[Deal]:
        print(f"[source] {source.name}", file=sys.stderr)
        try:
            return FETCHERS[source.kind](source, per_source)
        except Exception as exc:
            print(f"[warn] {source.id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return []

    deals: list[Deal] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        for raw in executor.map(work, active):
            for deal in raw:
                deals.append(score_deal(deal))
    return dedupe(deals)


def deal_key(deal: Deal) -> str:
    return re.sub(r"[^a-z0-9]+", "", (deal.url or deal.title).lower())


def dedupe(deals: list[Deal]) -> list[Deal]:
    best: dict[str, Deal] = {}
    for deal in deals:
        key = deal_key(deal)
        current = best.get(key)
        if current is None or deal.score > current.score:
            best[key] = deal
    return list(best.values())


def load_seen() -> dict[str, str]:
    if not SEEN_PATH.exists():
        return {}
    try:
        data = json.loads(SEEN_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_seen(seen: dict[str, str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")


SEEN_TTL_DAYS = 30


def mark_seen(deals: list[Deal]) -> None:
    seen = load_seen()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=SEEN_TTL_DAYS)

    # Drop entries older than the TTL so seen.json does not grow forever.
    fresh: dict[str, str] = {}
    for key, stamp in seen.items():
        try:
            if datetime.fromisoformat(stamp) >= cutoff:
                fresh[key] = stamp
        except ValueError:
            fresh[key] = stamp

    now_iso = now.isoformat()
    for deal in deals:
        fresh[deal_key(deal)] = now_iso
    save_seen(fresh)


def score_badge(score: int) -> str:
    if score >= 75:
        return "🟢"
    if score >= 55:
        return "🟡"
    return "🟠"


def format_card(deal: Deal, index: int) -> str:
    reasons = ", ".join(deal.reasons) if deal.reasons else "-"
    risks = ", ".join(sorted(set(deal.risks))) if deal.risks else "нет явных"
    budget = deal.budget or "не указан"
    return (
        f"🔥 EN Freelance Deal #{index}\n\n"
        f"{deal.title}\n"
        f"Источник: {deal.source}\n"
        f"Бюджет: {budget}\n"
        f"Score: {deal.score}/100\n\n"
        f"Почему похоже на заказ:\n{reasons}\n\n"
        f"Риски:\n{risks}\n\n"
        f"Как зайти:\n{deal.next_step}\n\n"
        f"Ссылка: {deal.url}"
    )


def format_card_html(deal: Deal, index: int) -> str:
    esc = html.escape
    reasons = esc(", ".join(deal.reasons)) if deal.reasons else "-"
    risks = esc(", ".join(sorted(set(deal.risks)))) if deal.risks else "нет явных"
    budget = esc(deal.budget) if deal.budget else "не указан"
    title = esc(deal.title) or "(без названия)"
    url = esc(deal.url)
    return (
        f"{score_badge(deal.score)} <b>Deal #{index} · {deal.score}/100</b>\n\n"
        f"<b><a href=\"{url}\">{title}</a></b>\n\n"
        f"💰 <b>Бюджет:</b> {budget}\n"
        f"📡 <b>Источник:</b> {esc(deal.source)}\n\n"
        f"✅ <b>Почему подходит:</b> {reasons}\n"
        f"⚠️ <b>Риски:</b> {risks}\n\n"
        f"🚀 <b>Как зайти:</b> {esc(deal.next_step)}"
    )


def send_telegram(deals: list[Deal], dry_run: bool) -> int:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or os.getenv("BOT_TOKEN", "").strip()
    chat_id = (
        os.getenv("TELEGRAM_CHAT_ID", "").strip()
        or os.getenv("TELEGRAM_TARGET_CHAT_ID", "").strip()
        or os.getenv("TARGET_USER_ID", "").strip()
    )
    if not token or not chat_id:
        print("[info] Telegram env not found; printing dry-run cards.", file=sys.stderr)
        dry_run = True

    if dry_run:
        for index, deal in enumerate(deals, 1):
            print("\n--- TELEGRAM CARD ---")
            print(format_card(deal, index))
        return 0

    sent = 0
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for index, deal in enumerate(deals, 1):
        payload = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": format_card_html(deal, index)[:4000],
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            urllib.request.urlopen(req, timeout=20).read()
            sent += 1
        except Exception as exc:  # noqa: BLE001 - one bad card must not stop the batch
            print(f"[warn] telegram send failed for deal #{index}: {exc}", file=sys.stderr)
        time.sleep(0.5)
    print(f"[telegram] sent {sent}/{len(deals)}", file=sys.stderr)
    return sent


def write_output(deals: list[Deal]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "deal_radar_latest.json").write_text(
        json.dumps([asdict(deal) for deal in deals], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [f"# Deal Radar latest — {datetime.now(timezone.utc).isoformat()}", ""]
    for index, deal in enumerate(deals, 1):
        lines.append(f"## {index}. {deal.title}")
        lines.append(f"- Source: {deal.source}")
        lines.append(f"- Budget: {deal.budget or '-'}")
        lines.append(f"- Score: {deal.score}/100")
        lines.append(f"- Reasons: {', '.join(deal.reasons) if deal.reasons else '-'}")
        lines.append(f"- Risks: {', '.join(sorted(set(deal.risks))) if deal.risks else '-'}")
        lines.append(f"- Link: {deal.url}")
        lines.append("")
    (OUTPUT_DIR / "deal_radar_latest.md").write_text("\n".join(lines), encoding="utf-8")


def audit_sources() -> None:
    print(f"{len(SOURCES)} sources audit")
    print("-" * 92)
    for source in SOURCES:
        status = "ON " if source.enabled else "OFF"
        print(f"{status} | {source.quality} | {source.id:16} | {source.name:36} | {source.kind:14} | {source.note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram-first foreign freelance deal radar.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--per-source", type=int, default=12)
    parser.add_argument("--min-score", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--telegram", action="store_true")
    parser.add_argument("--audit-sources", action="store_true")
    parser.add_argument("--env-file", help="Optional .env with TELEGRAM_BOT_TOKEN/BOT_TOKEN and TELEGRAM_CHAT_ID/TARGET_USER_ID.")
    parser.add_argument("--telegram-only", action="store_true", help="Scan only Telegram sources.")
    parser.add_argument("--use-telegram-session", action="store_true", help="Read Telegram sources through a user session instead of public t.me/s pages.")
    parser.add_argument("--clean-only", action="store_true", help="Hide cards with any risk flags.")
    parser.add_argument("--min-budget", type=int, default=0, help="Drop deals whose parsed budget (USD estimate) is below this. 0 = off.")
    parser.add_argument("--workers", type=int, default=8, help="Parallel workers for fetching sources.")
    parser.add_argument("--all", action="store_true", help="Include deals already seen in previous runs.")
    parser.add_argument("--forget", action="store_true", help="Clear the 'already seen' memory and exit.")
    args = parser.parse_args()
    load_env(args.env_file)

    if args.forget:
        if SEEN_PATH.exists():
            SEEN_PATH.unlink()
        print("[ok] cleared seen memory.")
        return

    if args.audit_sources:
        audit_sources()
        return

    selected_sources = [source for source in SOURCES if not args.telegram_only or source.kind == "telegram_web"]
    if args.use_telegram_session:
        web_sources = [source for source in selected_sources if source.kind != "telegram_web"]
        telegram_sources = [source for source in selected_sources if source.kind == "telegram_web" and source.enabled]
        deals = collect(web_sources, args.per_source, args.workers)
        try:
            session_deals = asyncio.run(fetch_telegram_session_sources(telegram_sources, args.per_source))
        except RuntimeError as exc:
            raise SystemExit(
                f"[error] {exc}\n"
                "[hint] Copy .env.example to .env and fill TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE."
            )
        deals.extend(score_deal(deal) for deal in session_deals)
        deals = dedupe(deals)
    else:
        deals = collect(selected_sources, args.per_source, args.workers)
    deals = [deal for deal in deals if deal.score >= args.min_score]
    if args.clean_only:
        deals = [deal for deal in deals if not deal.risks]
    if args.min_budget > 0:
        deals = [
            deal
            for deal in deals
            if (estimate := budget_usd_estimate(deal.budget)) is None or estimate >= args.min_budget
        ]
    deals.sort(key=lambda item: (item.score, budget_usd_estimate(item.budget) or 0.0), reverse=True)

    if not args.all:
        seen = load_seen()
        fresh = [deal for deal in deals if deal_key(deal) not in seen]
        skipped = len(deals) - len(fresh)
        if skipped:
            print(f"[info] skipped {skipped} already-seen deals (use --all to include them).", file=sys.stderr)
        deals = fresh

    deals = deals[: args.limit]
    write_output(deals)

    if args.telegram or args.dry_run:
        send_telegram(deals, dry_run=args.dry_run)
    else:
        for index, deal in enumerate(deals, 1):
            print(f"{index}. {deal.score}/100 | {deal.budget or '-'} | {deal.title}")
            print(f"   {deal.source} | {deal.url}")
            print(f"   why: {', '.join(deal.reasons) if deal.reasons else '-'}")
            print(f"   next: {deal.next_step}")

    if deals and not args.dry_run:
        mark_seen(deals)
    print(f"[done] shown={len(deals)} output={OUTPUT_DIR / 'deal_radar_latest.md'}", file=sys.stderr)


if __name__ == "__main__":
    main()
