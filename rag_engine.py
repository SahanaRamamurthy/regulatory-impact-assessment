"""
RAG Engine — TF-IDF vectorization + cosine similarity retrieval,
followed by GPT-powered compliance verdict generation.

Documents are loaded from the docs/ folder at startup and can be
reloaded at any time via reload().
"""

import json
import os
from typing import List, Dict, Any

import anthropic
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from document_loader import load_documents_from_folder


class RAGEngine:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=10000,
        )
        self.documents: List[Dict[str, Any]] = []
        self.doc_vectors = None
        self._build_index()

    def _build_index(self):
        """Load documents from disk and rebuild the TF-IDF index."""
        self.documents = load_documents_from_folder()
        if not self.documents:
            print("[RAG] No documents found in docs/ folder. Add files and call reload().")
            self.doc_vectors = None
            return

        corpus = [f"{doc['title']} {doc['content']}" for doc in self.documents]
        self.doc_vectors = self.vectorizer.fit_transform(corpus)
        print(f"[RAG] Index built — {len(self.documents)} chunks from {self._unique_sources()} files.")

    def _unique_sources(self) -> int:
        return len({d["source"] for d in self.documents})

    def reload(self):
        """Re-scan the docs/ folder and rebuild the index. Call after uploading new files."""
        self._build_index()
        return {
            "chunks": len(self.documents),
            "files": self._unique_sources(),
        }

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Return the top_k most relevant chunks for the query."""
        if self.doc_vectors is None or len(self.documents) == 0:
            return []

        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.doc_vectors).flatten()
        top_indices = np.argsort(scores)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0.0:
                doc = self.documents[idx].copy()
                doc["similarity_score"] = round(float(scores[idx]), 4)
                results.append(doc)
        return results

    def assess_compliance(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        """
        Full RAG pipeline:
        1. Retrieve relevant chunks via TF-IDF cosine similarity.
        2. Send query + chunks to GPT for a structured compliance verdict.
        """
        retrieved_clauses = self.retrieve(query, top_k=top_k)

        if not retrieved_clauses:
            return {
                "query": query,
                "verdict": "INSUFFICIENT DATA",
                "confidence": "LOW",
                "summary": "No relevant content found. Please upload regulatory documents to the docs/ folder.",
                "key_findings": [],
                "citations": [],
                "retrieved_clauses": [],
                "recommendation": "Upload PDF, Word, Excel, or PowerPoint files via the Upload button.",
                "risk_level": "LOW",
            }

        context_block = ""
        for i, clause in enumerate(retrieved_clauses, 1):
            context_block += (
                f"\n[CLAUSE {i}]\n"
                f"Source: {clause['source']}\n"
                f"Section: {clause['section']}\n"
                f"Title: {clause['title']}\n"
                f"Content: {clause['content']}\n"
                f"Relevance Score: {clause['similarity_score']}\n"
            )

        system_prompt = (
            "You are a regulatory compliance expert specialising in healthcare data governance, "
            "privacy law, and organisational policy. You analyse compliance questions against "
            "regulatory clauses and produce structured, evidence-backed assessments.\n\n"
            "Always respond in the following JSON format:\n"
            "{\n"
            '  "verdict": "<COMPLIANT | NON-COMPLIANT | PARTIALLY COMPLIANT | NEEDS REVIEW>",\n'
            '  "confidence": "<HIGH | MEDIUM | LOW>",\n'
            '  "summary": "<2-3 sentence plain-English explanation of the verdict>",\n'
            '  "key_findings": ["<finding 1>", "<finding 2>", ...],\n'
            '  "citations": [\n'
            '    {"source": "<source name>", "section": "<section ref>", "relevance": "<why this clause applies>"}\n'
            "  ],\n"
            '  "recommendation": "<actionable next step for the compliance team>",\n'
            '  "risk_level": "<HIGH | MEDIUM | LOW>"\n'
            "}"
        )

        user_message = (
            f"COMPLIANCE QUERY:\n{query}\n\n"
            f"RELEVANT REGULATORY CLAUSES RETRIEVED:\n{context_block}\n\n"
            "Based solely on the clauses above, provide a structured compliance assessment."
        )

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text
        # Strip markdown code fences if Claude wraps the JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        verdict_data = json.loads(raw.strip())
        return {
            "query": query,
            "retrieved_clauses": retrieved_clauses,
            **verdict_data,
        }
