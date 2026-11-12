# Local PDF Library and index recovery

Production and automated test code is written for this slice; execution evidence
remains pending. Manually install `pip install -e './backend[dev,rag]'` in the
virtual environment before using PDF indexing or executing its tests.

## Downloads and encoding

The first nonempty indexing job lazily loads `intfloat/multilingual-e5-small` on
CPU through Sentence Transformers. Initial model downloads require internet access
and cache space. Parsing, embeddings and retrieval run locally; no PDF text goes
to an embedding API. Model loading disables remote model code.

Use `RAG_EMBEDDING_MODEL` and optional `RAG_EMBEDDING_REVISION` for model selection.
Changing either requires restarting with the new configuration and rebuilding the
full Library. Generations record model identity, requested revision and the resolved
commit when available. A different encoder or resolved revision cannot query old
vectors. E5 uses `query: ` and `passage: ` prefixes; other models use their native
query/document encoders or configured prompts. Vectors are normalized consistently.

Chunks start at the configured 500-token target with 80-token overlap. The effective
target reserves room for model prefixes/special tokens and is reduced for smaller
embedding windows. The tokenizer supplies offsets into the exact page text.
Oversized embedding input is rejected explicitly rather than silently truncated.

## Uploads and actual progress

The Library accepts one PDF at a time through the picker or drag/drop. Validation
covers filenames, extension, signature, readable pages, encryption, and the configured
byte limit (50 MiB default). Original UUID-named PDFs and their SHA-256 metadata stay
local. Identical content returns a duplicate error and adds no duplicate chunks.

A 202 upload response returns the document/job IDs. `/api/index/status` reports real
queued, model loading, extraction, chunking, embedding, indexing, ready/failed stages.
Counts appear only when totals are known. CPU work runs on a single indexing worker;
the API remains available for status and chat reads. Conflicting mutations return 409.
Documents become ready only after a complete validated generation is published.

Preview uses `/api/library/{document_id}/pdf#page=N`. The backend serves only a
managed existing PDF; the browser controls its page fragment. Browser PDF support
varies, so an Open PDF link is provided alongside the embedded preview. Removed
sources return 404. Historical chat content is preserved.

## Extraction and optional OCR

PyMuPDF extracts ordered text blocks per page, preserving table text where possible
without claiming arbitrary layout reconstruction. Chunk records keep exact document,
filename and one-based page provenance. Sparse/image-only pages produce OCR warnings;
a PDF with no searchable text is failed rather than falsely marked ready.

Optional local OCR is implemented with PyMuPDF rendering and the Tesseract executable.
It is disabled by default. Enable it with `RAG_OCR_ENABLED=true` or the Settings
toggle, and configure the `RAG_OCR_LANGUAGES` value (default `eng+fra+fas`) to match
installed Tesseract language packs. Before recognizing a sparse page, the backend
checks that Tesseract is on `PATH` and that every configured language pack is
installed. Missing executables, packs, or recognition failures produce explicit
warnings; pages that remain sparse are not treated as searchable content. OCR stays
on the local machine and does not send page images or text to an OCR service.

Implementation and automated test code are written; run the multilingual scanned
PDF fixtures manually with the requested language packs installed before claiming
OCR or extraction quality. OCR output is subject to the accuracy limits of the
installed Tesseract model packs.

## Generations, deletion, and recovery

Each immutable generation lives under `data/index/generations/<version>/`:

```text
faiss.index       # dense vectors
faiss_ids.json   # stable numeric-row to chunk-ID mapping
chunks.jsonl     # UTF-8 text and provenance
bm25_index.json  # JSON lexical corpus; never unpickled
generation.json  # encoder identity and component checksums
```

The Library manifest stores its active generation pointer and the hash of the
generation metadata. A rebuild writes, validates and flushes an entirely new
generation, then atomically publishes pointer and document readiness together in
one manifest snapshot. Readers use a complete pinned in-memory generation. Prior
generations remain available for recovery; automatic generation GC is not enabled.

Removal marks a document unavailable for future searches before rebuilding without
it. Its original is removed after publication. If rebuilding fails, the prior
generation remains usable with the removed document filtered out. A later rebuild
resumes pending deletion cleanup; other PDFs and raw chats are preserved.

