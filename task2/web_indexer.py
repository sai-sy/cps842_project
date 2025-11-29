#!/usr/bin/env python3
"""Build an inverted index from crawled web pages."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from porterstemmer import PorterStemmer

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return TOKEN_PATTERN.findall(text.lower())


def load_stopwords(path: str | None) -> set[str]:
    if not path:
        return set()
    stopwords = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            word = line.strip().lower()
            if word and not word.startswith("#"):
                stopwords.add(word)
    return stopwords


def read_corpus(path: Path) -> List[dict]:
    corpus: List[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            corpus.append(json.loads(line))
    return corpus


def build_index(
    documents: List[dict],
    stopwords: set[str],
    stemmer: PorterStemmer | None,
) -> Tuple[Dict[str, Dict], Dict[str, List[Dict]], Dict[str, float], Dict[str, Dict]]:
    term_doc_freq: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    doc_norm_sums: Dict[str, float] = defaultdict(float)
    metadata: Dict[str, Dict] = {}

    for doc in documents:
        doc_id = str(doc["doc_id"])
        text_parts = [doc.get("title", ""), doc.get("content", "")]
        tokens = tokenize(" ".join(text_parts))
        filtered: List[str] = []
        for token in tokens:
            if token in stopwords:
                continue
            if stemmer:
                token = stemmer.stem(token, 0, len(token) - 1)
            filtered.append(token)

        for token in filtered:
            term_doc_freq[token][doc_id] += 1

        metadata[doc_id] = {
            "doc_id": doc_id,
            "url": doc.get("url"),
            "title": doc.get("title"),
            "snippet": doc.get("content", "")[:240],
        }

    num_docs = len(documents)
    dictionary: Dict[str, Dict[str, float]] = {}
    postings: Dict[str, List[dict]] = {}

    for term, doc_freqs in term_doc_freq.items():
        df = len(doc_freqs)
        if df == 0:
            continue
        idf = math.log((num_docs + 1) / (df + 1)) + 1
        dictionary[term] = {"df": df, "idf": idf}
        postings_list: List[dict] = []
        for doc_id, tf in doc_freqs.items():
            tf_weight = 1 + math.log(tf)
            weight = tf_weight * idf
            doc_norm_sums[doc_id] += weight ** 2
            postings_list.append({"doc_id": doc_id, "weight": weight})
        postings[term] = sorted(postings_list, key=lambda item: item["weight"], reverse=True)

    doc_norms = {doc_id: math.sqrt(value) for doc_id, value in doc_norm_sums.items() if value > 0}
    return dictionary, postings, doc_norms, metadata


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build inverted index for crawled web corpus")
    parser.add_argument("--input", default="webdata/crawl/pages.jsonl", help="Path to crawled JSONL corpus")
    parser.add_argument("--dict", default="webdata/index/dictionary.json", help="Dictionary output path")
    parser.add_argument("--postings", default="webdata/index/postings.json", help="Postings output path")
    parser.add_argument("--doc-norms", default="webdata/index/doc_norms.json", help="Document norms output path")
    parser.add_argument("--doc-meta", default="webdata/index/documents.json", help="Document metadata output")
    parser.add_argument("--stopwords", help="Optional stopwords file")
    parser.add_argument("--stem", action="store_true", help="Enable Porter stemming")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus_path = Path(args.input)
    documents = read_corpus(corpus_path)
    if not documents:
        raise SystemExit("No documents found in the corpus. Run the crawler first.")

    stopwords = load_stopwords(args.stopwords)
    stemmer = PorterStemmer() if args.stem else None

    dictionary, postings, doc_norms, metadata = build_index(documents, stopwords, stemmer)

    write_json(Path(args.dict), dictionary)
    write_json(Path(args.postings), postings)
    write_json(Path(args.doc_norms), doc_norms)
    write_json(Path(args.doc_meta), metadata)

    print(f"Indexed {len(documents)} documents, vocabulary size {len(dictionary)}")


if __name__ == "__main__":
    main()
