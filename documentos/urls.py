from django.urls import path
from . import views

urlpatterns = [
    path('', views.lista_documentos, name='lista_documentos'),
    path('cadastro/', views.cadastro, name='cadastro'),
    path('upload/', views.upload_documento, name='upload_documento'),
    path('documento/<int:pk>/', views.detalhe_documento, name='detalhe_documento'),
    path('documento/<int:pk>/editar/', views.editar_documento, name='editar_documento'),
    path('documento/<int:pk>/excluir/', views.excluir_documento, name='excluir_documento'),
    path('documento/<int:pk>/analisar/', views.analisar_documento, name='analisar_documento'),
    path('documento/<int:pk>/converter/', views.converter_documento, name='converter_documento'),
    path('documento/<int:pk>/indexar/', views.indexar_documento, name='indexar_documento'),

    path('colecoes/', views.colecoes_lista, name='colecoes_lista'),
    path('colecoes/criar/', views.colecao_criar, name='colecao_criar'),
    path('colecoes/<int:pk>/editar/', views.colecao_editar, name='colecao_editar'),
    path('colecoes/<int:pk>/excluir/', views.colecao_excluir, name='colecao_excluir'),

    path('perguntar/', views.perguntar, name='perguntar'),
]
