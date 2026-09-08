"""Funções de apoio para a análise de documentos com IA.

Fluxo: extrair_texto(documento) -> resumir_com_ia(texto)
"""
from pathlib import Path

from django.conf import settings

# Margem de segurança para não estourar o contexto do modelo.
LIMITE_CARACTERES = 15000


class ExtracaoTextoError(Exception):
    """Erro ao extrair texto de um arquivo (formato não suportado, PDF de imagem etc.)."""


def extrair_texto(documento):
    """Extrai o texto do arquivo de um Documento (.pdf, .docx ou .txt/.md)."""
    caminho = Path(documento.arquivo.path)
    extensao = caminho.suffix.lower()

    if extensao == '.pdf':
        return _extrair_texto_pdf(caminho)
    elif extensao == '.docx':
        return _extrair_texto_docx(caminho)
    elif extensao == '.xlsx':
        return _extrair_texto_xlsx(caminho)
    elif extensao in ('.txt', '.md'):
        return caminho.read_text(encoding='utf-8', errors='ignore').strip()

    raise ExtracaoTextoError(
        f"Formato '{extensao or 'desconhecido'}' não suportado. "
        "Envie um arquivo PDF, DOCX, XLSX ou TXT."
    )


# Limite de páginas convertidas em imagem no fallback de OCR, para não travar
# em PDFs enormes.
LIMITE_PAGINAS_OCR = 20


def _extrair_texto_pdf(caminho):
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    partes = [pagina.extract_text() or '' for pagina in leitor.pages]
    texto = '\n'.join(partes).strip()

    if texto:
        return texto

    # PDF provavelmente escaneado (sem camada de texto): tenta OCR.
    texto_ocr = _ocr_pdf(caminho)
    if texto_ocr:
        return texto_ocr

    raise ExtracaoTextoError(
        'Não foi possível extrair texto do PDF, mesmo com OCR. '
        'Verifique se o arquivo não está corrompido ou em branco.'
    )


def _ocr_pdf(caminho):
    """Converte páginas do PDF em imagens e roda OCR (tesseract) nelas.

    Requer os binários do sistema `tesseract-ocr` e `poppler-utils`
    instalados (ver README).
    """
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise ExtracaoTextoError(
            'Este PDF parece ser escaneado (sem texto extraível) e o suporte '
            'a OCR não está instalado. Rode "pip install -r requirements.txt".'
        ) from exc

    try:
        imagens = convert_from_path(str(caminho), dpi=200)
    except Exception as exc:
        raise ExtracaoTextoError(
            'Este PDF parece ser escaneado, mas não foi possível convertê-lo '
            'para imagem para OCR. Verifique se o "poppler-utils" está '
            f'instalado no sistema (detalhe: {exc}).'
        ) from exc

    partes = []
    for imagem in imagens[:LIMITE_PAGINAS_OCR]:
        try:
            partes.append(pytesseract.image_to_string(imagem, lang='por+eng'))
        except pytesseract.TesseractNotFoundError as exc:
            raise ExtracaoTextoError(
                'Este PDF parece ser escaneado, mas o binário "tesseract-ocr" '
                'não está instalado no sistema (ver README).'
            ) from exc

    return '\n'.join(partes).strip()


def _extrair_texto_docx(caminho):
    import docx

    doc = docx.Document(str(caminho))
    texto = '\n'.join(p.text for p in doc.paragraphs).strip()

    if not texto:
        raise ExtracaoTextoError('O documento DOCX não contém texto extraível.')
    return texto


# Limite de linhas lidas por planilha, para não gerar um texto gigante.
LIMITE_LINHAS_XLSX = 500


