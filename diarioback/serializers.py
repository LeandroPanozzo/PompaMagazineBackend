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
    def validate_email(self, value):
        # Verifica si el email ya existe en User
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo electrónico.")
        
        # Verifica si el email ya existe en Trabajador
        if Trabajador.objects.filter(correo=value).exists():
            raise serializers.ValidationError("Ya existe un trabajador con este correo electrónico.")
            
        return value

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
    descripcion_usuario = serializers.CharField(required=False, allow_blank=True)
    es_trabajador = serializers.BooleanField(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'nombre', 'apellido', 'foto_perfil', 'foto_perfil_local', 'descripcion_usuario', 'es_trabajador']

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
    editor_en_jefe = serializers.PrimaryKeyRelatedField(queryset=Trabajador.objects.all(), required=False, allow_null=True)
    estado = serializers.PrimaryKeyRelatedField(queryset=EstadoPublicacion.objects.all())
    # Cambio principal: categorias como campo personalizado
     # Define categorias as a string field that will be validated against allowed categories
    categorias = serializers.CharField(
        required=False, 
        allow_blank=True,
        allow_null=True
    )
    visitas_24h = serializers.IntegerField(source='visitas_ultimas_24h', read_only=True)
    conteo_reacciones = serializers.SerializerMethodField()

    imagen_cabecera = serializers.CharField(allow_blank=True, required=False)
    imagen_1 = serializers.CharField(allow_blank=True, required=False)
    imagen_2 = serializers.CharField(allow_blank=True, required=False)
    imagen_3 = serializers.CharField(allow_blank=True, required=False)
    imagen_4 = serializers.CharField(allow_blank=True, required=False)
    imagen_5 = serializers.CharField(allow_blank=True, required=False)
    imagen_6 = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Noticia
        fields = [
            'id', 'autor', 'editor_en_jefe', 'nombre_noticia', 'subtitulo', 
            'fecha_publicacion', 'categorias', 'Palabras_clave', 
            'imagen_cabecera', 'imagen_1', 'imagen_2', 'imagen_3', 
            'imagen_4', 'imagen_5', 'imagen_6', 
            'estado', 'solo_para_subscriptores', 
            'contenido', 'tiene_comentarios', 
            'conteo_reacciones', 'contador_visitas','visitas_24h'
        ]

    def get_conteo_reacciones(self, obj):
        return obj.get_conteo_reacciones()

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

    def create(self, validated_data):
        # Ensure ID is not in the data
        validated_data.pop('id', None)
        # Debug log to verify validated data
        print("Validated Data in create:", validated_data)

        # Ensure categorias is properly formatted
        categorias = validated_data.get('categorias', '')
        if categorias and isinstance(categorias, list):
            validated_data['categorias'] = ','.join(categorias)
        elif not categorias:
            validated_data['categorias'] = ''

        # Create the Noticia instance
        noticia = Noticia.objects.create(**validated_data)

        # Generate URL for the new Noticia
        noticia.url = f"/noticia/{noticia.id}/{noticia.nombre_noticia.replace(' ', '-').lower()}/"
        noticia.save()

        # Debug log to verify the created instance
        print("Created Noticia:", noticia)
        return noticia
    def to_internal_value(self, data):
        if 'categorias' in data and isinstance(data['categorias'], list):
            data['categorias'] = ','.join(data['categorias'])
        return super().to_internal_value(data)

    def validate_categorias(self, value):
        if not value:
            return ''
        categories = value.split(',')
        invalid_cats = [cat for cat in categories if cat not in Noticia.FLAT_CATEGORIAS]
        if invalid_cats:
            raise serializers.ValidationError(f'Invalid categories: {", ".join(invalid_cats)}')
        return value

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret['categorias'] = instance.get_categorias()
        return ret

    def update(self, instance, validated_data):
        # Debug log to verify validated data
        print("Validated Data in update:", validated_data)

        # Ensure categorias is properly formatted
        categorias = validated_data.get('categorias', '')
        if categorias and isinstance(categorias, list):
            validated_data['categorias'] = ','.join(categorias)
        elif not categorias:
            validated_data['categorias'] = instance.categorias

        # Update fields
        fields_to_update = [
            'nombre_noticia', 'fecha_publicacion', 'categorias', 
            'Palabras_clave', 'subtitulo', 'solo_para_subscriptores', 
            'contenido', 'tiene_comentarios', 'estado', 
            'autor', 'editor_en_jefe'
        ]
        for field in fields_to_update:
            if field in validated_data:
                setattr(instance, field, validated_data.get(field, getattr(instance, field)))

        # Handle image updates
        for i in range(7):  # 0 for imagen_cabecera, 1-6 for imagen_1 to imagen_6
            field_name = f'imagen_{i}' if i > 0 else 'imagen_cabecera'
            image_url = validated_data.get(field_name)
            if image_url:
                setattr(instance, field_name, image_url)

        # Save the updated instance
        instance.save()

        # Debug log to verify the updated instance
        print("Updated Noticia:", instance)
        return instance
from .models import ReaccionNoticia

class ReaccionNoticiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReaccionNoticia
        fields = ['id', 'tipo_reaccion', 'fecha_creacion']
        read_only_fields = ['usuario']

# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PasswordResetToken

User = get_user_model()

class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        # Verifica si existe un usuario con este email
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No existe un usuario con este correo electrónico.")
        return value

class VerifyTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)  # Cambiado de UUIDField a CharField
    
    def validate_token(self, value):
        # Verifica si el token existe y es válido
        token_obj = PasswordResetToken.objects.filter(token=value).first()
        if not token_obj or not token_obj.is_valid():
            raise serializers.ValidationError("Token inválido o expirado.")
        return value

class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)  # Cambiado de UUIDField a CharField
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate(self, data):
        # Verifica que las contraseñas coincidan
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        
        # Verifica si el token existe y es válido
        token_obj = PasswordResetToken.objects.filter(token=data['token']).first()
        if not token_obj or not token_obj.is_valid():
            raise serializers.ValidationError("Token inválido o expirado.")
        
        return data