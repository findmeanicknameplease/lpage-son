#!/usr/bin/env python3
# cbp_rulings_master_grabber.py
# Minimalist, stealth-first CBP rulings harvester (NY/HQ).
# - 11s gap between EACH ruling
# - Rotate proxy every 4 rulings
# - Cool down 4 minutes after every 20 rulings (then rotate to a fresh proxy)
# - Safe resume from checkpoint; also skips already-downloaded PDFs
#
# Requires: Python 3.11+, httpx>=0.28. Optional: fake-useragent for richer UA rotation.

import asyncio, httpx, sys, json, random, re, signal, argparse, math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

SEARCH_URL = "https://rulings.cbp.gov/api/search"
PDF_URL_TPL = "https://rulings.cbp.gov/api/getdoc/{col}/{year}/{num}.pdf"

# ---------- UA rotation (no mandatory deps) ----------
try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
except Exception:
    _UA = None

_FALLBACK_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

_ACCEPT_LANGS = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-CA,en;q=0.9",
    "en-AU,en;q=0.9",
    "en;q=0.9",
]

JITTER_RATIO = 0.15


def jittered_interval(base: float, ratio: float = JITTER_RATIO) -> float:
    if base <= 0:
        return 0.0
    factor = random.uniform(max(0.0, 1.0 - ratio), 1.0 + ratio)
    return max(0.0, base * factor)

def rand_ua() -> str:
    if _UA is not None:
        try:
            return _UA.random  # type: ignore[attr-defined]
        except Exception:
            pass
    return random.choice(_FALLBACK_UAS)

def base_headers() -> Dict[str, str]:
    try:
        accept_lang = random.choice(_ACCEPT_LANGS)
    except Exception:
        accept_lang = "en-US,en;q=0.9"
    return {
        "User-Agent": rand_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": accept_lang,
        "Connection": "keep-alive",
        "Referer": "https://rulings.cbp.gov/",
    }


def build_client(proxy: Optional[str]) -> httpx.AsyncClient:
    base_kwargs = {
        "http2": False,
        "follow_redirects": True,
        "trust_env": False,
        "timeout": httpx.Timeout(45.0),
    }
    if proxy:
        # Prefer modern httpx API; fall back to transport-based proxy for older versions.
        try:
            return httpx.AsyncClient(proxies=proxy, **base_kwargs)  # type: ignore[arg-type]
        except TypeError:
            transport = httpx.AsyncHTTPTransport(proxy=proxy)
            return httpx.AsyncClient(transport=transport, **base_kwargs)
    return httpx.AsyncClient(**base_kwargs)


async def warmup_client(client: httpx.AsyncClient, label: str) -> bool:
    params = {
        "term": random.choice(["3", "4", "5"]),
        "collection": "NY",
        "commodityGrouping": "ALL",
        "pageSize": "1",
        "page": "1",
        "sortBy": "DATE_DESC",
    }
    try:
        resp = await client.get(SEARCH_URL, params=params, headers=base_headers())
        status = resp.status_code
        if status == 200:
            return True
        if status in (403, 429):
            print(f"[{label}] proxy warmup blocked (HTTP {status})")
            return False
        if 500 <= status < 600:
            print(f"[{label}] proxy warmup server error (HTTP {status})")
            return False
        resp.raise_for_status()
        return True
    except Exception as exc:
        print(f"[{label}] proxy warmup exception: {exc.__class__.__name__}: {exc}")
        return False

