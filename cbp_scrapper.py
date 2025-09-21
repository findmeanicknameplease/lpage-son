#!/usr/bin/env python3
# cbp_rulings_master_grabber.py
# Minimalist, stealth-first CBP rulings harvester (NY/HQ).
# - 11s gap between EACH ruling
# - Rotate proxy every 4 rulings
# - Cool down 4 minutes after every 20 rulings (then rotate to a fresh proxy)
# - Safe resume from checkpoint; also skips already-downloaded PDFs

import asyncio, httpx, os, sys, json, random, re, signal, argparse, math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SEARCH_URL = "https://rulings.cbp.gov/api/search"
PDF_URL_TPL = "https://rulings.cbp.gov/api/getdoc/{col}/{year}/{num}.pdf"

# ---------- UA rotation (no mandatory deps) ----------
try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def rand_ua() -> str: return _UA.random
except Exception:
    _FALLBACK_UAS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]
    def rand_ua() -> str: return random.choice(_FALLBACK_UAS)

def base_headers() -> Dict[str, str]:
    return {
        "User-Agent": rand_ua(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(["en-US,en;q=0.9","en-GB,en;q=0.9","en;q=0.9"]),
        "Connection": "keep-alive",
        "Referer": "https://rulings.cbp.gov/",
    }

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
    def __init__(self, proxies: List[str]):
        self.proxies = proxies[:]
        self.idx = -1 if not proxies else random.randrange(0, len(proxies))
    def current(self) -> Optional[str]:
        if not self.proxies: return None
        return self.proxies[self.idx % len(self.proxies)]
    def rotate(self) -> Optional[str]:
        if not self.proxies: return None
        self.idx = (self.idx + 1) % len(self.proxies)
        return self.current()
    def set_idx(self, i: int):
        if self.proxies and i is not None:
            self.idx = i % len(self.proxies)

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
        if isinstance(payload.get("results"), list):
            return payload["results"]
        for v in payload.values():
            if isinstance(v, list) and (not v or isinstance(v[0], dict)):
                return v
    return []

def extract_totals(payload: Dict, page_size: int) -> Tuple[Optional[int], Optional[int]]:
    total_pages = payload.get("totalPages") or payload.get("total_pages")
    total_results = payload.get("totalResults") or payload.get("total")
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
    date_str = item.get("date") or item.get("dateIssued") or item.get("issueDate") or item.get("publicationDate")
    if date_str:
        m = re.search(r"\b(20\d{2}|19\d{2})\b", str(date_str))
        if m: year = int(m.group(1))
    if not number:
        title = item.get("title") or item.get("heading")
        if title:
            m = re.search(r"\b([NH]\d{6})\b", title)  # e.g., N352679 or H350250
            if m: number = m.group(1)
    return number, year

async def fetch_json(client: httpx.AsyncClient, params: Dict, proxy: Optional[str]) -> Dict:
    for attempt in range(1, 6):
        try:
            r = await client.get(SEARCH_URL, params=params, headers=base_headers(), proxy=proxy, timeout=45.0)
            if r.status_code in (429, 403):
                await asyncio.sleep(2.0 * attempt)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            await asyncio.sleep(1.0 * attempt)
    return {}

async def download_pdf(client: httpx.AsyncClient, url: str, dest: Path, proxy: Optional[str]) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    try:
        async with client.stream("GET", url, headers=base_headers(), proxy=proxy, timeout=120.0) as r:
            if r.status_code in (403, 429): return False
            if r.status_code == 404: return False
            r.raise_for_status()
            with open(tmp, "wb") as f:
                async for chunk in r.aiter_bytes():
                    f.write(chunk)
            tmp.replace(dest)
            return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False

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

    async with httpx.AsyncClient(http2=True, follow_redirects=True) as client:
        current_page_items: List[Dict] = []
        total_pages_hint: Optional[int] = None
        total_results_hint: Optional[int] = None
        page_limit = pages if pages and pages > 0 else None

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
                proxy = proxy_cycle.current()
                payload = await fetch_json(client, params, proxy)
                if not payload:
                    print(f"[{col}] page {state['page']}: empty payload; stopping.")
                    break
                total_pages_hint, total_results_hint = extract_totals(payload, page_size)
                if state["page"] == 1:
                    if total_results_hint is not None:
                        print(f"[{col}] term='{term}' total results ≈ {total_results_hint}")
                    if total_pages_hint is not None:
                        print(f"[{col}] term='{term}' pagination target {total_pages_hint} pages")
                if total_pages_hint and state["page"] > total_pages_hint:
                    break
                current_page_items = extract_items(payload)
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
                        # Proxy rotation rule
                        if state["since_rotate"] >= rotate_every:
                            newp = proxy_cycle.rotate()
                            state["since_rotate"] = 0
                            print(f"[{col}] rotated proxy → {newp}")
                        proxy = proxy_cycle.current()

                        ok = await download_pdf(client, pdf_url, dest, proxy)
                        if ok:
                            print(f"[{col}] saved → {dest}")
                        else:
                            print(f"[{col}] fail  → {pdf_url}")

                        # update counters
                        state["processed_total"] += 1
                        state["since_rotate"] += 1
                        state["since_cooldown"] += 1
                        state["proxy_idx"] = proxy_cycle.idx if proxy_cycle.proxies else None
                        save_state(state_path, state)

                        # Cooldown rule
                        if state["since_cooldown"] >= cooldown_every:
                            print(f"[{col}] cooldown {cooldown_secs}s…")
                            await asyncio.sleep(cooldown_secs)
                            # Fresh rotated proxy when cooling ends
                            newp = proxy_cycle.rotate()
                            print(f"[{col}] post-cooldown fresh proxy → {newp}")
                            state["since_cooldown"] = 0
                            state["since_rotate"] = 0
                            state["proxy_idx"] = proxy_cycle.idx if proxy_cycle.proxies else None
                            save_state(state_path, state)

                    # 11s gap after EACH ruling
                    await asyncio.sleep(gap_secs)

            # Next page
            state["page"] += 1
            state["index"] = 0
            current_page_items = []
            save_state(state_path, state)

            if page_limit and state["page"] > page_limit:
                break
            if total_pages_hint and state["page"] > total_pages_hint:
                break

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
    ap.add_argument("--restart", action="store_true", help="Ignore saved state; start fresh (files still skipped if present)")
    args = ap.parse_args()

    install_sigint_handler()
    out_dir = Path(args.out); out_dir.mkdir(parents=True, exist_ok=True)
    state_dir = Path(args.state_dir); state_dir.mkdir(parents=True, exist_ok=True)

    proxies = parse_proxy_file(args.proxy_file)
    proxy_cycle = ProxyCycle(proxies)

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
            )
    asyncio.run(run_all())

if __name__ == "__main__":
    main()
