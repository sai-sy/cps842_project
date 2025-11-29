#!/usr/bin/env python3
"""Search utilities for the web corpus index."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from porterstemmer import PorterStemmer

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall(text.lower())


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    values = list(scores.values())
    v_min = min(values)
    v_max = max(values)
    if v_max - v_min <= 0:
        return {doc: 1.0 for doc in scores}
    return {doc: (value - v_min) / (v_max - v_min) for doc, value in scores.items()}


def combine_scores(cos_scores, pr_scores, w1, w2):
    if not pr_scores or w2 == 0:
        return cos_scores
    combined = {}
    for doc_id, cos_value in cos_scores.items():
        combined[doc_id] = w1 * cos_value + w2 * pr_scores.get(doc_id, 0.0)
    return combined


class WebSearchEngine:
    def __init__(
        self,
        dict_path: Path,
        postings_path: Path,
        doc_norms_path: Path,
        metadata_path: Path,
        stopwords_path: str | None = None,
        stem: bool = False,
    ) -> None:
        self.dictionary = load_json(dict_path)
        self.postings = load_json(postings_path)
        self.doc_norms = load_json(doc_norms_path)
        self.metadata = load_json(metadata_path)
        self.stopwords = self._load_stopwords(stopwords_path)
        self.stemmer = PorterStemmer() if stem else None
        self.num_docs = len(self.doc_norms)

    def _load_stopwords(self, path: str | None) -> set[str]:
        if not path:
            return set()
        words = set()
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                word = line.strip().lower()
                if word and not word.startswith("#"):
                    words.add(word)
        return words

    def _prepare_tokens(self, text: str) -> List[str]:
        tokens = tokenize(text)
        filtered: List[str] = []
        for token in tokens:
            if token in self.stopwords:
                continue
            if self.stemmer:
                token = self.stemmer.stem(token, 0, len(token) - 1)
            filtered.append(token)
        return filtered

    def search(
        self,
        query: str,
        top_k: int = 10,
        pagerank_path: Path | None = None,
        w1: float = 0.7,
        w2: float = 0.3,
        normalize_pr: bool = True,
    ) -> List[dict]:
        tokens = self._prepare_tokens(query)
        if not tokens:
            return []
        term_freqs = defaultdict(int)
        for token in tokens:
            term_freqs[token] += 1

        query_weights = {}
        query_norm_sum = 0.0
        for term, freq in term_freqs.items():
            entry = self.dictionary.get(term)
            if not entry:
                continue
            tf_weight = 1 + math.log(freq)
            weight = tf_weight * entry["idf"]
            query_weights[term] = weight
            query_norm_sum += weight ** 2

        query_norm = math.sqrt(query_norm_sum)
        if not query_weights or query_norm == 0:
            return []

        scores = defaultdict(float)
        for term, q_weight in query_weights.items():
            postings = self.postings.get(term, [])
            for posting in postings:
                doc_id = posting["doc_id"]
                doc_weight = posting["weight"]
                scores[doc_id] += q_weight * doc_weight

        cos_scores = {}
        for doc_id, numerator in scores.items():
            doc_norm = self.doc_norms.get(doc_id)
            if not doc_norm:
                continue
            cos_scores[doc_id] = numerator / (doc_norm * query_norm)

        pr_scores = {}
        if pagerank_path:
            pr_scores = load_json(pagerank_path)
            if normalize_pr:
                pr_scores = normalize_scores(pr_scores)

        combined_scores = combine_scores(cos_scores, pr_scores, w1, w2)
        ranked = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

        results = []
        for doc_id, score in ranked:
            meta = self.metadata.get(str(doc_id)) or self.metadata.get(doc_id, {})
            result = {
                "doc_id": doc_id,
                "score": score,
                "cosine": cos_scores.get(doc_id, 0.0),
                "pagerank": pr_scores.get(doc_id, 0.0),
                "title": meta.get("title"),
                "url": meta.get("url"),
                "snippet": meta.get("snippet"),
            }
            results.append(result)
        return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search the crawled web index from CLI")
    parser.add_argument("query", help="Query string")
    parser.add_argument("--dict", default="webdata/index/dictionary.json")
    parser.add_argument("--postings", default="webdata/index/postings.json")
    parser.add_argument("--doc-norms", default="webdata/index/doc_norms.json")
    parser.add_argument("--doc-meta", default="webdata/index/documents.json")
    parser.add_argument("--pagerank", default="webdata/index/pagerank.json")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--w1", type=float, default=0.7)
    parser.add_argument("--w2", type=float, default=0.3)
    parser.add_argument("--no-normalize-pr", action="store_true", help="Disable PageRank normalization")
    parser.add_argument("--stopwords", help="Optional stopwords file")
    parser.add_argument("--stem", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = WebSearchEngine(
        dict_path=Path(args.dict),
        postings_path=Path(args.postings),
        doc_norms_path=Path(args.doc_norms),
        metadata_path=Path(args.doc_meta),
        stopwords_path=args.stopwords,
        stem=args.stem,
    )
    results = engine.search(
        args.query,
        top_k=args.top,
        pagerank_path=Path(args.pagerank) if args.pagerank else None,
        w1=args.w1,
        w2=args.w2,
        normalize_pr=not args.no_normalize_pr,
    )
    for idx, result in enumerate(results, start=1):
        print(f"{idx}. {result['title']} ({result['url']}) -> score={result['score']:.4f}")
        print(f"   Cosine={result['cosine']:.4f}, PageRank={result['pagerank']:.4f}")
        print(f"   {result['snippet']}")


if __name__ == "__main__":
    main()
