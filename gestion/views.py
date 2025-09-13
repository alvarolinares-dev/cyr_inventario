from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Case, When, IntegerField, F, Value
from django.db.models.functions import Coalesce
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import NotaPedido, NotaPedidoItem, Producto, Cliente, Proveedor
from .forms import ProductoForm, NotaForm

from decimal import Decimal
import json

# —— PDF con ReportLab (sin dependencias nativas en Windows)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import io


# =====================
# Dashboard principal
# =====================
def index(request):
    q = (request.GET.get("q") or "").strip()

    productos = (
        Producto.objects
        .select_related('proveedor')
        .annotate(
            stock=Coalesce(
                Sum(
                    Case(
                        When(notapedidoitem__nota__tipo='Entrada', then=F('notapedidoitem__cantidad')),
                        When(notapedidoitem__nota__tipo='Salida', then=-F('notapedidoitem__cantidad')),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0)
            )
        )
    )

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) |
            Q(codigo__icontains=q) |
            Q(proveedor__nombre__icontains=q)
        )

    notas = NotaPedido.objects.all().order_by("-fecha")

    return render(
        request,
        "index.html",
        {"productos": productos, "notas": notas, "active_tab": "dashboard"}
    )

# =====================
# Gestión de datos
# =====================
def gestion_datos(request):
    return render(request, "gestion_datos.html")

# =====================
# Seguimiento de pedidos (con filtros)
# =====================
def seguimiento(request):
    notas = NotaPedido.objects.prefetch_related("items__producto").all().order_by("-fecha")

    # --- filtros ---
    search = request.GET.get("q")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if search:
        notas = notas.filter(
            Q(items__producto__nombre__icontains=search) |
            Q(orden_compra__icontains=search) |
            Q(proveedor__nombre__icontains=search) |
            Q(cliente__nombre__icontains=search)
        ).distinct()

    if start_date:
        notas = notas.filter(fecha__date__gte=start_date)

    if end_date:
        notas = notas.filter(fecha__date__lte=end_date)

    return render(request, "seguimiento.html", {"notas": notas, "active_tab": "seguimiento"})

# =====================
# CRUD de Productos
# =====================
def crear_producto(request):
    if request.method == "POST":
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("index")
    else:
        form = ProductoForm()
    return render(request, "crear_producto.html", {"form": form})

def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect("index")
    else:
        form = ProductoForm(instance=producto)
    return render(request, "editar_producto.html", {"form": form})

def eliminar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    producto.delete()
    return redirect("index")

# =====================
# CRUD de Notas de Pedido (servidor)
# =====================
def crear_nota(request):
    if request.method == "POST":
        form = NotaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("seguimiento")
    else:
        form = NotaForm()
    return render(request, "crear_nota.html", {"form": form})

