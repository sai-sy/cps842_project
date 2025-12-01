# CPS842 Final Project Task 2

Saihaan Syed
501105781
saihaan.syed@torontomu.ca

## Task 2: Web Search Engine

The Task 2 deliverable adds a configurable crawler, a JSON-based corpus, a fresh inverted index, PageRank over the crawled graph, and a Flask UI that combines vector-space and link-based scores. The default seed is the Information Retrieval entry on Wikipedia, but any domain can be configured (keep the total corpus size under 5GB so it can be versioned reliably).

All scripts live under `task2/`. Install the extra dependencies once:

```bash
pip3 install -r task2/requirements.txt
```
### Full Run

#### Setup

```bash
./crawl.sh && \ 
./index_web.sh && \
./pagerank_web.sh
```

#### Run CLI or flask

```bash
./search_web.sh
./flaskUp.sh
```

### 1. Crawl at least 500 HTML pages

```bash
cd task2
./crawl.sh
```

- The crawler enforces robots.txt via `RobotFileParser`, applies a configurable politeness delay, and stores one JSON object per line containing `doc_id`, `url`, `title`, `content`, raw `html`, and normalized outlinks.
- Change `--seeds` to target other domains; keep `--allowed-domain` aligned so the crawl stays focused. Stop once ≥500 HTML pages are collected.

#### crawl navigation strategy

the crawler advances in a breadth-first manner. it initializes the frontier queue with every seed url at depth zero, then repeatedly pops the oldest entry so newer links stay in line until earlier ones finish. every url is normalized to strip fragments, screened against the allowed domain, and added to the `discovered` set before insertion so duplicates never balloon the queue.

the crawler stores each visited url in the `visited` set to avoid re-fetching it. whenever a page passes the robots.txt check, the crawler downloads the html, saves the document, and expands normalized outlinks that stay within the allowed domain. each discovered link is appended to the frontier with `depth + 1`, but links beyond `max_depth` are ignored. crawling halts when `max_pages` documents are written or the frontier becomes empty, whichever comes first. the optional delay runs after processing a page so the politeness timer never inflates the per-page parsing time that is reported in the crawl logs.

### 2. Build the inverted index for the web corpus

```bash
./index_web.sh
```

- The indexer tokenizes title + body text, removes stopwords, optionally stems, and writes dictionary/postings/norms/metadata JSON files for downstream components.

Outputs:
- `dictionary.json`: DF + IDF per term.
- `postings.json`: TF-IDF weights per document.
- `doc_norms.json`: vector norms for cosine similarity.
- `documents.json`: metadata (title, URL, snippet).

### 3. Compute PageRank over the crawled link graph

```bash
./pagerank_web.sh
```

- Links are restricted to URLs discovered in the crawl; dangling pages are handled via power iteration with redistribution.

`pagerank.json` maps doc_id → score (normalized to `[0,1]` if `--normalize` is set).

### 4. Query from the CLI (optional)

```bash
./search_web.sh
```

The CLI prints each result with cosine, PageRank, and combined scores. Disable normalization with `--no-normalize-pr` if you want raw PageRank values.

### 5. Launch the web UI

```bash
./flaskUp.sh
```

- Opens `http://127.0.0.1:5000/` with a simple HTML form. Adjust `w1`/`w2` directly in the UI; the app renormalizes weights so they always sum to 1.
- Results display the title, outbound link, snippet, cosine score, PageRank contribution, and overall score.

### Data layout

```
webdata/
  crawl/
    pages.jsonl              # corpus (one JSON per page)
    pages.manifest.json      # crawl metadata and URL mappings
  index/
    dictionary.json
    postings.json
    doc_norms.json
    documents.json
    pagerank.json
```

This layout keeps the generated data under version control (well below the 5GB ceiling) and decouples crawling from indexing/search/UI so each phase can be repeated independently.
