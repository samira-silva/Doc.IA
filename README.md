# DocIA

🇧🇷 Português | 🇺🇸 [English](README.en.md)

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)
![RAG](https://img.shields.io/badge/RAG-embeddings%20locais-8B5CF6)
![Groq](https://img.shields.io/badge/LLM-Groq%20(gr%C3%A1tis)-6425C9)

**Assistente inteligente de documentos** com um pipeline de RAG (Retrieval-
Augmented Generation) construído do zero — chunking, embeddings, busca por
similaridade e geração de resposta com citação de fonte — além de resumo
automático, conversão de arquivos e OCR. Roda **inteiramente de graça**
(embeddings locais + Groq no tier gratuito).

> Envie os PDFs de uma matéria da faculdade, agrupe em uma coleção, e
> pergunte "quais são os prazos de entrega desse semestre?" — a resposta
> vem só do que está nos seus documentos, com a fonte indicada.

## Funcionalidades

- 🔐 **Contas de usuário** — cada pessoa só vê e gerencia seus próprios documentos
- 📄 **Upload de PDF, DOCX, XLSX e TXT**, incluindo PDFs escaneados (OCR)
- 🤖 **Resumo automático** com tópicos principais, via LLM
- 🔄 **Conversão PDF ↔ Word**
- 💬 **Perguntas em linguagem natural (RAG)** sobre um documento ou sobre
  uma coleção inteira de documentos, com os trechos-fonte visíveis
- 📁 **Coleções** — agrupe documentos relacionados (uma matéria, um projeto)
- ✏️ Editar e excluir documentos

## Como funciona o RAG (o coração do projeto)

```
upload → extrai texto (PDF/DOCX/XLSX/OCR)
       → divide em pedaços com sobreposição (chunking)
       → gera embedding de cada pedaço (modelo local multilíngue)
       → salva no banco

pergunta → gera embedding da pergunta
         → busca os pedaços mais parecidos (similaridade de cosseno)
         → envia só esses pedaços (não o documento inteiro) pro LLM
         → resposta com citação de qual documento veio cada parte
```

Os embeddings usam `intfloat/multilingual-e5-small`, rodando localmente via
`sentence-transformers` — modelo assimétrico (prefixos diferentes para
pergunta e para trecho de documento), sem depender de nenhuma API paga. A
geração de texto usa a API da Groq, que tem um tier gratuito real.

## Stack técnica

| Camada | Tecnologia |
|---|---|
| Backend | Django 6.1 |
| Banco de dados | SQLite |
| LLM (resumo e respostas) | Groq (`openai/gpt-oss-120b`) |
| Embeddings | `sentence-transformers` (local, multilíngue) |
| Extração de PDF | `pypdf` + OCR via `pytesseract`/`pdf2image` |
| Extração de DOCX/XLSX | `python-docx`, `openpyxl` |
| Conversão PDF ↔ Word | `pdf2docx`, LibreOffice headless |

## Como rodar

```bash
python -m venv venv
source venv/bin/activate  # Windows (PowerShell): .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

cp .env.example .env
# edite o .env e cole sua chave em GROQ_API_KEY (gratuita, veja abaixo)

python manage.py migrate
python manage.py runserver
```

Acesse http://127.0.0.1:8000/ — você será redirecionado para o login;
clique em "Cadastre-se" para criar uma conta.

**Chave da Groq (gratuita):** crie uma conta em
[console.groq.com](https://console.groq.com/) (sem cartão de crédito),
gere uma chave em **API Keys** e cole no `.env`.

**Recursos opcionais** (o app funciona sem eles, mostrando um aviso claro
em vez de travar):

- OCR de PDFs escaneados: `sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils`
- Conversão Word → PDF: `sudo apt-get install libreoffice-writer`

## Possíveis próximos passos

- Vetor de banco de dados de verdade (pgvector, Chroma, FAISS) em vez de
  calcular similaridade em Python — muda de "algumas centenas" pra milhões
  de trechos.
- Suíte de testes automatizados (`pytest`/`django.test`).
- Processamento assíncrono (Celery) para indexação/OCR/análise.
- Avaliação sistemática da qualidade das respostas do RAG.
- Streaming da resposta da IA.
