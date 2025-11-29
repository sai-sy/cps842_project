#!/bin/bash

python3 pagerank.py --input cacm.all --output pagerank.txt --damping 0.85 --max-iter 100 --tol 1e-8

