"""
RAG Engine — TF-IDF retrieval + Claude compliance verdict.
Falls back to web search when document relevance is too low.
"""

import json
import os
from typing import List, Dict, Any

import anthropic
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from document_loader import load_documents_from_folder

WEB_FALLBACK_THRESHOLD = 0.05  # if best score below this, use web search


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
        self.documents = load_documents_from_folder()
        if not self.documents:
            print("[RAG] No documents found in docs/ folder.")
            self.doc_vectors = None
            return
        corpus = [f"{doc['title']} {doc['content']}" for doc in self.documents]
        self.doc_vectors = self.vectorizer.fit_transform(corpus)
        print(f"[RAG] Index built — {len(self.documents)} chunks from {self._unique_sources()} files.")

    def _unique_sources(self) -> int:
        return len({d["source"] for d in self.documents})

    def reload(self):
        self._build_index()
        return {"chunks": len(self.documents), "files": self._unique_sources()}

    def retrieve(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
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

    # ── Web search fallback ───────────────────────────────────────────────────

    def _web_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query + " healthcare compliance regulation", max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url":   r.get("href", ""),
                        "body":  r.get("body", ""),
                    })
            return results
        except Exception as e:
            print(f"[RAG] Web search failed: {e}")
            return []

    def _assess_from_web(self, query: str, web_results: List[Dict]) -> Dict[str, Any]:
        context = ""
        for i, r in enumerate(web_results, 1):
            context += f"\n[WEB SOURCE {i}]\nTitle: {r['title']}\nURL: {r['url']}\nContent: {r['body']}\n"

        system_prompt = (
            "You are a regulatory compliance expert. The user's query could not be answered "
            "from internal documents, so you have been given web search results. "
            "Answer the query using the web sources. Be clear that this is from public web sources, "
            "not internal regulatory documents.\n\n"
            "Respond ONLY in this JSON format:\n"
            "{\n"
            '  "verdict": "<COMPLIANT | NON-COMPLIANT | PARTIALLY COMPLIANT | NEEDS REVIEW>",\n'
            '  "confidence": "<HIGH | MEDIUM | LOW>",\n'
            '  "summary": "<2-3 sentence answer based on web sources>",\n'
            '  "key_findings": ["<finding 1>", "<finding 2>", ...],\n'
            '  "web_citations": [\n'
            '    {"title": "<page title>", "url": "<full URL>", "snippet": "<relevant excerpt>"}\n'
            "  ],\n"
            '  "recommendation": "<actionable next step>",\n'
            '  "risk_level": "<HIGH | MEDIUM | LOW>"\n'
            "}"
        )

        user_message = (
            f"COMPLIANCE QUERY:\n{query}\n\n"
            f"WEB SEARCH RESULTS:\n{context}\n\n"
            "Provide a compliance assessment based on these web sources."
        )

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        verdict_data = json.loads(raw.strip())
        return {
            "query":             query,
            "source_type":       "web",
            "retrieved_clauses": [],
            "web_results":       web_results,
            **verdict_data,
        }

    # ── Main assess ───────────────────────────────────────────────────────────

    def assess_compliance(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        retrieved_clauses = self.retrieve(query, top_k=top_k)

        # Check if best match is strong enough
        best_score = max((c["similarity_score"] for c in retrieved_clauses), default=0)
        if best_score < WEB_FALLBACK_THRESHOLD or not retrieved_clauses:
            print(f"[RAG] Low relevance ({best_score:.3f}) — falling back to web search.")
            web_results = self._web_search(query)
            if web_results:
                return self._assess_from_web(query, web_results)
            # No web results either
            return {
                "query":             query,
                "source_type":       "none",
                "verdict":           "INSUFFICIENT DATA",
                "confidence":        "LOW",
                "summary":           "No relevant content found in documents or web search.",
                "key_findings":      [],
                "citations":         [],
                "retrieved_clauses": [],
                "recommendation":    "Upload relevant regulatory documents or refine your query.",
                "risk_level":        "LOW",
            }

        # Build context block with full metadata
        context_block = ""
        for i, clause in enumerate(retrieved_clauses, 1):
            meta_parts = []
            if clause.get("page"):       meta_parts.append(f"Page {clause['page']}")
            if clause.get("version"):    meta_parts.append(f"Version {clause['version']}")
            if clause.get("effective_date"): meta_parts.append(f"Effective {clause['effective_date']}")
            meta_str = " | ".join(meta_parts) if meta_parts else "N/A"

            context_block += (
                f"\n[CLAUSE {i}]\n"
                f"Source: {clause['source']}\n"
                f"Title: {clause['title']}\n"
                f"Section: {clause['section']}\n"
                f"Metadata: {meta_str}\n"
                f"Relevance Score: {clause['similarity_score']}\n"
                f"Content: {clause['content']}\n"
            )

        system_prompt = (
            "You are a regulatory compliance expert specialising in healthcare data governance, "
            "privacy law, and organisational policy.\n\n"
            "Always respond in this exact JSON format:\n"
            "{\n"
            '  "verdict": "<COMPLIANT | NON-COMPLIANT | PARTIALLY COMPLIANT | NEEDS REVIEW>",\n'
            '  "confidence": "<HIGH | MEDIUM | LOW>",\n'
            '  "summary": "<2-3 sentence plain-English explanation>",\n'
            '  "key_findings": ["<finding 1>", "<finding 2>", ...],\n'
            '  "citations": [\n'
            '    {\n'
            '      "source": "<filename>",\n'
            '      "title": "<document title>",\n'
            '      "section": "<section heading or chunk>",\n'
            '      "page": "<page number or N/A>",\n'
            '      "version": "<version or N/A>",\n'
            '      "effective_date": "<date or N/A>",\n'
            '      "relevance": "<why this clause applies>"\n'
            '    }\n'
            "  ],\n"
            '  "recommendation": "<actionable next step>",\n'
            '  "risk_level": "<HIGH | MEDIUM | LOW>"\n'
            "}"
        )

        user_message = (
            f"COMPLIANCE QUERY:\n{query}\n\n"
            f"RELEVANT REGULATORY CLAUSES:\n{context_block}\n\n"
            "Provide a structured compliance assessment. Include page, version, and effective date "
            "in each citation where available."
        )

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        verdict_data = json.loads(raw.strip())
        return {
            "query":             query,
            "source_type":       "documents",
            "retrieved_clauses": retrieved_clauses,
            **verdict_data,
        }
