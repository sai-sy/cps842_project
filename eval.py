#!/usr/bin/env python3

import argparse
import re
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple

from search import search
import time
from dotenv import load_dotenv
import os
load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT")

def dprint(*args, **kwargs):
    """Prints only if ENVIRONMENT is not 'prod'."""
    if ENVIRONMENT != "prod":
        builtins.print(*args, **kwargs)

QueryMap = Dict[int, str]
RelevanceMap = Dict[int, List[int]]
SearchResult = Sequence[Tuple[str, float]]


def tokenize(text: str) -> List[str]:
    """Tokenize a query string using word characters and lowercasing."""
    return re.findall(r"\w+", text.lower())


def parse_queries(path: str) -> QueryMap:
    """Parse query text file into a mapping of query id to query string."""
    queries: QueryMap = {}
    current_id: int | None = None
    collecting = False
    buffer: List[str] = []

    with open(path, encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.startswith(".I"):
                if current_id is not None:
                    queries[current_id] = " ".join(buffer).strip()
                parts = line.split()
                current_id = int(parts[1]) if len(parts) > 1 else None
                buffer = []
                collecting = False
            elif line.startswith(".W"):
                collecting = True
            elif line.startswith("."):
                collecting = False
            elif collecting:
                buffer.append(line.strip())

    if current_id is not None and current_id not in queries:
        queries[current_id] = " ".join(buffer).strip()

    return queries


def parse_qrels(path: str) -> RelevanceMap:
    """Parse qrels file into mapping of query id to ordered relevant doc ids."""
    qrels: RelevanceMap = defaultdict(list)
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                qid = int(parts[0])
                doc_id = int(parts[1])
            except ValueError:
                continue
            qrels[qid].append(doc_id)
    return qrels


def unique_preserve_order(items: Iterable[int]) -> List[int]:
    seen: set[int] = set()
    ordered: List[int] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def average_precision(results: SearchResult, relevant_docs: Sequence[int]) -> float:
    relevant = unique_preserve_order(relevant_docs)
    if not relevant:
        return 0.0

    relevant_set = set(relevant)
    hits = 0
    precision_sum = 0.0

    for rank, (doc_id, _score) in enumerate(results, start=1):
        try:
            doc_num = int(doc_id)
        except ValueError:
            continue
        if doc_num in relevant_set:
            hits += 1
            precision_sum += hits / rank

    return precision_sum / len(relevant)


def r_precision(results: SearchResult, relevant_docs: Sequence[int]) -> float:
    relevant = unique_preserve_order(relevant_docs)
    r = len(relevant)
    if r == 0:
        return 0.0

    relevant_set = set(relevant)
    hits = 0

    for idx in range(r):
        if idx >= len(results):
            break
        try:
            doc_num = int(results[idx][0])
        except ValueError:
            continue
        if doc_num in relevant_set:
            hits += 1

    return hits / r


def evaluate(queries: QueryMap, qrels: RelevanceMap, postings_path: str, top_k: int) -> Tuple[float, float]:
    ap_values: List[float] = []
    r_precision_values: List[float] = []
    times = []
    for qid, query_text in queries.items():
        print("Query ID:", qid)
        t0 = time.time()

        tokens = tokenize(query_text)
        results = search(tokens, postings_path, top_k=top_k)
        truncated_results = results
        relevant_docs = qrels.get(qid, [])
        ap = average_precision(truncated_results, relevant_docs)
        print("Average Precision", ap)
        ap_values.append(ap)
        rp = r_precision(truncated_results, relevant_docs)
        print("R-Precision", rp)
        r_precision_values.append(rp)
        elapsed = time.time()-t0
        times.append(elapsed)
        print('Duration: ', elapsed)
        print('')

    map_value = sum(ap_values) / len(ap_values) if ap_values else 0.0
    mean_r_precision = sum(r_precision_values) / len(r_precision_values) if r_precision_values else 0.0
    return map_value, mean_r_precision, times


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality using MAP and R-Precision.")
    parser.add_argument("--queries", default="query.text", help="Path to query file (default: query.text)")
    parser.add_argument("--qrels", default="qrels.text", help="Path to qrels file (default: qrels.text)")
    parser.add_argument("--postings", default="postings.txt", help="Path to postings file (default: postings.txt)")
    parser.add_argument("--top", type=int, default=5, help="Number of top documents to evaluate (default: 5)")
    args = parser.parse_args()

    queries = parse_queries(args.queries)
    qrels = parse_qrels(args.qrels)
    map_value, mean_r_precision, times = evaluate(queries, qrels, args.postings, args.top)

    print(f"MAP: {map_value:.4f}")
    print(f"Average R-Precision: {mean_r_precision:.4f}")
    print(f"Average time: {sum(times)/len(times):.6f} seconds")



if __name__ == "__main__":
    main()
