#!/bin/bash

python3 webcrawler.py \
  --seeds https://en.wikipedia.org/wiki/Information_retrieval \
  --allowed-domain en.wikipedia.org \
  --max-pages 100 \
  --max-depth 2 \
  --delay 0.25 \
  --output webdata/crawl/pages.jsonl
