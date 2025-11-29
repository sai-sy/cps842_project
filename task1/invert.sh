#!/bin/bash

echo "Running..."
python3 invert.py cacm.all --dict dict.txt --postings postings.txt --stopwords stopwords.txt --stem
echo "Run complete"
