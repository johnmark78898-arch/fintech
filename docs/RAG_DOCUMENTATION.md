# RAG Documentation

**Status:** A local public-source text index, lexical retrieval endpoint, and locally generated Ollama answers with server-validated citations are implemented. No embeddings, semantic retrieval, retrieval/answer evaluation, or private document ingestion are deployed.

## Current Data Status
The selected public corpus is agency-authored page text from the SBA's “Manage your finances” page and IRS Publication 334 (2025). Source URLs, edition, retrieval time, and content hashes are recorded in the generated index. `scripts/ingest_public_rag.py` extracts each page's main text, skips navigation, does not fetch linked pages, and writes chunked text to the local `RAG_CORPUS_PATH`. The source register is `data/rag_sources.json`.

The ingestion policy relies on 17 U.S.C. §§ 101 and 105 only for qualifying U.S. Government works. Federal hosting alone is not enough: ingest agency-authored text only, exclude logos, images, linked pages, and third-party material, and preserve source/version information. The corpus is public reference material; it is not customer data, transaction training data, tax advice, or a complete authoritative rule set.

The public library exposes cited lexical passage search and an Ollama-backed answer route. Only the question and retrieved public excerpts are sent to the local Ollama service; the API rejects remote model endpoints and validates citation IDs against retrieved passages. It does not use embeddings or index user-uploaded private documents. Ask only public-topic questions and do not enter personal or confidential information. Install Ollama on the host, pull the configured model (`ollama pull llama3.2` by default), and keep its local service running.

## Scope
Support organization-authorized financial reports, policies, loan documents, and guidelines in PDF, DOCX, TXT, and CSV form. Retrieval supplies evidence and citations; it does not calculate financial predictions or authorize actions. Document Q&A is an MVP decision gate; the architecture supports it as a follow-on if the first slice is kept strictly cash-flow/scenario focused.

## Ingestion and Indexing
1. Authenticate uploader and check organization/document permissions.
2. Enforce file size, extension, MIME and content signature; reject encrypted/unsupported or malformed files with safe messages; scan for malware where available.
3. Extract text with PyMuPDF for PDFs and format-specific parsers for DOCX/TXT/CSV; preserve page/row provenance. Do not execute macros or formulas.
4. Normalize whitespace and encoding; preserve original artifact/checksum. Apply sensitive-data policy before external embedding/LLM processing.
5. Chunk by document structure with bounded size and overlap; tune on a labeled evaluation set rather than assuming a universal chunk size.
6. Attach `organization_id`, document ID/name/type, source, uploaded timestamp, page/section, access scope, parser version, and content hash.
7. Generate embeddings using a configured, versioned model/provider; record model/dimension and provider processing terms.
8. Upsert deterministic point IDs into Qdrant. Store a database mapping to the source chunk and object storage key.
9. Track indexing states and retry idempotently. Re-index by deleting old points and replacing metadata atomically where possible.

## Retrieval
- Resolve authenticated tenant and document permissions before search.
- Apply organization and access-level filters in Qdrant; re-check every returned point against authoritative PostgreSQL metadata.
- Combine semantic search and lexical ranking only if evaluation shows benefit. Apply a reranker only with measured quality/latency/privacy tradeoffs.
- Return bounded passages with source IDs and exact page references; no cross-tenant fallback.
- If no sufficiently relevant evidence exists, say so. Do not construct citations from model-generated names or page numbers.

## Grounded Answer Generation
Provide the LLM with separately typed inputs: user question, structured prediction result (if any), retrieved passages, citations, policy/instructions, and allowed response format. Tell it to distinguish model outputs, document statements, assumptions, and unknowns. Treat retrieved documents as untrusted data; ignore instructions embedded in them, prohibit unauthorized tool calls, and do not expose hidden prompts or other tenants' content. The current public-answer route has no tools and validates model-returned citation IDs against the retrieved set; invalid citations fail rather than being displayed. Evaluate answer faithfulness and abstention before relying on answers.

## Metadata and ACLs
Required metadata: document name, type, upload date, organization, source, page number, access permissions, checksum, parser status, and embedding version. Document-level access may be narrower than organization membership. Re-check permission when reading history/citations, not only at indexing time.

## Deletion and Re-indexing
Delete disables retrieval immediately, then removes Qdrant points and source/extracted storage via tracked job. Verify completion across stores; backup expiry follows retention policy. Re-index must preserve original upload audit and increment parser/chunk/embedding versions. Authorization and deletion status are checked before serving cached results.

## Evaluation
Build a manually reviewed, permission-labeled query set representative of document types. Measure Recall@K, Precision@K, MRR, citation correctness (source and page), answer faithfulness, relevance, and abstention quality. Evaluate tenant filters and ACL revocation separately. Version corpus/query set/model/chunking/ranker; report confidence intervals and failures. No score is claimed until measured.

## Risks and Limitations
Scanned PDFs/OCR errors, tables, stale versions, ambiguous page numbering, duplicated documents, conflicting policies, malicious prompt instructions, and provider retention/processing terms. Document content is not automatically authoritative or current; show source and upload date, and let users inspect it. External provider use requires privacy and contractual approval.