def _extrair_texto_xlsx(caminho):
    from openpyxl import load_workbook

    try:
        planilha = load_workbook(str(caminho), data_only=True, read_only=True)
    except Exception as exc:
        raise ExtracaoTextoError(
            f'Não foi possível abrir a planilha (detalhe: {exc}).'
        ) from exc

    blocos = []
    for aba in planilha.worksheets:
        linhas = list(aba.iter_rows(values_only=True))
        if not linhas:
            continue

        cabecalho = [str(c).strip() if c is not None else f'col{i+1}' for i, c in enumerate(linhas[0])]
        linhas_texto = [f'Planilha: {aba.title}']

        for linha in linhas[1:1 + LIMITE_LINHAS_XLSX]:
            celulas = [
                f'{cabecalho[i]}: {valor}'
                for i, valor in enumerate(linha)
                if valor is not None and i < len(cabecalho)
            ]
            if celulas:
                linhas_texto.append(' | '.join(celulas))

        if len(linhas) - 1 > LIMITE_LINHAS_XLSX:
            linhas_texto.append(
                f'... ({len(linhas) - 1 - LIMITE_LINHAS_XLSX} linhas adicionais não incluídas)'
            )

        blocos.append('\n'.join(linhas_texto))

    texto = '\n\n'.join(blocos).strip()
    if not texto:
        raise ExtracaoTextoError('A planilha está vazia ou não contém dados legíveis.')
    return texto


MODELO_GROQ = 'openai/gpt-oss-120b'


def _chamar_groq(system, conteudo_usuario, max_tokens=1024):
    """Chama a API da Groq (gratuita, sem cartão de crédito) e retorna o
    texto da resposta. Centraliza a configuração do cliente e o erro de
    chave ausente, usado tanto pelo resumo quanto pelas perguntas (RAG)."""
    import groq

    api_key = getattr(settings, 'GROQ_API_KEY', '')
    if not api_key:
        raise RuntimeError(
            'GROQ_API_KEY não configurada. Crie uma chave gratuita em '
            'console.groq.com e adicione-a ao arquivo .env na raiz do projeto.'
        )

    client = groq.Groq(api_key=api_key)
    resposta = client.chat.completions.create(
        model=MODELO_GROQ,
        max_completion_tokens=max_tokens,
        # O gpt-oss-120b é um modelo de "raciocínio"; para resumir texto ou
        # responder com base em trechos já recuperados não precisamos de
        # esforço alto, então mantemos rápido e barato (dentro do limite
        # gratuito da Groq).
        reasoning_effort='low',
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': conteudo_usuario},
        ],
    )

    return (resposta.choices[0].message.content or '').strip()


def resumir_com_ia(texto):
    """Envia o texto extraído para a IA (Groq) e retorna um resumo."""
    texto_truncado = texto[:LIMITE_CARACTERES]
    truncado = len(texto) > LIMITE_CARACTERES

    resumo = _chamar_groq(
        system=(
            'Você é um assistente que resume documentos e planilhas em '
            'português do Brasil. Estruture a resposta em duas partes: '
            '(1) um resumo curto e objetivo do conteúdo, em 1-3 parágrafos; '
            '(2) uma lista de tópicos principais (bullet points), destacando '
            'pontos-chave, números importantes, decisões e prazos citados, '
            'se houver. Não invente informações que não estejam no texto.'
        ),
        conteudo_usuario=f'Resuma o documento abaixo:\n\n{texto_truncado}',
    )

    if truncado:
        resumo += (
            '\n\n_(Observação: o documento é longo; apenas os primeiros '
            f'{LIMITE_CARACTERES} caracteres foram analisados.)_'
        )

    return resumo


class ConversaoError(Exception):
    """Erro ao converter um documento entre PDF e Word."""


def converter_arquivo(documento):
    """Converte o arquivo do documento entre PDF e DOCX.

    Retorna (caminho_do_arquivo_gerado, nome_do_arquivo, extensao) e não
    salva nada no modelo — quem chama decide o que fazer com o resultado.
    """
    caminho = Path(documento.arquivo.path)
    extensao = caminho.suffix.lower()

    if extensao == '.pdf':
        return _pdf_para_docx(caminho)
    elif extensao == '.docx':
        return _docx_para_pdf(caminho)

    raise ConversaoError(
        f"Não é possível converter arquivos '{extensao or 'desse tipo'}'. "
        "A conversão funciona apenas entre PDF e DOCX."
    )


