from rest_framework.routers import DefaultRouter
from django.urls import path, include, re_path
from . import views
from .views import (
    RolViewSet,
    TrabajadorViewSet,
    UsuarioViewSet,
    NoticiaViewSet,
    ComentarioViewSet,
    EstadoPublicacionViewSet,
    ImagenViewSet,
    PublicidadViewSet,
    AdminViewSet,
    UserrViewSet,
    redirect_to_home,
    CurrentUserView,
    ComentarioListCreateAPIView,
    CommentDeleteView,
    RegisterView,
    LoginView,
    RequestPasswordResetView,
    ResetPasswordView,
    UserProfileView,
    EstadoPublicacionList,
    TrabajadorList,
    VerifyTokenView,
    upload_image
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Crear un router y registrar todos los viewsets
router = DefaultRouter()
router.register(r'roles', RolViewSet)
router.register(r'users', UserrViewSet, basename='user')
router.register(r'admin', AdminViewSet, basename='admin')
router.register(r'trabajadores', TrabajadorViewSet)
router.register(r'usuarios', UsuarioViewSet)
router.register(r'estados', EstadoPublicacionViewSet)
router.register(r'comentarios', ComentarioViewSet)
router.register(r'imagenes', ImagenViewSet)
router.register(r'publicidades', PublicidadViewSet)
router.register(r'noticias', NoticiaViewSet, basename='noticias')

urlpatterns = [
    path('', redirect_to_home, name='redirect_to_home'),
    path('', include(router.urls)),
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('user-profile/', UserProfileView.as_view(), name='user-profile'),
    path('estados-publicacion/', EstadoPublicacionList.as_view(), name='estado-publicacion-list'),
    path('trabajadores/', TrabajadorList.as_view(), name='trabajador-list'),
    path('upload_image/', NoticiaViewSet.as_view({'post': 'upload_image'}), name='upload_image'),
    
    # URL para detalle de noticia con ID y slug
    re_path(r'^noticias/(?P<pk>\d+)-(?P<slug>[\w-]+)/$', 
        NoticiaViewSet.as_view({'get': 'retrieve'}), 
        name='noticia-detail'),
    
    # Mantén la URL original solo con ID para compatibilidad
    path('noticias/<int:pk>/', NoticiaViewSet.as_view({'get': 'retrieve'}), name='noticia-detail-id-only'),
    
    path('noticias/<int:noticia_id>/comentarios/', ComentarioViewSet.as_view({'get': 'list', 'post': 'create'}), name='comentarios'),
    path('noticias/<int:noticia_id>/comentarios/<int:comment_id>/', ComentarioViewSet.as_view({'delete': 'destroy'}), name='delete_comentario'),
    path('upload/', upload_image, name='upload_image'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('user-profile/', UserProfileView.as_view(), name='update_trabajador_profile'),
    path('noticias/<int:id>/reacciones/', views.reacciones_noticia, name='reacciones_noticia'),
    path('noticias/<int:id>/mi-reaccion/', views.mi_reaccion, name='mi_reaccion'),
    
    # URLs específicas para las secciones de noticias
    path('noticias/mas-vistas/', NoticiaViewSet.as_view({'get': 'mas_vistas'}), name='noticias-mas-vistas'),
    path('noticias/recientes/', NoticiaViewSet.as_view({'get': 'recientes'}), name='noticias-recientes'),
    path('noticias/destacadas/', NoticiaViewSet.as_view({'get': 'destacadas'}), name='noticias-destacadas'),
    path('noticias/politica/', NoticiaViewSet.as_view({'get': 'politica'}), name='noticias-politica'),
    path('noticias/cultura/', NoticiaViewSet.as_view({'get': 'cultura'}), name='noticias-cultura'),
    path('noticias/economia/', NoticiaViewSet.as_view({'get': 'economia'}), name='noticias-economia'),
    path('noticias/mundo/', NoticiaViewSet.as_view({'get': 'mundo'}), name='noticias-mundo'),
    path('noticias/tipos-notas/', NoticiaViewSet.as_view({'get': 'tipos_notas'}), name='noticias-tipos-notas'),
    path('noticias/por-categoria/', NoticiaViewSet.as_view({'get': 'por_categoria'}), name='noticias-por-categoria'),
    
    path('current-user/', CurrentUserView.as_view(), name='current-user'),
    path('password/reset/request/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('password/reset/verify/', VerifyTokenView.as_view(), name='password-reset-verify'),
    path('password/reset/confirm/', ResetPasswordView.as_view(), name='password-reset-confirm'),
]