#!/bin/bash

echo "Running index.py..."
python3 index.py --dict dict.txt --postings postings.txt --stopwords stopwords.txt --stem
echo "Run index.py complete"