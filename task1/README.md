# CPS842 Final Project Task 1

Saihaan Syed
501105781
saihaan.syed@torontomu.ca

# Run

Ensure python3, pip3 are available

```bash
pip3 install dotenv
./setup.sh
./invert.sh
./eval.sh
```

## PageRank

Use the citation field (`.X`) from `cacm.all` to generate link-based scores before combining them with the vector-space ranking.

```bash
python3 pagerank.py --input cacm.all --output pagerank.txt --damping 0.85 --max-iter 100 --tol 1e-8
```

The script writes one line per document: `doc_id <TAB> pagerank_score`. Pass `--normalize` to add a third column containing min-max normalized scores (0–1) for easier blending with cosine similarity.

## Search weights

Both the interactive query tool (`index.py`) and evaluator (`eval.py`) accept PageRank-aware parameters:

```bash
python3 index.py --dict dict.txt --postings postings.txt --pagerank pagerank.txt --w1 0.7 --w2 0.3 --normalize-pr
python3 eval.py --pagerank pagerank.txt --w1 0.5 --w2 0.5 --top 10
python3 eval.py --pagerank pagerank.txt --w1 0.7 --w2 0.3 --top 10
```

Ensure that `w1 + w2 = 1`. Use `--normalize-pr` when you want PageRank scores scaled to `[0, 1]` before combining with cosine similarity, which is helpful when the raw PageRank magnitudes are very small.

## Evaluation results

Assignment 2 Step 4 re-run with the PageRank-augmented search (top 10 documents per query):

- `w1=0.5`, `w2=0.5`, normalized PageRank: `MAP = 0.0918`, `Avg R-Precision = 0.1213`, `Avg time = 0.178s`
- `w1=0.7`, `w2=0.3`, normalized PageRank: `MAP = 0.0992`, `Avg R-Precision = 0.1294`, `Avg time = 0.193s`

### Comparison to Assignment 2 baseline
  
Assignment 2 reported `MAP = 0.1023`, `Avg R-Precision = 0.1255`, and `Avg time = 0.149933s` without PageRank blending. Incorporating PageRank narrows the MAP gap but stays slightly below the baseline (`-0.0105` with equal weights and `-0.0031` when TF-IDF is emphasized), while R-Precision surpasses the baseline only when more weight is given to TF-IDF (`+0.0039`). Both PageRank runs incur higher latency (approximately +0.028s to +0.043s per query) due to the extra scoring blend.

Use these settings to compare how emphasizing PageRank shifts overall effectiveness.
