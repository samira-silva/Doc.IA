# DocIA

🇺🇸 English | 🇧🇷 [Português](README.md)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)
![RAG](https://img.shields.io/badge/RAG-local%20embeddings-8B5CF6)
![Groq](https://img.shields.io/badge/LLM-Groq%20(free)-6425C9)

**Intelligent document assistant** with a RAG (Retrieval-Augmented
Generation) pipeline built from scratch — chunking, embeddings,
similarity search, and answer generation with source citation — plus
automatic summarization, file conversion, and OCR. Runs **entirely for
free** (local embeddings + Groq's free tier).

> Upload the PDFs for a college course, group them into a collection, and
> ask "what are this semester's deadlines?" — the answer comes only from
> your own documents, with the source cited.

## Features

- 🔐 **User accounts** — each person only sees and manages their own documents
- 📄 **Upload PDF, DOCX, XLSX, and TXT**, including scanned PDFs (OCR)
- 🤖 **Automatic summarization** with key topics, via LLM
- 🔄 **PDF ↔ Word conversion**
- 💬 **Natural-language questions (RAG)** about a single document or an
  entire collection of documents, with source snippets shown
- 📁 **Collections** — group related documents (a course, a project)
- ✏️ Edit and delete documents

## How the RAG pipeline works (the core of the project)

```
upload → extract text (PDF/DOCX/XLSX/OCR)
       → split into overlapping chunks
       → embed each chunk (local multilingual model)
       → store in the database

question → embed the question
         → retrieve the most similar chunks (cosine similarity)
         → send only those chunks (not the whole document) to the LLM
         → answer with a citation of which document each part came from
```

Embeddings use `intfloat/multilingual-e5-small`, running locally via
`sentence-transformers` — an asymmetric model (different prefixes for
queries vs. passages), with no paid API required. Text generation uses
the Groq API, which has a genuine free tier.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Django 6.1 |
| Database | SQLite |
| LLM (summaries & answers) | Groq (`openai/gpt-oss-120b`) |
| Embeddings | `sentence-transformers` (local, multilingual) |
| PDF extraction | `pypdf` + OCR via `pytesseract`/`pdf2image` |
| DOCX/XLSX extraction | `python-docx`, `openpyxl` |
| PDF ↔ Word conversion | `pdf2docx`, headless LibreOffice |

## Running it locally

```bash
python -m venv venv
source venv/bin/activate  # Windows (PowerShell): .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your key into GROQ_API_KEY (free, see below)

python manage.py migrate
python manage.py runserver
```

Visit http://127.0.0.1:8000/ — you'll be redirected to the login page;
click "Cadastre-se" (Sign up) to create an account.

**Free Groq API key:** create an account at
[console.groq.com](https://console.groq.com/) (no credit card required),
generate a key under **API Keys**, and paste it into `.env`.

**Optional features** (the app works fine without them, showing a clear
error instead of crashing):

- OCR for scanned PDFs: `sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils`
- Word → PDF conversion: `sudo apt-get install libreoffice-writer`

## Possible next steps

- A real vector database (pgvector, Chroma, FAISS) instead of computing
  similarity in Python — scales from "a few hundred" to millions of chunks.
- Automated test suite (`pytest`/`django.test`).
- Async processing (Celery) for indexing/OCR/analysis.
- Systematic evaluation of RAG answer quality.
- Streaming the AI's response.
