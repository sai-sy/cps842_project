#!/usr/bin/env python3
"""Flask web interface for the custom search engine."""

from __future__ import annotations

import argparse
from pathlib import Path
import importlib.util

from flask import Flask, render_template, request

CURRENT_DIR = Path(__file__).resolve().parent


def _load_engine_class():
    spec = importlib.util.spec_from_file_location("web_search", CURRENT_DIR / "web_search.py")
    if spec is None or spec.loader is None:
        raise ImportError("Cannot locate web_search module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.WebSearchEngine

WebSearchEngine = _load_engine_class()


def create_app(args) -> Flask:
    engine = WebSearchEngine(
        dict_path=Path(args.dict),
        postings_path=Path(args.postings),
        doc_norms_path=Path(args.doc_norms),
        metadata_path=Path(args.doc_meta),
        stopwords_path=args.stopwords,
        stem=args.stem,
    )

    pagerank_path = Path(args.pagerank) if args.pagerank else None

    app = Flask(__name__, template_folder="templates")

    def _get_float(param: str, default: float) -> float:
        try:
            value = request.args.get(param, None)
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    @app.route("/", methods=["GET"])
    def search_view():
        query = request.args.get("q", "")
        w1 = _get_float("w1", args.w1)
        w2 = _get_float("w2", args.w2)
        normalize = request.args.get("normalize", "1") == "1"
        results = []
        if query:
            weight_sum = w1 + w2
            if weight_sum != 0:
                w1_adj = w1 / weight_sum
                w2_adj = w2 / weight_sum
            else:
                w1_adj, w2_adj = 1.0, 0.0
            results = engine.search(
                query,
                top_k=args.top,
                pagerank_path=pagerank_path,
                w1=w1_adj,
                w2=w2_adj,
                normalize_pr=normalize,
            )
        return render_template(
            "search.html",
            query=query,
            results=results,
            w1=w1,
            w2=w2,
            normalize=normalize,
        )

    return app


def parse_args():
    parser = argparse.ArgumentParser(description="Run the Task 2 web search interface")
    parser.add_argument("--dict", default="webdata/index/dictionary.json")
    parser.add_argument("--postings", default="webdata/index/postings.json")
    parser.add_argument("--doc-norms", default="webdata/index/doc_norms.json")
    parser.add_argument("--doc-meta", default="webdata/index/documents.json")
    parser.add_argument("--pagerank", default="webdata/index/pagerank.json")
    parser.add_argument("--stopwords")
    parser.add_argument("--stem", action="store_true")
    parser.add_argument("--w1", type=float, default=0.7)
    parser.add_argument("--w2", type=float, default=0.3)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = create_app(args)
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
