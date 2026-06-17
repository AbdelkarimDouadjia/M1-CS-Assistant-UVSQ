"""Reranking helpers shared by the chatbot and evaluation.

The current project first tries the UVSQ/server reranker when available. This
module also keeps the useful fallback from the older project path: a local
``sentence-transformers`` CrossEncoder reranker, configured without hardcoded
keys.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Sequence

import requests
from sentence_transformers import CrossEncoder


@lru_cache(maxsize=2)
def _load_cross_encoder(model_name: str) -> CrossEncoder:
    return CrossEncoder(model_name)


def _server_rerank(
    query: str,
    docs: Sequence[object],
    *,
    top_k: int,
    server_base: str,
    server_model: str,
    request_timeout: int,
) -> list[object]:
    documents = [getattr(doc, "page_content", "") for doc in docs]
    base = server_base.rstrip("/")
    endpoints = [
        (
            f"{base}/v1/rerank",
            {"model": server_model, "query": query, "documents": documents, "top_n": min(top_k, len(documents))},
        ),
        (
            f"{base}/rerank",
            {"model": server_model, "query": query, "documents": documents, "top_n": min(top_k, len(documents))},
        ),
        (
            f"{base}/score",
            {"model": server_model, "queries": [query] * len(documents), "documents": documents},
        ),
    ]
    for endpoint, payload in endpoints:
        try:
            response = requests.post(endpoint, json=payload, timeout=request_timeout)
            response.raise_for_status()
            body = response.json()
            if "results" in body:
                ranked_docs = [docs[item["index"]] for item in body["results"][:top_k]]
                if ranked_docs:
                    return ranked_docs
            if "data" in body:
                scores = [item.get("score", item.get("relevance_score", 0.0)) for item in body["data"]]
                if len(scores) == len(docs):
                    ranked = sorted(zip(scores, docs), key=lambda pair: pair[0], reverse=True)
                    return [doc for _, doc in ranked[:top_k]]
        except requests.RequestException:
            continue
        except (KeyError, TypeError, ValueError):
            continue
    return []


def _local_rerank(
    query: str,
    docs: Sequence[object],
    *,
    top_k: int,
    local_model: str,
) -> list[object]:
    model = _load_cross_encoder(local_model)
    pairs = [[query, getattr(doc, "page_content", "")] for doc in docs]
    scores = model.predict(pairs)
    ranked = sorted(zip(scores, docs), key=lambda pair: float(pair[0]), reverse=True)
    return [doc for _, doc in ranked[:top_k]]


def rerank_documents(
    query: str,
    docs: Sequence[object],
    *,
    top_k: int,
    enabled: bool,
    server_base: str,
    server_model: str,
    request_timeout: int,
    server_available: Callable[[], bool] | None = None,
    local_enabled: bool = True,
    local_model: str = "BAAI/bge-reranker-base",
) -> list[object]:
    """Rank documents with server reranker first, then local CrossEncoder.

    If reranking is disabled or both rerankers fail, the original order is
    preserved and truncated to ``top_k``.
    """
    if not docs:
        return []
    if not enabled:
        return list(docs[:top_k])

    if server_base and (server_available is None or server_available()):
        ranked = _server_rerank(
            query,
            docs,
            top_k=top_k,
            server_base=server_base,
            server_model=server_model,
            request_timeout=request_timeout,
        )
        if ranked:
            return ranked

    if local_enabled:
        try:
            return _local_rerank(query, docs, top_k=top_k, local_model=local_model)
        except Exception:
            pass

    return list(docs[:top_k])
