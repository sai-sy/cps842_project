#!/usr/bin/env python3
"""Compute PageRank scores for the CACM citation graph."""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Set, Tuple


DocId = int
Graph = Dict[DocId, Set[DocId]]


def parse_citations(path: str, relation_code: int = 5) -> Tuple[List[DocId], Graph]:
    """Parse CACM .X fields and return document ids and outlink graph."""
    adjacency: Graph = defaultdict(set)
    doc_ids: List[DocId] = []
    doc_set: Set[DocId] = set()
    current_doc: DocId | None = None
    field: str | None = None

    # read the collection and capture citation edges for the desired relation
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if line.startswith(".I "):
                # register each document id as we encounter new records
                parts = line.split()
                if len(parts) > 1:
                    current_doc = int(parts[1])
                    if current_doc not in doc_set:
                        doc_ids.append(current_doc)
                        doc_set.add(current_doc)
                    adjacency.setdefault(current_doc, set())
                field = None
            elif line.startswith(".X"):
                # note that following lines belong to the citation field
                field = "citations"
            elif line.startswith("."):
                field = None
            else:
                if field != "citations" or current_doc is None:
                    continue
                stripped = line.strip()
                if not stripped:
                    continue
                # extract cited target and relation code from the triplet
                parts = stripped.split()
                if len(parts) < 3:
                    continue
                try:
                    target = int(parts[0])
                    relation = int(parts[1])
                except ValueError:
                    continue
                # skip entries whose relation code is not the desired link type
                if relation != relation_code:
                    continue
                adjacency.setdefault(current_doc, set()).add(target)
                if target not in doc_set:
                    doc_ids.append(target)
                    doc_set.add(target)
                    adjacency.setdefault(target, set())

    # keep ids sorted for deterministic downstream processing
    doc_ids.sort()
    return doc_ids, adjacency


def power_iteration(
    doc_ids: Sequence[DocId],
    adjacency: Graph,
    damping: float,
    max_iter: int,
    tol: float,
) -> Tuple[Dict[DocId, float], int, float]:
    """Run PageRank power iteration until convergence or max iterations."""
    n = len(doc_ids)
    if n == 0:
        return {}, 0, 0.0

    # start from uniform probability distribution over all nodes
    rank = {doc: 1.0 / n for doc in doc_ids}
    iteration = 0
    delta = float("inf")

    # iterate until change is below tolerance or max iterations reached
    while iteration < max_iter and delta > tol:
        iteration += 1
        # initialize next vector with random jump probability
        new_rank = {doc: (1.0 - damping) / n for doc in doc_ids}
        # capture total weight sitting on dangling nodes and redistribute evenly
        dangling_mass = sum(rank[doc] for doc in doc_ids if not adjacency.get(doc))
        dangling_share = damping * dangling_mass / n

        # push damped probability mass across each outgoing edge
        for doc in doc_ids:
            targets = adjacency.get(doc)
            if not targets:
                continue
            share = damping * rank[doc] / len(targets)
            for target in targets:
                if target not in new_rank:
                    # target outside known docs, create entry to keep mass
                    new_rank[target] = (1.0 - damping) / n + dangling_share
                new_rank[target] += share

        # add redistributed dangling mass back to every node
        for doc in doc_ids:
            new_rank[doc] += dangling_share

        # measure convergence in l1 norm before next iteration
        delta = sum(abs(new_rank.get(doc, 0.0) - rank.get(doc, 0.0)) for doc in doc_ids)
        rank = new_rank

    return rank, iteration, delta


def normalize_scores(ranks: Dict[DocId, float]) -> Dict[DocId, float]:
    # guard against empty graphs that would break scaling math
    if not ranks:
        return {}
    values = list(ranks.values())
    v_min = min(values)
    v_max = max(values)
    if v_max - v_min <= 0.0:
        return {doc: 1.0 for doc in ranks}
    return {doc: (score - v_min) / (v_max - v_min) for doc, score in ranks.items()}


def write_scores(
    path: str,
    doc_ids: Sequence[DocId],
    ranks: Dict[DocId, float],
    normalized: Dict[DocId, float] | None = None,
) -> None:
    # emit each document id with its raw (and optional normalized) rank value
    with open(path, "w", encoding="utf-8") as handle:
        for doc in doc_ids:
            score = ranks.get(doc, 0.0)
            if normalized is not None:
                norm_score = normalized.get(doc, 0.0)
                handle.write(f"{doc}\t{score:.12f}\t{norm_score:.12f}\n")
            else:
                handle.write(f"{doc}\t{score:.12f}\n")


def parse_args() -> argparse.Namespace:
    # configure cli flags for pagerank computation
    parser = argparse.ArgumentParser(description="Compute PageRank for CACM citations")
    parser.add_argument("--input", default="cacm.all", help="Path to CACM collection (default: cacm.all)")
    parser.add_argument("--output", default="pagerank.txt", help="Output file for PageRank scores")
    parser.add_argument("--relation", type=int, default=5, help="Relation code to keep from .X field (default: 5)")
    parser.add_argument("--damping", type=float, default=0.85, help="Damping factor (default: 0.85)")
    parser.add_argument("--max-iter", type=int, default=100, help="Maximum iterations (default: 100)")
    parser.add_argument("--tol", type=float, default=1e-6, help="Convergence tolerance for L1 delta (default: 1e-6)")
    parser.add_argument("--normalize", action="store_true", help="Write normalized scores (extra column)")
    return parser.parse_args()


def main() -> None:
    # parse inputs, build citation graph, and run pagerank
    args = parse_args()
    doc_ids, adjacency = parse_citations(args.input, relation_code=args.relation)
    if not doc_ids:
        raise SystemExit("No documents found in input; cannot compute PageRank")

    ranks, iterations, delta = power_iteration(
        doc_ids,
        adjacency,
        damping=args.damping,
        max_iter=args.max_iter,
        tol=args.tol,
    )

    # optionally normalize ranks before writing them to disk
    normalized = normalize_scores(ranks) if args.normalize else None
    write_scores(args.output, doc_ids, ranks, normalized)

    print(f"Processed {len(doc_ids)} documents")
    print(f"Iterations: {iterations}")
    print(f"Final delta: {delta:.6e}")
    print(f"Output written to {args.output}")
    if args.normalize:
        print("Normalized scores included as third column")


if __name__ == "__main__":
    main()
