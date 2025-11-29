# CPS84 A2

Saihaan Syed
501105781
saihaan.syed@torontomu.ca

# Run

Ensure python3, pip3 are available

```bash
pip3 install dotenv
./setup.sh
./invert.sh
./eval.sh
```

## PageRank

Use the citation field (`.X`) from `cacm.all` to generate link-based scores before combining them with the vector-space ranking.

```bash
python3 pagerank.py --input cacm.all --output pagerank.txt --damping 0.85 --max-iter 100 --tol 1e-8
```

The script writes one line per document: `doc_id <TAB> pagerank_score`. Pass `--normalize` to add a third column containing min-max normalized scores (0–1) for easier blending with cosine similarity.

## Search weights

Both the interactive query tool (`index.py`) and evaluator (`eval.py`) accept PageRank-aware parameters:

```bash
python3 index.py --dict dict.txt --postings postings.txt --pagerank pagerank.txt --w1 0.7 --w2 0.3 --normalize-pr
python3 eval.py --pagerank pagerank.txt --w1 0.5 --w2 0.5 --top 10
python3 eval.py --pagerank pagerank.txt --w1 0.7 --w2 0.3 --top 10
```

Ensure that `w1 + w2 = 1`. Use `--normalize-pr` when you want PageRank scores scaled to `[0, 1]` before combining with cosine similarity, which is helpful when the raw PageRank magnitudes are very small.

## Evaluation results

Assignment 2 Step 4 re-run with the PageRank-augmented search (top 10 documents per query):

- `w1=0.5`, `w2=0.5`, normalized PageRank: `MAP = 0.0918`, `Avg R-Precision = 0.1213`, `Avg time = 0.178s`
- `w1=0.7`, `w2=0.3`, normalized PageRank: `MAP = 0.0992`, `Avg R-Precision = 0.1294`, `Avg time = 0.193s`

Use these settings to compare how emphasizing PageRank shifts overall effectiveness.

# Task 2: Web Search Engine

All scripts live under `task2/`. Install the extra dependencies once:

```bash
pip3 install -r task2/requirements.txt
```

## 1. Crawl at least 500 HTML pages

```bash
cd task2
python3 webcrawler.py \
  --seeds https://en.wikipedia.org/wiki/Information_retrieval \
  --max-pages 600 \
  --max-depth 2 \
  --delay 1.5 \
  --allowed-domain en.wikipedia.org \
  --output webdata/crawl/pages.jsonl
```

- The crawler enforces robots.txt via `RobotFileParser`, applies a configurable politeness delay, and stores one JSON object per line containing `doc_id`, `url`, `title`, `content`, raw `html`, and normalized outlinks.
- Change `--seeds` to target other domains; keep `--allowed-domain` aligned so the crawl stays focused. Stop once ≥500 HTML pages are collected.

### crawl navigation strategy

the crawler advances in a breadth-first manner. it initializes the frontier queue with every seed url at depth zero, then repeatedly pops the oldest entry so newer links stay in line until earlier ones finish. every url is normalized to strip fragments, screened against the allowed domain, and added to the `discovered` set before insertion so duplicates never balloon the queue.

the crawler stores each visited url in the `visited` set to avoid re-fetching it. whenever a page passes the robots.txt check, the crawler downloads the html, saves the document, and expands normalized outlinks that stay within the allowed domain. each discovered link is appended to the frontier with `depth + 1`, but links beyond `max_depth` are ignored. crawling halts when `max_pages` documents are written or the frontier becomes empty, whichever comes first. the optional delay runs after processing a page so the politeness timer never inflates the per-page parsing time that is reported in the crawl logs.

## 2. Build the inverted index for the web corpus

```bash
python3 web_indexer.py \
  --input webdata/crawl/pages.jsonl \
  --dict webdata/index/dictionary.json \
  --postings webdata/index/postings.json \
  --doc-norms webdata/index/doc_norms.json \
  --doc-meta webdata/index/documents.json \
  --stopwords ../stopwords.txt \
  --stem
```

- The indexer tokenizes title + body text, removes stopwords, optionally stems, and writes dictionary/postings/norms/metadata JSON files for downstream components.

## 3. Compute PageRank over the crawled link graph

```bash
python3 web_pagerank.py \
  --input webdata/crawl/pages.jsonl \
  --output webdata/index/pagerank.json \
  --damping 0.85 \
  --max-iter 100 \
  --tol 1e-6 \
  --normalize
```

- Links are restricted to URLs discovered in the crawl; dangling pages are handled via power iteration with redistribution.

## 4. Query from the CLI (optional)

```bash
python3 web_search.py "vector space model" \
  --pagerank webdata/index/pagerank.json \
  --w1 0.7 --w2 0.3 --top 10
```

The CLI prints each result with cosine, PageRank, and combined scores. Disable normalization with `--no-normalize-pr` if you want raw PageRank values.

## 5. Launch the web UI

```bash
python3 webapp.py \
  --pagerank webdata/index/pagerank.json \
  --w1 0.7 --w2 0.3 --top 10
```

- Opens `http://127.0.0.1:5000/` with a simple HTML form. Adjust `w1`/`w2` directly in the UI; the app renormalizes weights so they always sum to 1.
- Results display the title, outbound link, snippet, cosine score, PageRank contribution, and overall score.

## Notes & Constraints

- Crawled data is stored as JSONL under `webdata/crawl/` (well under the 5 GB limit for a ~500–600 page crawl).
- All components are Python-based (requests + BeautifulSoup for crawling/parsing, Flask for the UI).
- The crawler is designed to be run offline before demos; the search UI only reads the saved corpus and never re-crawls.

---

# Task 2 – Web Search Engine

The Task 2 deliverable adds a configurable crawler, a JSON-based corpus, a fresh inverted index, PageRank over the crawled graph, and a Flask UI that combines vector-space and link-based scores. The default seed is the Information Retrieval entry on Wikipedia, but any domain can be configured (keep the total corpus size under 5GB so it can be versioned reliably).

## 0. Install dependencies

```bash
pip3 install -r requirements.txt
```

## 1. Crawl (polite + configurable)

```bash
./crawl.sh
```

- Respects robots.txt per domain and applies the requested delay between requests.
- Stores one JSON line per page (HTML, cleaned text, outgoing links) plus a manifest containing crawl metadata + URL→doc_id mapping.
- Change `--seeds`, `--allowed-domain`, or `--max-pages` to focus on a different site or grow the corpus (minimum requirement: 500 HTML pages).

## 2. Build the inverted index

```bash
./index_web.sh
```

Outputs:
- `dictionary.json`: DF + IDF per term.
- `postings.json`: TF-IDF weights per document.
- `doc_norms.json`: vector norms for cosine similarity.
- `documents.json`: metadata (title, URL, snippet).

## 3. Compute PageRank on the crawled graph

```bash
./pagerank_web.sh
```

`pagerank.json` maps doc_id → score (normalized to `[0,1]` if `--normalize` is set).

## 4. Command-line search over the web corpus

```bash
./search_web.sh
```

The CLI prints ranked results with cosine, PageRank, and combined scores. `w1 + w2 = 1` determines how much weight PageRank receives; pass `--no-normalize-pr` to combine raw PageRank magnitudes.

## 5. Web interface

```bash
./flaskUp.sh
```

- Launches a Flask server (default `http://127.0.0.1:5000`).
- The UI exposes query, `w1`, `w2`, and “normalize PageRank” controls, then renders titles/snippets with per-component scores.
- The crawler does **not** run during the demo; regenerate the JSONL corpus ahead of time so the UI stays responsive.

## Data layout

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
