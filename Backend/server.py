import json
import re
from collections import Counter
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "technology_dataset.json"
IMAGE_FILE = BASE_DIR / "images_only.json"        

BERT_WEIGHT = 0.7
BM25_WEIGHT = 0.3

HYBRID_THRESHOLD = 0.50
HIGH_RELEVANCE_THRESHOLD = 0.6
                                       



def setup_nltk():
    resources = [
        ("tokenizers/punkt", "punkt"),
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("corpora/stopwords", "stopwords"),
        ("corpora/wordnet", "wordnet"),
        ("corpora/omw-1.4", "omw-1.4"),
    ]
    for resource_path, resource_name in resources:
        try:
            nltk.data.find(resource_path)
        except LookupError:
            nltk.download(resource_name)

setup_nltk()

STOP_WORDS = set(stopwords.words("english"))
LEMMA = WordNetLemmatizer()







def load_docs():
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as error:
        print(f"Could not load {DATA_FILE.name}: {error}")
        return []
    if not isinstance(data, list):
        print(f"{DATA_FILE.name} must contain a JSON list of documents.")
        return []

    docs = []
    for i, d in enumerate(data):                       #id for each doc
        if not isinstance(d, dict):
            continue
        text = (
            f"{d.get('topic', '')} "
            f"{d.get('category', '')} "
            f"{' '.join(d.get('tags', []))} "
            f"{d.get('summary', '')}"
        )
        docs.append({
            "id": d.get("id", i + 1),
            "topic": d.get("topic", ""),
            "category": d.get("category", ""),
            "summary": d.get("summary", ""),
            "page_url": d.get("page_url", ""),
            "source": d.get("source", ""),
            "tags": d.get("tags", []),
            "text": text
        })
    return docs






