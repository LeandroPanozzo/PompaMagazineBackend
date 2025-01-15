from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ComentarioListCreateAPIView, CommentDeleteView, RegisterView, LoginView, UserProfileView, EstadoPublicacionList, TrabajadorList, upload_image
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
    redirect_to_home,  # Importa la vista de redirección
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views
# Crear un router y registrar todos los viewsets
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'roles', RolViewSet)
router.register(r'users', UserrViewSet, basename='user')  # Asegúrate de que 'user' no esté duplicado
router.register(r'admin', AdminViewSet, basename='admin')
router.register(r'trabajadores', TrabajadorViewSet)
router.register(r'usuarios', UsuarioViewSet)
router.register(r'estados', EstadoPublicacionViewSet)
router.register(r'comentarios', ComentarioViewSet)
router.register(r'imagenes', ImagenViewSet)
router.register(r'publicidades', PublicidadViewSet)
router.register(r'noticias', NoticiaViewSet, basename='noticias')  # Registrar el NoticiaViewSet aquí

urlpatterns = [
    path('', redirect_to_home, name='redirect_to_home'),  # Redirige la ruta raíz
    path('', include(router.urls)),  # Incluye todas las rutas generadas por el router
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('user-profile/', UserProfileView.as_view(), name='user-profile'),
    path('estados-publicacion/', EstadoPublicacionList.as_view(), name='estado-publicacion-list'),
    path('trabajadores/', TrabajadorList.as_view(), name='trabajador-list'),
    path('upload_image/', NoticiaViewSet.as_view({'post': 'upload_image'}), name='upload_image'),
    path('noticias/<int:noticia_id>/comentarios/', ComentarioViewSet.as_view({'get': 'list', 'post': 'create'}), name='comentarios'),
    path('noticias/<int:noticia_id>/comentarios/<int:comment_id>/', ComentarioViewSet.as_view({'delete': 'destroy'}), name='delete_comentario'),
    path('upload/', upload_image, name='upload_image'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Nueva ruta para actualizar perfil de trabajador
    path('user-profile/', UserProfileView.as_view(), name='update_trabajador_profile'),
    path('noticias/<int:id>/reacciones/', views.reacciones_noticia, name='reacciones_noticia'),
    path('noticias/<int:id>/mi-reaccion/', views.mi_reaccion, name='mi_reaccion'),
    path('diarioback/noticias/mas-vistas/', views.NoticiaViewSet.as_view({'get': 'mas_vistas'}), name='noticias-mas-vistas'),

]

