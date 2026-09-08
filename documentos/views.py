from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.files import File
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ColecaoForm, DocumentoForm, PerguntaForm
from .models import Colecao, Documento, Pergunta
from .utils import (
    ConversaoError,
    ExtracaoTextoError,
    IndexacaoError,
    buscar_trechos_relevantes,
    converter_arquivo,
    extrair_texto,
    indexar_documento as indexar_documento_util,
    responder_pergunta,
    resumir_com_ia,
)


def cadastro(request):
    if request.user.is_authenticated:
        return redirect('lista_documentos')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            usuario = form.save()
            login(request, usuario)
            messages.success(request, f'Bem-vindo(a), {usuario.username}!')
            return redirect('lista_documentos')
    else:
        form = UserCreationForm()

    return render(request, 'registration/cadastro.html', {'form': form})


@login_required
def lista_documentos(request):
    documentos = Documento.objects.filter(proprietario=request.user).order_by('-criado_em')
    return render(request, 'documentos/lista.html', {'documentos': documentos})


@login_required
def upload_documento(request):
    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES)

        if form.is_valid():
            documento = form.save(commit=False)
            documento.proprietario = request.user
            documento.save()
            messages.success(request, 'Documento enviado com sucesso.')
            return redirect('lista_documentos')
    else:
        form = DocumentoForm()

    return render(request, 'documentos/upload.html', {'form': form})


@login_required
def detalhe_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk, proprietario=request.user)
    return render(request, 'documentos/detalhe.html', {'documento': documento})


@login_required
def editar_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk, proprietario=request.user)

    if request.method == 'POST':
        form = DocumentoForm(request.POST, request.FILES, instance=documento)
        if form.is_valid():
            arquivo_mudou = 'arquivo' in form.changed_data
            documento = form.save()

            # Se um novo arquivo foi enviado, a análise e a conversão anteriores não valem mais.
            if arquivo_mudou:
                documento.texto_extraido = ''
                documento.resumo = ''
                documento.status_ia = Documento.Status.PENDENTE
                documento.erro_ia = ''
                documento.analisado_em = None

                if documento.arquivo_convertido:
                    documento.arquivo_convertido.delete(save=False)
                documento.status_conversao = Documento.Status.PENDENTE
                documento.erro_conversao = ''
                documento.convertido_em = None

                documento.chunks.all().delete()
                documento.status_indexacao = Documento.Status.PENDENTE
                documento.erro_indexacao = ''
                documento.indexado_em = None

                documento.save()

            messages.success(request, 'Documento atualizado com sucesso.')
            return redirect('detalhe_documento', pk=documento.pk)
    else:
        form = DocumentoForm(instance=documento)

    return render(request, 'documentos/editar.html', {'form': form, 'documento': documento})


@login_required
def excluir_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk, proprietario=request.user)

    if request.method == 'POST':
        titulo = documento.titulo
        documento.arquivo.delete(save=False)
        if documento.arquivo_convertido:
            documento.arquivo_convertido.delete(save=False)
        documento.delete()
        messages.success(request, f'"{titulo}" foi excluído.')
        return redirect('lista_documentos')

    return render(request, 'documentos/confirmar_exclusao.html', {'documento': documento})


@login_required
def analisar_documento(request, pk):
    """Extrai o texto do documento e pede um resumo à IA."""
    documento = get_object_or_404(Documento, pk=pk, proprietario=request.user)

    if request.method != 'POST':
        return redirect('detalhe_documento', pk=pk)

    documento.status_ia = Documento.Status.PROCESSANDO
    documento.erro_ia = ''
    documento.save(update_fields=['status_ia', 'erro_ia'])

    try:
        texto = extrair_texto(documento)
        resumo = resumir_com_ia(texto)

        documento.texto_extraido = texto
        documento.resumo = resumo
        documento.status_ia = Documento.Status.CONCLUIDO
        documento.analisado_em = timezone.now()
        documento.save()

        messages.success(request, 'Documento analisado com sucesso.')
    except ExtracaoTextoError as exc:
        documento.status_ia = Documento.Status.ERRO
        documento.erro_ia = str(exc)
        documento.save(update_fields=['status_ia', 'erro_ia'])
        messages.error(request, str(exc))
    except Exception as exc:
        documento.status_ia = Documento.Status.ERRO
        documento.erro_ia = str(exc)
        documento.save(update_fields=['status_ia', 'erro_ia'])
        messages.error(request, f'Erro ao analisar documento: {exc}')

    return redirect('detalhe_documento', pk=pk)


