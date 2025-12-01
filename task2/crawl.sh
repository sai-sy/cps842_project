#!/bin/bash

python3 webcrawler.py \
  --seeds https://en.wikipedia.org/wiki/Information_retrieval \
  --max-pages 600 \
  --max-depth 2 \
  --delay 0.25 \
  --allowed-domain en.wikipedia.org \
  --output webdata/crawl/pages.jsonl
