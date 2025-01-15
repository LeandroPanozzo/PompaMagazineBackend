from rest_framework import serializers
from .models import Rol, Trabajador, UserProfile, Usuario,  upload_to_imgur, Noticia, Comentario, EstadoPublicacion, Imagen, Publicidad
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from rest_framework import generics
from django.urls import reverse

User = get_user_model()
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
# Serializador para el registro de usuarios
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

# Serializador para el inicio de sesión de usuarios
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()  # Cambiado de email a username
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(
            username=data.get('username'),  # Cambiado de email a username
            password=data.get('password')
        )
        if user is None:
            raise serializers.ValidationError('Invalid credentials')
        return {'user': user}


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = '__all__'


class UsuarioSerializer(serializers.ModelSerializer):
    rol = serializers.PrimaryKeyRelatedField(queryset=Rol.objects.all())
    class Meta:
        model = Usuario
        fields = '__all__'

class EstadoPublicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoPublicacion
        fields = '__all__'

class ImagenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Imagen
        fields = '__all__'

class ComentarioSerializer(serializers.ModelSerializer):
    autor = serializers.StringRelatedField()  # Representar el usuario por su representación en cadena

    class Meta:
        model = Comentario
        fields = '__all__'

class PublicidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicidad
        fields = '__all__'

class TrabajadorSerializer(serializers.ModelSerializer):
    foto_perfil_local = serializers.ImageField(write_only=True, required=False)
    foto_perfil = serializers.URLField(read_only=True)  # Para retornar la URL de la imagen subida a Imgur
    descripcion_usuario = serializers.CharField(required=False, allow_blank=True)  # Asegúrate de incluir esto
    
    class Meta:
        model = Trabajador
        fields = ['id', 'nombre', 'apellido', 'foto_perfil', 'foto_perfil_local', 'descripcion_usuario']

    def create(self, validated_data):
        foto_perfil_local = validated_data.pop('foto_perfil_local', None)
        trabajador = Trabajador.objects.create(**validated_data)

        if foto_perfil_local:
            # Guarda la imagen local y la URL de la imagen en Imgur
            trabajador.foto_perfil_local = foto_perfil_local
            trabajador.foto_perfil = upload_to_imgur(foto_perfil_local)
            trabajador.save()

        return trabajador

    def update(self, instance, validated_data):
        foto_perfil_local = validated_data.pop('foto_perfil_local', None)

        # Actualiza los campos de nombre y apellido
        for field in ['nombre', 'apellido']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        # Actualiza la descripcion_usuario si está en validated_data
        if 'descripcion_usuario' in validated_data:
            if instance.user_profile:  # Verifica que el perfil del usuario exista
                instance.descripcion_usuario = validated_data['descripcion_usuario']
            else:
                # Opcional: Si no existe un perfil de usuario, puedes crear uno o manejarlo de otra manera
                user_profile = UserProfile.objects.create(user=instance.user)
                user_profile.descripcion_usuario = validated_data['descripcion_usuario']
                user_profile.save()

        # Manejo de la imagen de perfil local
        if foto_perfil_local:
            instance.foto_perfil_local = foto_perfil_local  # Guardar en el campo local
            instance.foto_perfil = upload_to_imgur(foto_perfil_local)  # Subir a Imgur y guardar URL

        instance.save()  # Guarda los cambios en la instancia Trabajador
        return instance

from django.conf import settings
class UserProfileSerializer(serializers.ModelSerializer):
    foto_perfil_local = serializers.ImageField(write_only=True, required=False)
    foto_perfil = serializers.CharField(required=False, allow_blank=True)
    descripcion_usuario = serializers.CharField(required=False, allow_blank=True)  # Nuevo campo añadido

    class Meta:
        model = UserProfile  # Cambié Trabajador por UserProfile
        fields = ['id', 'nombre', 'apellido', 'foto_perfil', 'foto_perfil_local', 'descripcion_usuario']  # Añadido descripcion_usuario

    def validate_foto_perfil(self, value):
        if value.startswith(settings.MEDIA_URL):
            return value
        elif value.startswith('/'):
            return f"{settings.MEDIA_URL.rstrip('/')}{value}"
        else:
            raise serializers.ValidationError("Ingrese una URL válida o una ruta válida.")

    def update(self, instance, validated_data):
        foto_perfil_local = validated_data.pop('foto_perfil_local', None)
        foto_perfil = validated_data.get('foto_perfil', '')

        # Convertir el path relativo a URL absoluta si es necesario
        if foto_perfil.startswith(settings.MEDIA_URL):
            validated_data['foto_perfil'] = foto_perfil.replace(settings.MEDIA_URL, '', 1)
        elif foto_perfil.startswith('/'):
            validated_data['foto_perfil'] = foto_perfil.lstrip('/')

        # Procesar la imagen local si es proporcionada
        if foto_perfil_local:
            instance.foto_perfil_local = foto_perfil_local
            instance.foto_perfil = upload_to_imgur(foto_perfil_local)

        # Llamar al método original de update
        return super().update(instance, validated_data)


