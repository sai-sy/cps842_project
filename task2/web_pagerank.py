#!/usr/bin/env python3
"""Compute PageRank scores for the crawled web corpus."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Set


DocId = str
Graph = Dict[DocId, Set[DocId]]


def load_corpus(path: Path) -> List[dict]:
    documents: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            documents.append(json.loads(line))
    return documents


def build_graph(documents: List[dict]) -> Graph:
    adjacency: Graph = defaultdict(set)
    url_to_id: Dict[str, DocId] = {}
    for doc in documents:
        doc_id = str(doc["doc_id"])
        url = doc.get("url")
        if isinstance(url, str):
            url_to_id[url] = doc_id
        adjacency.setdefault(doc_id, set())

    for doc in documents:
        doc_id = str(doc["doc_id"])
        links = doc.get("links", [])
        for link in links:
            target_id = url_to_id.get(link)
            if target_id and target_id != doc_id:
                adjacency[doc_id].add(target_id)
    return adjacency


def power_iteration(
    doc_ids: Sequence[DocId],
    adjacency: Graph,
    damping: float,
    max_iter: int,
    tol: float,
) -> Dict[DocId, float]:
    n = len(doc_ids)
    if n == 0:
        return {}
    rank = {doc: 1.0 / n for doc in doc_ids}
    for _ in range(max_iter):
        new_rank = {doc: (1.0 - damping) / n for doc in doc_ids}
        dangling_mass = sum(rank[doc] for doc in doc_ids if not adjacency.get(doc))
        dangling_share = damping * dangling_mass / n
        for doc in doc_ids:
            targets = adjacency.get(doc, set())
            if not targets:
                continue
            share = damping * rank[doc] / len(targets)
            for target in targets:
                new_rank[target] = new_rank.get(target, 0.0) + share
        for doc in doc_ids:
            new_rank[doc] = new_rank.get(doc, 0.0) + dangling_share
        delta = sum(abs(new_rank[doc] - rank.get(doc, 0.0)) for doc in doc_ids)
        rank = new_rank
        if delta < tol:
            break
    return rank


def normalize(ranks: Dict[DocId, float]) -> Dict[DocId, float]:
    if not ranks:
        return {}
    values = list(ranks.values())
    v_min = min(values)
    v_max = max(values)
    if v_max - v_min <= 0:
        return {doc: 1.0 for doc in ranks}
    return {doc: (score - v_min) / (v_max - v_min) for doc, score in ranks.items()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PageRank for crawled web corpus")
    parser.add_argument("--input", default="webdata/crawl/pages.jsonl", help="Path to crawled JSONL corpus")
    parser.add_argument("--output", default="webdata/index/pagerank.json", help="Path to store PageRank scores")
    parser.add_argument("--damping", type=float, default=0.85, help="Damping factor (default: 0.85)")
    parser.add_argument("--max-iter", type=int, default=100, help="Maximum iterations (default: 100)")
    parser.add_argument("--tol", type=float, default=1e-6, help="Convergence tolerance (default: 1e-6)")
    parser.add_argument("--normalize", action="store_true", help="Normalize PageRank scores to [0, 1]")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus_path = Path(args.input)
    documents = load_corpus(corpus_path)
    if not documents:
        raise SystemExit("No documents found. Crawl pages before running PageRank.")

    adjacency = build_graph(documents)
    doc_ids = sorted(adjacency.keys())
    ranks = power_iteration(doc_ids, adjacency, args.damping, args.max_iter, args.tol)
    if args.normalize:
        ranks = normalize(ranks)

    output_path = Path(args.output)
    output_path.write_text(json.dumps(ranks, indent=2), encoding="utf-8")
    print(f"Computed PageRank for {len(doc_ids)} documents. Output: {output_path}")


if __name__ == "__main__":
    main()
