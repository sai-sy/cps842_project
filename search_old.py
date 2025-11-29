from collections import defaultdict
import math
import builtins

from dotenv import load_dotenv
import os
load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT")

def dprint(*args, **kwargs):
    """Prints only if ENVIRONMENT is not 'prod'."""
    if ENVIRONMENT != "prod":
        builtins.print(*args, **kwargs)

TOP_K = 10

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

def search(query_terms, filename, top_k=TOP_K):
  query_vector = evaluate(query_terms, filename)
  sim = compare(query_vector, filename)
  sorted_sim = sorted(sim.items(), key=lambda item: item[1], reverse=True)
  return sorted_sim