class NoticiaSerializer(serializers.ModelSerializer):
    autor = serializers.PrimaryKeyRelatedField(queryset=Trabajador.objects.all())
    editor_en_jefe = serializers.PrimaryKeyRelatedField(queryset=Trabajador.objects.all())
    estado = serializers.PrimaryKeyRelatedField(queryset=EstadoPublicacion.objects.all())
    
    visitas_24h = serializers.IntegerField(source='visitas_ultimas_24h', read_only=True)
    
    imagen_cabecera = serializers.CharField(allow_blank=True, required=False)
    imagen_1 = serializers.CharField(allow_blank=True, required=False)
    imagen_2 = serializers.CharField(allow_blank=True, required=False)
    imagen_3 = serializers.CharField(allow_blank=True, required=False)
    imagen_4 = serializers.CharField(allow_blank=True, required=False)
    imagen_5 = serializers.CharField(allow_blank=True, required=False)
    imagen_6 = serializers.CharField(allow_blank=True, required=False)

    # Secciones: Permitir que sean opcionales y en blanco
    seccion1 = serializers.CharField(allow_blank=True, required=False)
    seccion2 = serializers.CharField(allow_blank=True, required=False)
    seccion3 = serializers.CharField(allow_blank=True, required=False)
    seccion4 = serializers.CharField(allow_blank=True, required=False)
    seccion5 = serializers.CharField(allow_blank=True, required=False)
    seccion6 = serializers.CharField(allow_blank=True, required=False)
    conteo_reacciones = serializers.SerializerMethodField()

    def get_conteo_reacciones(self, obj):
        return obj.get_conteo_reacciones()
    class Meta:
        model = Noticia
        fields = [
            'id', 'autor', 'editor_en_jefe', 'nombre_noticia', 'subtitulo', 'fecha_publicacion', 
            'seccion1', 'seccion2','seccion3','seccion4','seccion5','seccion6',  # Reemplaza 'seccion' por secciones específicas si es necesario
            'tags', 'imagen_cabecera', 'imagen_1', 'imagen_2', 'imagen_3', 
            'imagen_4', 'imagen_5', 'imagen_6', 'estado', 
            'solo_para_subscriptores', 'contenido', 'tiene_comentarios', 'conteo_reacciones','contador_visitas',
            'visitas_24h'
        ]

    def create(self, validated_data):
        # Asegúrate de que no se incluye un id
        validated_data.pop('id', None)  # Eliminar id si está presente

        # Crear la noticia
        noticia = Noticia.objects.create(**validated_data)
        
        # Generar la URL
        noticia.url = f"/noticia/{noticia.id}/{noticia.nombre_noticia.replace(' ', '-').lower()}/"
        noticia.save()  # Guardar la URL en la base de datos

        return noticia


    def get_imagen_cabecera(self, obj):
        return obj.imagen_cabecera

    def get_imagen_1(self, obj):
        return obj.imagen_1

    def get_imagen_2(self, obj):
        return obj.imagen_2

    def get_imagen_3(self, obj):
        return obj.imagen_3

    def get_imagen_4(self, obj):
        return obj.imagen_4

    def get_imagen_5(self, obj):
        return obj.imagen_5

    def get_imagen_6(self, obj):
        return obj.imagen_6

    def update(self, instance, validated_data):
        # Asegúrate de procesar el campo `subtitulo`
        for field in ['nombre_noticia', 'fecha_publicacion', 'seccion1', 'seccion2', 'seccion3', 'seccion4', 'seccion5', 'seccion6',
                  'tags', 'subtitulo', 'solo_para_subscriptores', 'contenido', 'tiene_comentarios', 'estado', 
                  'autor', 'editor_en_jefe']:
            if field in validated_data:
                setattr(instance, field, validated_data.get(field, getattr(instance, field)))
        
        # Lógica de manejo de imágenes
        for i in range(7):  # 0 for imagen_cabecera, 1-6 for imagen_1 to imagen_6
            field_name = f'imagen_{i}' if i > 0 else 'imagen_cabecera'
            image_url = validated_data.get(field_name)
            if image_url:
                setattr(instance, field_name, image_url)
        
        instance.save()
        return instance


from .models import ReaccionNoticia

class ReaccionNoticiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReaccionNoticia
        fields = ['id', 'tipo_reaccion', 'fecha_creacion']
        read_only_fields = ['usuario']

