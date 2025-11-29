import argparse
import time
import re
from porterstemmer import PorterStemmer

from search import search

import builtins
from dotenv import load_dotenv
import os
load_dotenv()
ENVIRONMENT = os.getenv("ENVIRONMENT")
def dprint(*args, **kwargs):
    """Prints only if ENVIRONMENT is not 'prod'."""
    if ENVIRONMENT != "prod":
        builtins.print(*args, **kwargs)
def parse_cacm(path):
    docs = {}
    with open(path, encoding='utf-8', errors='ignore') as f:
        doc_id = None
        field = None
        title = ''
        author = ''
        abstract = ''
        for line in f:
            line = line.rstrip() 
            if line.startswith('.I '):
                if doc_id is not None:
                    docs[doc_id] = {'title': title.strip(), 'author': author, 'abstract': abstract.strip()}
                doc_id = int(line.split()[1])
                field = None
                title = ''
                author = ''
                abstract = ''
            elif line.startswith('.T'):
                field = 'title'
            elif line.startswith('.A'):
                field= 'author'
            elif line.startswith('.W'):
                field = 'abstract'
            elif line.startswith('.'):
                field = None
            else:
                if field == 'title':
                    title += ' ' + line
                elif field == 'author':
                    author += ' ' + line
                elif field == 'abstract':
                    abstract += ' ' + line
        if doc_id is not None:
            docs[doc_id] = {'title': title, 'author':author, 'abstract': abstract}
    return docs

def tokenize(text):
    return re.findall(r"\w+", text.lower())

def pretty_print_sim(p):
    print(p['rank'], p['did'], p['title'], p['author'], p['score'], sep='\t')

def process_sim(sim, index, docs):
    dprint('sim', sim)
    did = sim[0]
    doc = docs[int(did)]
    title = doc['title']
    author = doc['author']
    output = {
        'rank': index+1,
        'did': did,
        'doc': doc,
        'score': sim[1],
        'title': title,
        'author': author
    }
    return output

def parse_sorted_sim(sorted_sim, docs):
    processed_sims = []
    for index, sim in enumerate(sorted_sim):
        processed_sims.append(process_sim(sim, index, docs))

    return processed_sims

def preprocess():
    pass 

def main():
    p = argparse.ArgumentParser(description='Interactive query testing for inverted index')
    p.add_argument('--dict', required=True)
    p.add_argument('--postings', required=True)
    p.add_argument('--stopwords')
    p.add_argument('--stem', action='store_true')
    p.add_argument('--pagerank', help='Path to PageRank score file')
    p.add_argument('--w1', type=float, default=1.0, help='Weight for cosine similarity score (default: 1.0)')
    p.add_argument('--w2', type=float, default=0.0, help='Weight for PageRank score (default: 0.0)')
    p.add_argument('--normalize-pr', action='store_true', help='Normalize PageRank values before combining')
    args = p.parse_args()

    weight_sum = args.w1 + args.w2
    if abs(weight_sum - 1.0) > 1e-6:
        p.error('w1 + w2 must equal 1.0')
    if args.w2 > 0 and not args.pagerank:
        p.error('Provide --pagerank when w2 is greater than zero')

    stopwords = set()
    if args.stopwords:
        with open(args.stopwords, encoding='utf-8') as f:
            stopwords = {w.strip().lower() for w in f if w.strip() and not w.startswith('#')}

    stemmer = PorterStemmer() if args.stem else None
    docs = parse_cacm('cacm.all')


    df = {}
    with open(args.dict, encoding='utf-8') as f:
        for line in f:
            term, freq = line.split()
            df[term] = int(freq)

    times = []
    while True:
        query = input("Query term (ZZEND to exit): ").strip().lower()
        if query == 'zzend': break
        query_terms = []
        t0 = time.time()
        if args.stopwords:
            # Split query into words and remove stopwords
            query_terms = [word for word in query.split() if word not in stopwords]
        else:
            query_terms = query.split()
        # If no terms left after removing stopwords
        if not query_terms:
            print("Query contains only stopwords — please enter another query.")
            continue
        query_terms = [stemmer.stem(term, 0, len(term) - 1) if stemmer else term for term in query_terms]
        sorted_sim = search(
            query_terms,
            args.postings,
            pagerank_path=args.pagerank,
            w_cos=args.w1,
            w_pr=args.w2,
            normalize_pr=args.normalize_pr,
        )
        if len(sorted_sim) == 0:
            print('No results')
        else:
            pretty_print_sim({'rank': 0,
                'did': 'DID',
                'doc': 'DOC',
                'score': 'SCORE',
                'title': 'TITLE',
                'author': 'AUTHOR'})
            for k, v in list(docs.items())[134:137]:
                dprint(k, v)
            processed_sims = parse_sorted_sim(sorted_sim, docs)
            for processed_sim in processed_sims:
                pretty_print_sim(processed_sim)
        elapsed = time.time()-t0
        times.append(elapsed)
        print(f"Time taken: {elapsed:.6f} seconds")
        print()
    if times:
        avg = sum(times)/len(times)
        print(f"Average time: {avg:.6f} seconds")

if __name__ == '__main__':
    main()