def _pdf_para_docx(caminho):
    from pdf2docx import Converter

    destino = caminho.with_suffix('.docx')

    try:
        conversor = Converter(str(caminho))
        try:
            conversor.convert(str(destino))
        finally:
            conversor.close()
    except Exception as exc:
        raise ConversaoError(
            f'Não foi possível converter o PDF para Word (detalhe: {exc}).'
        ) from exc

    if not destino.exists() or destino.stat().st_size == 0:
        raise ConversaoError(
            'A conversão não gerou um arquivo Word válido. O PDF pode estar '
            'protegido, corrompido ou ser apenas uma imagem escaneada '
            '(nesse caso, use a análise de IA para extrair o texto via OCR).'
        )

    return destino, destino.name, 'docx'


def _docx_para_pdf(caminho):
    import shutil
    import subprocess
    import tempfile

    soffice = shutil.which('soffice') or shutil.which('libreoffice')
    if not soffice:
        raise ConversaoError(
            'Conversão de Word para PDF requer o LibreOffice instalado no '
            'servidor ("soffice"/"libreoffice" não encontrado no PATH).'
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            resultado = subprocess.run(
                [
                    soffice, '--headless', '--norestore',
                    '--convert-to', 'pdf',
                    '--outdir', tmp_dir,
                    str(caminho),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversaoError(
                'A conversão para PDF demorou demais e foi cancelada.'
            ) from exc

        destino_tmp = Path(tmp_dir) / (caminho.stem + '.pdf')
        if resultado.returncode != 0 or not destino_tmp.exists():
            detalhe = (resultado.stderr or resultado.stdout or '').strip()
            raise ConversaoError(
                f'Não foi possível converter o Word para PDF (detalhe: {detalhe[:300]}).'
            )

        # Copia para fora do diretório temporário antes que ele seja apagado.
        destino_final = caminho.with_suffix('.pdf')
        shutil.copyfile(destino_tmp, destino_final)

    return destino_final, destino_final.name, 'pdf'


# =====================================================================
# RAG: dividir em pedaços (chunking), gerar embeddings, indexar e buscar
# =====================================================================

# Nome do modelo de embeddings local (multilíngue, roda sem API paga).
# Segue a convenção de prefixos "query: " / "passage: " do modelo E5,
# que melhora a busca porque trata pergunta e trecho de forma assimétrica.
MODELO_EMBEDDINGS = 'intfloat/multilingual-e5-small'

TAMANHO_CHUNK = 1000
SOBREPOSICAO_CHUNK = 150


class IndexacaoError(Exception):
    """Erro ao indexar um documento para busca (chunking/embeddings)."""


def dividir_em_chunks(texto, tamanho=TAMANHO_CHUNK, sobreposicao=SOBREPOSICAO_CHUNK):
    """Divide um texto longo em pedaços menores, com sobreposição entre eles.

    A sobreposição evita que uma informação fique cortada exatamente na
    fronteira entre dois pedaços e a resposta perca contexto.
    """
    texto = ' '.join(texto.split())  # normaliza espaços/quebras de linha
    if not texto:
        return []

    chunks = []
    inicio = 0
    passo = max(tamanho - sobreposicao, 1)

    while inicio < len(texto):
        fim = min(inicio + tamanho, len(texto))

        # Tenta terminar num espaço em vez de cortar uma palavra ao meio.
        if fim < len(texto):
            ultimo_espaco = texto.rfind(' ', inicio, fim)
            if ultimo_espaco > inicio:
                fim = ultimo_espaco

        pedaco = texto[inicio:fim].strip()
        if pedaco:
            chunks.append(pedaco)

        if fim >= len(texto):
            break
        inicio += passo

    return chunks


_MODELO_CACHE = {}


def _get_modelo_embeddings():
    """Carrega o modelo de embeddings uma única vez por processo (é lento
    de carregar, então evitamos recarregar a cada chamada)."""
    if 'modelo' not in _MODELO_CACHE:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise IndexacaoError(
                'Suporte a perguntas (RAG) requer "sentence-transformers" '
                'instalado. Rode "pip install -r requirements.txt".'
            ) from exc

        try:
            _MODELO_CACHE['modelo'] = SentenceTransformer(MODELO_EMBEDDINGS)
        except Exception as exc:
            raise IndexacaoError(
                'Não foi possível carregar o modelo de embeddings '
                f'"{MODELO_EMBEDDINGS}" (detalhe: {exc}). Na primeira '
                'execução ele precisa ser baixado do Hugging Face — '
                'confira se o servidor tem acesso à internet.'
            ) from exc

    return _MODELO_CACHE['modelo']


def gerar_embeddings(textos, tipo='passage'):
    """Gera um vetor de embedding para cada texto da lista.

    `tipo` é 'query' para perguntas ou 'passage' para trechos de documentos
    — o modelo E5 espera esse prefixo para buscar melhor.
    """
    if not textos:
        return []

    prefixo = 'query: ' if tipo == 'query' else 'passage: '
    modelo = _get_modelo_embeddings()
    vetores = modelo.encode(
        [prefixo + t for t in textos],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vetores]


def indexar_documento(documento):
    """Extrai o texto do documento, divide em chunks e gera+salva os
    embeddings. Substitui qualquer indexação anterior desse documento."""
    from .models import Chunk

    texto = extrair_texto(documento)
    pedacos = dividir_em_chunks(texto)

    if not pedacos:
        raise IndexacaoError('Não há texto suficiente neste documento para indexar.')

    embeddings = gerar_embeddings(pedacos, tipo='passage')

    documento.chunks.all().delete()
    Chunk.objects.bulk_create([
        Chunk(documento=documento, indice=i, texto=pedaco, embedding=vetor)
        for i, (pedaco, vetor) in enumerate(zip(pedacos, embeddings))
    ])

    return len(pedacos)


def _similaridade_cosseno(a, b):
    import numpy as np

    a = np.array(a)
    b = np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(np.dot(a, b) / denom)


def buscar_trechos_relevantes(pergunta, documento_ids, top_k=6):
    """Retorna os `top_k` chunks (de entre os documentos informados) mais
    parecidos semanticamente com a pergunta."""
    from .models import Chunk

    chunks = list(Chunk.objects.filter(documento_id__in=documento_ids).select_related('documento'))
    if not chunks:
        return []

    (vetor_pergunta,) = gerar_embeddings([pergunta], tipo='query')

    pontuados = [
        (_similaridade_cosseno(vetor_pergunta, chunk.embedding), chunk)
        for chunk in chunks
    ]
    pontuados.sort(key=lambda par: par[0], reverse=True)

    return [chunk for _pontuacao, chunk in pontuados[:top_k]]


def responder_pergunta(pergunta, trechos):
    """Gera uma resposta com a IA (Groq), baseada apenas nos trechos
    recuperados (RAG). Retorna o texto da resposta."""
    if not trechos:
        return (
            'Não encontrei nenhum trecho indexado para procurar essa resposta. '
            'Indexe o(s) documento(s) e tente novamente.'
        )

    contexto = '\n\n'.join(
        f'[Trecho {i+1} — fonte: {chunk.documento.titulo}]\n{chunk.texto}'
        for i, chunk in enumerate(trechos)
    )

    return _chamar_groq(
        system=(
            'Você responde perguntas em português do Brasil usando apenas '
            'os trechos de documentos fornecidos como contexto. Se a '
            'resposta não estiver nos trechos, diga claramente que não '
            'encontrou essa informação nos documentos — não invente nada. '
            'Quando fizer sentido, mencione de qual documento (fonte) veio '
            'cada parte da resposta.'
        ),
        conteudo_usuario=f'Trechos disponíveis:\n\n{contexto}\n\nPergunta: {pergunta}',
    )
