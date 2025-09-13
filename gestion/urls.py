from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Dashboard y gestión
    path("", views.index, name="index"),
    path("gestion-datos/", views.gestion_datos, name="gestion_datos"),
    path("seguimiento/", views.seguimiento, name="seguimiento"),

    # CRUD Productos (HTML)
    path("producto/nuevo/", views.crear_producto, name="crear_producto"),
    path("producto/<int:pk>/editar/", views.editar_producto, name="editar_producto"),
    path("producto/<int:pk>/eliminar/", views.eliminar_producto, name="eliminar_producto"),

    # CRUD Notas de Pedido (HTML)
    path("nota/nueva/", views.crear_nota, name="crear_nota"),
    path("nota/<int:pk>/editar/", views.editar_nota, name="editar_nota"),
    path("nota/<int:pk>/eliminar/", views.eliminar_nota, name="eliminar_nota"),

    # APIs Proveedores
    path("api/proveedores/", views.api_proveedores, name="api_proveedores"),                 # GET, POST
    path("api/proveedores/<int:proveedor_id>/", views.api_proveedor_delete, name="api_proveedor_delete"),  # DELETE  <-- NUEVO

    # APIs Clientes
    path("api/clientes/", views.api_clientes, name="api_clientes"),                          # GET, POST
    path("api/clientes/<int:cliente_id>/", views.api_cliente_delete, name="api_cliente_delete"),          # DELETE  <-- NUEVO

    # APIs Productos
    path("api/productos/", views.api_productos, name="api_productos"),
    path("api/productos/crear/", views.api_producto_crear, name="api_producto_crear"),
    path("api/productos/<int:producto_id>/editar/", views.api_producto_editar, name="api_producto_editar"),

    # APIs Notas
    path("api/notas/", views.api_notas_list, name="api_notas_list"),          # GET
    path("api/notas/crear/", views.api_notas_crear, name="api_notas_crear"),  # POST
    path("api/notas/<int:nota_id>/", views.api_notas_delete, name="api_notas_delete"),  # DELETE

    path("api/notas/export/pdf/", views.api_notas_export_pdf, name="api_notas_export_pdf"),

]
