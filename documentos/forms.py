from django import forms

from .models import Colecao, Documento


class DocumentoForm(forms.ModelForm):
    class Meta:
        model = Documento
        fields = ['titulo', 'arquivo']


class ColecaoForm(forms.ModelForm):
    documentos = forms.ModelMultipleChoiceField(
        queryset=Documento.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Documentos nesta coleção',
    )

    class Meta:
        model = Colecao
        fields = ['titulo', 'documentos']

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None:
            self.fields['documentos'].queryset = Documento.objects.filter(
                proprietario=usuario
            ).order_by('-criado_em')


class PerguntaForm(forms.Form):
    ESCOPO_CHOICES = [
        ('documento', 'Um documento'),
        ('colecao', 'Uma coleção'),
    ]

    escopo = forms.ChoiceField(
        choices=ESCOPO_CHOICES, widget=forms.RadioSelect, initial='documento'
    )
    documento = forms.ModelChoiceField(
        queryset=Documento.objects.none(), required=False, label='Documento'
    )
    colecao = forms.ModelChoiceField(
        queryset=Colecao.objects.none(), required=False, label='Coleção'
    )
    pergunta = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), label='Sua pergunta'
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None:
            self.fields['documento'].queryset = Documento.objects.filter(
                proprietario=usuario
            ).order_by('-criado_em')
            self.fields['colecao'].queryset = Colecao.objects.filter(
                proprietario=usuario
            ).order_by('-criado_em')

    def clean(self):
        cleaned = super().clean()
        escopo = cleaned.get('escopo')

        if escopo == 'documento' and not cleaned.get('documento'):
            self.add_error('documento', 'Escolha um documento.')
        elif escopo == 'colecao' and not cleaned.get('colecao'):
            self.add_error('colecao', 'Escolha uma coleção.')

        return cleaned
