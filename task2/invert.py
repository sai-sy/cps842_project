#!/usr/bin/env python3

# i have no idea if ^ that s fixinf my bash script 

import argparse
import re
import math
from collections import defaultdict
from typing import Dict, List, Tuple
from porterstemmer import PorterStemmer

def parse_cacm(path, link_relation=5):
    docs = {}
    citations = defaultdict(set)
    with open(path, encoding='utf-8', errors='ignore') as f:
        doc_id = None
        field = None
        title = ''
        author = ''
        abstract = ''
        for line in f:
            line = line.rstrip('\n')
            if line.startswith('.I '):
                if doc_id is not None:
                    docs[doc_id] = {'title': title, 'author': author, 'abstract': abstract}
                doc_id = int(line.split()[1])
                field = None
                title = ''
                author = ''
                abstract = ''
                citations.setdefault(doc_id, set())
            elif line.startswith('.T'):
                field = 'title'
            elif line.startswith('.A'):
                field = 'author'
            elif line.startswith('.W'):
                field = 'abstract'
            elif line.startswith('.X'):
                field = 'citations'
            elif line.startswith('.'):
                field = None
            else:
                if field == 'title':
                    title += ' ' + line
                elif field == 'author':
                    author += ' ' + line
                elif field == 'abstract':
                    abstract += ' ' + line
                elif field == 'citations':
                    if not line.strip():
                        continue
                    parts = re.split(r"\s+", line.strip())
                    if len(parts) < 3:
                        continue
                    try:
                        target = int(parts[0])
                        relation = int(parts[1])
                    except ValueError:
                        continue
                    if relation != link_relation:
                        continue
                    citations.setdefault(doc_id, set()).add(target)
        if doc_id is not None:
            docs[doc_id] = {'title': title, 'author': author, 'abstract': abstract}
    return docs, citations

def tokenize(text):
    return re.findall(r"\w+", text.lower())

def main():
    p = argparse.ArgumentParser(description='Build inverted index from CACM')
    p.add_argument('input', help='cacm.all file')
    p.add_argument('--dict', required=True, help='dictionary output')
    p.add_argument('--postings', required=True, help='postings output')
    p.add_argument('--links', help='output file for citation links')
    p.add_argument('--stopwords', help='stopwords file')
    p.add_argument('--stem', action='store_true', help='enable stemming')
    args = p.parse_args()

    stopwords = set()
    if args.stopwords:
        with open(args.stopwords, encoding='utf-8') as f:
            stopwords = {w.strip().lower() for w in f if w.strip() and not w.startswith('#')}

    stemmer = PorterStemmer() if args.stem else None

    docs, citations = parse_cacm(args.input)
    doc_count = len(docs)
    index = {}

    for doc_id, info in docs.items():
        text = info['title'] + ' ' + info['author'] + info['abstract']
        tokens = tokenize(text)
        pos = 0
        for tok in tokens:
            pos += 1
            if args.stopwords and tok in stopwords:
                continue
            term = stemmer.stem(tok, 0, len(tok)-1) if stemmer else tok
            index.setdefault(term, {}).setdefault(doc_id, []).append(pos)

    terms = sorted(index.keys())
    term_stats = {}
    norm_sums = defaultdict(float)

    for term in terms:
        docs_post = index[term]
        df = len(docs_post)
        idf = math.log(doc_count / df) if df > 0 else 0.0
        term_stats[term] = {}
        for did, positions in docs_post.items():
            positions_sorted = list(positions)
            f = len(positions_sorted)
            tf = 1 + math.log(f) if f > 0 else 0.0
            w = tf * idf
            norm_sums[did] += w ** 2
            term_stats[term][did] = {
                'freq': f,
                'tf': tf,
                'df': df,
                'idf': idf,
                'weight': w,
                'positions': positions_sorted,
            }

    with open(args.dict, 'w', encoding='utf-8') as dictionary_file, open(args.postings, 'w', encoding='utf-8') as postings_file:
        for term in terms:
            docs_post = term_stats[term]
            df = len(docs_post)
            dictionary_file.write(f"{term} {df}\n")
            postings_file.write(term)
            ordered_postings = sorted(
                docs_post.items(),
                key=lambda item: (item[1]['tf'], item[1]['weight'], -item[0]),
                reverse=True,
            )
            for did, data in ordered_postings:
                norm = math.sqrt(norm_sums[did]) if norm_sums[did] > 0 else 0.0
                nw = data['weight'] / norm if norm else 0.0
                postings_file.write(
                    f" {did}:{data['freq']}:{data['tf']:.6f}:{data['df']}:{data['idf']:.6f}:{data['weight']:.6f}:{nw:.6f}:{','.join(map(str, data['positions']))}"
                )
            postings_file.write('\n')

    if args.links:
        with open(args.links, 'w', encoding='utf-8') as link_file:
            for did in sorted(docs.keys()):
                neighbors = sorted(citations.get(did, set()))
                if neighbors:
                    link_file.write(f"{did} {' '.join(map(str, neighbors))}\n")
                else:
                    link_file.write(f"{did}\n")

if __name__ == '__main__':
    main()
