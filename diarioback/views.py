from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Rol, Trabajador, UserProfile, Usuario, Noticia, Comentario, EstadoPublicacion, Imagen, Publicidad
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from .serializers import UserProfileSerializer, UserRegistrationSerializer, LoginSerializer
from django.core.files.storage import default_storage
import uuid
from .imgur_utils import upload_to_imgur, delete_from_imgur
from django.core.files.base import ContentFile
from rest_framework.decorators import api_view
import os
from django.conf import settings
from rest_framework import generics
from rest_framework.exceptions import NotFound
from django.shortcuts import redirect
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.models import User
from .serializers import UserSerializer
from django.utils import timezone  # Añade esta importación
from datetime import timedelta     # Añade esta importación
from rest_framework.permissions import AllowAny, IsAuthenticated

from .serializers import (
    RolSerializer, TrabajadorSerializer, UsuarioSerializer, NoticiaSerializer,
    ComentarioSerializer, EstadoPublicacionSerializer, ImagenSerializer, PublicidadSerializer
)

BASE_QUERYSET = User.objects.all()

class UserrViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]  # Permite el acceso sin autenticación

class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer

class TrabajadorViewSet(viewsets.ModelViewSet):
    queryset = Trabajador.objects.all()
    serializer_class = TrabajadorSerializer
    

class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer

class EstadoPublicacionViewSet(viewsets.ModelViewSet):
    queryset = EstadoPublicacion.objects.all()
    serializer_class = EstadoPublicacionSerializer

class ImagenViewSet(viewsets.ModelViewSet):
    queryset = Imagen.objects.all()
    serializer_class = ImagenSerializer

class ComentarioViewSet(viewsets.ModelViewSet):
    queryset = Comentario.objects.all()
    serializer_class = ComentarioSerializer

    def get_queryset(self):
        noticia_id = self.kwargs['noticia_id']
        return self.queryset.filter(noticia_id=noticia_id)

    def destroy(self, request, noticia_id, comment_id):
        try:
            comentario = self.get_queryset().get(id=comment_id)
            comentario.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Comentario.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # Log the exception for debugging
            print(f"Error deleting comment: {e}")
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CommentDeleteView(APIView):
    def delete(self, request, noticia_id, comment_id):
        try:
            comment = Comentario.objects.get(id=comment_id, noticia_id=noticia_id)
            comment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Comentario.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

class ComentarioListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ComentarioSerializer

    def get_queryset(self):
        noticia_id = self.kwargs['noticia_id']
        return Comentario.objects.filter(noticia_id=noticia_id)

    def perform_create(self, serializer):
        noticia_id = self.kwargs['noticia_id']
        serializer.save(noticia_id=noticia_id)

class PublicidadViewSet(viewsets.ModelViewSet):
    queryset = Publicidad.objects.all()
    serializer_class = PublicidadSerializer

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
from .models import Noticia, Trabajador
from .serializers import NoticiaSerializer
from django.shortcuts import get_object_or_404

def upload_to_imgur(image):
    # Implementación del servicio de subida a Imgur
    pass
