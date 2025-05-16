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
    editores_en_jefe = serializers.PrimaryKeyRelatedField(
        queryset=Trabajador.objects.all(),
        required=False,
        many=True
    )
    estado = serializers.PrimaryKeyRelatedField(queryset=EstadoPublicacion.objects.all())
    # Define categorias as a string field that will be validated against allowed categories
    categorias = serializers.CharField(
        required=False, 
        allow_blank=True,
        allow_null=True
    )
    visitas_semana = serializers.IntegerField(source='visitas_ultima_semana', read_only=True)
    conteo_reacciones = serializers.SerializerMethodField()
    # Añadir campos para URL y slug
    url = serializers.SerializerMethodField(read_only=True)
    slug = serializers.CharField(read_only=True)
    imagen_1 = serializers.URLField(allow_blank=True, required=False, allow_null=True)
    imagen_2 = serializers.URLField(allow_blank=True, required=False, allow_null=True)
    imagen_3 = serializers.URLField(allow_blank=True, required=False, allow_null=True)
    imagen_4 = serializers.URLField(allow_blank=True, required=False, allow_null=True)
    imagen_5 = serializers.URLField(allow_blank=True, required=False, allow_null=True)
    imagen_6 = serializers.URLField(allow_blank=True, required=False, allow_null=True)

    # Add autorData and editorData fields for easier frontend access
    autorData = serializers.SerializerMethodField(read_only=True)
    editoresData = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Noticia
        fields = [
            'id', 'autor', 'editores_en_jefe', 'nombre_noticia', 'subtitulo', 
            'fecha_publicacion', 'categorias', 'Palabras_clave', 
            'imagen_1', 'imagen_2', 'imagen_3', 
            'imagen_4', 'imagen_5', 'imagen_6', 
            'estado', 'solo_para_subscriptores', 
            'contenido', 'tiene_comentarios', 
            'conteo_reacciones', 'contador_visitas', 'visitas_semana',
            'autorData', 'editoresData', 'url', 'slug'  # Incluir nuevos campos
        ]

    def get_url(self, obj):
        """Devuelve la URL amigable con el slug"""
        return obj.get_absolute_url()

    def get_conteo_reacciones(self, obj):
        return obj.get_conteo_reacciones()

    def get_autorData(self, obj):
        """Return author data if include_autor was requested"""
        if hasattr(self.context.get('request'), 'query_params'):
            include_autor = self.context.get('request').query_params.get('include_autor')
            if include_autor and include_autor.lower() == 'true':
                if obj.autor:
                    return {
                        'id': obj.autor.id,
                        'nombre': obj.autor.nombre,
                        'apellido': obj.autor.apellido,
                        'cargo': getattr(obj.autor, 'cargo', None),
                    }
        return None
        
    def get_editoresData(self, obj):
        """Return editors data if include_editor was requested"""
        if hasattr(self.context.get('request'), 'query_params'):
            include_editor = self.context.get('request').query_params.get('include_editor')
            if include_editor and include_editor.lower() == 'true':
                return [{
                    'id': editor.id,
                    'nombre': editor.nombre,
                    'apellido': editor.apellido,
                    'cargo': getattr(editor, 'cargo', None),
                } for editor in obj.editores_en_jefe.all()]
        return None

    def to_internal_value(self, data):
        """
        Sobrescribe to_internal_value para manejar correctamente las comillas en el título
        y otros posibles problemas de caracteres especiales
        """
        # Si es un QueryDict o similar, convertir a dict normal
        if hasattr(data, 'dict'):
            data = data.dict()
        
        # Crear una copia mutable de los datos
        mutable_data = data.copy() if isinstance(data, dict) else {}
        
        # Asegurarse de que nombre_noticia sea tratado correctamente
        if 'nombre_noticia' in mutable_data:
            # No es necesario hacer un escape adicional, 
            # el serializador debería manejar los caracteres correctamente
            pass
        
        # Manejar las categorias si están en formato lista
        if 'categorias' in mutable_data and isinstance(mutable_data['categorias'], list):
            mutable_data['categorias'] = ','.join(mutable_data['categorias'])
        
        # Procesar el resto de los datos normalmente
        return super().to_internal_value(mutable_data)

    def create(self, validated_data):
        # Ensure ID is not in the data
        validated_data.pop('id', None)
        
        # Debug log to verify validated data
        print("Validated Data in create:", validated_data)

        # Extraer los editores_en_jefe antes de crear el objeto
        editores_en_jefe = validated_data.pop('editores_en_jefe', [])

        # Ensure categorias is properly formatted
        categorias = validated_data.get('categorias', '')
        if categorias and isinstance(categorias, list):
            validated_data['categorias'] = ','.join(categorias)
        elif not categorias:
            validated_data['categorias'] = ''

        # Create the Noticia instance without the many-to-many field
        noticia = Noticia.objects.create(**validated_data)

        # Ahora asignamos los editores_en_jefe usando el método set()
        if editores_en_jefe:
            noticia.editores_en_jefe.set(editores_en_jefe)
        
        # Debug log to verify the created instance
        print("Created Noticia:", noticia)
        return noticia

    def validate_categorias(self, value):
        """Validate categories against allowed list with support for legacy categories"""
        if not value:
            return ''
        categories = value.split(',')
        
        # Lista temporal de categorías permitidas durante la transición
        temp_allowed = ['argentina']  # Categorías obsoletas pero que aún existen en DB
        
        # Verificar solo categorías que no estén en la lista temporal
        invalid_cats = [cat for cat in categories if cat not in Noticia.FLAT_CATEGORIAS and cat not in temp_allowed]
        
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
        
        # Extract editores_en_jefe separately as it's a many-to-many field
        editores = validated_data.pop('editores_en_jefe', None)
        
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
            'autor'
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
        
        # Actualiza los editores si se proporcionaron
        if editores is not None:
            # Limpia los editores existentes y añade los nuevos
            instance.editores_en_jefe.clear()
            instance.editores_en_jefe.add(*editores)
        
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