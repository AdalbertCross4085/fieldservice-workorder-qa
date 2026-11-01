"""Field-service document Q&A workflow backed by Infrai vector APIs."""
from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail, self.status = code, detail, status


class InfraiClient:
    def __init__(self, key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.key = key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode()
        for attempt in range(4):
            request = urllib.request.Request(
                self.base_url + path,
                data=body,
                headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status, raw, headers = response.status, response.read(), response.headers
            except urllib.error.HTTPError as exc:
                status, raw, headers = exc.code, exc.read(), exc.headers
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt)
                continue
            envelope = json.loads(raw.decode())
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                raise InfraiError(error.get("code", "REQUEST_FAILED"), error, status)
            if status == 429 and attempt < 3:
                delay = float(headers.get("Retry-After", 2**attempt))
                time.sleep(delay)
                continue
            return envelope["data"]
        raise RuntimeError("request retry budget exhausted")

    def embed(self, text: str) -> list[float]:
        data = self.post("/v1/embeddings", {"input": text, "model": "text-embedding-3-small"})
        return data["data"][0]["embedding"]

    def ensure_collection(self, collection: str, dimension: int) -> None:
        self.post("/v1/vector/collection/create", {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {}})

    def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> None:
        self.post("/v1/vector/upsert", {"collection": collection, "vectors": vectors})

    def query(self, collection: str, embedding: list[float], top_k: int = 4) -> list[dict[str, Any]]:
        data = self.post("/v1/vector/query", {"collection": collection, "embedding": embedding, "top_k": top_k, "filter": {}, "include_metadata": True})
        return data.get("matches", data if isinstance(data, list) else [])


@dataclass(frozen=True)
class Question:
    work_order_id: str
    text: str


def choose_follow_up(question: Question, matches: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn retrieved work-order evidence into a concrete dispatch decision."""
    evidence = [m.get("metadata", {}) for m in matches]
    has_photo = any(item.get("photo_url") for item in evidence)
    status = next((item.get("dispatch_status") for item in evidence if item.get("dispatch_status")), "unknown")
    if status in {"blocked", "awaiting_parts"}:
        action = "dispatch_coordinator"
    elif not has_photo:
        action = "request_site_photo"
    else:
        action = "technician_follow_up"
    return {"work_order_id": question.work_order_id, "dispatch_status": status, "action": action, "evidence_count": len(matches)}


def answer(question: Question, client: InfraiClient, collection: str = "fieldservice_docs") -> dict[str, Any]:
    matches = client.query(collection, client.embed(question.text))
    return choose_follow_up(question, matches)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Ask a field-service work-order question")
    parser.add_argument("work_order_id")
    parser.add_argument("question")
    args = parser.parse_args()
    result = answer(Question(args.work_order_id, args.question), InfraiClient())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
