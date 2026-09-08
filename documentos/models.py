from pathlib import Path

from django.conf import settings
from django.db import models


class Documento(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        PROCESSANDO = 'processando', 'Processando'
        CONCLUIDO = 'concluido', 'Concluído'
        ERRO = 'erro', 'Erro'

    titulo = models.CharField('título', max_length=200)
    arquivo = models.FileField(upload_to='documentos/')
    criado_em = models.DateTimeField(auto_now_add=True)
    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documentos',
        null=True,
        blank=True,
    )

    # Campos preenchidos pela análise de IA
    texto_extraido = models.TextField(blank=True, default='')
    resumo = models.TextField(blank=True, default='')
    status_ia = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    erro_ia = models.TextField(blank=True, default='')
    analisado_em = models.DateTimeField(null=True, blank=True)

    # Campos preenchidos pela conversão PDF <-> Word
    arquivo_convertido = models.FileField(
        upload_to='documentos/convertidos/', null=True, blank=True
    )
    status_conversao = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    erro_conversao = models.TextField(blank=True, default='')
    convertido_em = models.DateTimeField(null=True, blank=True)

    # Indexação para o RAG (busca por similaridade + pergunta e resposta)
    status_indexacao = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDENTE
    )
    erro_indexacao = models.TextField(blank=True, default='')
    indexado_em = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.titulo

    @property
    def extensao(self):
        return Path(self.arquivo.name).suffix.lower()

    @property
    def formato_destino(self):
        """Para que formato este documento pode ser convertido, se houver algum."""
        if self.extensao == '.pdf':
            return 'DOCX'
        if self.extensao == '.docx':
            return 'PDF'
        return None


class Colecao(models.Model):
    """Agrupa vários documentos (ex: uma matéria da faculdade, um projeto)
    para permitir perguntas sobre todos eles de uma vez."""

    titulo = models.CharField('título', max_length=200)
    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='colecoes',
    )
    documentos = models.ManyToManyField(
        Documento, related_name='colecoes', blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'coleção'
        verbose_name_plural = 'coleções'
        ordering = ['-criado_em']

    def __str__(self):
        return self.titulo


class Chunk(models.Model):
    """Um pedaço de texto de um documento, com seu embedding, usado na
    busca por similaridade do RAG."""

    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE, related_name='chunks'
    )
    indice = models.PositiveIntegerField()
    texto = models.TextField()
    embedding = models.JSONField()

    class Meta:
        ordering = ['indice']

    def __str__(self):
        return f'{self.documento.titulo} — trecho {self.indice}'


class Pergunta(models.Model):
    """Uma pergunta feita sobre um documento ou uma coleção, e a resposta
    gerada pela IA com base nos trechos mais relevantes (RAG)."""

    proprietario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perguntas'
    )
    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE, null=True, blank=True, related_name='perguntas'
    )
    colecao = models.ForeignKey(
        Colecao, on_delete=models.CASCADE, null=True, blank=True, related_name='perguntas'
    )
    pergunta = models.TextField()
    resposta = models.TextField(blank=True, default='')
    trechos_usados = models.JSONField(default=list, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'pergunta'
        verbose_name_plural = 'perguntas'

    def __str__(self):
        return self.pergunta[:60]

    @property
    def escopo_titulo(self):
        if self.documento_id:
            return self.documento.titulo
        if self.colecao_id:
            return self.colecao.titulo
        return ''