def clean(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def preprocess(text):
    tokens = word_tokenize(clean(text))
    return [LEMMA.lemmatize(t) for t in tokens if t not in STOP_WORDS and len(t) > 1]





def build_index(docs):
    for doc in docs:
        tokens = preprocess(doc["text"])
        doc["tokens"] = tokens
        doc["tf"] = Counter(tokens)
    return docs

def build_inverted_index(docs):
    inverted_index = {}
    for doc in docs:
        for term, freq in doc["tf"].items():
            if term not in inverted_index:
                inverted_index[term] = []
            inverted_index[term].append({"doc_id": doc["id"], "freq": freq})
    return inverted_index




DOCS = load_docs()
DOCS = build_index(DOCS)

INVERTED_INDEX = build_inverted_index(DOCS)
DOC_ID_TO_IDX = {doc["id"]: idx for idx, doc in enumerate(DOCS)}   ##################################### 
BM25_INDEX = BM25Okapi([doc["tokens"] for doc in DOCS]) if DOCS else None            


DOC_IMAGES = {}
if IMAGE_FILE.exists():
    try:
        with open(IMAGE_FILE, "r", encoding="utf-8") as f:
            images_data = json.load(f)
        for item in images_data:
            DOC_IMAGES[item["id"]] = item.get("images", [])
        print(f"Loaded images for {len(DOC_IMAGES)} documents.")
    except Exception as e:
        print(f"Could not load images: {e}")






def build_suggestion_terms(docs):
    terms = set()
    for doc in docs:
        category = doc.get("category", "")
        if category:
            terms.add(category.replace("_", " ").lower())
        for tag in doc.get("tags", []):
            if tag:
                terms.add(str(tag).lower())
        topic = doc.get("topic", "")
        if topic:
            topic_words = clean(topic).split()
            for word in topic_words:
                if len(word) > 2:
                    terms.add(word)
            for i in range(len(topic_words) - 1):
                terms.add(f"{topic_words[i]} {topic_words[i+1]}")
            for i in range(len(topic_words) - 2):
                terms.add(f"{topic_words[i]} {topic_words[i+1]} {topic_words[i+2]}")
    return sorted(list(terms), key=lambda x: (len(x), x))

SUGGESTION_TERMS = build_suggestion_terms(DOCS)







BERT_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def get_bert_embedding(text):
    return BERT_MODEL.encode(text, convert_to_numpy=True)


DOC_EMBEDDINGS = np.array([get_bert_embedding(doc["text"]) for doc in DOCS]) if DOCS else np.empty((0, 384))



SUGGESTION_EMBEDDINGS = np.array([get_bert_embedding(term) for term in SUGGESTION_TERMS])


def get_suggestions(query, limit=8):    #ektera7at
    
    q = clean(query)
    if not q:
        return []

    suggestions = []

  
    for term in SUGGESTION_TERMS:
        if term.startswith(q) and term != q:
            suggestions.append(term)
        if len(suggestions) >= limit:
            break



    if len(suggestions) < limit:
        for term in SUGGESTION_TERMS:
            if q in term and term not in suggestions and term != q:
                suggestions.append(term)
            if len(suggestions) >= limit:
                break



    if len(suggestions) < limit:
        q_emb = get_bert_embedding(q).reshape(1, -1)
        sims = cosine_similarity(q_emb, SUGGESTION_EMBEDDINGS)[0]
        sorted_indices = np.argsort(sims)[::-1]
        for idx in sorted_indices:
            term = SUGGESTION_TERMS[idx]
            if term != q and term not in suggestions:
                suggestions.append(term)
            if len(suggestions) >= limit:
                break

    return suggestions[:limit]



def empty_search_response(query, bert_active=True):
    return {
        "query": query,
        "results": [],
        "count": 0,
        "shown": 0,
        "precision": 0,
        "recall": 0,
        "f1_score": 0,
        "bert_active": bert_active,
        "ranking": {
            "method": "70% BERT + 30% BM25",
            "hybrid_threshold": HYBRID_THRESHOLD,
            "high_relevance_threshold": HIGH_RELEVANCE_THRESHOLD
            
        }
    }

def precision(retrieved, relevant_in_result):
    if len(retrieved) == 0:
        return 0
    return len(set(retrieved) & set(relevant_in_result)) / len(retrieved)

def recall(retrieved, relevant, relevant_in_result):
    if len(relevant) == 0:
        return 0
    return len(set(retrieved) & set(relevant_in_result)) / len(relevant)

def f1_score(p, r):
    if (p + r) == 0:
        return 0
    return 2 * p * r / (p + r)

def search_query(query, feedback=None):
    q_terms = preprocess(query)
    print("\nQuery:", query)
    print("Processed:", q_terms)

    if not query.strip():
        return empty_search_response(query)
    if not DOCS or BM25_INDEX is None or DOC_EMBEDDINGS.size == 0:
        return empty_search_response(query, bert_active=False)


    if q_terms:
        bm25_raw = BM25_INDEX.get_scores(q_terms)
    else:
        bm25_raw = np.zeros(len(DOCS))
    bm25_max = float(np.max(bm25_raw)) if bm25_raw.size else 0
    bm25_norm = (bm25_raw / bm25_max) if bm25_max > 0 else np.zeros(len(DOCS))


    q_emb = get_bert_embedding(query).reshape(1, -1)
    bert_raw = cosine_similarity(q_emb, DOC_EMBEDDINGS)[0]
    bert_norm = np.clip((bert_raw + 1) / 2, 0, 1)


    hybrid = (BERT_WEIGHT * bert_norm) + (BM25_WEIGHT * bm25_norm)

    if feedback:
        for doc_id_str, vote in feedback.items():
            try:
                doc_id = int(doc_id_str)
                idx = DOC_ID_TO_IDX.get(doc_id)
                if idx is not None:
                    if vote == "relevant":
                        hybrid[idx] = min(1.0, hybrid[idx] + 0.20)
                    elif vote == "irrelevant":
                        hybrid[idx] = max(HYBRID_THRESHOLD + 0.01, hybrid[idx] - 0.40)
            except (ValueError, TypeError):
                pass

    results = []
    for idx, doc in enumerate(DOCS):
        if hybrid[idx] < HYBRID_THRESHOLD:
            continue
        results.append({
            "id": doc["id"],
            "topic": doc["topic"],
            "category": doc["category"],
            "summary": doc["summary"],
            "page_url": doc["page_url"],
            "source": doc["source"],
            "bm25_score": round(float(bm25_norm[idx]), 4),
            "bert_score": round(float(bert_norm[idx]), 4),
            "hybrid_score": round(float(hybrid[idx]), 4),
            "images": DOC_IMAGES.get(doc["id"], [])
        })

    results.sort(key=lambda x: x["hybrid_score"], reverse=True)

    count = len(results)
    shown = count

    retrieved = [r["id"] for r in results]
    relevant = [doc["id"] for idx, doc in enumerate(DOCS) if hybrid[idx] >= HIGH_RELEVANCE_THRESHOLD]
    relevant_in_result = [doc_id for doc_id in retrieved if doc_id in relevant]

    p = precision(retrieved, relevant_in_result)
    r_val = recall(retrieved, relevant, relevant_in_result)
    f1 = f1_score(p, r_val)

    return {
        "query": query,
        "results": results,
        "count": count,
        "shown": shown,
        "precision": round(p, 4),
        "recall": round(r_val, 4),
        "f1_score": round(f1, 4),
        "bert_active": True,
        "ranking": {
            "method": "70% BERT + 30% BM25",
            "hybrid_threshold": HYBRID_THRESHOLD,
            "high_relevance_threshold": HIGH_RELEVANCE_THRESHOLD
        }
    }



@app.route("/")
def home():
    return jsonify({
        "message": "Search Engine Running",
        "documents": len(DOCS),
        "ranking": "70% BERT + 30% BM25",
        "hybrid_threshold": HYBRID_THRESHOLD
    })

@app.route("/index")
def get_index():
    sample_terms = list(INVERTED_INDEX.keys())[:50]
    sample_index = {term: INVERTED_INDEX[term] for term in sample_terms}
    return jsonify({
        "terms_returned": len(sample_index),
        "total_terms": len(INVERTED_INDEX),
        "sample": sample_index
    })

@app.route("/suggest")
def suggest():
    q = request.args.get("q", "").strip()
    return jsonify({
        "query": q,
        "suggestions": get_suggestions(q)
    })

@app.route("/search")
def api_search():
    q = request.args.get("q", "").strip()
    return jsonify(search_query(q))

@app.route("/feedback-search", methods=["POST"])
def feedback_search():
    data = request.get_json(silent=True) or {}
    q = data.get("query", "").strip()
    feedback = data.get("feedback", {})
    return jsonify(search_query(q, feedback))


if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)