@login_required
def converter_documento(request, pk):
    """Converte o arquivo entre PDF e Word (na direção que fizer sentido)."""
    documento = get_object_or_404(Documento, pk=pk, proprietario=request.user)

    if request.method != 'POST':
        return redirect('detalhe_documento', pk=pk)

    if not documento.formato_destino:
        messages.error(request, 'Este tipo de arquivo não pode ser convertido.')
        return redirect('detalhe_documento', pk=pk)

    documento.status_conversao = Documento.Status.PROCESSANDO
    documento.erro_conversao = ''
    documento.save(update_fields=['status_conversao', 'erro_conversao'])

    try:
        caminho_gerado, nome_arquivo, _extensao = converter_arquivo(documento)

        if documento.arquivo_convertido:
            documento.arquivo_convertido.delete(save=False)

        with open(caminho_gerado, 'rb') as arquivo_aberto:
            documento.arquivo_convertido.save(nome_arquivo, File(arquivo_aberto), save=False)

        documento.status_conversao = Documento.Status.CONCLUIDO
        documento.convertido_em = timezone.now()
        documento.save()

        caminho_gerado.unlink(missing_ok=True)

        messages.success(request, 'Documento convertido com sucesso.')
    except ConversaoError as exc:
        documento.status_conversao = Documento.Status.ERRO
        documento.erro_conversao = str(exc)
        documento.save(update_fields=['status_conversao', 'erro_conversao'])
        messages.error(request, str(exc))
    except Exception as exc:
        documento.status_conversao = Documento.Status.ERRO
        documento.erro_conversao = str(exc)
        documento.save(update_fields=['status_conversao', 'erro_conversao'])
        messages.error(request, f'Erro ao converter documento: {exc}')

    return redirect('detalhe_documento', pk=pk)


@login_required
def indexar_documento(request, pk):
    """Prepara o documento para perguntas: extrai texto, divide em pedaços
    e gera os embeddings de cada pedaço (RAG)."""
    documento = get_object_or_404(Documento, pk=pk, proprietario=request.user)

    if request.method != 'POST':
        return redirect('detalhe_documento', pk=pk)

    documento.status_indexacao = Documento.Status.PROCESSANDO
    documento.erro_indexacao = ''
    documento.save(update_fields=['status_indexacao', 'erro_indexacao'])

    try:
        num_chunks = indexar_documento_util(documento)

        documento.status_indexacao = Documento.Status.CONCLUIDO
        documento.indexado_em = timezone.now()
        documento.save()

        messages.success(request, f'Documento indexado ({num_chunks} trechos). Já pode perguntar sobre ele.')
    except (ExtracaoTextoError, IndexacaoError) as exc:
        documento.status_indexacao = Documento.Status.ERRO
        documento.erro_indexacao = str(exc)
        documento.save(update_fields=['status_indexacao', 'erro_indexacao'])
        messages.error(request, str(exc))
    except Exception as exc:
        documento.status_indexacao = Documento.Status.ERRO
        documento.erro_indexacao = str(exc)
        documento.save(update_fields=['status_indexacao', 'erro_indexacao'])
        messages.error(request, f'Erro ao indexar documento: {exc}')

    return redirect('detalhe_documento', pk=pk)


@login_required
def colecoes_lista(request):
    colecoes = Colecao.objects.filter(proprietario=request.user)
    return render(request, 'documentos/colecoes.html', {'colecoes': colecoes})


@login_required
def colecao_criar(request):
    if request.method == 'POST':
        form = ColecaoForm(request.POST, usuario=request.user)
        if form.is_valid():
            colecao = form.save(commit=False)
            colecao.proprietario = request.user
            colecao.save()
            form.save_m2m()
            messages.success(request, 'Coleção criada com sucesso.')
            return redirect('colecoes_lista')
    else:
        form = ColecaoForm(usuario=request.user)

    return render(request, 'documentos/colecao_form.html', {'form': form, 'modo': 'criar'})


