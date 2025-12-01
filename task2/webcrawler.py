#!/usr/bin/env python3
"""Simple polite web crawler for building a custom IR corpus."""

from __future__ import annotations

import argparse
import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

try:
    from bs4 import BeautifulSoup  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise SystemExit("beautifulsoup4 is required. Install via pip install beautifulsoup4") from exc


DEFAULT_SEED = "https://en.wikipedia.org/wiki/Information_retrieval"
DEFAULT_ALLOWED_DOMAIN = "en.wikipedia.org"
USER_AGENT = "CPS842-SearchBot/1.0 (+https://github.com/opencode-project)"


@dataclass
class CrawlConfig:
    """configuration bundle describing seeds, limits, and politeness settings."""

    seeds: List[str]
    max_pages: int
    max_depth: int
    delay: float
    allowed_domain: Optional[str]
    output: Path
    user_agent: str


class WebCrawler:
    """breadth-first crawler that respects robots rules and domain restrictions."""

    def __init__(self, config: CrawlConfig):
        """prepare the http session and bookkeeping structures before crawling."""

        self.config = config
        self.session = requests.Session()
        self.user_agent = config.user_agent
        self.session.headers.update({"User-Agent": self.user_agent})
        # cache robots.txt parsers per host so they can be reused without extra network calls
        self.robot_parsers: Dict[str, RobotFileParser] = {}
        # track urls that have been fetched already so they are never processed twice
        self.visited: Set[str] = set()
        # track urls that are queued but not yet visited to avoid duplicate frontier entries
        self.discovered: Set[str] = set()
        # breadth-first frontier stores (url, depth, parent_url) tuples beginning with the configured seeds
        self.frontier: Deque[Tuple[str, int, Optional[str]]] = deque((seed, 0, None) for seed in config.seeds)
        # ensure the output location exists before streaming jsonl records
        self.output_path = config.output
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        # assign incremental ids to urls as they are written
        self.url_to_id: Dict[str, int] = {}
        self.doc_id_counter = 0
        # timers differentiate between pure processing time and wall-clock time with delays
        self.start_time: Optional[float] = None
        self.total_processing_time = 0.0

    def crawl(self) -> None:
        """perform a breadth-first crawl until the page limit or depth limit is met."""

        self.start_time = time.perf_counter()
        with self.output_path.open("w", encoding="utf-8") as out_file:
            # crawl until the frontier empties or the document budget is reached
            while self.frontier and self.doc_id_counter < self.config.max_pages:
                # pop the oldest frontier entry to maintain breadth-first ordering
                url, depth, parent_url = self.frontier.popleft()

                normalized_url = self._normalize_url(url)
                if not normalized_url:
                    continue
                # ignore urls that were already processed earlier in the crawl
                if normalized_url in self.visited:
                    continue
                # enforce the optional domain guard before spending time on robots or fetches
                if self.config.allowed_domain and urlparse(normalized_url).netloc != self.config.allowed_domain:
                    continue
                # consult robots.txt so the crawler never fetches disallowed pages
                if not self._can_fetch(normalized_url):
                    continue

                # mark the normalized url as visited and begin timing the processing work
                self.visited.add(normalized_url)
                page_start = time.perf_counter()
                # fetch the page and parse outlinks; transient failures are ignored to keep crawling
                try:
                    page_data, outlinks = self._fetch_page(normalized_url)
                except requests.RequestException:
                    continue

                if page_data is None:
                    continue

                title = page_data.get("title", "")
                if self._should_skip_page(title):
                    continue

                # store metadata and text for each successfully parsed document
                self.doc_id_counter += 1
                doc_id = self.doc_id_counter
                self.url_to_id[normalized_url] = doc_id

                record = {
                    "doc_id": doc_id,
                    "url": normalized_url,
                    "title": title,
                    "parent_url": parent_url,
                    "content": page_data["text"],
                    "html": page_data["html"],
                    "links": outlinks,
                }
                out_file.write(json.dumps(record, ensure_ascii=False) + "\n")

                if depth < self.config.max_depth:

                    for link in outlinks:
                        # only follow links that stay inside the allowed domain
                        if self.config.allowed_domain and urlparse(link).netloc != self.config.allowed_domain:
                            continue
                        # prevent duplicates by checking both visited and queued sets
                        if link not in self.visited and link not in self.discovered:
                            self.frontier.append((link, depth + 1, normalized_url))
                            self.discovered.add(link)

                # update processing timers before any politeness delay is applied
                page_duration = time.perf_counter() - page_start
                self.total_processing_time += page_duration
                self._report_progress(doc_id, normalized_url, depth, parent_url, page_duration)

                if self.frontier and self.config.delay > 0:
                    # pause between requests to remain polite toward the destination site
                    time.sleep(self.config.delay)


        self._write_manifest()

    def _fetch_page(self, url: str) -> Tuple[Optional[Dict[str, str]], List[str]]:
        """download html, extract text, and collect normalized outlinks."""

        response = self.session.get(url, timeout=15)
        if response.status_code != 200:
            raise requests.RequestException(f"HTTP {response.status_code}")
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            raise requests.RequestException("Non-HTML content")

        html = response.text
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else url
        text = soup.get_text(" ", strip=True)

        outlinks: List[str] = []
        anchor_root = soup.find("main") or soup
        # restrict navigation map to the main tag when it exists
        for anchor in anchor_root.find_all("a", href=True):
            # skip anchors that live inside navigation, header, or footer regions to avoid boilerplate links
            if anchor.find_parent(["nav", "header", "footer"]):
                continue
            href = anchor.get("href")
            if not href:
                continue
            absolute = urljoin(url, str(href))
            normalized = self._normalize_url(absolute)
            if not normalized:
                continue
            if "user:" in normalized.lower():
                continue
            # keep only normalized http(s) links so later filters can operate reliably
            outlinks.append(normalized)

        return {"title": title, "text": text, "html": html}, outlinks

    def _should_skip_page(self, title: str) -> bool:
        """filter out namespace pages such as Help: or Wikipedia:"""

        normalized = (title or "").lower()
        return "help:" in normalized or "wikipedia:" in normalized

    def _can_fetch(self, url: str) -> bool:
        """consult robots.txt for the url host to decide if fetching is permitted."""

        parsed = urlparse(url)
        netloc = parsed.netloc
        if not netloc:
            return False
        parser = self._get_robot_parser(parsed.scheme or "https", netloc)
        return parser.can_fetch(self.user_agent, url)

    def _get_robot_parser(self, scheme: str, netloc: str) -> RobotFileParser:
        """cache and reuse robot parsers so each host is fetched at most once."""

        parser = self.robot_parsers.get(netloc)
        if parser is not None:
            return parser
        parser = RobotFileParser()
        robots_url = f"{scheme}://{netloc}/robots.txt"
        try:
            # when robots.txt cannot be retrieved the crawler errs on the side of allow all
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                setattr(parser, "allow_all", True)
        except requests.RequestException:
            setattr(parser, "allow_all", True)
        self.robot_parsers[netloc] = parser
        return parser

    @staticmethod
    def _normalize_url(url: str) -> Optional[str]:
        """standardize urls by removing fragments and rejecting non-http schemes."""

        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return None
        # remove fragments
        normalized = parsed._replace(fragment="").geturl()
        return normalized

    def _report_progress(
        self,
        doc_id: int,
        url: str,
        depth: int,
        parent_url: Optional[str],
        page_duration: float,
    ) -> None:
        """emit a concise status line showing queue depth, timing, and lineage."""

        if self.config.max_pages > 0:
            percentage = (doc_id / self.config.max_pages) * 100
        else:
            percentage = 0.0
        parse_elapsed = self.total_processing_time
        if self.start_time is not None:
            wall_elapsed = time.perf_counter() - self.start_time
        else:
            wall_elapsed = parse_elapsed
        status = (
            f"[{doc_id}/{self.config.max_pages}] "
            f"{percentage:.1f}% complete | depth {depth} | frontier {len(self.frontier)}"
        )
        timing = (
            f"page {page_duration:.2f}s excl delay | "
            f"total {parse_elapsed:.2f}s excl delay | "
            f"wall {wall_elapsed:.2f}s incl delay"
        )
        parent = parent_url or "seed"
        print(f"{status} | parent {parent} | {timing} | {url}", flush=True)

    def _write_manifest(self) -> None:
        """persist crawl metadata so later stages can map doc ids back to urls."""

        manifest = {
            "total_documents": self.doc_id_counter,
            "output": str(self.output_path),
            "seeds": self.config.seeds,
            "allowed_domain": self.config.allowed_domain,
            "max_pages": self.config.max_pages,
            "max_depth": self.config.max_depth,
            "delay": self.config.delay,
            "url_to_id": self.url_to_id,
        }
        manifest_path = self.output_path.with_suffix(".manifest.json")
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """collect crawler configuration from command-line flags."""

    parser = argparse.ArgumentParser(description="Polite crawler for Task 2 web search engine")
    parser.add_argument(
        "--seeds",
        nargs="*",
        default=[DEFAULT_SEED],
        help="Seed URLs to start crawling (default: Wikipedia Information Retrieval article)",
    )
    parser.add_argument("--max-pages", type=int, default=600, help="Maximum pages to crawl (default: 600)")
    parser.add_argument("--max-depth", type=int, default=2, help="Maximum crawl depth from the seed (default: 2)")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Delay in seconds between consecutive requests (default: 1.0)",
    )
    parser.add_argument(
        "--allowed-domain",
        default=DEFAULT_ALLOWED_DOMAIN,
        help="Restrict crawling to this domain (default: en.wikipedia.org)",
    )
    parser.add_argument(
        "--output",
        default="webdata/crawl/pages.jsonl",
        help="Path to JSONL file for storing crawled pages (default: webdata/crawl/pages.jsonl)",
    )
    parser.add_argument(
        "--user-agent",
        default=USER_AGENT,
        help="User-Agent header for requests and robots.txt (default: CPS842-SearchBot)",
    )
    return parser.parse_args()


def main() -> None:
    """parse options, execute a crawl, and summarize the result."""

    args = parse_args()
    output_path = Path(args.output)
    config = CrawlConfig(
        seeds=args.seeds,
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        delay=args.delay,
        allowed_domain=args.allowed_domain,
        output=output_path,
        user_agent=args.user_agent,
    )
    crawler = WebCrawler(config)
    crawler.crawl()
    print(f"Crawled {crawler.doc_id_counter} documents. Output written to {output_path}")


if __name__ == "__main__":
    main()