Persistent jobs in `data/state/index_jobs.json` become failed with retry guidance
when interrupted by restart. Failed writes can leave unreferenced original PDFs or
generation directories, which are retained for diagnosis and never advertised as
ready merely because files exist. If component hashes/mappings are corrupt, status
reports unavailability and rebuilding from original PDFs is required.

Hashes are checked before FAISS deserialization. They detect corruption; someone
with write access to both files and metadata remains inside the local OS trust
boundary. Protect the data directory and backups accordingly.

## Retrieval evaluation

FAISS and BM25 each start with roughly 20 candidates. Reciprocal Rank Fusion combines
ranks; duplicate source text is removed; snippet count and token budgets bound output.
Filters apply to both channels. Scores are ranking values, not confidence percentages.

Optional local multilingual reranking is configured with `RAG_RERANKER_MODEL` (unset
by default). When set, the backend loads a Sentence Transformers CrossEncoder lazily
on CPU, scores only the bounded local hybrid candidate pool, and selects final
snippets under the normal count and token budgets. Candidate PDF text is passed only
to the local model; no reranking API or hosted service is used. A missing or failing
optional model falls back to deterministic hybrid ranking and is recorded in the
local activity log. Model downloads may require internet access on first use. Relevance
ordering and multilingual quality still require manual fixture evaluation.

## Feature toggles and measured tuning status

| Feature | Configuration | Default | Data boundary / fallback | Status |
|---|---|---|---|---|
| Dense + BM25 hybrid search with RRF | Core local index | Enabled | Uses active local generation; no hosted vector service | Implemented; relevance unverified |
| Local OCR | `RAG_OCR_ENABLED` / Settings toggle; `RAG_OCR_LANGUAGES` | Off; `eng+fra+fas` | Tesseract runs on this machine; missing executable/language packs produce warnings and do not mark scans searchable | Implemented; language fixtures unverified |
| Local reranking | `RAG_RERANKER_MODEL` | Unset | Optional local CrossEncoder ranks only bounded hybrid candidates; an unavailable model falls back to RRF | Implemented; relevance fixtures unverified |
| Additional retrieval tool rounds | `RAG_MAX_TOOL_ROUNDS` | 2 (valid range 0–2) | Only `search_library` and `get_source_excerpt`; initial local retrieval works when provider tools are disabled or rejected | Implemented; provider/tool verification unrun |
| Full chunk logging | `RAG_DEBUG_CHUNKS` | Off | Full chunks are excluded from routine operational logs | Implemented; log inspection unrun |
| Embedding model | `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_REVISION` | multilingual-e5-small; revision unset | Model changes require a complete local rebuild; no remote embedding endpoint | Implemented; platform compatibility unverified |
| Candidate and snippet limits | `RAG_RETRIEVAL_CANDIDATES`, `RAG_RETRIEVAL_SNIPPETS`, `RAG_RETRIEVAL_TOKENS` | 20, 6, 4000 | Bound local candidate generation and final context selection | Configured starting values; tuning unmeasured |

For an OpenAI-compatible endpoint, Settings separately controls whether the endpoint
is configured for the two Library tools and reports token usage. These are explicit
settings; actual endpoint support remains unverified until exercised.

Retrieval fixture results, latency measurements, empirically selected thresholds,
and supported-platform capability claims have not been recorded. Candidate counts
and snippet/token limits above are configured starting values, not measured quality
or confidence claims. Record measured findings and the exact model/platform before
changing those defaults or claiming support. Current unverified status is summarized
in [`verification.md`](verification.md) and [`provider-capabilities.md`](provider-capabilities.md).

Written tests use deterministic fake-model fixtures for exact identifiers, Unicode,
filtering, budgets, restart, corrupt generations and rebuild failures. They do not
prove real embedding relevance. Evaluate real multilingual absent-evidence,
contradiction, multi-PDF, identifier and follow-up fixtures before choosing relevance
thresholds. No empirical thresholds or latency claims are made yet.

Implementation references: [Sentence Transformers](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html)
and [FAISS persistence](https://github.com/facebookresearch/faiss/wiki/Index-IO,-cloning-and-hyper-parameter-tuning).
