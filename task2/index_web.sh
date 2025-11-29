#!/bin/bash

python3 web_indexer.py \
  --input webdata/crawl/pages.jsonl \
  --dict webdata/index/dictionary.json \
  --postings webdata/index/postings.json \
  --doc-norms webdata/index/doc_norms.json \
  --doc-meta webdata/index/documents.json \
  --stopwords stopwords.txt --stem
