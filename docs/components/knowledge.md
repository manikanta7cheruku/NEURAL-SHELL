# Knowledge (your documents)

| | |
|---|---|
| Status | Complete for 1.x |
| Code | `knowledge/`, `backend/routes/knowledge.py`, `brain_modules/layers/layer_53_knowledge.py` |
| UI | `frontend/src/pages/Knowledge.jsx`, the paperclip in `frontend/src/pages/Console.jsx` |
| Tests | `tests/test_documents.py` |

## Purpose

Students and anyone working from notes add their PDFs, Word files, slides and sheets, then ask about them in a chat.
Seven answers from the document, cites the page, and formats study answers as tables and lists. Everything is read
and stored on the computer; nothing is uploaded.

## How Seven reads a document (it has no eyes)

Seven does not look at pages the way a person does. It reads the text stored inside the file:

- **PDF**: the text layer of each page (pypdf). A PDF made from a scan is only pictures of pages, with no text layer,
  so there is nothing to read until it is converted with OCR (optical character recognition). Seven says so instead of
  answering from nothing.
- **Word**: paragraphs, headings and tables, in order (python-docx).
- **PowerPoint**: the text on each slide, tables and speaker notes (python-pptx).
- **Excel**: each sheet's cells, row by row (openpyxl).
- **Text and Markdown**: as they are.

Pictures, charts and handwriting are not read; equations typed as text are. Reading happens once, when the file is
added; questions are answered from the stored passages in a fraction of a second.

## How it works

```
add (Knowledge page or Console paperclip)
  -> copy into the library, status "reading"            knowledge/store.py  add()
  -> background reader thread
       extract.py: one unit per PDF page, slide or sheet; Word headings marked with "#"; tables kept as "a | b | c"
       chunk_units(): passages of about 1,000 characters, 180 overlapping, a new passage at every heading,
                      each remembering its page label ("p. 12", "slide 3") and section
       embed in batches of 64 with the same MiniLM model as memory (one shared instance)
  -> status "ready" with pages, words, headings, read time

question in a chat
  -> layer 5.3 decides whether documents apply (below)
  -> knowledge/core.py context_for()
       summary-type question ("summarize", "revision notes", "key points", "what is this about")
           -> passages spread evenly across the whole document, plus its list of sections
       any other question
           -> keyword ranking (BM25) and meaning ranking (cosine) fused with reciprocal rank fusion
       trimmed to fit the active model's context window (knowledge/core.py budget_chars)
  -> <knowledge_context> block with formatting rules: lead with the answer, markdown tables for comparisons,
     numbered lists for steps, **bold** key terms, a citation like (p. 4) after facts, and "the document doesn't
     cover it" instead of guessing
  -> the reply's trace carries "citations"; the Console shows them under the answer
```

### When documents are used

| Situation | Behaviour |
|---|---|
| The chat has documents attached (paperclip, or "Ask about it" on the Knowledge page) | Every question in that chat searches them. No relevance gate. The attachment is remembered per chat (`conversations.json`). |
| No attachment, library not empty | Searched only for study-type questions or ones that point at a document ("in my notes"), and only passages that clearly match are used. |
| Commands, greetings, weather, volume and so on | Never searched. |
| "open the pdf" in a chat with an attachment | Opens that document's file instead of searching the PC. |

When documents are used, the web layer is skipped and the reply gets a larger token budget (750, or 1,100 for
whole-document answers) so tables and notes are not cut off.

### Why not ChromaDB

A personal library is a few thousand passages. NumPy search over that takes milliseconds, keeps keyword and meaning
search over exactly the same passages, and avoids the native-code crashes ChromaDB has caused. Personal memory still
uses ChromaDB.

## Data

Under `<data>/seven_data/knowledge/library` (`seven_paths.paths.knowledge_dir`; tests set `SEVEN_KNOWLEDGE_DIR`):

| File | Holds |
|---|---|
| `index.json` | every document: id, name, type, size, status, progress, error, pages, words, passages, headings, reader version |
| `<id>.json`, `<id>.npy` | passages with page labels, and their normalised vectors |
| `files/<id><ext>` | the original file, opened by "Open" |
| `conversations.json` | which documents each chat answers from |
| `migrated.json` | marks that files from the old ChromaDB knowledge base were brought over |

Adding the same file twice returns the existing document (matched by SHA-1).

`READER_VERSION` in `store.py` is raised whenever extraction or chunking improves; at launch, documents read by an
older version are read again automatically.

## Interfaces

| Endpoint | Purpose |
|---|---|
| `GET /api/knowledge/documents` | library with progress, totals and the plan limit |
| `POST /api/knowledge/documents` | add a file (multipart `file`, optional `conversation_id` to attach it) |
| `GET /api/knowledge/documents/{id}` | one document with a preview of its opening passage |
| `DELETE /api/knowledge/documents/{id}` | remove the document, its passages and the copy |
| `POST /api/knowledge/documents/{id}/retry` | read again after a failure |
| `POST /api/knowledge/documents/{id}/open` | open the original file |
| `GET /api/knowledge/search?q=` | matching passages with page labels |
| `POST /api/knowledge/attach`, `GET /api/knowledge/attached` | documents attached to a chat |
| `POST /api/chat` with `documents: [ids]` | attach and ask in one step |

`/api/knowledge/stats` and `/api/knowledge/clear` remain for the `/knowledge` slash commands.

The number of documents is limited by plan (`license.TIER_FEATURES[...]["knowledge_files"]`). Adding a file that is
already in the library never counts against it.

## Failure modes

| Problem | What the user sees |
|---|---|
| Scanned PDF (images only) | "This PDF looks like scanned images, so there is no text to read. Export it with text (OCR) and add it again." |
| Password-protected PDF | asks to remove the password |
| Damaged or unsupported file | a plain reason, and "Try again" on the Knowledge page |
| Seven closed while reading | reading resumes at the next launch |
| Embedding model missing | falls back to hashed word vectors; keyword search still finds passages |

## Offline behaviour

The embedding model is downloaded once during setup. `seven_utils/hf_offline.enable()` runs at the top of `main.py`
and `backend/api_server.py`, before anything imports Hugging Face libraries, and switches them to offline mode when the
model is on disk. Without it, every model load retried huggingface.co for about 20 seconds when the PC had no internet.
`hf_offline.allow_downloads()` lifts offline mode for the one deliberate download (the voice model in setup).

## Known limitations

- Scanned PDFs need OCR before they can be read.
- Images, charts and equations drawn as pictures are not read; equations written as text are.
- The 1B model follows the formatting rules less reliably than 3B and 7B models.
- Page numbers are PDF page indexes, which can differ from the numbers printed on the page.
