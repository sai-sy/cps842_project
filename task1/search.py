from collections import defaultdict
import math
import builtins
from typing import Dict, Tuple

from dotenv import load_dotenv
import os
load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT")

def dprint(*args, **kwargs):
    """Prints only if ENVIRONMENT is not 'prod'."""
    if ENVIRONMENT != "prod":
        builtins.print(*args, **kwargs)

TOP_K = 10
_PAGERANK_CACHE: Dict[Tuple[str, bool], Dict[str, float]] = {}

def load_pagerank_scores(path: str, normalize: bool) -> Dict[str, float]:
    cache_key = (path, normalize)
    if cache_key in _PAGERANK_CACHE:
        return _PAGERANK_CACHE[cache_key]

    scores: Dict[str, float] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            did = parts[0]
            try:
                score = float(parts[1])
            except ValueError:
                continue
            scores[did] = score

    if normalize and scores:
        values = list(scores.values())
        v_min = min(values)
        v_max = max(values)
        if v_max - v_min > 0:
            scores = {did: (value - v_min) / (v_max - v_min) for did, value in scores.items()}
        else:
            scores = {did: 1.0 for did in scores}

    _PAGERANK_CACHE[cache_key] = scores
    return scores

def combine_scores(sim, pagerank_scores, w_cos, w_pr):
    weight_sum = w_cos + w_pr
    if weight_sum and abs(weight_sum - 1.0) > 1e-6:
        w_cos = w_cos / weight_sum
        w_pr = w_pr / weight_sum

    if not pagerank_scores or w_pr == 0:
        return sim

    combined = {}
    for did, cos_score in sim.items():
        pr_score = pagerank_scores.get(did, 0.0)
        combined[did] = w_cos * cos_score + w_pr * pr_score
    return combined

def evaluateTerm(term, filename):
  term_data = {}
  term_data['postings'] = {}
  with open(filename, 'r', encoding='utf-8') as f:
    for line in f:
      ls = line.strip()
      if not ls:
        continue
      arr = ls.split()
      #dprint(arr[0])
      if arr[0] == term:
        term_data['df'] = int(arr[1].split(':')[3])
        term_data['idf'] = float(arr[1].split(':')[4])
        for doc_num in range(term_data['df']):
          doc_info = arr[doc_num+1].split(':')
          term_data['postings'][doc_info[0]] = {'nw': float(doc_info[6])}
        dprint('term_data', term_data)
        return term_data
  term_data['df'] = 0
  term_data['idf'] = 0
  return term_data
           
def evaluate(query_terms, filename):
  print("query_terms", query_terms)
  vector = defaultdict(float)
  vector['terms'] = defaultdict(float)
  for term in query_terms:
    dprint("term", term)
    vector['terms'][term] = {
      'f': query_terms.count(term),
      'tf': 1 + math.log(query_terms.count(term)) if query_terms.count(term) > 0 else 0,
      **evaluateTerm(term, filename)
    }
    dprint("vector_terms", term, vector['terms'][term])
    vector['terms'][term]['w'] = vector['terms'][term]['tf'] * vector['terms'][term]['idf']
    vector['norm_sums'] += vector['terms'][term]['w'] ** 2
    vector['norm'] = math.sqrt(vector['norm_sums']) if vector['norm_sums'] > 0 else 0.0
    dprint("vector term", term, vector['terms'][term])
  return vector

def compare(query_vector, filename, top_k=TOP_K):
  dprint("query_vector", query_vector)
  sim = defaultdict(float)
  for term in query_vector['terms']:
    dprint('term', term)
    query_vector['terms'][term]['nw'] = query_vector['terms'][term]['w'] / query_vector['norm'] if (query_vector['norm'] and query_vector['norm'] !=  0) else 0.0
    dprint('query_vector_terms_term_nw',term, query_vector['terms'][term]['nw'])
    for index, did in enumerate(query_vector['terms'][term]['postings']):
      dprint('term postings',term, did)
      if index >= top_k:
        query_vector['terms'][term]["k-stop"] = index
        dprint('query_vector_terms_term_k-stop', index)
        break;
      query_vector['terms'][term]['postings'][did]['product'] = query_vector['terms'][term]['postings'][did]['nw'] * query_vector['terms'][term]['nw']
      dprint('qv term didNW, termNW, product', term, query_vector['terms'][term]['postings'][did]['nw'], query_vector['terms'][term]['nw'], query_vector['terms'][term]['postings'][did]['product'])
      sim[did] += query_vector['terms'][term]['postings'][did]['product']
      dprint('sim[did]', sim[did])
  return sim

def search(query_terms, filename, top_k=TOP_K, pagerank_path=None, w_cos=1.0, w_pr=0.0, normalize_pr=True):
  query_vector = evaluate(query_terms, filename)
  sim = compare(query_vector, filename, top_k=top_k)

  pagerank_scores = None
  if pagerank_path and w_pr != 0.0:
    pagerank_scores = load_pagerank_scores(pagerank_path, normalize_pr)

  combined = combine_scores(sim, pagerank_scores, w_cos, w_pr)
  sorted_sim = sorted(combined.items(), key=lambda item: item[1], reverse=True)
  return sorted_sim
