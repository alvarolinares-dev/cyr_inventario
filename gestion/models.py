from decimal import Decimal
from django.db import models
from django.utils import timezone

# ---------- Catálogo de unidades ----------
UNIDAD_CHOICES = [
    ("Und", "Unidad"),
    ("Caja", "Caja"),
    ("Paquete", "Paquete"),
    ("Par", "Par"),
    ("Docena", "Docena"),

    ("Kg", "Kilogramo"),
    ("g", "Gramo"),
    ("Ton", "Tonelada"),

    ("L", "Litro"),
    ("mL", "Mililitro"),
    ("Gal", "Galón"),

    ("m", "Metro"),
    ("cm", "Centímetro"),
    ("mm", "Milímetro"),
    ("Rollo", "Rollo"),
    ("Pliego", "Pliego"),

    ("Set", "Set"),
    ("Kit", "Kit"),
]

class Proveedor(models.Model):
    nombre = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.nombre


class Cliente(models.Model):
    nombre = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    codigo = models.CharField(max_length=50, unique=True, blank=True, null=True)

    # 👇 Ahora es un dropdown con choices
    unidad = models.CharField(
        max_length=20,
        choices=UNIDAD_CHOICES,
        default="Und",
    )

    adquisicion = models.CharField(
        max_length=20,
        choices=[("Fabricacion", "Fabricación"), ("Compra", "Compra")],
        default="Compra",
    )
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    peso = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    proveedor = models.ForeignKey(Proveedor, on_delete=models.CASCADE, related_name="productos")

    def save(self, *args, **kwargs):
        if not self.codigo:
            prefijo = "F1" if self.adquisicion == "Fabricacion" else "M1"
            base = (self.nombre or "").upper()
            abreviatura = (base[:3] if len(base) >= 3 else base.ljust(3, "X"))
            count = Producto.objects.filter(
                codigo__startswith=prefijo + abreviatura
            ).count() + 1
            correlativo = str(count).zfill(3)
            self.codigo = f"{prefijo}{abreviatura}{correlativo}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} ({self.codigo or 'S/C'})"


class NotaPedido(models.Model):
    TIPO_CHOICES = [
        ("Entrada", "Entrada"),
        ("Salida", "Salida"),
    ]
    fecha = models.DateTimeField(default=timezone.now)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True)
    orden_compra = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.tipo} - {self.fecha.strftime('%d/%m/%Y')}"


class NotaPedidoItem(models.Model):
    nota = models.ForeignKey(NotaPedido, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.cantidad * self.producto.precio

    def __str__(self):
        return f"{self.producto.nombre} x {self.cantidad}"