class NoticiaViewSet(viewsets.ModelViewSet):
    queryset = Noticia.objects.all()
    serializer_class = NoticiaSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['fecha_publicacion', 'contador_visitas']
    ordering = ['-fecha_publicacion']  # Default ordering
    lookup_field = 'pk'  # Default lookup field
    lookup_value_regex = r'[0-9]+(?:-[a-zA-Z0-9-_]+)?'  # Accept both ID and ID-slug formats
    def get_queryset(self):
        """
        Customizes the queryset based on query parameters to support efficient filtering.
        This avoids retrieving all records every time.
        """
        queryset = Noticia.objects.all()
        
        # Filter by estado (publication status)
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        
        # Filter by categoria (one or multiple categories)
        categoria = self.request.query_params.get('categoria')
        if categoria:
            # Check if it's a comma-separated list
            categorias = categoria.split(',')
            if len(categorias) > 1:
                # Create a complex query for multiple categories
                category_query = Q()
                for cat in categorias:
                    category_query |= Q(categorias__contains=cat)
                queryset = queryset.filter(category_query)
            else:
                # Simple single category filter
                queryset = queryset.filter(categorias__contains=categoria)
        
        # Filter by date range
        fecha_desde = self.request.query_params.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha_publicacion__gte=fecha_desde)
            
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha_publicacion__lte=fecha_hasta)
        
        # Include author and editor information if requested
        include_autor = self.request.query_params.get('include_autor')
        include_editor = self.request.query_params.get('include_editor')
        
        # Note: In a real implementation, you would use prefetch_related and select_related
        # here to optimize the query instead of making additional queries for each article
        
        # IMPORTANT: Removed the limit slicing from here since it conflicts with ordering
        # The limit will be applied after ordering in list() and other methods
            
        return queryset

    def list(self, request, *args, **kwargs):
        """Override list method to apply limit after ordering"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Apply limit from request params after filtering and ordering
        limit = self.request.query_params.get('limit')
        if limit and limit.isdigit():
            queryset = queryset[:int(limit)]
        
        # Use pagination if configured and not explicitly limited
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        # Obtiene la IP del cliente
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
            
        # Incrementa el contador de visitas
        instance.incrementar_visitas(ip_address=ip)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def mas_vistas(self, request):
        """
        Return the most viewed news from the past week.
        Optimized to limit results and preload related data.
        """
        # Get limit from query params or default to 10
        limit = request.query_params.get('limit', 10)
        try:
            limit = int(limit)
        except ValueError:
            limit = 10
            
        # Calculate one week ago
        hace_una_semana = timezone.now() - timedelta(days=7)
        
        # Filter by estado and date, order by visit count
        # Don't slice here, wait until all filtering and ordering is done
        noticias_mas_vistas = self.queryset.filter(
            estado=3,  # Published status
            ultima_actualizacion_contador__gte=hace_una_semana
        ).order_by('-contador_visitas')
        
        # Apply limit after all ordering is done
        noticias_mas_vistas = noticias_mas_vistas[:limit]
        
        # Optimize with prefetch_related if needed
        # noticias_mas_vistas = noticias_mas_vistas.prefetch_related('autor', 'editores_en_jefe')
        
        serializer = self.get_serializer(noticias_mas_vistas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recientes(self, request):
        """
        Return the most recent news.
        """
        # Get limit from query params or default to 5
        limit = request.query_params.get('limit', 5)
        try:
            limit = int(limit)
        except ValueError:
            limit = 5
            
        # Filter by estado, order by publication date
        noticias_recientes = self.queryset.filter(
            estado=3  # Published status
        ).order_by('-fecha_publicacion')
        
        # Apply limit after ordering
        noticias_recientes = noticias_recientes[:limit]
        
        serializer = self.get_serializer(noticias_recientes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def destacadas(self, request):
        """
        Return featured news for the carousel.
        """
        # Get limit from query params or default to 12 (for 4 slides with 3 articles each)
        limit = request.query_params.get('limit', 12)
        try:
            limit = int(limit)
        except ValueError:
            limit = 12
            
        # Filter by estado, order by publication date to get the most recent
        noticias_destacadas = self.queryset.filter(
            estado=3  # Published status
        ).order_by('-fecha_publicacion')
        
        # Apply limit after ordering
        noticias_destacadas = noticias_destacadas[:limit]
        
        serializer = self.get_serializer(noticias_destacadas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def politica(self, request):
        """
        Return news from the Politics section.
        """
        # Categories defined for Politics
        politica_categories = [
            'nacion', 'legislativos', 'policiales', 
            'elecciones', 'gobierno', 'provincias', 'capital'
        ]
        
        return self._get_section_news(request, politica_categories)

    @action(detail=False, methods=['get'])
    def cultura(self, request):
        """
        Return news from the Culture section.
        """
        # Categories defined for Culture
        cultura_categories = [
            'cine', 'literatura', 'salud', 'tecnologia', 
            'eventos', 'educacion', 'efemerides', 'deporte'
        ]
        
        return self._get_section_news(request, cultura_categories)

    @action(detail=False, methods=['get'])
    def economia(self, request):
        """
        Return news from the Economy section.
        """
        # Categories defined for Economy
        economia_categories = [
            'finanzas', 'comercio_internacional', 'politica_economica', 
            'dolar', 'pobreza_e_inflacion'
        ]
        
        return self._get_section_news(request, economia_categories)

    @action(detail=False, methods=['get'])
    def mundo(self, request):
        """
        Return news from the World section.
        """
        # Categories defined for World
        mundo_categories = [
            'estados_unidos', 'asia', 'medio_oriente', 
            'internacional', 'latinoamerica'
        ]
        
        return self._get_section_news(request, mundo_categories)

    @action(detail=False, methods=['get'])
    def tipos_notas(self, request):
        """
        Return news by note types.
        """
        # Categories defined for note types
        tipos_categories = [
            'de_analisis', 'de_opinion', 'informativas', 'entrevistas'
        ]
        
        return self._get_section_news(request, tipos_categories)

    def _get_section_news(self, request, categories):
        """
        Helper method to get news for a specific section by categories.
        """
        # Get limit from query params or default to 7
        limit = request.query_params.get('limit', 7)
        try:
            limit = int(limit)
        except ValueError:
            limit = 7
            
        # Create category query
        category_query = Q()
        for cat in categories:
            category_query |= Q(categorias__contains=cat)
            
        # Filter by estado and categories, order by publication date
        section_news = self.queryset.filter(
            category_query,
            estado=3  # Published status
        ).order_by('-fecha_publicacion')
        
        # Apply limit after all filtering and ordering
        section_news = section_news[:limit]
        
        serializer = self.get_serializer(section_news, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def por_categoria(self, request):
        """
        Return news filtered by one or more categories.
        Support for comma-separated category list.
        """
        # Get the category parameter
        categoria = request.query_params.get('categoria')
        if not categoria:
            return Response({"error": "Se requiere el parámetro 'categoria'"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Check if it's a comma-separated list
        categorias = categoria.split(',')
        
        # Get estado filter (default to published)
        estado = request.query_params.get('estado', 3)
        
        # Get limit from query params or default
        limit = request.query_params.get('limit')
        
        # Base queryset filtered by estado
        queryset = self.queryset.filter(estado=estado)
        
        # Apply category filtering
        if len(categorias) > 1:
            # Complex query for multiple categories
            category_query = Q()
            for cat in categorias:
                if cat.strip():  # Skip empty strings
                    category_query |= Q(categorias__contains=cat.strip())
            queryset = queryset.filter(category_query)
        else:
            # Simple single category filter
            queryset = queryset.filter(categorias__contains=categoria)
            
        # Apply ordering by publication date first
        queryset = queryset.order_by('-fecha_publicacion')
        
        # Apply limit AFTER ordering
        if limit and limit.isdigit():
            queryset = queryset[:int(limit)]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def agregar_editor(self, request, pk=None):
        noticia = self.get_object()
        editor_id = request.data.get('editor_id')
        
        if not editor_id:
            return Response({'error': 'Se requiere un ID de editor'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            editor = Trabajador.objects.get(pk=editor_id)
            noticia.editores_en_jefe.add(editor)
            return Response({'success': True})
        except Trabajador.DoesNotExist:
            return Response({'error': 'Editor no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def eliminar_editor(self, request, pk=None):
        noticia = self.get_object()
        editor_id = request.data.get('editor_id')
        
        if not editor_id:
            return Response({'error': 'Se requiere un ID de editor'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            editor = Trabajador.objects.get(pk=editor_id)
            noticia.editores_en_jefe.remove(editor)
            return Response({'success': True})
        except Trabajador.DoesNotExist:
            return Response({'error': 'Editor no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    # Permite buscar por slug además de por id
    lookup_field = 'pk'  # Mantiene pk como campo principal para compatibilidad
    
    def get_object(self):
        """
        Retrieve the object with support for pk or pk-slug format in the URL.
        """
        # Get the pk value from the URL (which might be in the format 'id-slug')
        pk_value = self.kwargs.get(self.lookup_field)
        
        # If it's in 'id-slug' format, extract the actual ID
        if pk_value and '-' in pk_value:
            pk = pk_value.split('-')[0]
        else:
            pk = pk_value
            
        # Do not filter by slug here, as we've already extracted the ID
        queryset = self.filter_queryset(self.get_queryset())
        
        # Get the object using just the ID
        obj = get_object_or_404(queryset, pk=pk)
        
        # Check object permissions
        self.check_object_permissions(self.request, obj)
        return obj
            
    @action(detail=False, methods=['post'])
    def upload_image(self, request):
        if 'image' not in request.FILES:
            return Response({'error': 'No image file found'}, status=status.HTTP_400_BAD_REQUEST)
            
        image = request.FILES['image']
        
        # Verificar tipo de archivo
        if not image.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            return Response({
                'error': 'Tipo de archivo no soportado. Por favor suba una imagen PNG, JPG, JPEG o GIF.'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Subir directamente a Imgur en lugar de almacenar localmente
        uploaded_url = upload_to_imgur(image)
            
        if uploaded_url:
            return Response({
                'success': True, 
                'url': uploaded_url,
                'message': 'Imagen subida exitosamente a Imgur'
            })
        else:
            return Response({
                'error': 'Error al subir la imagen a Imgur'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
User = get_user_model()

# Vista para el registro de usuarios
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def redirect_to_home(request):
    return redirect('/home/')

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied("Usuario no autenticado.")
        
        # Intentar obtener el perfil del usuario
        try:
            # Primero buscamos en UserProfile
            return UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            # Si no existe, verificamos si es un trabajador
            try:
                trabajador = Trabajador.objects.get(user=user)
                # Si es un trabajador, creamos un UserProfile asociado
                profile = UserProfile.objects.create(
                    user=user,
                    nombre=trabajador.nombre,
                    apellido=trabajador.apellido,
                    foto_perfil=trabajador.foto_perfil,
                    descripcion_usuario=trabajador.descripcion_usuario,
                    es_trabajador=True
                )
                return profile
            except Trabajador.DoesNotExist:
                # Si no es un trabajador, creamos un perfil vacío
                profile = UserProfile.objects.create(
                    user=user,
                    nombre=user.first_name,
                    apellido=user.last_name,
                    es_trabajador=False
                )
                return profile

    def get(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = self.get_serializer(profile)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = self.get_serializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Vista para el inicio de sesión de usuarios
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Add debugging to see what's being received
        print(f"Login attempt with data: {request.data}")
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response({'error': 'Please provide both username and password'},
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Authenticate user
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({'error': 'Invalid credentials'}, 
                            status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Check if user is a worker (Trabajador)
        try:
            from .models import Trabajador
            trabajador = Trabajador.objects.get(user=user)
            from .serializers import TrabajadorSerializer
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'trabajador': TrabajadorSerializer(trabajador).data
            })
        except Exception as e:
            # Regular user or error occurred
            print(f"Error fetching trabajador: {e}")
            from .serializers import UserSerializer
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Check if user is a worker
        try:
            trabajador = Trabajador.objects.get(user=user)
            return Response({
                'isWorker': True,
                **TrabajadorSerializer(trabajador).data
            })
        except Trabajador.DoesNotExist:
            # Regular user
            return Response({
                'isWorker': False,
                **UserSerializer(user).data
            })

class AdminViewSet(viewsets.ModelViewSet):
    queryset = BASE_QUERYSET.filter(is_staff=True)
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        # Add logic for admin dashboard data
        total_users = User.objects.count()
        total_noticias = Noticia.objects.count()
        # Add more statistics as needed
        return Response({
            'total_users': total_users,
            'total_noticias': total_noticias,
            # Add more data as needed
        })
class EstadoPublicacionList(generics.ListAPIView):
    queryset = EstadoPublicacion.objects.all()
    serializer_class = EstadoPublicacionSerializer

class TrabajadorList(generics.ListAPIView):
    queryset = Trabajador.objects.all()
    serializer_class = TrabajadorSerializer

class UserProfileViewSet(viewsets.ModelViewSet):
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

    def perform_update(self, serializer):
        serializer.save()


@api_view(['POST'])
def upload_image(request):
    if 'image' not in request.FILES:
        return Response({'error': 'No image file found'}, status=status.HTTP_400_BAD_REQUEST)

    image = request.FILES['image']

    # Verificar tipo de archivo
    if not image.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        return Response({
            'error': 'Tipo de archivo no soportado. Por favor suba una imagen PNG, JPG, JPEG o GIF.'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Subir directamente a Imgur
    uploaded_url = upload_to_imgur(image)

    if uploaded_url:
        return Response({
            'success': True, 
            'url': uploaded_url,
            'message': 'Imagen subida exitosamente a Imgur'
        })
    else:
        return Response({
            'error': 'Error al subir la imagen a Imgur'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT'])
def update_trabajador(request, pk):
    try:
        trabajador = Trabajador.objects.get(pk=pk)
    except Trabajador.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    serializer = TrabajadorSerializer(trabajador, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
@api_view(['PUT'])
def update_user_profile(request):
    trabajador = request.user.trabajador  # Obtener el trabajador asociado al usuario
    
    # Obtener los datos enviados en la solicitud
    nombre = request.data.get('nombre')
    apellido = request.data.get('apellido')
    foto_perfil_url = request.data.get('foto_perfil')  # URL de la imagen
    foto_perfil_file = request.FILES.get('foto_perfil_local')  # Imagen local

    # Actualizar los campos básicos si están presentes
    if nombre:
        trabajador.nombre = nombre
    if apellido:
        trabajador.apellido = apellido

    # Manejo de la imagen de perfil
    if foto_perfil_file:
        # Si se envía una imagen local, se guarda en el servidor
        try:
            file_name = default_storage.save(f'perfil/{foto_perfil_file.name}', ContentFile(foto_perfil_file.read()))
            trabajador.foto_perfil_local = file_name
            trabajador.foto_perfil = None  # Limpiar el campo de URL si se sube una imagen local
        except Exception as e:
            return Response({'error': f'Error uploading file: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    elif foto_perfil_url:
        # Si se envía una URL de la imagen, actualizamos el campo
        trabajador.foto_perfil = foto_perfil_url
        trabajador.foto_perfil_local = None  # Limpiar el campo de archivo local si se proporciona una URL

    # Guardar los cambios en el perfil del trabajador
    trabajador.save()

    # Devolver una respuesta con los datos actualizados del trabajador
    return Response({
        'nombre': trabajador.nombre,
        'apellido': trabajador.apellido,
        'foto_perfil': trabajador.get_foto_perfil(),  # Método que devuelve la URL o el archivo local
    }, status=status.HTTP_200_OK)


#para las reacciones de las noticias:


# views.py
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Noticia, ReaccionNoticia
from .serializers import ReaccionNoticiaSerializer

@api_view(['GET', 'POST', 'DELETE'])
def reacciones_noticia(request, id):
    try:
        noticia = Noticia.objects.get(pk=id)
    except Noticia.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        # Cualquier usuario puede ver el conteo
        return Response(noticia.get_conteo_reacciones())

    # Para POST y DELETE requerimos autenticación
    if not request.user.is_authenticated:
        return Response(
            {'error': 'Debes iniciar sesión para realizar esta acción'}, 
            status=status.HTTP_401_UNAUTHORIZED
        )

    if request.method == 'POST':
        tipo_reaccion = request.data.get('tipo_reaccion')
        if not tipo_reaccion:
            return Response(
                {'error': 'tipo_reaccion es requerido'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        reaccion, created = ReaccionNoticia.objects.update_or_create(
            noticia=noticia,
            usuario=request.user,
            defaults={'tipo_reaccion': tipo_reaccion}
        )
        
        serializer = ReaccionNoticiaSerializer(reaccion)
        return Response(
            serializer.data, 
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    elif request.method == 'DELETE':
        ReaccionNoticia.objects.filter(
            noticia=noticia,
            usuario=request.user
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mi_reaccion(request, id):
    try:
        noticia = Noticia.objects.get(pk=id)
        reaccion = ReaccionNoticia.objects.get(
            noticia=noticia,
            usuario=request.user
        )
        serializer = ReaccionNoticiaSerializer(reaccion)
        return Response(serializer.data)
    except Noticia.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)
    except ReaccionNoticia.DoesNotExist:
        return Response({'tipo_reaccion': None})
    

# views.py
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from .models import PasswordResetToken
from .serializers import RequestPasswordResetSerializer, VerifyTokenSerializer, ResetPasswordSerializer
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()

class RequestPasswordResetView(APIView):
    def post(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)
            
            # Crear token de recuperación
            token_obj = PasswordResetToken.objects.create(user=user)
            
            # Enviar correo con el token
            subject = "Recuperación de contraseña"
            message = f"""
            Hola {user.username},
            
            Recibimos una solicitud para restablecer tu contraseña.
            
            Tu código de recuperación es: {token_obj.token}
            
            Este código es válido por 24 horas.
            
            Si no solicitaste este cambio, puedes ignorar este correo.
            
            Saludos,
            El equipo de [Nombre de tu aplicación]
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            return Response({"message": "Se ha enviado un correo con instrucciones para recuperar tu contraseña."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyTokenView(APIView):
    def post(self, request):
        serializer = VerifyTokenSerializer(data=request.data)
        if serializer.is_valid():
            return Response({"message": "Token válido."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordView(APIView):
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            password = serializer.validated_data['password']
            
            # Buscar el token
            token_obj = PasswordResetToken.objects.get(token=token)
            
            # Cambiar la contraseña del usuario
            user = token_obj.user
            user.set_password(password)
            user.save()
            
            # Marcar el token como usado
            token_obj.used = True
            token_obj.save()
            
            return Response({"message": "Contraseña actualizada exitosamente."}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)