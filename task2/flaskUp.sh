
#!/bin/bash
python3 webapp.py \
  --pagerank webdata/index/pagerank.json \
  --w1 0.7 --w2 0.3 --top 10 --stem --stopwords stopwords.txt
