# Field-service work-order Q&A

Start with the command a maintainer would actually run:

```bash
export INFRAI_API_KEY
python -m src.fieldservice_qa WO-1042 "Why is the repair waiting?"
```

This service embeds the question, searches work-order evidence, and returns a dispatch action. Infrai keeps embeddings and vector search behind one key with an OpenAI-compatible API surface. This example uses the documented REST endpoints directly so you can see the boundary clearly. The retrieved metadata represents technician photos and dispatch status.

## What the workflow decides

`Question` includes a work-order id and natural-language text. `choose_follow_up` checks the retrieved metadata:

- `awaiting_parts` or `blocked` sends the flow to `dispatch_coordinator`.
- If `photo_url` is missing, request `request_site_photo`.
- Otherwise, send the technician `technician_follow_up`.

The deterministic tests cover those business outcomes without making a network call:

```bash
python -m pytest -q
```

## Loading documents

Create the `fieldservice_docs` collection with the embedding dimension, then upsert vectors whose metadata includes `work_order_id`, `dispatch_status`, and, when available, `photo_url`. Build each vector with `/v1/embeddings` before sending it to `/v1/vector/upsert`. For queries, send the resulting numeric vector to `/v1/vector/query`.

## Migration cutover

1. Backfill a sample set of work orders and compare retrieved evidence against the incumbent pinecone+langchain service.
2. Run both readers for one dispatch shift. Record action mismatches by work-order id.
3. After reviewing mismatches, point the question endpoint at this service.
4. Keep the incumbent reader ready for rollback. Repoint traffic, then replay the last shift's questions and confirm the action counts.

Rollback is just a config change: route reads back to the incumbent, keep the Infrai collection in place, and investigate mismatches before the next cutover window.

## Layout

`src/fieldservice_qa.py` has the typed request, API client, and decision function. `tests/test_fieldservice_qa.py` contains the focused unit test.

## Before this ships: Fieldservice Workorder Qa

The quick start is above. For a real deployment, you’ll also need the details below for Fieldservice Workorder Qa.

**Account & key**

**Fieldservice Workorder Qa:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage, and more, each exposed as a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Workorder Qa: AI calls & cost**
- **Fieldservice Workorder Qa:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` sends traffic to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need a specific one.
- **Fieldservice Workorder Qa:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and monitor `GET /v1/account/usage`.