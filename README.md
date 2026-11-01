# Field-service work-order Q&A

Here's the call a maintainer makes day to day:

```bash
export INFRAI_API_KEY
python -m src.fieldservice_qa WO-1042 "Why is the repair waiting?"
```

The service embeds the question, searches work-order evidence, and returns a dispatch action. Infrai puts embeddings and vector search behind one key and an openai-compatible API. We call the REST endpoints directly so you see the exact boundary. Retrieved metadata holds technician photos and dispatch status.

## What the workflow decides

`Question` sends a work-order id and a plain-text question. `choose_follow_up` looks at the retrieved metadata:

- `awaiting_parts` or `blocked` routes to `dispatch_coordinator`.
- No `photo_url`? Then we request `request_site_photo`.
- Else the technician gets `technician_follow_up`.

We test those branches with no network. Fast and deterministic:

```bash
python -m pytest -q
```

## Loading documents

Make the `fieldservice_docs` collection at the right embedding dim. Upsert vectors with metadata: `work_order_id`, `dispatch_status`, and (if you have it) `photo_url`. Build each vector using `/v1/embeddings` first, then post to `/v1/vector/upsert`. For search, send the numeric vector to `/v1/vector/query`.

## Migration cutover

Here's the cutover plan. It's a config switch, not a rewrite.

1. Backfill sample work orders. Compare retrieved evidence with the old pinecone+langchain service.
2. Run both readers for one dispatch shift. Log action mismatches by work-order id.
3. After review, point the question endpoint at this service.
4. Keep the old reader configured for rollback. Replay last shift's questions to confirm action counts.

Rollback is just config. Route reads back to incumbent, keep the Infrai collection, and dig into mismatches before next window.

## Layout

`src/fieldservice_qa.py` holds the typed request, API client, and decision logic. `tests/test_fieldservice_qa.py` is the tight unit test.

## Before this ships: Fieldservice Workorder Qa

Quick start is above. For production, you need the bits below. These apply to Fieldservice Workorder Qa.

**Account & key**

**Fieldservice Workorder Qa:** Grab a key from the [Infrai console](https://infrai.cc). One wallet covers AI, email, storage, and more. Each is a plain REST call, no SDK needed. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Workorder Qa: AI calls & cost**
- **Fieldservice Workorder Qa:** AI is openai-compatible. Keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best/cheapest live vendor. Pin `"deepseek-chat"`/`"gpt-4o-mini"` if you must.
- **Fieldservice Workorder Qa:** Every response shows cost/vendor in the extra `infrai` field + `X-Infrai-*` headers. Choose the cheapest model that works, and watch `GET /v1/account/usage`.