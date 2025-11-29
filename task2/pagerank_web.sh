#!/bin/bash
python3 web_pagerank.py \
  --input webdata/crawl/pages.jsonl \
  --output webdata/index/pagerank.json \
  --damping 0.85 --max-iter 100 --normalize
