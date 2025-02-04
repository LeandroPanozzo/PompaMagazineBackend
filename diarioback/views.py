from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Rol, Trabajador, UserProfile, Usuario, Noticia, Comentario, EstadoPublicacion, Imagen, Publicidad
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import UserProfileSerializer, UserRegistrationSerializer, LoginSerializer
from django.core.files.storage import default_storage
import uuid
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

class NoticiaViewSet(viewsets.ModelViewSet):
    queryset = Noticia.objects.all()
    serializer_class = NoticiaSerializer

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
        hace_24h = timezone.now() - timedelta(hours=24)
        noticias_mas_vistas = self.get_queryset().filter(
            estado=3,
            ultima_actualizacion_contador__gte=hace_24h
        ).order_by('-contador_visitas')[:10]
        
        serializer = self.get_serializer(noticias_mas_vistas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def por_categoria(self, request):
        categoria = request.query_params.get('categoria')
        queryset = self.get_queryset()
        
        if categoria:
            # Busca noticias donde la categoría esté en la lista de categorías
            queryset = queryset.filter(categorias__contains=categoria)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['post'])
    def upload_image(self, request):
        if 'image' not in request.FILES:
            return Response({'error': 'No image file found'}, status=400)

        image = request.FILES['image']
        filename = f"{uuid.uuid4()}.{image.name.split('.')[-1]}"
        path = default_storage.save(f'news_images/{filename}', ContentFile(image.read()))
        return Response({'success': True, 'url': default_storage.url(path)})
User = get_user_model()

# Vista para el registro de usuarios
class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            # Verificar si el usuario registrado es un trabajador
            try:
                trabajador = Trabajador.objects.get(user=user)
                return Response({
                    'message': 'User registered successfully',
                    'user': UserRegistrationSerializer(user).data,
                    'trabajador_id': trabajador.id  # Añadir ID del trabajador
                }, status=status.HTTP_201_CREATED)
            except Trabajador.DoesNotExist:
                return Response({
                    'message': 'User registered successfully, but is not a worker.',
                    'user': UserRegistrationSerializer(user).data
                }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

def redirect_to_home(request):
    return redirect('/home/')

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer

    def get_object(self):
        user = self.request.user
        if user.is_authenticated:  # Verificar que el usuario esté autenticado
            try:
                return Trabajador.objects.get(user=user)
            except Trabajador.DoesNotExist:
                raise NotFound("Perfil de trabajador no encontrado.")
        else:
            raise PermissionDenied("Usuario no autenticado.")

    def get(self, request, *args, **kwargs):
        try:
            trabajador = self.get_object()
            return Response({
                'trabajador': True,
                'id': trabajador.id,
                'nombre': trabajador.nombre,
                'apellido': trabajador.apellido,
                'foto_perfil': trabajador.foto_perfil,  # Incluye la foto de perfil si es necesario
                'descripcion_usuario': trabajador.descripcion_usuario,  # Nuevo campo añadido en la respuesta
            }, status=status.HTTP_200_OK)
        except NotFound as e:
            return Response({'detail': str(e)}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, *args, **kwargs):
        trabajador = self.get_object()
        serializer = self.get_serializer(trabajador, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Vista para el inicio de sesión de usuarios
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)

            # Verificar si el usuario es un trabajador
            try:
                trabajador = Trabajador.objects.get(user=user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'trabajador_id': trabajador.id  # Incluir el ID del trabajador
                })
            except Trabajador.DoesNotExist:
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'trabajador_id': None  # No es un trabajador
                })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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
    if request.method == 'POST':
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES['file']

        if not file.name.endswith(('.png', '.jpg', '.jpeg')):
            return Response({'error': 'File type not supported. Please upload a PNG or JPG image.'}, status=status.HTTP_400_BAD_REQUEST)

        # Intenta guardar el archivo y maneja las excepciones
        try:
            # Verifica que el directorio existe
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
            os.makedirs(upload_dir, exist_ok=True)

            file_path = os.path.join(upload_dir, file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            file_url = os.path.join(settings.MEDIA_URL, 'uploads', file.name)
            return Response({'url': file_url}, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({'error': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

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