from django import forms
from .models import Producto, NotaPedido, NotaPedidoItem

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["codigo", "nombre", "unidad", "adquisicion", "precio", "peso", "proveedor"]

class NotaForm(forms.ModelForm):
    class Meta:
        model = NotaPedido
        fields = ["fecha", "tipo", "proveedor", "cliente", "orden_compra"]


class NotaItemForm(forms.ModelForm):
    class Meta:
        model = NotaPedidoItem
        fields = ["producto", "cantidad"]

class NotaPedidoForm(forms.ModelForm):
    class Meta:
        model = NotaPedido
        fields = ['tipo', 'proveedor', 'cliente', 'orden_compra']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg'}),
            'proveedor': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg'}),
            'cliente': forms.Select(attrs={'class': 'w-full p-2 border rounded-lg'}),
            'orden_compra': forms.TextInput(attrs={'class': 'w-full p-2 border rounded-lg'}),
        }
