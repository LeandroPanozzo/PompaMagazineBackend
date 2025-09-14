from rest_framework.routers import DefaultRouter
from django.urls import path, include, re_path
from . import views
from django.views.generic import TemplateView
from .views import (
    # ViewSets principales
    ContenidoViewSet,
    NewsletterPublicoView,
    NewsletterViewSet,
    SuscriptorViewSet,
    TiendaMadeInArgViewSet,
    ProductoMadeInArgViewSet,
    ArtistaMadeInArgViewSet,
    MadeInArgViewSet,  # ViewSet integrado para MadeInArg
    
    # ViewSets auxiliares
    TrabajadorViewSet,
    UsuarioViewSet,
    EstadoPublicacionViewSet,
    PublicidadViewSet,
    EspacioReferenciaViewSet,
    ImagenLinkViewSet,
    UserProfileViewSet,
    
    # Views de autenticación
    RegisterView,
    LoginView,
    CurrentUserView,
    
    # Views de recuperación de contraseña
    RequestPasswordResetView,
    VerifyTokenView,
    ResetPasswordView,
    
    # Views administrativas
    AdminDashboardView,
    
    # Views genéricas
    EstadoPublicacionList,
    TrabajadorList,
    
    # Funciones auxiliares
    redirect_to_home,
    upload_image,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Crear un router y registrar todos los viewsets
router = DefaultRouter()

# ================== VIEWSETS PRINCIPALES ==================

# Contenido principal (todas las categorías)
router.register(r'contenido', ContenidoViewSet, basename='contenido')

# MadeInArg - Componentes separados
router.register(r'tiendas', TiendaMadeInArgViewSet, basename='tiendas')
router.register(r'productos', ProductoMadeInArgViewSet, basename='productos')
router.register(r'artistas', ArtistaMadeInArgViewSet, basename='artistas')

# MadeInArg - ViewSet integrado
router.register(r'madeinarg', MadeInArgViewSet, basename='madeinarg')

# ================== VIEWSETS AUXILIARES ==================

router.register(r'trabajadores', TrabajadorViewSet, basename='trabajadores')
router.register(r'usuarios', UsuarioViewSet, basename='usuarios')
router.register(r'estados-publicacion', EstadoPublicacionViewSet, basename='estados-publicacion')
router.register(r'publicidades', PublicidadViewSet, basename='publicidades')
router.register(r'espacios-referencia', EspacioReferenciaViewSet, basename='espacios-referencia')
router.register(r'imagen-links', ImagenLinkViewSet, basename='imagen-links')
router.register(r'user-profiles', UserProfileViewSet, basename='user-profiles')


# En la sección donde registras los viewsets en el router:
router.register(r'suscriptores', SuscriptorViewSet, basename='suscriptores')
router.register(r'newsletters', NewsletterViewSet, basename='newsletters')

# ================== URLS PRINCIPALES ==================

urlpatterns = [
    # Redirección principal
    path('', redirect_to_home, name='redirect_to_home'),
    
    # Incluir todas las rutas del router
    path('api/v1/', include(router.urls)),
    
    # ================== AUTENTICACIÓN ==================
    
    # Registro y login personalizados
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('current-user/', CurrentUserView.as_view(), name='current-user'),
    
    # Tokens JWT
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Recuperación de contraseña
    path('password/reset/request/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('password/reset/verify/', VerifyTokenView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/', ResetPasswordView.as_view(), name='password-reset-confirm'),
    
    # ================== CONTENIDO - ACCIONES ESPECÍFICAS ==================
    
    # URLs para contenido con soporte de slug (SEO friendly)
    re_path(r'^api/v1/contenido/(?P<pk>\d+)-(?P<slug>[\w-]+)/$', 
            ContenidoViewSet.as_view({'get': 'retrieve'}), 
            name='contenido-detail-slug'),
    
    # Acciones estadísticas de contenido
    path('api/v1/contenido/estadisticas/', 
         ContenidoViewSet.as_view({'get': 'estadisticas_visitas'}), 
         name='contenido-estadisticas'),
    
    path('api/v1/contenido/mas-vistas/', 
         ContenidoViewSet.as_view({'get': 'mas_vistas'}), 
         name='contenido-mas-vistas'),
    
    path('api/v1/contenido/mas-leidas/', 
         ContenidoViewSet.as_view({'get': 'mas_leidas'}), 
         name='contenido-mas-leidas'),
    
    path('api/v1/contenido/recientes/', 
         ContenidoViewSet.as_view({'get': 'recientes'}), 
         name='contenido-recientes'),
    
    path('api/v1/contenido/destacados/', 
         ContenidoViewSet.as_view({'get': 'destacados'}), 
         name='contenido-destacados'),
    
    path('api/v1/contenido/buscar/', 
         ContenidoViewSet.as_view({'get': 'buscar'}), 
         name='contenido-buscar'),
    
    # Acciones por categoría
    path('api/v1/contenido/editorials/', 
         ContenidoViewSet.as_view({'get': 'editorials'}), 
         name='contenido-editorials'),
    
    path('api/v1/contenido/issues/', 
         ContenidoViewSet.as_view({'get': 'issues'}), 
         name='contenido-issues'),
    
    path('api/v1/contenido/madeinarg/', 
         ContenidoViewSet.as_view({'get': 'madeinarg'}), 
         name='contenido-madeinarg'),
         
    
    path('api/v1/contenido/news/', 
         ContenidoViewSet.as_view({'get': 'news'}), 
         name='contenido-news'),
    
    path('api/v1/contenido/club-pompa/', 
         ContenidoViewSet.as_view({'get': 'club_pompa'}), 
         name='contenido-club-pompa'),
    
    # Acciones administrativas específicas de contenido
    path('api/v1/contenido/<int:pk>/duplicar/', 
         ContenidoViewSet.as_view({'post': 'duplicar'}), 
         name='contenido-duplicar'),
    
    path('api/v1/contenido/<int:pk>/cambiar-estado/', 
         ContenidoViewSet.as_view({'post': 'cambiar_estado'}), 
         name='contenido-cambiar-estado'),
    
    # Subida de imágenes para contenido
    path('api/v1/contenido/upload-image/', 
         ContenidoViewSet.as_view({'post': 'upload_image'}), 
         name='contenido-upload-image'),
    
    # ================== MADEINARG - ACCIONES ESPECÍFICAS ==================
    
    # MadeInArg - ViewSet integrado con todas las funcionalidades
    path('api/v1/madeinarg/resumen/', 
         MadeInArgViewSet.as_view({'get': 'resumen'}), 
         name='madeinarg-resumen'),
    
    path('api/v1/madeinarg/categoria/', 
         MadeInArgViewSet.as_view({'get': 'categoria'}), 
         name='madeinarg-categoria'),
    
    path('api/v1/madeinarg/estadisticas/', 
         MadeInArgViewSet.as_view({'get': 'estadisticas'}), 
         name='madeinarg-estadisticas'),
    
    path('api/v1/madeinarg/buscar/', 
         MadeInArgViewSet.as_view({'get': 'buscar'}), 
         name='madeinarg-buscar'),
    
    # ================== TIENDAS - ACCIONES ESPECÍFICAS MEJORADAS ==================

path('api/v1/tiendas/destacadas/', 
     TiendaMadeInArgViewSet.as_view({'get': 'destacadas'}), 
     name='tiendas-destacadas'),

# NUEVA: Tiendas que tienen productos de una categoría específica
path('api/v1/tiendas/con-productos-categoria/', 
     TiendaMadeInArgViewSet.as_view({'get': 'con_productos_categoria'}), 
     name='tiendas-con-productos-categoria'),

path('api/v1/tiendas/<int:pk>/productos-por-categoria/', 
     TiendaMadeInArgViewSet.as_view({'get': 'productos_por_categoria'}), 
     name='tiendas-productos-por-categoria'),

path('api/v1/tiendas/<int:pk>/cambiar-estado/', 
     TiendaMadeInArgViewSet.as_view({'post': 'cambiar_estado'}), 
     name='tiendas-cambiar-estado'),

# ================== PRODUCTOS - ACCIONES MEJORADAS ==================

# MEJORADA: Ahora soporta filtro por categoría específica
path('api/v1/productos/por-categoria/', 
     ProductoMadeInArgViewSet.as_view({'get': 'por_categoria'}), 
     name='productos-por-categoria'),

# MEJORADA: Ahora respeta filtros de categoría
path('api/v1/productos/destacados/', 
     ProductoMadeInArgViewSet.as_view({'get': 'destacados'}), 
     name='productos-destacados'),

path('api/v1/productos/<int:pk>/cambiar-estado/', 
     ProductoMadeInArgViewSet.as_view({'post': 'cambiar_estado'}), 
     name='productos-cambiar-estado'),

# ================== MADEINARG - ACCIONES MEJORADAS ==================

# MEJORADA: Filtrado correcto por categorías
path('api/v1/madeinarg/categoria/', 
     MadeInArgViewSet.as_view({'get': 'categoria'}), 
     name='madeinarg-categoria'),

# MEJORADA: Búsqueda con filtro de categoría
path('api/v1/madeinarg/buscar/', 
     MadeInArgViewSet.as_view({'get': 'buscar'}), 
     name='madeinarg-buscar'),

# Las demás URLs se mantienen igual
path('api/v1/madeinarg/resumen/', 
     MadeInArgViewSet.as_view({'get': 'resumen'}), 
     name='madeinarg-resumen'),

path('api/v1/madeinarg/estadisticas/', 
     MadeInArgViewSet.as_view({'get': 'estadisticas'}), 
     name='madeinarg-estadisticas'),
    # ================== ARTISTAS - ACCIONES ESPECÍFICAS ==================
    
    path('api/v1/artistas/destacados/', 
         ArtistaMadeInArgViewSet.as_view({'get': 'destacados'}), 
         name='artistas-destacados'),
    
    path('api/v1/artistas/con-video/', 
         ArtistaMadeInArgViewSet.as_view({'get': 'con_video'}), 
         name='artistas-con-video'),
    
    path('api/v1/artistas/<int:pk>/galeria/', 
         ArtistaMadeInArgViewSet.as_view({'get': 'galeria'}), 
         name='artistas-galeria'),
    
    path('api/v1/artistas/<int:pk>/cambiar-estado/', 
         ArtistaMadeInArgViewSet.as_view({'post': 'cambiar_estado'}), 
         name='artistas-cambiar-estado'),
    
    # ================== ADMINISTRACIÓN ==================
    
    # Dashboard administrativo
    path('api/v1/admin/dashboard/', 
         AdminDashboardView.as_view(), 
         name='admin-dashboard'),
    
    # ================== UTILIDADES ==================
    
    # Subida de imágenes general
    path('api/v1/upload/', 
         upload_image, 
         name='upload_image'),
    
    # Listas genéricas
    path('api/v1/estados-list/', 
         EstadoPublicacionList.as_view(), 
         name='estados-list'),
    
    path('api/v1/trabajadores-list/', 
         TrabajadorList.as_view(), 
         name='trabajadores-list'),
    
    # ================== URLS DE COMPATIBILIDAD ==================
    
    # Para mantener compatibilidad con versiones anteriores (sin api/v1)
    path('contenido/', include([
        path('', ContenidoViewSet.as_view({'get': 'list'}), name='contenido-list-legacy'),
        path('<int:pk>/', ContenidoViewSet.as_view({'get': 'retrieve'}), name='contenido-detail-legacy'),
        path('mas-vistas/', ContenidoViewSet.as_view({'get': 'mas_vistas'}), name='contenido-mas-vistas-legacy'),
        path('recientes/', ContenidoViewSet.as_view({'get': 'recientes'}), name='contenido-recientes-legacy'),
    ])),
    
    path('madeinarg/', include([
        path('', MadeInArgViewSet.as_view({'get': 'resumen'}), name='madeinarg-resumen-legacy'),
        path('tiendas/', TiendaMadeInArgViewSet.as_view({'get': 'list'}), name='tiendas-list-legacy'),
        path('productos/', ProductoMadeInArgViewSet.as_view({'get': 'list'}), name='productos-list-legacy'),
        path('artistas/', ArtistaMadeInArgViewSet.as_view({'get': 'list'}), name='artistas-list-legacy'),
    ])),
    
    # ================== URLS ESPECIALIZADAS POR CATEGORÍA ==================
    
    # Editorials
    path('api/v1/editorials/', include([
        path('', ContenidoViewSet.as_view({'get': 'editorials'}), name='editorials-list'),
        path('recientes/', ContenidoViewSet.as_view({'get': 'recientes'}), {'categoria': 'editorials'}, name='editorials-recientes'),
        path('destacados/', ContenidoViewSet.as_view({'get': 'destacados'}), {'categoria': 'editorials'}, name='editorials-destacados'),
    ])),
    
    # Issues
    path('api/v1/issues/', include([
        path('', ContenidoViewSet.as_view({'get': 'issues'}), name='issues-list'),
        path('recientes/', ContenidoViewSet.as_view({'get': 'recientes'}), {'categoria': 'issues'}, name='issues-recientes'),
        path('por-numero/', ContenidoViewSet.as_view({'get': 'issues'}), name='issues-por-numero'),
    ])),
    
    # News
    path('api/v1/news/', include([
        path('', ContenidoViewSet.as_view({'get': 'news'}), name='news-list'),
        path('recientes/', ContenidoViewSet.as_view({'get': 'recientes'}), {'categoria': 'news'}, name='news-recientes'),
        path('destacadas/', ContenidoViewSet.as_view({'get': 'destacados'}), {'categoria': 'news'}, name='news-destacadas'),
    ])),
    
    # Club Pompa
    path('api/v1/club-pompa/', include([
        path('', ContenidoViewSet.as_view({'get': 'club_pompa'}), name='club-pompa-list'),
        path('recientes/', ContenidoViewSet.as_view({'get': 'recientes'}), {'categoria': 'club_pompa'}, name='club-pompa-recientes'),
        path('destacados/', ContenidoViewSet.as_view({'get': 'destacados'}), {'categoria': 'club_pompa'}, name='club-pompa-destacados'),
    ])),
    path('<int:pk>/', ContenidoViewSet.as_view({'get': 'retrieve'}), name='contenido-detail-legacy'),
    path('', ContenidoViewSet.as_view({'get': 'list'}), name='contenido-list-legacy'),





     # Newsletter público (información general)
    path('api/v1/newsletter/', NewsletterPublicoView.as_view(), name='newsletter-publico'),
    
    # Suscripción pública (sin autenticación)
    path('api/v1/newsletter/suscribirse/', 
         SuscriptorViewSet.as_view({'post': 'suscribirse'}), 
         name='newsletter-suscribirse'),
    
    # Desuscripción pública
    path('api/v1/newsletter/desuscribirse/', 
         SuscriptorViewSet.as_view({'post': 'desuscribirse'}), 
         name='newsletter-desuscribirse'),
    
    # Actualizar preferencias
    path('api/v1/newsletter/preferencias/', 
         SuscriptorViewSet.as_view({'post': 'actualizar_preferencias'}), 
         name='newsletter-preferencias'),
    
    # ================== NEWSLETTER - ENDPOINTS ADMINISTRATIVOS ==================
    
    # Estadísticas de suscriptores (solo admin)
    path('api/v1/admin/newsletter/estadisticas/', 
         SuscriptorViewSet.as_view({'get': 'estadisticas'}), 
         name='admin-newsletter-estadisticas'),
    
    # Envío manual de newsletter (solo admin)
    path('api/v1/admin/newsletter/enviar/', 
         NewsletterViewSet.as_view({'post': 'enviar_manual'}), 
         name='admin-newsletter-enviar'),
    
    # Reenviar newsletter (solo admin)
    path('api/v1/admin/newsletter/<int:pk>/reenviar/', 
         NewsletterViewSet.as_view({'post': 'reenviar'}), 
         name='admin-newsletter-reenviar'),
    
    # Lista de suscriptores (solo admin)
    path('api/v1/admin/suscriptores/', 
         SuscriptorViewSet.as_view({'get': 'list'}), 
         name='admin-suscriptores-list'),
    
    # Gestión de suscriptor específico (solo admin)
    path('api/v1/admin/suscriptores/<int:pk>/', 
         SuscriptorViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), 
         name='admin-suscriptor-detail'),
    
    # ================== NEWSLETTER - URLS DE COMPATIBILIDAD ==================
    
    # URLs cortas para fácil acceso
    path('suscribirse/', 
         SuscriptorViewSet.as_view({'post': 'suscribirse'}), 
         name='suscribirse-corto'),
    
    path('desuscribirse/', 
         SuscriptorViewSet.as_view({'post': 'desuscribirse'}), 
         name='desuscribirse-corto'),
    
    # URL específica para desuscripción desde email (con token en URL)
    path('desuscribirse/<uuid:token>/', 
         TemplateView.as_view(template_name='newsletter/desuscripcion.html'), 
         name='desuscripcion-template'),
    
]

# ================== CONFIGURACIÓN ADICIONAL ==================

# Configuración para desarrollo
from django.conf import settings
if settings.DEBUG:
    from django.conf.urls.static import static
    # Servir archivos de media en desarrollo
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Servir archivos estáticos en desarrollo
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)