@login_required
def colecao_editar(request, pk):
    colecao = get_object_or_404(Colecao, pk=pk, proprietario=request.user)

    if request.method == 'POST':
        form = ColecaoForm(request.POST, instance=colecao, usuario=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coleção atualizada com sucesso.')
            return redirect('colecoes_lista')
    else:
        form = ColecaoForm(instance=colecao, usuario=request.user)

    return render(request, 'documentos/colecao_form.html', {'form': form, 'modo': 'editar', 'colecao': colecao})


@login_required
def colecao_excluir(request, pk):
    colecao = get_object_or_404(Colecao, pk=pk, proprietario=request.user)

    if request.method == 'POST':
        titulo = colecao.titulo
        colecao.delete()
        messages.success(request, f'Coleção "{titulo}" foi excluída.')
        return redirect('colecoes_lista')

    return render(request, 'documentos/colecao_confirmar_exclusao.html', {'colecao': colecao})


@login_required
def perguntar(request):
    """Página de perguntas e respostas (RAG): escolhe um documento ou uma
    coleção, faz a pergunta, e recebe uma resposta baseada nos trechos
    mais relevantes encontrados por busca semântica."""
    resposta = None
    trechos = None

    documento_inicial = request.GET.get('documento')
    colecao_inicial = request.GET.get('colecao')
    initial = {}
    if documento_inicial:
        initial = {'escopo': 'documento', 'documento': documento_inicial}
    elif colecao_inicial:
        initial = {'escopo': 'colecao', 'colecao': colecao_inicial}

    if request.method == 'POST':
        form = PerguntaForm(request.POST, usuario=request.user)

        if form.is_valid():
            escopo = form.cleaned_data['escopo']
            pergunta_texto = form.cleaned_data['pergunta']

            if escopo == 'documento':
                documento = form.cleaned_data['documento']
                documentos = [documento]
                colecao = None
            else:
                colecao = form.cleaned_data['colecao']
                documentos = list(colecao.documentos.all())
                documento = None

            # Indexa (na hora, se preciso) qualquer documento do escopo que
            # ainda não tenha sido indexado.
            pendentes = [d for d in documentos if d.status_indexacao != Documento.Status.CONCLUIDO]
            erros_indexacao = []
            for d in pendentes:
                try:
                    indexar_documento_util(d)
                    d.status_indexacao = Documento.Status.CONCLUIDO
                    d.indexado_em = timezone.now()
                    d.erro_indexacao = ''
                    d.save()
                except Exception as exc:
                    d.status_indexacao = Documento.Status.ERRO
                    d.erro_indexacao = str(exc)
                    d.save()
                    erros_indexacao.append(f'{d.titulo}: {exc}')

            documento_ids = [d.pk for d in documentos if d.status_indexacao == Documento.Status.CONCLUIDO]

            if not documento_ids:
                messages.error(
                    request,
                    'Nenhum documento do escopo escolhido pôde ser indexado. '
                    + ' '.join(erros_indexacao),
                )
            else:
                try:
                    trechos = buscar_trechos_relevantes(pergunta_texto, documento_ids)
                    resposta = responder_pergunta(pergunta_texto, trechos)

                    Pergunta.objects.create(
                        proprietario=request.user,
                        documento=documento,
                        colecao=colecao,
                        pergunta=pergunta_texto,
                        resposta=resposta,
                        trechos_usados=[
                            {'documento': t.documento.titulo, 'trecho': t.texto[:300]}
                            for t in trechos
                        ],
                    )

                    if erros_indexacao:
                        messages.error(
                            request,
                            'Alguns documentos da coleção não puderam ser indexados e '
                            'foram ignorados nesta pergunta: ' + ' '.join(erros_indexacao),
                        )
                except Exception as exc:
                    messages.error(request, f'Erro ao gerar a resposta: {exc}')
    else:
        form = PerguntaForm(usuario=request.user, initial=initial)

    return render(request, 'documentos/perguntar.html', {
        'form': form,
        'resposta': resposta,
        'trechos': trechos,
    })
