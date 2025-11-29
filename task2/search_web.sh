
#!/bin/bash
python3 web_search.py "retrieval" \
  --pagerank webdata/index/pagerank.json \
  --w1 0.7 --w2 0.3 --top 10 --stem --stopwords stopwords.txt