def editar_nota(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    if request.method == "POST":
        form = NotaForm(request.POST, instance=nota)
        if form.is_valid():
            form.save()
            return redirect("seguimiento")
    else:
        form = NotaForm(instance=nota)
    return render(request, "editar_nota.html", {"form": form})

def eliminar_nota(request, pk):
    nota = get_object_or_404(NotaPedido, pk=pk)
    nota.delete()
    return redirect("seguimiento")

# =====================
# APIs simples legacy (sin DRF)
# =====================
def get_proveedores(request):
    proveedores = list(Proveedor.objects.values("id", "nombre"))
    return JsonResponse(proveedores, safe=False)

def get_clientes(request):
    clientes = list(Cliente.objects.values("id", "nombre"))
    return JsonResponse(clientes, safe=False)

def get_productos(request):
    # Si sigues usando esta ruta, mejor ya devolver stock también
    productos = (
        Producto.objects
        .annotate(
            stock=Coalesce(
                Sum(
                    Case(
                        When(notapedidoitem__nota__tipo='Entrada', then=F('notapedidoitem__cantidad')),
                        When(notapedidoitem__nota__tipo='Salida', then=-F('notapedidoitem__cantidad')),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0)
            )
        )
        .values("id", "nombre", "codigo", "precio", "unidad", "stock")
    )
    return JsonResponse(list(productos), safe=False)

def agregar_nota(request):
    if request.method == "POST":
        form = NotaForm(request.POST)
        if form.is_valid():
            nota = form.save()
            return JsonResponse({"status": "ok", "nota_id": nota.id}, status=201)
    return JsonResponse({"error": "Invalid request"}, status=400)

# =====================
# APIs para Proveedores
# =====================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_proveedores(request):
    """API para gestionar proveedores"""
    if request.method == "GET":
        proveedores = Proveedor.objects.all().values('id', 'nombre')
        return JsonResponse(list(proveedores), safe=False)
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            if not nombre:
                return JsonResponse({'error': 'El nombre del proveedor es requerido'}, status=400)
            proveedor = Proveedor.objects.create(nombre=nombre)
            return JsonResponse({'id': proveedor.id, 'nombre': proveedor.nombre, 'mensaje': 'Proveedor creado exitosamente'}, status=201)
        except IntegrityError:
            return JsonResponse({'error': 'Ya existe un proveedor con ese nombre'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Datos JSON inválidos'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)

# =====================
# APIs para Clientes
# =====================
@csrf_exempt
@require_http_methods(["GET", "POST"])
def api_clientes(request):
    """API para gestionar clientes"""
    if request.method == "GET":
        clientes = Cliente.objects.all().values('id', 'nombre')
        return JsonResponse(list(clientes), safe=False)
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            nombre = data.get('nombre', '').strip()
            if not nombre:
                return JsonResponse({'error': 'El nombre del cliente es requerido'}, status=400)
            cliente = Cliente.objects.create(nombre=nombre)
            return JsonResponse({'id': cliente.id, 'nombre': cliente.nombre, 'mensaje': 'Cliente creado exitosamente'}, status=201)
        except IntegrityError:
            return JsonResponse({'error': 'Ya existe un cliente con ese nombre'}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Datos JSON inválidos'}, status=400)
        except Exception as e:
            return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)

# =====================
# APIs para Productos
# =====================
@require_http_methods(["GET"])
def api_productos(request):
    q = (request.GET.get("q") or "").strip()

    productos = (
        Producto.objects
        .select_related('proveedor')
        .annotate(
            stock=Coalesce(
                Sum(
                    Case(
                        When(notapedidoitem__nota__tipo='Entrada', then=F('notapedidoitem__cantidad')),
                        When(notapedidoitem__nota__tipo='Salida', then=-F('notapedidoitem__cantidad')),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ),
                Value(0)
            )
        )
    )

    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) |
            Q(codigo__icontains=q) |
            Q(proveedor__nombre__icontains=q)
        )

    # paginado robusto
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(int(request.GET.get("page_size", 30)), 200)
    except (TypeError, ValueError):
        page_size = 30

    start = (page - 1) * page_size
    end = start + page_size
    total = productos.count()
    productos = productos.order_by('nombre')[start:end]

    results = [{
        'id': p.id,
        'nombre': p.nombre,
        'codigo': p.codigo,
        'unidad': p.unidad,
        'adquisicion': p.adquisicion,
        'precio': float(p.precio),
        'peso': float(p.peso),
        'proveedor': p.proveedor.id,
        'proveedor_nombre': p.proveedor.nombre,
        'stock': p.stock or 0,
    } for p in productos]

    return JsonResponse({'results': results, 'total': total, 'page': page, 'page_size': page_size})


@csrf_exempt
@require_http_methods(["POST"])
def api_producto_crear(request):
    """API para crear un nuevo producto"""
    try:
        data = json.loads(request.body)
        # Validar campos requeridos (solo nombre, adquisición y proveedor son obligatorios)
        if not data.get('nombre', '').strip():
            return JsonResponse({'error': 'El nombre del producto es requerido'}, status=400)
        if not data.get('adquisicion'):
            return JsonResponse({'error': 'El tipo de adquisición es requerido'}, status=400)
        if not data.get('proveedor'):
            return JsonResponse({'error': 'El proveedor es requerido'}, status=400)

        # Validar que el proveedor existe
        try:
            proveedor = Proveedor.objects.get(id=data['proveedor'])
        except Proveedor.DoesNotExist:
            return JsonResponse({'error': 'El proveedor seleccionado no existe'}, status=400)

        # Crear producto - el código se genera automáticamente en el modelo
        producto = Producto.objects.create(
            nombre=data['nombre'].strip(),
            unidad=(data.get('unidad') or 'unidad').strip() or 'unidad',
            adquisicion=data['adquisicion'],
            precio=Decimal(str(data.get('precio', '0.00'))),
            peso=Decimal(str(data.get('peso', '0.00'))),
            proveedor=proveedor
        )

        return JsonResponse({
            'id': producto.id,
            'nombre': producto.nombre,
            'codigo': producto.codigo,
            'unidad': producto.unidad,
            'adquisicion': producto.adquisicion,
            'precio': float(producto.precio),
            'peso': float(producto.peso),
            'proveedor': producto.proveedor.id,
            'proveedor_nombre': producto.proveedor.nombre,
            'mensaje': 'Producto creado exitosamente'
        }, status=201)

    except ValueError as e:
        return JsonResponse({'error': f'Valores numéricos inválidos: {str(e)}'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)

@csrf_exempt
@require_http_methods(["PUT"])
def api_producto_editar(request, producto_id):
    """API para editar un producto específico"""
    try:
        producto = get_object_or_404(Producto, id=producto_id)
        data = json.loads(request.body)

        # Validar campos requeridos
        campos_requeridos = ['nombre', 'codigo', 'unidad', 'adquisicion', 'precio', 'peso', 'proveedor']
        for campo in campos_requeridos:
            if campo not in data or not str(data[campo]).strip():
                return JsonResponse({'error': f'El campo {campo} es requerido'}, status=400)

        # Validar que el proveedor existe
        try:
            proveedor = Proveedor.objects.get(id=data['proveedor'])
        except Proveedor.DoesNotExist:
            return JsonResponse({'error': 'El proveedor seleccionado no existe'}, status=400)

        # Validar que el código no esté duplicado (excepto para el mismo producto)
        if Producto.objects.filter(codigo=data['codigo']).exclude(id=producto_id).exists():
            return JsonResponse({'error': 'Ya existe un producto con ese código'}, status=400)

        # Actualizar producto
        producto.nombre = data['nombre'].strip()
        producto.codigo = data['codigo'].strip()
        producto.unidad = data['unidad'].strip()
        producto.adquisicion = data['adquisicion']
        producto.precio = float(data['precio'])
        producto.peso = float(data['peso'])
        producto.proveedor = proveedor

        producto.full_clean()  # Validación del modelo
        producto.save()

        return JsonResponse({
            'id': producto.id,
            'nombre': producto.nombre,
            'codigo': producto.codigo,
            'unidad': producto.unidad,
            'adquisicion': producto.adquisicion,
            'precio': float(producto.precio),
            'peso': float(producto.peso),
            'proveedor': producto.proveedor.id,
            'proveedor_nombre': producto.proveedor.nombre,
            'mensaje': 'Producto actualizado exitosamente'
        })

    except ValidationError as e:
        return JsonResponse({'error': f'Error de validación: {e.message_dict}'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Valores numéricos inválidos: {str(e)}'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Datos JSON inválidos'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error interno del servidor: {str(e)}'}, status=500)

# =====================
# API NUEVA: crear Nota + Items (impacta stock)
# =====================
@csrf_exempt
@require_http_methods(["POST"])
def api_notas_crear(request):
    """
    JSON:
    {
      "tipo": "Entrada" | "Salida" | "entrada" | "salida",
      "proveedor": <id> (si Entrada),
      "cliente": <id> (si Salida),
      "orden": "texto" (se guarda en orden_compra),
      "items": [{"producto": <id>, "cantidad": <int>}...]
    }
    """
    try:
        payload = json.loads(request.body)

        # ✅ normaliza el tipo
        tipo_raw = str(payload.get("tipo", "")).strip().lower()
        if tipo_raw not in ("entrada", "salida"):
            return JsonResponse({"error": "tipo inválido (Entrada | Salida)"}, status=400)
        tipo = "Entrada" if tipo_raw == "entrada" else "Salida"

        proveedor_id = payload.get("proveedor")
        cliente_id = payload.get("cliente")

        if tipo == "Entrada" and not proveedor_id:
            return JsonResponse({"error": "proveedor requerido para Entrada"}, status=400)
        if tipo == "Salida" and not cliente_id:
            return JsonResponse({"error": "cliente requerido para Salida"}, status=400)

        # admite 'orden', 'orden_compra' o 'orden_venta'
        orden = payload.get("orden") or payload.get("orden_compra") or payload.get("orden_venta") or None

        items = payload.get("items", [])
        if not items or not isinstance(items, list):
            return JsonResponse({"error": "items es requerido y debe ser lista"}, status=400)

        with transaction.atomic():
            proveedor = Proveedor.objects.get(id=proveedor_id) if proveedor_id else None
            cliente = Cliente.objects.get(id=cliente_id) if cliente_id else None

            nota = NotaPedido.objects.create(
                tipo=tipo,
                proveedor=proveedor,
                cliente=cliente,
                orden_compra=orden
            )

            creado = []
            for it in items:
                prod_id = it.get("producto")
                cantidad = it.get("cantidad")
                if not prod_id or not cantidad or int(cantidad) <= 0:
                    raise ValidationError("Cada item requiere producto y cantidad > 0")
                producto = Producto.objects.get(id=prod_id)
                NotaPedidoItem.objects.create(nota=nota, producto=producto, cantidad=int(cantidad))
                creado.append(prod_id)

        return JsonResponse({"status": "ok", "nota_id": nota.id, "items": creado}, status=201)

    except Proveedor.DoesNotExist:
        return JsonResponse({"error": "Proveedor no existe"}, status=400)
    except Cliente.DoesNotExist:
        return JsonResponse({"error": "Cliente no existe"}, status=400)
    except Producto.DoesNotExist:
        return JsonResponse({"error": "Producto no existe"}, status=400)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON inválido"}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Error interno: {e}"}, status=500)




# =====================
# API: listar notas (para seguimiento)
# ====================

@require_http_methods(["GET"])
def api_notas_list(request):
    """
    Devuelve todas las notas en un formato que el seguimiento entiende.
    """
    notas_qs = (
        NotaPedido.objects
        .select_related("proveedor", "cliente")
        .prefetch_related("items__producto")
        .order_by("-fecha")
    )

    data = []
    for n in notas_qs:
        items = [{
            "producto": it.producto_id,
            "producto_nombre": getattr(it.producto, "nombre", ""),
            "cantidad": float(getattr(it, "cantidad", 0) or 0),
            "precio_unitario": float(getattr(it, "precio_unitario", 0) or 0),
        } for it in n.items.all()]

        # fecha robusta (usa n.fecha si existe; si no, intenta created_at)
        fecha_val = getattr(n, "fecha", None) or getattr(n, "created_at", None)
        data.append({
            "id": n.id,
            "fecha": fecha_val.isoformat() if fecha_val else None,
            "tipo": (n.tipo or "").lower(),  # "entrada" | "salida"
            "orden_compra": getattr(n, "orden_compra", "") or None,
            "orden_venta": None,
            "orden": getattr(n, "orden_compra", "") or "",
            "proveedor": (
                {"id": n.proveedor_id, "nombre": getattr(n.proveedor, "nombre", "")}
                if getattr(n, "proveedor_id", None) else None
            ),
            "cliente": (
                {"id": n.cliente_id, "nombre": getattr(n.cliente, "nombre", "")}
                if getattr(n, "cliente_id", None) else None
            ),
            "items": items,
        })

    return JsonResponse(data, safe=False)



@csrf_exempt
@require_http_methods(["DELETE"])
def api_notas_delete(request, nota_id: int):
    """
    Elimina una NotaPedido y sus items.
    El stock se recalcula automáticamente porque lo anotas desde los items.
    """
    try:
        with transaction.atomic():
            nota = get_object_or_404(NotaPedido, id=nota_id)
            nota.delete()
        return JsonResponse({"status": "ok", "deleted_id": nota_id})
    except Exception as e:
        return JsonResponse({"error": f"No se pudo eliminar la nota: {e}"}, status=500)

# views.py



# ...

@csrf_exempt
@require_http_methods(["DELETE"])
def api_proveedor_delete(request, proveedor_id: int):
    """
    Elimina un proveedor si no está en uso.
    Rechaza si hay productos o notas que lo referencian.
    """
    try:
        proveedor = get_object_or_404(Proveedor, id=proveedor_id)

        # ¿Algún producto usa este proveedor?
        hay_productos = Producto.objects.filter(proveedor_id=proveedor_id).exists()
        if hay_productos:
            return JsonResponse(
                {"error": "No se puede eliminar: existen productos asociados a este proveedor."},
                status=400
            )

        # ¿Alguna nota lo referencia?
        hay_notas = NotaPedido.objects.filter(proveedor_id=proveedor_id).exists()
        if hay_notas:
            return JsonResponse(
                {"error": "No se puede eliminar: existen notas de pedido que referencian este proveedor."},
                status=400
            )

        proveedor.delete()
        return JsonResponse({"status": "ok", "deleted_id": proveedor_id})
    except Exception as e:
        return JsonResponse({"error": f"Error al eliminar proveedor: {e}"}, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def api_cliente_delete(request, cliente_id: int):
    """
    Elimina un cliente si no está en uso.
    Rechaza si hay notas que lo referencian.
    """
    try:
        cliente = get_object_or_404(Cliente, id=cliente_id)

        # ¿Alguna nota lo referencia?
        hay_notas = NotaPedido.objects.filter(cliente_id=cliente_id).exists()
        if hay_notas:
            return JsonResponse(
                {"error": "No se puede eliminar: existen notas de pedido que referencian este cliente."},
                status=400
            )

        cliente.delete()
        return JsonResponse({"status": "ok", "deleted_id": cliente_id})
    except Exception as e:
        return JsonResponse({"error": f"Error al eliminar cliente: {e}"}, status=500)



@require_http_methods(["GET"])
def api_notas_export_pdf(request):
    """
    Exporta a PDF las notas seleccionadas.
    GET /api/notas/export/pdf/?ids=1,2,3
    Si no vienen ids, acepta filtros: q, start_date, end_date (como en seguimiento).
    Si no viene nada, exporta todas.
    """
    ids = (request.GET.get("ids") or "").strip()
    q = request.GET.get("q")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    notas = (
        NotaPedido.objects
        .select_related("proveedor", "cliente")
        .prefetch_related("items__producto")
        .order_by("-fecha", "-id")
    )

    if ids:
        try:
            id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
            if not id_list:
                return JsonResponse({"error": "Parámetro ids inválido"}, status=400)
            notas = notas.filter(id__in=id_list)
        except Exception:
            return JsonResponse({"error": "Parámetro ids inválido"}, status=400)
    else:
        if q:
            notas = notas.filter(
                Q(items__producto__nombre__icontains=q) |
                Q(orden_compra__icontains=q) |
                Q(proveedor__nombre__icontains=q) |
                Q(cliente__nombre__icontains=q)
            ).distinct()
        if start_date:
            notas = notas.filter(fecha__date__gte=start_date)
        if end_date:
            notas = notas.filter(fecha__date__lte=end_date)

    # --- construir PDF con ReportLab ---
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=18, rightMargin=18, topMargin=20, bottomMargin=20
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Hdr", fontName="Helvetica", fontSize=14, leading=16, spaceAfter=8))
    styles.add(ParagraphStyle(name="Cell", fontName="Helvetica", fontSize=9, leading=11))

    story = []
    story.append(Paragraph("C&R Logística — Notas de Pedido (Exportación)", styles["Hdr"]))
    story.append(Spacer(1, 6))

    data = [[
        Paragraph("<b># Nota</b>", styles["Cell"]),
        Paragraph("<b>Fecha</b>", styles["Cell"]),
        Paragraph("<b>Tipo</b>", styles["Cell"]),
        Paragraph("<b>Productos</b>", styles["Cell"]),
        Paragraph("<b>Destinatario</b>", styles["Cell"]),
        Paragraph("<b>Orden</b>", styles["Cell"]),
    ]]

    def fmt_fecha(n):
        f = getattr(n, "fecha", None)
        return f.strftime("%d/%m/%Y %H:%M") if f else "-"

    def fmt_tipo(n):
        t = (n.tipo or "").lower()
        return "Entrada" if t == "entrada" else "Salida" if t == "salida" else (n.tipo or "-")

    def fmt_dest(n):
        if n.proveedor_id:
            return f"Proveedor: {getattr(n.proveedor, 'nombre', '') or '-'}"
        if n.cliente_id:
            return f"Cliente: {getattr(n.cliente, 'nombre', '') or '-'}"
        return "-"

    def fmt_items(n):
        líneas = []
        for it in n.items.all():
            nombre = getattr(it.producto, "nombre", "") or "-"
            cant = getattr(it, "cantidad", 0) or 0
            líneas.append(f"{nombre} (x{cant})")
        # ReportLab hace wrap de \n automáticamente
        return "\n".join(líneas) or "-"

    # filas
    for n in notas:
        # Si quieres replicar EXACTO tu numeración del front,
        # tendrás que traer ese secuencial por año desde BD.
        numero = f"N{ (n.fecha.year if n.fecha else 0) }_{str(n.id).zfill(4)}"
        data.append([
            Paragraph(numero, styles["Cell"]),
            Paragraph(fmt_fecha(n), styles["Cell"]),
            Paragraph(fmt_tipo(n), styles["Cell"]),
            Paragraph(fmt_items(n).replace("&", "&amp;"), styles["Cell"]),
            Paragraph(fmt_dest(n).replace("&", "&amp;"), styles["Cell"]),
            Paragraph((n.orden_compra or "-").replace("&", "&amp;"), styles["Cell"]),
        ])

    table = Table(
        data,
        colWidths=[70, 90, 60, 330, 150, 120],
        repeatRows=1
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor("#111827")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ALIGN", (0,0), (-1,0), "LEFT"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))

    story.append(table)
    doc.build(story)

    pdf_value = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="notas_pedido.pdf"'
    resp.write(pdf_value)
    return resp