# ---------- Proxy cycle ----------
def parse_proxy_file(path: Optional[str]) -> List[str]:
    if not path: return []
    lines = [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")]
    out = []
    for ln in lines:
        parts = ln.split(":")
        if len(parts) == 4:
            host, port, user, pw = parts
            out.append(f"http://{user}:{pw}@{host}:{port}")
        elif len(parts) == 2:
            host, port = parts
            out.append(f"http://{host}:{port}")
    return out

class ProxyCycle:
    def __init__(self, proxies: List[str], max_failures: int = 3):
        self.proxies = proxies[:]
        self.idx = -1 if not proxies else random.randrange(0, len(proxies))
        self.max_failures = max(1, max_failures)
        self.fail_counts = defaultdict(int)
        self.disabled: Set[str] = set()

    def _ensure_index(self) -> Optional[str]:
        if not self.proxies:
            return None
        if self.idx < 0:
            self.idx = 0
        for offset in range(len(self.proxies)):
            i = (self.idx + offset) % len(self.proxies)
            proxy = self.proxies[i]
            if proxy not in self.disabled:
                self.idx = i
                return proxy
        return None

    def current(self) -> Optional[str]:
        return self._ensure_index()

    def rotate(self) -> Optional[str]:
        if not self.proxies:
            return None
        start = (self.idx + 1) if self.idx >= 0 else 0
        for offset in range(len(self.proxies)):
            i = (start + offset) % len(self.proxies)
            proxy = self.proxies[i]
            if proxy not in self.disabled:
                self.idx = i
                return proxy
        self.idx = -1
        return None

    def set_idx(self, i: int):
        if self.proxies and i is not None:
            self.idx = i % len(self.proxies)
            if self.current() is None:
                self.idx = -1

    def has_usable(self) -> bool:
        return any(p not in self.disabled for p in self.proxies)

    def mark_failure(self, proxy: Optional[str], reason: str = ""):
        if not proxy or proxy not in self.proxies:
            return
        self.fail_counts[proxy] += 1
        if self.fail_counts[proxy] >= self.max_failures:
            if proxy not in self.disabled:
                self.disabled.add(proxy)
                msg = f"[proxy] disabling {proxy} after {self.fail_counts[proxy]} failures"
                if reason:
                    msg += f" ({reason})"
                print(msg)

    def mark_success(self, proxy: Optional[str]):
        if not proxy or proxy not in self.proxies:
            return
        self.fail_counts[proxy] = 0
        self.disabled.discard(proxy)

# ---------- State (resume) ----------
def load_state(state_path: Path) -> Dict:
    if state_path.exists():
        try:
            return json.loads(state_path.read_text())
        except Exception:
            pass
    return {
        "collection": None,        # e.g., "NY"
        "term": None,
        "page": 1,                 # current page
        "index": 0,                # index within current page's items
        "processed_total": 0,      # all-time processed within this run scope
        "since_rotate": 0,         # rulings since last proxy rotate
        "since_cooldown": 0,       # rulings since last cooldown
        "proxy_idx": None,         # where we were in the proxy cycle
    }

def save_state(state_path: Path, st: Dict):
    tmp = state_path.with_suffix(".part")
    tmp.write_text(json.dumps(st, indent=2))
    tmp.replace(state_path)

# ---------- API helpers ----------
def extract_items(payload: Dict) -> List[Dict]:
    if isinstance(payload, dict):
        if isinstance(payload.get("rulings"), list):
            return payload["rulings"]
        if isinstance(payload.get("results"), list):
            return payload["results"]
        for v in payload.values():
            if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                return v
    return []

def extract_totals(payload: Dict, page_size: int) -> Tuple[Optional[int], Optional[int]]:
    total_pages = payload.get("totalPages") or payload.get("total_pages")
    total_results = payload.get("totalResults") or payload.get("total") or payload.get("totalHits")
    if not total_pages and total_results is not None:
        try:
            total_pages = math.ceil(int(total_results) / page_size) if page_size else None
        except Exception:
            total_pages = None
    return total_pages, total_results

def get_doc_key(item: Dict) -> Tuple[Optional[str], Optional[int]]:
    number = item.get("number") or item.get("rulingNumber") or item.get("docNumber") or item.get("controlNumber")
    year = None
    # Try date fields, then fallback to title
    date_str = (item.get("rulingDate") or item.get("date") or item.get("dateIssued") or item.get("issueDate") or item.get("publicationDate"))
    if date_str:
        m = re.search(r"\b(20\d{2}|19\d{2})\b", str(date_str))
        if m: year = int(m.group(1))
    if not number:
        title = item.get("title") or item.get("heading")
        if title:
            m = re.search(r"\b([NH]\d{6})\b", title)  # e.g., N352679 or H350250
            if m: number = m.group(1)
    return number, year

async def fetch_json(client: httpx.AsyncClient, params: Dict, label: str, http429_backoff_max: float) -> Tuple[Dict, bool, bool]:
    proxy_issue = False
    throttled_seen = False
    for attempt in range(1, 6):
        try:
            resp = await client.get(SEARCH_URL, params=params, headers=base_headers())
            status = resp.status_code
            if status in (429, 403):
                throttled_seen = True
                wait = jittered_interval(min(float(http429_backoff_max), 2.0 * attempt), ratio=0.25)
                print(f"[{label}] fetch attempt {attempt} throttled (HTTP {status}); sleeping {wait:.1f}s")
                await asyncio.sleep(wait)
                continue
            if 500 <= status < 600:
                wait = jittered_interval(min(30.0, float(2 ** attempt)), ratio=0.25)
                print(f"[{label}] fetch attempt {attempt} server error (HTTP {status}); sleeping {wait:.1f}s")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            try:
                return resp.json(), False, throttled_seen
            except Exception as parse_exc:
                snippet = resp.text[:160].replace("\n", " ")
                print(f"[{label}] JSON parse fallback ({parse_exc.__class__.__name__}): {snippet!r}")
                return json.loads(resp.text), False, throttled_seen
        except httpx.RequestError as exc:
            proxy_issue = True
            wait = jittered_interval(min(30.0, float(2 ** attempt)), ratio=0.25)
            print(f"[{label}] fetch_json network error {exc.__class__.__name__}: {exc}; sleeping {wait:.1f}s")
            await asyncio.sleep(wait)
        except Exception as exc:
            wait = jittered_interval(min(30.0, float(2 ** attempt)), ratio=0.25)
            print(f"[{label}] fetch_json attempt {attempt} error: {exc.__class__.__name__}: {exc}; sleeping {wait:.1f}s")
            await asyncio.sleep(wait)
    print(f"[{label}] fetch_json exhausted retries for params: {params}")
    return {}, proxy_issue, throttled_seen

async def download_pdf(client: httpx.AsyncClient, url: str, dest: Path, label: str, http429_backoff_max: float) -> Tuple[bool, bool, bool]:
    if dest.exists() and dest.stat().st_size > 0:
        return True, False, False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    proxy_issue = False
    throttled_seen = False
    for attempt in range(1, 4):
        try:
            async with client.stream("GET", url, headers=base_headers()) as resp:
                status = resp.status_code
                if status in (403, 429):
                    throttled_seen = True
                    wait = jittered_interval(min(float(http429_backoff_max), 2.0 * attempt), ratio=0.25)
                    print(f"[{label}] download attempt {attempt} throttled (HTTP {status}) for {url}; sleeping {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue
                if status == 404:
                    print(f"[{label}] download not found (HTTP 404) for {url}")
                    return False, False, False
                if 500 <= status < 600:
                    wait = jittered_interval(min(30.0, float(2 ** attempt)), ratio=0.25)
                    print(f"[{label}] download server error (HTTP {status}) for {url}; sleeping {wait:.1f}s")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    async for chunk in resp.aiter_bytes():
                        fh.write(chunk)
                tmp.replace(dest)
                return True, False, throttled_seen
        except httpx.RequestError as exc:
            proxy_issue = True
            tmp.unlink(missing_ok=True)
            wait = jittered_interval(min(30.0, float(2 ** attempt)), ratio=0.25)
            print(f"[{label}] download network error {exc.__class__.__name__} for {url}: {exc}; sleeping {wait:.1f}s")
            await asyncio.sleep(wait)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            wait = jittered_interval(min(30.0, float(2 ** attempt)), ratio=0.25)
            print(f"[{label}] download attempt {attempt} failed for {url}: {exc.__class__.__name__}: {exc}; sleeping {wait:.1f}s")
            await asyncio.sleep(wait)
    return False, proxy_issue, throttled_seen

# ---------- Orchestrator ----------
async def harvest_collection(
    collection: str,
    pages: int,
    term: str,
    page_size: int,
    out_dir: Path,
    proxy_cycle: ProxyCycle,
    state_path: Path,
    cooldown_every: int = 20,
    cooldown_secs: int = 240,
    rotate_every: int = 4,
    gap_secs: int = 11,
    page_fetch_jitter: float = 2.0,
    http429_backoff_max: float = 90.0,
    circuit_breaker: int = 0,
    circuit_sleep: int = 900,
):
    col = collection.upper()
    state = load_state(state_path)
    # Initialize state on first run or if collection/term changed
    if state.get("collection") != col or state.get("term") != term:
        state = {
            "collection": col,
            "term": term,
            "page": 1,
            "index": 0,
            "processed_total": 0,
            "since_rotate": 0,
            "since_cooldown": 0,
            "proxy_idx": proxy_cycle.idx if proxy_cycle.proxies else None,
        }
        save_state(state_path, state)
    # Restore proxy index if any
    if proxy_cycle.proxies and state["proxy_idx"] is not None:
        proxy_cycle.set_idx(state["proxy_idx"])

    client: Optional[httpx.AsyncClient] = None
    current_proxy: Optional[str] = None

    async def acquire_client(reason: str) -> None:
        nonlocal client, current_proxy
        if client:
            await client.aclose()
            client = None
        while True:
            proxy = proxy_cycle.current()
            if proxy:
                candidate = build_client(proxy)
                healthy = await warmup_client(candidate, col)
                if healthy:
                    proxy_cycle.mark_success(proxy)
                    client = candidate
                    current_proxy = proxy
                    state["proxy_idx"] = proxy_cycle.idx
                    save_state(state_path, state)
                    if reason:
                        print(f"[{col}] using proxy {proxy} ({reason})")
                    return
                proxy_cycle.mark_failure(proxy, "warmup")
                await candidate.aclose()
                if not proxy_cycle.has_usable():
                    print(f"[{col}] all proxies disabled; using direct connection.")
                    client = build_client(None)
                    current_proxy = None
                    state["proxy_idx"] = None
                    save_state(state_path, state)
                    return
                proxy_cycle.rotate()
                continue
            else:
                client = build_client(None)
                current_proxy = None
                state["proxy_idx"] = None
                save_state(state_path, state)
                if reason:
                    print(f"[{col}] using direct connection ({reason})")
                return

    current_page_items: List[Dict] = []
    total_pages_hint: Optional[int] = None
    total_results_hint: Optional[int] = None
    page_limit = pages if pages and pages > 0 else None

    # Throttle streak trackers (only increment on 403/429)
    search_throttle_streak = 0
    download_throttle_streak = 0

    try:
        await acquire_client("startup")
        while True:
            if page_limit and state["page"] > page_limit:
                break
            if total_pages_hint and state["page"] > total_pages_hint:
                break
            # Fetch page if needed
            if not current_page_items:
                params = {
                    "term": term,
                    "collection": col,
                    "commodityGrouping": "ALL",
                    "pageSize": str(page_size),
                    "page": str(state["page"]),
                    "sortBy": "DATE_DESC",
                }
                if client is None:
                    await acquire_client("reconnect")
                # Extra jitter before page fetch (search endpoints are sensitive)
                if page_fetch_jitter and page_fetch_jitter > 0:
                    await asyncio.sleep(jittered_interval(float(page_fetch_jitter)))
                payload, proxy_fault, throttled_search = await fetch_json(client, params, col, http429_backoff_max)
                if throttled_search:
                    search_throttle_streak += 1
                else:
                    search_throttle_streak = 0
                if circuit_breaker and search_throttle_streak >= circuit_breaker:
                    cb_wait = jittered_interval(float(circuit_sleep))
                    print(f"[{col}] circuit breaker (search) sleeping {cb_wait:.1f}s…")
                    await asyncio.sleep(cb_wait)
                    search_throttle_streak = 0
                    if proxy_cycle.proxies:
                        proxy_cycle.rotate()
                        await acquire_client("post-circuit")
                if proxy_fault and proxy_cycle.proxies and current_proxy:
                    proxy_cycle.mark_failure(current_proxy, "fetch")
                    proxy_cycle.rotate()
                    await acquire_client("fetch retry")
                    continue
                if not payload:
                    print(f"[{col}] page {state['page']}: empty payload; stopping.")
                    break
                total_pages_hint, total_results_hint = extract_totals(payload, page_size)
                if state["page"] == 1:
                    if total_results_hint is not None:
                        print(f"[{col}] term='{term}' total hits ≈ {total_results_hint}")
                    if total_pages_hint is not None:
                        print(f"[{col}] term='{term}' pagination target {total_pages_hint} pages")
                if total_pages_hint and state["page"] > total_pages_hint:
                    break
                current_page_items = extract_items(payload)
                if current_proxy:
                    proxy_cycle.mark_success(current_proxy)
                if not current_page_items:
                    print(f"[{col}] page {state['page']}: no items; stopping.")
                    break

            # Iterate from current index
            while state["index"] < len(current_page_items):
                item = current_page_items[state["index"]]
                number, year = get_doc_key(item)
                state["index"] += 1  # move pointer ASAP (safety)
                save_state(state_path, state)

                if not number or not year:
                    print(f"[{col}] skip (missing number/year) at page {state['page']} idx {state['index']-1}")
                else:
                    pdf_url = PDF_URL_TPL.format(col=col.lower(), year=year, num=number)
                    dest = out_dir / col / str(year) / f"{number}.pdf"
                    meta_path = dest.with_suffix(".json")
                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        meta_path.write_text(json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2))
                    except Exception as exc:
                        print(f"[{col}] warn metadata write failed for {dest.name}: {exc}")
                    if dest.exists() and dest.stat().st_size > 0:
                        print(f"[{col}] exists: {dest}")
                    else:
                        if (
                            proxy_cycle.proxies
                            and rotate_every > 0
                            and state["since_rotate"] >= rotate_every
                        ):
                            proxy_cycle.rotate()
                            await acquire_client("scheduled rotate")

                        if client is None:
                            await acquire_client("reconnect")
                        ok, proxy_fault, throttled_dl = await download_pdf(client, pdf_url, dest, col, http429_backoff_max)

                        state["processed_total"] += 1
                        state["since_rotate"] += 1
                        state["since_cooldown"] += 1
                        state["proxy_idx"] = proxy_cycle.idx if proxy_cycle.proxies else None
                        save_state(state_path, state)

                        if ok:
                            print(f"[{col}] saved → {dest}")
                            if current_proxy:
                                proxy_cycle.mark_success(current_proxy)
                        else:
                            print(f"[{col}] fail  → {pdf_url}")
                            if proxy_fault:
                                state["index"] = max(0, state["index"] - 1)
                                save_state(state_path, state)
                                if throttled_dl:
                                    download_throttle_streak += 1
                                else:
                                    download_throttle_streak = 0
                                if circuit_breaker and download_throttle_streak >= circuit_breaker:
                                    cb_wait = jittered_interval(float(circuit_sleep))
                                    print(f"[{col}] circuit breaker (download) sleeping {cb_wait:.1f}s…")
                                    await asyncio.sleep(cb_wait)
                                    download_throttle_streak = 0
                                    if proxy_cycle.proxies:
                                        proxy_cycle.rotate()
                                        await acquire_client("post-circuit")
                                if proxy_cycle.proxies and current_proxy:
                                    proxy_cycle.mark_failure(current_proxy, "download")
                                    proxy_cycle.rotate()
                                    await acquire_client("download retry")
                                    await asyncio.sleep(jittered_interval(gap_secs * 0.5))
                                else:
                                    wait = jittered_interval(max(1.0, gap_secs * 0.5))
                                    print(f"[{col}] retrying after {wait:.1f}s (direct connection)")
                                    await asyncio.sleep(wait)
                                continue

                        # Cooldown rule
                        if (
                            cooldown_every > 0
                            and state["since_cooldown"] >= cooldown_every
                        ):
                            cooldown_wait = jittered_interval(float(cooldown_secs))
                            print(f"[{col}] cooldown {cooldown_wait:.1f}s…")
                            await asyncio.sleep(cooldown_wait)
                            if proxy_cycle.proxies:
                                proxy_cycle.rotate()
                                await acquire_client("post-cooldown")
                            state["since_cooldown"] = 0
                            state["since_rotate"] = 0
                            save_state(state_path, state)

                    await asyncio.sleep(jittered_interval(float(gap_secs)))

            # Next page
            state["page"] += 1
            state["index"] = 0
            current_page_items = []
            save_state(state_path, state)

        # Exit conditions handled by loop guards
    finally:
        if client:
            await client.aclose()

def install_sigint_handler():
    def _h(sig, frame):
        print("\n[!] Interrupted. State saved. Bye.")
        sys.exit(1)
    signal.signal(signal.SIGINT, _h)

def main():
    ap = argparse.ArgumentParser(description="CBP Rulings downloader (stealth-mode, resumable).")
    ap.add_argument("--collections", default="NY,HQ", help="Comma list (NY,HQ)")
    ap.add_argument("--pages", type=int, default=0, help="Pages per collection (0 = auto)")
    ap.add_argument("--term", default="3", help="Search term (default '3')")
    ap.add_argument("--page-size", type=int, default=100, help="Page size (default 100)")
    ap.add_argument("--out", default="cbp_rulings_out", help="Output directory")
    ap.add_argument("--proxy-file", default=None, help="Optional proxies file (HOST:PORT or HOST:PORT:USER:PASS)")
    ap.add_argument("--state-dir", default=".cbp_state", help="Where to store checkpoints")
    ap.add_argument("--cooldown-every", type=int, default=20, help="Cooldown after N rulings (default 20)")
    ap.add_argument("--cooldown-secs", type=int, default=240, help="Cooldown duration in seconds (default 240)")
    ap.add_argument("--rotate-every", type=int, default=4, help="Rotate proxy every N rulings (default 4)")
    ap.add_argument("--gap-secs", type=int, default=11, help="Gap between rulings in seconds (default 11)")
    ap.add_argument("--page-fetch-jitter", type=float, default=2.0, help="Extra jitter seconds before each page fetch (default 2.0)")
    ap.add_argument("--http429-backoff-max", type=float, default=90.0, help="Max backoff cap for HTTP 429/403 in seconds (default 90)")
    ap.add_argument("--circuit-breaker", type=int, default=0, help="If >0, sleep after N consecutive 403/429s (default 0=disabled)")
    ap.add_argument("--circuit-sleep", type=int, default=900, help="Circuit breaker sleep in seconds (default 900)")
    ap.add_argument("--check-proxies", action="store_true", help="Check proxies from --proxy-file and exit")
    ap.add_argument("--restart", action="store_true", help="Ignore saved state; start fresh (files still skipped if present)")
    args = ap.parse_args()

    install_sigint_handler()
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = Path(args.state_dir); state_dir.mkdir(parents=True, exist_ok=True)

    proxies = parse_proxy_file(args.proxy_file)
    proxy_cycle = ProxyCycle(proxies)

    async def proxy_check_flow():
        def mask_proxy(p: str) -> str:
            try:
                # http://user:pass@host:port -> mask user:pass
                m = re.match(r"^(https?://)?([^:/@]+):([^@]+)@(.+)$", p)
                if m:
                    scheme = m.group(1) or ""
                    user = m.group(2)
                    hostpart = m.group(4)
                    return f"{scheme}{user}:****@{hostpart}"
                return p
            except Exception:
                return p

        if not proxies:
            print("[CHECK] No proxies loaded. Provide --proxy-file.")
            return
        ok = blocked = server_err = errors = 0
        params = {
            "term": random.choice(["3", "4", "5"]),
            "collection": "NY",
            "commodityGrouping": "ALL",
            "pageSize": "1",
            "page": "1",
            "sortBy": "DATE_DESC",
        }
        for i, proxy in enumerate(proxies, 1):
            label = f"P{i:03d}"
            mp = mask_proxy(proxy)
            client = build_client(proxy)
            t0 = asyncio.get_event_loop().time()
            status = None
            err = None
            try:
                resp = await client.get(SEARCH_URL, params=params, headers=base_headers())
                status = resp.status_code
            except Exception as exc:
                err = f"{exc.__class__.__name__}: {exc}"
            finally:
                try:
                    await client.aclose()
                except Exception:
                    pass
            ms = int((asyncio.get_event_loop().time() - t0) * 1000)
            if status == 200:
                ok += 1
                print(f"[CHECK] {label} {mp} -> OK {ms}ms")
            elif status in (403, 429):
                blocked += 1
                print(f"[CHECK] {label} {mp} -> BLOCKED HTTP {status} {ms}ms")
            elif status is not None and 500 <= status < 600:
                server_err += 1
                print(f"[CHECK] {label} {mp} -> SERVER_ERR HTTP {status} {ms}ms")
            elif status is not None:
                errors += 1
                print(f"[CHECK] {label} {mp} -> FAIL HTTP {status} {ms}ms")
            else:
                errors += 1
                print(f"[CHECK] {label} {mp} -> ERROR {err} {ms}ms")
        total = ok + blocked + server_err + errors
        print(f"[CHECK] Summary: total={total} ok={ok} blocked={blocked} server_err={server_err} other={errors}")

    if args.check_proxies:
        asyncio.run(proxy_check_flow())
        return

    # Collections are processed sequentially to honor exact pacing rules.
    collections = [c.strip().upper() for c in args.collections.split(",") if c.strip()]
    term_slug = re.sub(r"[^0-9A-Za-z]+", "_", args.term).strip("_") or "blank"
    async def run_all():
        for col in collections:
            state_path = state_dir / f"state_{col}_{term_slug}.json"
            if args.restart and state_path.exists():
                state_path.unlink(missing_ok=True)
            await harvest_collection(
                collection=col,
                pages=args.pages,
                term=args.term,
                page_size=args.page_size,
                out_dir=out_dir,
                proxy_cycle=proxy_cycle,
                state_path=state_path,
                cooldown_every=args.cooldown_every,
                cooldown_secs=args.cooldown_secs,
                rotate_every=args.rotate_every,
                gap_secs=args.gap_secs,
                page_fetch_jitter=args.page_fetch_jitter,
                http429_backoff_max=args.http429_backoff_max,
                circuit_breaker=args.circuit_breaker,
                circuit_sleep=args.circuit_sleep,
            )
    asyncio.run(run_all())

if __name__ == "__main__":
    main()
