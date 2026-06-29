import sqlite3
import os
import numpy as np
from typing import List, Dict
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DB_PATH = os.environ.get("RAG_DB_PATH", "/data/rag.db")

class RAGEngine:
    def __init__(self):
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        self._init_db()
    
    def _init_db(self):
        # Create directory if not exists
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("CREATE TABLE IF NOT EXISTS facts (id TEXT PRIMARY KEY, text TEXT, embedding BLOB, source TEXT, category TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS products (name TEXT PRIMARY KEY, rate REAL, min_amount REAL, max_amount REAL, description TEXT)")
        conn.close()
    
    def embed(self, text: str) -> np.ndarray:
        return self.model.encode(text)
    
    def add_fact(self, fact_id: str, text: str, source: str, category: str):
        emb = self.embed(text)
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT OR REPLACE INTO facts VALUES (?, ?, ?, ?, ?)",
            (fact_id, text, emb.tobytes(), source, category)
        )
        conn.commit()
        conn.close()
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        q_emb = self.embed(query)
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT id, text, embedding, source, category FROM facts").fetchall()
        conn.close()
        
        results = []
        for row in rows:
            emb = np.frombuffer(row[2], dtype=np.float32)
            sim = np.dot(q_emb, emb) / (np.linalg.norm(q_emb) * np.linalg.norm(emb))
            results.append((sim, {"id": row[0], "text": row[1], "source": row[3], "category": row[4]}))
        
        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_k]]
    
    def verify_financial_claim(self, claim: str) -> Dict:
        """Check a financial claim against RAG facts."""
        matches = self.search(claim, top_k=3)
        for m in matches:
            if m["category"] == "interest_rate" or m["category"] == "product_rate":
                # Extract claimed rate from text
                import re
                claimed_rates = re.findall(r'(\d+\.?\d*)%', claim)
                if claimed_rates:
                    claimed = float(claimed_rates[0])
                    factual_rates = re.findall(r'(\d+\.?\d*)%', m["text"])
                    if factual_rates:
                        factual_rate = float(factual_rates[0])
                        if abs(claimed - factual_rate) > 5.0:
                            return {"verified": False, "reason": f"Claimed {claimed}%, actual {factual_rate}%", "source": m["source"]}
        return {"verified": True, "matches": matches}
