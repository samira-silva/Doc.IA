from django.contrib import admin

from .models import Chunk, Colecao, Documento, Pergunta


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = (
        'titulo', 'proprietario', 'status_ia', 'status_conversao',
        'status_indexacao', 'criado_em',
    )
    list_filter = ('status_ia', 'status_conversao', 'status_indexacao')
    search_fields = ('titulo', 'proprietario__username')
    readonly_fields = (
        'texto_extraido', 'resumo', 'erro_ia', 'analisado_em', 'criado_em',
        'erro_conversao', 'convertido_em',
        'erro_indexacao', 'indexado_em',
    )


@admin.register(Colecao)
class ColecaoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'proprietario', 'criado_em')
    search_fields = ('titulo', 'proprietario__username')
    filter_horizontal = ('documentos',)


@admin.register(Pergunta)
class PerguntaAdmin(admin.ModelAdmin):
    list_display = ('pergunta_curta', 'proprietario', 'escopo_titulo', 'criado_em')
    search_fields = ('pergunta', 'resposta', 'proprietario__username')
    readonly_fields = ('trechos_usados', 'criado_em')

    def pergunta_curta(self, obj):
        return obj.pergunta[:60]
    pergunta_curta.short_description = 'pergunta'


admin.site.register(Chunk)
