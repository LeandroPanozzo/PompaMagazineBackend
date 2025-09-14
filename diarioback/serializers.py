from rest_framework import serializers
from .models import (
    Newsletter, Suscriptor, Trabajador, UserProfile, Usuario, Contenido, EstadoPublicacion, 
    Publicidad, EspacioReferencia, ImagenLink, upload_to_imgbb,
    PasswordResetToken, TiendaMadeInArg, ProductoMadeInArg, ArtistaMadeInArg,
    get_madeinarg_stats
)
import json
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.conf import settings
import json

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
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Ya existe una cuenta con este correo electrónico.")
        
        if Trabajador.objects.filter(correo=value).exists():
            raise serializers.ValidationError("Ya existe un trabajador con este correo electrónico.")
            
        return value

# Serializador para el inicio de sesión
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(
            username=data.get('username'),
            password=data.get('password')
        )
        if user is None:
            raise serializers.ValidationError('Invalid credentials')
        return {'user': user}

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = '__all__'

class EstadoPublicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = EstadoPublicacion
        fields = '__all__'

class PublicidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicidad
        fields = '__all__'

# ACTUALIZADO: TrabajadorSerializer con UserProfile integrado
class TrabajadorSerializer(serializers.ModelSerializer):
    foto_perfil_local = serializers.ImageField(write_only=True, required=False)
    foto_perfil = serializers.URLField(read_only=True)
    descripcion_usuario = serializers.CharField(required=False, allow_blank=True)
    
    # Include permission methods as read-only fields
    puede_publicar = serializers.SerializerMethodField(read_only=True)
    puede_editar = serializers.SerializerMethodField(read_only=True)
    puede_eliminar = serializers.SerializerMethodField(read_only=True)
    puede_asignar_roles = serializers.SerializerMethodField(read_only=True)
    
    # NUEVO: Campos del UserProfile relacionado
    user_profile_id = serializers.IntegerField(source='user_profile.id', read_only=True)
    es_trabajador = serializers.BooleanField(source='user_profile.es_trabajador', read_only=True)
    
    class Meta:
        model = Trabajador
        fields = [
            'id', 'nombre', 'apellido', 'correo', 'foto_perfil', 
            'foto_perfil_local', 'descripcion_usuario',
            'puede_publicar', 'puede_editar', 'puede_eliminar', 'puede_asignar_roles',
            'user_profile_id', 'es_trabajador', 'user'
        ]

    def get_puede_publicar(self, obj):
        return obj.puede_publicar()
    
    def get_puede_editar(self, obj):
        return obj.puede_editar()
    
    def get_puede_eliminar(self, obj):
        return obj.puede_eliminar()
    
    def get_puede_asignar_roles(self, obj):
        return obj.puede_asignar_roles()

    def create(self, validated_data):
        foto_perfil_local = validated_data.pop('foto_perfil_local', None)
        trabajador = Trabajador.objects.create(**validated_data)

        if foto_perfil_local:
            trabajador.foto_perfil_local = foto_perfil_local
            trabajador.save()

        return trabajador

    def update(self, instance, validated_data):
        foto_perfil_local = validated_data.pop('foto_perfil_local', None)

        # Actualizar campos básicos
        for field in ['nombre', 'apellido', 'correo']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        # Actualizar la descripcion_usuario usando la property
        if 'descripcion_usuario' in validated_data:
            instance.descripcion_usuario = validated_data['descripcion_usuario']

        # Manejo de la imagen de perfil local
        if foto_perfil_local:
            instance.foto_perfil_local = foto_perfil_local

        instance.save()
        return instance

# ACTUALIZADO: UserProfileSerializer
class UserProfileSerializer(serializers.ModelSerializer):
    foto_perfil_local = serializers.ImageField(write_only=True, required=False)
    foto_perfil = serializers.URLField(required=False, allow_blank=True)
    descripcion_usuario = serializers.CharField(required=False, allow_blank=True)
    es_trabajador = serializers.BooleanField(read_only=True)
    
    # NUEVO: Campo para mostrar si tiene un trabajador asociado
    trabajador_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'nombre', 'apellido', 'foto_perfil', 'foto_perfil_local', 
            'descripcion_usuario', 'es_trabajador', 'trabajador_id'
        ]
    
    def get_trabajador_id(self, obj):
        try:
            return obj.trabajador.id if hasattr(obj, 'trabajador') else None
        except:
            return None

    def update(self, instance, validated_data):
        foto_perfil_local = validated_data.pop('foto_perfil_local', None)

        # Procesar la imagen local si es proporcionada
        if foto_perfil_local:
            instance.foto_perfil_local = foto_perfil_local
            instance.foto_perfil = upload_to_imgbb(foto_perfil_local)

        return super().update(instance, validated_data)

# Serializador para EspacioReferencia
class EspacioReferenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EspacioReferencia
        fields = ['id', 'texto_descriptivo', 'texto_mostrar', 'url', 'orden']

# Serializador para ImagenLink (MadeInArg)
class ImagenLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenLink
        fields = ['id', 'numero_imagen', 'url_tienda', 'texto_descripcion']

class ContenidoSerializer(serializers.ModelSerializer):
    autor = serializers.PrimaryKeyRelatedField(queryset=Trabajador.objects.all())
    estado = serializers.PrimaryKeyRelatedField(queryset=EstadoPublicacion.objects.all())
    
    # Espacios de referencia anidados - MARK AS WRITE_ONLY to prevent issues
    espacios_referencia = EspacioReferenciaSerializer(many=True, required=False, write_only=True)
    
    # Links de imagen para MadeInArg - MARK AS WRITE_ONLY to prevent issues
    imagen_links = ImagenLinkSerializer(many=True, required=False, write_only=True)
    
    # Campos calculados
    contador_visitas_total = serializers.IntegerField(read_only=True)
    
    # Datos del autor y estado para facilitar el frontend
    autor_data = serializers.SerializerMethodField(read_only=True)
    estado_data = serializers.SerializerMethodField(read_only=True)
    
    # URLs de imágenes procesadas
    imagenes_urls = serializers.SerializerMethodField(read_only=True)
    backstage_urls = serializers.SerializerMethodField(read_only=True)
    tags_marcas_list = serializers.SerializerMethodField(read_only=True)
    
    # ADD READ-ONLY FIELD FOR RESPONSE
    espacios_referencia_display = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Contenido
        fields = [
            # Campos básicos heredados de ContenidoBase
            'id', 'categoria', 'titulo', 'autor', 'fecha_publicacion', 'estado',
            
            # Campos específicos por categoría
            'numero_issue', 'nombre_modelo', 'subtitulo_issue', 'frase_final_issue', 
            'video_youtube_issue',
            'subcategoria_madeinarg', 'subtitulo_madeinarg', 'tags_marcas',
            'subtitulos_news', 'contenido_news', 'video_youtube_news',
            
            # Contadores heredados de ContenidoBase
            'contador_visitas', 'contador_visitas_total', 'ultima_actualizacion_contador',
            
            # Relaciones (write-only for input, read-only for output)
            'espacios_referencia', 'imagen_links', 'espacios_referencia_display',
            
            # Datos calculados
            'autor_data', 'estado_data', 'imagenes_urls', 'backstage_urls', 
            'tags_marcas_list',
        ] + [
            # Campos de imágenes principales heredados (1-30)
            f'imagen_{i}' for i in range(1, 31)
        ] + [
            # Campos de imágenes locales (write-only)
            f'imagen_{i}_local' for i in range(1, 31)
        ] + [
            # Campos de backstage para Issues (1-30)
            f'backstage_{i}' for i in range(1, 31)
        ] + [
            # Campos de backstage locales (write-only)
            f'backstage_{i}_local' for i in range(1, 31)
        ]
        
        extra_kwargs = {
            # Hacer que los campos locales sean write-only
            **{f'imagen_{i}_local': {'write_only': True, 'required': False} for i in range(1, 31)},
            **{f'backstage_{i}_local': {'write_only': True, 'required': False} for i in range(1, 31)},
        }

    def get_espacios_referencia_display(self, obj):
        """Return espacios_referencia for read operations"""
        return EspacioReferenciaSerializer(obj.espacios_referencia.all(), many=True).data

    def to_internal_value(self, data):
        """Override para manejar FormData que viene como arrays"""
        
        # Función para procesar valores que pueden venir como arrays
        def process_value(value):
            if isinstance(value, list) and len(value) == 1:
                return value[0]
            elif isinstance(value, list) and len(value) == 0:
                return ''
            return value
        
        # Procesar todos los datos
        processed_data = {}
        for key, value in data.items():
            processed_data[key] = process_value(value)
        
        # Log para debug
        print(f"=== PROCESSING SERIALIZER DATA ===")
        for key, value in processed_data.items():
            print(f"{key}: {value} (type: {type(value)})")
        
        # Convertir tipos específicos
        if 'autor' in processed_data:
            try:
                autor_value = processed_data['autor']
                if autor_value == '' or autor_value is None:
                    raise ValidationError({'autor': 'Este campo es requerido.'})
                processed_data['autor'] = int(autor_value)
            except (ValueError, TypeError):
                raise ValidationError({'autor': 'Debe ser un ID válido de trabajador.'})
        
        if 'estado' in processed_data:
            try:
                estado_value = processed_data['estado']
                if estado_value == '' or estado_value is None:
                    raise ValidationError({'estado': 'Este campo es requerido.'})
                processed_data['estado'] = int(estado_value)
            except (ValueError, TypeError):
                raise ValidationError({'estado': 'Debe ser un ID válido de estado.'})
                
        if 'numero_issue' in processed_data:
            numero_value = processed_data['numero_issue']
            if numero_value == '' or numero_value is None:
                processed_data['numero_issue'] = None
            else:
                try:
                    processed_data['numero_issue'] = int(numero_value)
                except (ValueError, TypeError):
                    raise ValidationError({'numero_issue': 'Debe ser un número válido.'})
        
        # Validar fecha
        if 'fecha_publicacion' in processed_data:
            fecha_value = processed_data['fecha_publicacion']
            if not fecha_value:
                raise ValidationError({'fecha_publicacion': 'Este campo es requerido.'})
        
        # Procesar espacios_referencia - Convert JSON string to Python objects
        if 'espacios_referencia' in processed_data:
            espacios_data = processed_data['espacios_referencia']
            if isinstance(espacios_data, str):
                try:
                    processed_data['espacios_referencia'] = json.loads(espacios_data)
                except json.JSONDecodeError:
                    raise ValidationError({'espacios_referencia': 'Formato JSON inválido.'})
        
        return super().to_internal_value(processed_data)

    def get_autor_data(self, obj):
        """Retorna datos del autor si se solicita"""
        if self.context.get('include_autor', False):
            return {
                'id': obj.autor.id,
                'nombre': obj.autor.nombre,
                'apellido': obj.autor.apellido,
                'foto_perfil': obj.autor.get_foto_perfil(),
            }
        return None

    def get_estado_data(self, obj):
        """Retorna datos del estado"""
        if obj.estado:
            return {
                'id': obj.estado.id,
                'nombre': obj.estado.nombre_estado,
                'display': obj.estado.get_nombre_estado_display(),
            }
        return None

    def get_imagenes_urls(self, obj):
        """Retorna lista de URLs de imágenes disponibles"""
        return obj.get_image_urls()

    def get_backstage_urls(self, obj):
        """Retorna lista de URLs de backstage disponibles"""
        if obj.categoria == 'issues':
            return obj.get_backstage_urls()
        return []

    def get_tags_marcas_list(self, obj):
        """Retorna lista de tags de marcas"""
        if obj.categoria == 'madeinarg':
            return obj.get_tags_marcas_list()
        return []

    def validate_categoria(self, value):
        """Valida que la categoría sea válida"""
        categorias_validas = [choice[0] for choice in Contenido.CATEGORIA_CHOICES]
        if value not in categorias_validas:
            raise serializers.ValidationError(f'Categoría inválida. Opciones: {categorias_validas}')
        return value

    def validate(self, data):
        """Validación cruzada según la categoría"""
        categoria = data.get('categoria')
        
        if categoria == 'issues':
            if not data.get('nombre_modelo'):
                raise serializers.ValidationError({
                    'nombre_modelo': 'Este campo es requerido para Issues.'
                })
        
        elif categoria == 'madeinarg':
            if not data.get('subcategoria_madeinarg'):
                raise serializers.ValidationError({
                    'subcategoria_madeinarg': 'Este campo es requerido para MadeInArg.'
                })
        
        elif categoria == 'news':
            if not data.get('contenido_news'):
                raise serializers.ValidationError({
                    'contenido_news': 'Este campo es requerido para News.'
                })
        
        return data

    def create(self, validated_data):
        # Extraer relaciones anidadas
        espacios_referencia_data = validated_data.pop('espacios_referencia', [])
        imagen_links_data = validated_data.pop('imagen_links', [])
        
        # Extraer imágenes locales
        imagenes_locales = {}
        backstage_locales = {}
        
        for i in range(1, 31):
            local_field = f'imagen_{i}_local'
            backstage_field = f'backstage_{i}_local'
            
            if local_field in validated_data:
                imagenes_locales[i] = validated_data.pop(local_field)
            
            if backstage_field in validated_data:
                backstage_locales[i] = validated_data.pop(backstage_field)

        # Crear el contenido
        contenido = Contenido.objects.create(**validated_data)

        # Asignar imágenes locales
        for i, imagen in imagenes_locales.items():
            setattr(contenido, f'imagen_{i}_local', imagen)
        
        for i, backstage in backstage_locales.items():
            setattr(contenido, f'backstage_{i}_local', backstage)

        # Guardar para procesar imágenes
        if imagenes_locales or backstage_locales:
            contenido.save()

        # Crear espacios de referencia
        for espacio_data in espacios_referencia_data:
            if 'orden' not in espacio_data:
                espacio_data['orden'] = len(contenido.espacios_referencia.all()) + 1
            
            EspacioReferencia.objects.create(contenido=contenido, **espacio_data)

        # Crear links de imagen para MadeInArg
        for link_data in imagen_links_data:
            ImagenLink.objects.create(contenido=contenido, **link_data)

        return contenido

    def update(self, request, *args, **kwargs):
        """Override update para manejar FormData correctamente"""
        
        # DEBUG: Log de datos recibidos
        print("=== DEBUG UPDATE CONTENIDO ===")
        print("Request data keys:", list(request.data.keys()))
        print("Request FILES keys:", list(request.FILES.keys()) if hasattr(request, 'FILES') else "No FILES")
        
        # Get the instance first
        instance = self.get_object()
        print(f"Updating instance ID: {instance.id}")
        
        # Process data manually to avoid DRF complications
        update_data = {}
        
        # Handle basic fields directly on the instance
        basic_fields = [
            'categoria', 'titulo', 'fecha_publicacion', 'estado', 'autor',
            'numero_issue', 'nombre_modelo', 'subtitulo_issue', 'frase_final_issue',
            'video_youtube_issue', 'subcategoria_madeinarg', 'subtitulo_madeinarg',
            'tags_marcas', 'subtitulos_news', 'contenido_news', 'video_youtube_news'
        ]
        
        # Process basic fields
        for field in basic_fields:
            if field in request.data:
                value = request.data[field]
                # Handle array values from FormData
                if isinstance(value, list) and len(value) == 1:
                    value = value[0]
                elif isinstance(value, list) and len(value) == 0:
                    value = ''
                
                # Convert specific types
                if field in ['autor', 'estado']:
                    try:
                        value = int(value) if value != '' else None
                    except (ValueError, TypeError):
                        return Response({
                            'error': f'Invalid {field}: must be a valid ID'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                if field == 'numero_issue':
                    try:
                        value = int(value) if value != '' else None
                    except (ValueError, TypeError):
                        return Response({
                            'error': 'Invalid numero_issue: must be a number'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                update_data[field] = value
                print(f"Processed {field}: {value}")
        
        # Handle image fields
        image_fields = []
        for i in range(1, 31):
            image_field = f'imagen_{i}_local'
            if image_field in request.FILES:
                image_fields.append((i, request.FILES[image_field]))
        
        # Handle backstage fields for issues
        backstage_fields = []
        for i in range(1, 31):
            backstage_field = f'backstage_{i}_local'
            if backstage_field in request.FILES:
                backstage_fields.append((i, request.FILES[backstage_field]))
        
        try:
            # Update basic fields using Django ORM
            for field, value in update_data.items():
                if field == 'autor' and value:
                    from .models import Trabajador
                    try:
                        autor = Trabajador.objects.get(pk=value)
                        setattr(instance, field, autor)
                    except Trabajador.DoesNotExist:
                        return Response({
                            'error': f'Trabajador with ID {value} does not exist'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                elif field == 'estado' and value:
                    from .models import EstadoPublicacion
                    try:
                        estado = EstadoPublicacion.objects.get(pk=value)
                        setattr(instance, field, estado)
                    except EstadoPublicacion.DoesNotExist:
                        return Response({
                            'error': f'EstadoPublicacion with ID {value} does not exist'
                        }, status=status.HTTP_400_BAD_REQUEST)
                
                else:
                    setattr(instance, field, value)
            
            # Handle image uploads
            for i, image_file in image_fields:
                setattr(instance, f'imagen_{i}_local', image_file)
            
            for i, backstage_file in backstage_fields:
                setattr(instance, f'backstage_{i}_local', backstage_file)
            
            # Save the instance
            instance.save()
            print("Instance saved successfully")
            
            # Handle espacios_referencia separately
            if 'espacios_referencia' in request.data:
                espacios_data = request.data['espacios_referencia']
                if isinstance(espacios_data, list) and len(espacios_data) == 1:
                    espacios_data = espacios_data[0]
                
                if isinstance(espacios_data, str):
                    try:
                        import json
                        espacios_list = json.loads(espacios_data)
                    except json.JSONDecodeError:
                        return Response({
                            'error': 'Invalid espacios_referencia JSON format'
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    espacios_list = espacios_data
                
                # Handle espacios_referencia
                if espacios_list:
                    from .models import EspacioReferencia
                    
                    # Delete existing
                    instance.espacios_referencia.all().delete()
                    
                    # Create new ones
                    for idx, espacio_data in enumerate(espacios_list):
                        if espacio_data.get('texto_mostrar') and espacio_data.get('url'):
                            EspacioReferencia.objects.create(
                                contenido=instance,
                                texto_descriptivo=espacio_data.get('texto_descriptivo', '') or '',
                                texto_mostrar=espacio_data.get('texto_mostrar', ''),
                                url=espacio_data.get('url', ''),
                                orden=espacio_data.get('orden', idx + 1)
                            )
                    print(f"Created {len(espacios_list)} espacios de referencia")
            
            # Serialize and return the updated instance
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
            
        except Exception as e:
            print(f"Error during update: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Error updating content: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# NUEVO: Serializers para TiendaMadeInArg y ProductoMadeInArg
class ProductoMadeInArgSerializer(serializers.ModelSerializer):
    imagen_local = serializers.ImageField(write_only=True, required=False)
    imagen = serializers.URLField(read_only=True)
    tienda_nombre = serializers.CharField(source='tienda.titulo', read_only=True)
    precio_formatted = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ProductoMadeInArg
        fields = [
            'id', 'tienda', 'nombre', 'descripcion', 'categoria', 'imagen', 'imagen_local',
            'link_producto', 'precio', 'moneda', 'fecha_creacion', 'fecha_actualizacion',
            'activo', 'orden', 'tienda_nombre', 'precio_formatted'
        ]
    
    def get_precio_formatted(self, obj):
        return obj.get_precio_formatted()

class ArtistaMadeInArgListSerializer(serializers.ModelSerializer):
    imagen_principal = serializers.SerializerMethodField(read_only=True)
    total_imagenes = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ArtistaMadeInArg
        fields = [
            'id', 'titulo', 'subtitulo', 'imagen_principal', 'total_imagenes',
            'fecha_creacion', 'activo', 'video_youtube'
        ]
    
    def get_imagen_principal(self, obj):
        imagenes = obj.get_imagenes_galeria()
        return imagenes[0] if imagenes else None
    
    def get_total_imagenes(self, obj):
        return len(obj.get_imagenes_galeria())

# Serializer completo que incluye tiendas y artistas para MadeInArg
class MadeInArgCompletaSerializer(ContenidoSerializer):
    """Serializer completo que incluye tiendas y artistas para MadeInArg"""
    tiendas_activas = serializers.SerializerMethodField(read_only=True)
    artistas_activos = serializers.SerializerMethodField(read_only=True)
    estadisticas = serializers.SerializerMethodField(read_only=True)
    
    class Meta(ContenidoSerializer.Meta):
        pass
    
    def get_tiendas_activas(self, obj):
        tiendas = TiendaMadeInArg.objects.filter(activa=True).order_by('-fecha_creacion')[:10]
        return TiendaMadeInArgListSerializer(tiendas, many=True).data
    
    def get_artistas_activos(self, obj):
        artistas = ArtistaMadeInArg.objects.filter(activo=True).order_by('-fecha_creacion')[:10]
        return ArtistaMadeInArgListSerializer(artistas, many=True).data
    
    def get_estadisticas(self, obj):
        return get_madeinarg_stats()

# Serializer para estadísticas de MadeInArg
class MadeInArgStatsSerializer(serializers.Serializer):
    total_tiendas = serializers.IntegerField()
    total_productos = serializers.IntegerField()
    total_artistas = serializers.IntegerField()
    productos_por_categoria = serializers.DictField()
    tiendas_con_mas_productos = serializers.ListField()

class MadeInArgSerializer(ContenidoSerializer):
    class Meta(ContenidoSerializer.Meta):
        pass
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'initial_data') and self.initial_data:
            self.initial_data = {**self.initial_data, 'categoria': 'madeinarg'}


class TiendaMadeInArgSerializer(serializers.ModelSerializer):
    imagen_portada_local = serializers.ImageField(write_only=True, required=False)
    imagen_portada = serializers.URLField(read_only=True)
    productos = ProductoMadeInArgSerializer(many=True, read_only=True)
    total_productos = serializers.SerializerMethodField(read_only=True)
    productos_por_categoria = serializers.SerializerMethodField(read_only=True)
    creado_por_nombre = serializers.CharField(source='creado_por.nombre', read_only=True)
    
    class Meta:
        model = TiendaMadeInArg
        fields = [
            'id', 'titulo', 'subtitulo', 'imagen_portada', 'imagen_portada_local',
            'descripcion', 'link_instagram', 'link_sitio_web', 'fecha_creacion',
            'fecha_actualizacion', 'activa', 'creado_por', 'creado_por_nombre',
            'productos', 'total_productos', 'productos_por_categoria'
        ]
        extra_kwargs = {
            'creado_por': {'required': False, 'read_only': True}  # Hacer que sea read_only
        }
    
    def get_total_productos(self, obj):
        return obj.get_total_productos()
    
    def get_productos_por_categoria(self, obj):
        result = {}
        for categoria, nombre in ProductoMadeInArg.CATEGORIA_CHOICES:
            productos = obj.get_productos_por_categoria(categoria)
            result[categoria] = {
                'nombre': nombre,
                'count': productos.count(),
                'productos': ProductoMadeInArgSerializer(productos, many=True).data
            }
        return result
    
    def create(self, validated_data):
        imagen_portada_local = validated_data.pop('imagen_portada_local', None)
        
        # Asignar automáticamente el trabajador del usuario autenticado
        user = self.context.get('request').user
        if hasattr(user, 'trabajador'):
            validated_data['creado_por'] = user.trabajador
        else:
            try:
                trabajador = Trabajador.objects.get(user=user)
                validated_data['creado_por'] = trabajador
            except Trabajador.DoesNotExist:
                raise serializers.ValidationError("Usuario debe ser un trabajador para crear tiendas")
        
        tienda = TiendaMadeInArg.objects.create(**validated_data)
        
        if imagen_portada_local:
            tienda.imagen_portada_local = imagen_portada_local
            tienda.save()
        
        return tienda
    
    def update(self, instance, validated_data):
        imagen_portada_local = validated_data.pop('imagen_portada_local', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if imagen_portada_local:
            instance.imagen_portada_local = imagen_portada_local
        
        instance.save()
        return instance

# NUEVO: Serializer para ArtistaMadeInArg
class ArtistaMadeInArgSerializer(serializers.ModelSerializer):
    # Campos de imágenes locales (write-only) - solo los primeros 20
    imagen_1_local = serializers.ImageField(write_only=True, required=False)
    imagen_2_local = serializers.ImageField(write_only=True, required=False)
    imagen_3_local = serializers.ImageField(write_only=True, required=False)
    imagen_4_local = serializers.ImageField(write_only=True, required=False)
    imagen_5_local = serializers.ImageField(write_only=True, required=False)
    imagen_6_local = serializers.ImageField(write_only=True, required=False)
    imagen_7_local = serializers.ImageField(write_only=True, required=False)
    imagen_8_local = serializers.ImageField(write_only=True, required=False)
    imagen_9_local = serializers.ImageField(write_only=True, required=False)
    imagen_10_local = serializers.ImageField(write_only=True, required=False)
    imagen_11_local = serializers.ImageField(write_only=True, required=False)
    imagen_12_local = serializers.ImageField(write_only=True, required=False)
    imagen_13_local = serializers.ImageField(write_only=True, required=False)
    imagen_14_local = serializers.ImageField(write_only=True, required=False)
    imagen_15_local = serializers.ImageField(write_only=True, required=False)
    imagen_16_local = serializers.ImageField(write_only=True, required=False)
    imagen_17_local = serializers.ImageField(write_only=True, required=False)
    imagen_18_local = serializers.ImageField(write_only=True, required=False)
    imagen_19_local = serializers.ImageField(write_only=True, required=False)
    imagen_20_local = serializers.ImageField(write_only=True, required=False)
    
    # Campos calculados
    imagenes_galeria = serializers.SerializerMethodField(read_only=True)
    creado_por_nombre = serializers.CharField(source='creado_por.nombre', read_only=True)
    
    class Meta:
        model = ArtistaMadeInArg
        fields = [
            # Campos básicos
            'id', 'titulo', 'subtitulo', 'descripcion', 'video_youtube',
            
            # Links sociales
            'link_instagram', 'link_sitio_web', 'link_spotify', 'link_otros',
            
            # Metadatos
            'fecha_creacion', 'fecha_actualizacion', 'activo', 'creado_por', 'creado_por_nombre',
            
            # Imágenes URLs (read-only) - las 20 imágenes
            'imagen_1', 'imagen_2', 'imagen_3', 'imagen_4', 'imagen_5',
            'imagen_6', 'imagen_7', 'imagen_8', 'imagen_9', 'imagen_10',
            'imagen_11', 'imagen_12', 'imagen_13', 'imagen_14', 'imagen_15',
            'imagen_16', 'imagen_17', 'imagen_18', 'imagen_19', 'imagen_20',
            
            # Imágenes locales (write-only)
            'imagen_1_local', 'imagen_2_local', 'imagen_3_local', 'imagen_4_local', 'imagen_5_local',
            'imagen_6_local', 'imagen_7_local', 'imagen_8_local', 'imagen_9_local', 'imagen_10_local',
            'imagen_11_local', 'imagen_12_local', 'imagen_13_local', 'imagen_14_local', 'imagen_15_local',
            'imagen_16_local', 'imagen_17_local', 'imagen_18_local', 'imagen_19_local', 'imagen_20_local',
            
            # Campos calculados
            'imagenes_galeria'
        ]
        
        # ADD THIS: Configure creado_por as read_only
        extra_kwargs = {
            'creado_por': {'required': False, 'read_only': True}  # Make it read_only like in TiendaMadeInArgSerializer
        }
    
    def get_imagenes_galeria(self, obj):
        return obj.get_imagenes_galeria()
    
    def create(self, validated_data):
        # Extraer imágenes locales
        imagenes_locales = {}
        for i in range(1, 21):
            local_field = f'imagen_{i}_local'
            if local_field in validated_data:
                imagenes_locales[i] = validated_data.pop(local_field)
        
        # Asignar el usuario autenticado como creador si no se especifica
        if 'creado_por' not in validated_data:
            user = self.context.get('request').user
            if hasattr(user, 'trabajador'):
                validated_data['creado_por'] = user.trabajador
            else:
                try:
                    trabajador = Trabajador.objects.get(user=user)
                    validated_data['creado_por'] = trabajador
                except Trabajador.DoesNotExist:
                    raise serializers.ValidationError("Usuario debe ser un trabajador para crear contenido de artistas")
        
        # Crear el artista
        artista = ArtistaMadeInArg.objects.create(**validated_data)
        
        # Asignar imágenes locales
        for i, imagen in imagenes_locales.items():
            setattr(artista, f'imagen_{i}_local', imagen)
        
        # Guardar para procesar imágenes
        if imagenes_locales:
            artista.save()
        
        return artista
    
    def update(self, instance, validated_data):
        # Extraer imágenes locales
        imagenes_locales = {}
        for i in range(1, 21):
            local_field = f'imagen_{i}_local'
            if local_field in validated_data:
                imagenes_locales[i] = validated_data.pop(local_field)
        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Asignar nuevas imágenes locales
        for i, imagen in imagenes_locales.items():
            setattr(instance, f'imagen_{i}_local', imagen)
        
        # Guardar para procesar imágenes
        instance.save()
        return instance

# Serializers simplificados para listas
class TiendaMadeInArgListSerializer(serializers.ModelSerializer):
    total_productos = serializers.SerializerMethodField(read_only=True)
    imagen_portada = serializers.URLField(read_only=True)
    
    class Meta:
        model = TiendaMadeInArg
        fields = [
            'id', 'titulo', 'subtitulo', 'imagen_portada', 
            'fecha_creacion', 'activa', 'total_productos'
        ]
    
    def get_total_productos(self, obj):
        return obj.get_total_productos()

class ProductoMadeInArgListSerializer(serializers.ModelSerializer):
    tienda_nombre = serializers.CharField(source='tienda.titulo', read_only=True)
    imagen = serializers.URLField(read_only=True)
    precio_formatted = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ProductoMadeInArg
        fields = [
            'id', 'nombre', 'categoria', 'imagen', 'link_producto',
            'precio_formatted', 'tienda', 'tienda_nombre', 'orden'
        ]
    
    def get_precio_formatted(self, obj):
        return obj.get_precio_formatted()
    


# Serializers específicos por categoría para mayor comodidad
class EditorialsSerializer(ContenidoSerializer):
    class Meta(ContenidoSerializer.Meta):
        pass
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'initial_data') and self.initial_data:
            self.initial_data = {**self.initial_data, 'categoria': 'editorials'}

class IssuesSerializer(ContenidoSerializer):
    class Meta(ContenidoSerializer.Meta):
        pass
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'initial_data') and self.initial_data:
            self.initial_data = {**self.initial_data, 'categoria': 'issues'}

class NewsSerializer(ContenidoSerializer):
    class Meta(ContenidoSerializer.Meta):
        pass
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'initial_data') and self.initial_data:
            self.initial_data = {**self.initial_data, 'categoria': 'news'}

class ClubPompaSerializer(ContenidoSerializer):
    # Incluir espacios_referencia explícitamente
    espacios_referencia = EspacioReferenciaSerializer(many=True, read_only=True)
    espacios_referencia_display = serializers.SerializerMethodField()
    
    class Meta(ContenidoSerializer.Meta):
        # Asegurar que espacios_referencia esté en los fields
        fields = ContenidoSerializer.Meta.fields + ['espacios_referencia_display']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'initial_data') and self.initial_data:
            self.initial_data = {**self.initial_data, 'categoria': 'club_pompa'}
    
    def get_espacios_referencia_display(self, obj):
        """Método para obtener espacios de referencia con formato personalizado"""
        espacios = obj.espacios_referencia.all().order_by('orden')
        return [{
            'id': espacio.id,
            'texto_descriptivo': espacio.texto_descriptivo,
            'texto_mostrar': espacio.texto_mostrar,
            'url': espacio.url,
            'orden': espacio.orden
        } for espacio in espacios]
    
    def to_representation(self, instance):
        """Override para asegurar que espacios_referencia se incluyan"""
        data = super().to_representation(instance)
        
        # Forzar la inclusión de espacios_referencia si no están presentes
        if 'espacios_referencia' not in data or not data['espacios_referencia']:
            espacios = instance.espacios_referencia.all().order_by('orden')
            data['espacios_referencia'] = [{
                'id': espacio.id,
                'texto_descriptivo': espacio.texto_descriptivo,
                'texto_mostrar': espacio.texto_mostrar,
                'url': espacio.url,
                'orden': espacio.orden
            } for espacio in espacios]
        
        return data

# Serializers para recuperación de contraseña
class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No existe un usuario con este correo electrónico.")
        return value

class VerifyTokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)
    
    def validate_token(self, value):
        token_obj = PasswordResetToken.objects.filter(token=value).first()
        if not token_obj or not token_obj.is_valid():
            raise serializers.ValidationError("Token inválido o expirado.")
        return value

class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=6)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    
    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        
        token_obj = PasswordResetToken.objects.filter(token=data['token']).first()
        if not token_obj or not token_obj.is_valid():
            raise serializers.ValidationError("Token inválido o expirado.")
        
        return data
    





# serializers.py - Agregar estos serializers a tu archivo existente

class SuscriptorSerializer(serializers.ModelSerializer):
    """Serializer para crear y gestionar suscriptores"""
    
    class Meta:
        model = Suscriptor
        fields = [
            'id', 'nombre', 'email', 'fecha_suscripcion', 'activo',
            'suscrito_editorials', 'suscrito_issues', 'suscrito_madeinarg',
            'suscrito_news', 'suscrito_club_pompa', 'token_desuscripcion'
        ]
        extra_kwargs = {
            'token_desuscripcion': {'read_only': True},
            'fecha_suscripcion': {'read_only': True},
            'activo': {'read_only': True},
        }
    
    def validate_email(self, value):
        """Valida que el email no esté duplicado para suscriptores activos"""
        if Suscriptor.objects.filter(email=value, activo=True).exists():
            raise serializers.ValidationError("Este email ya está suscrito.")
        return value
    
    def validate_nombre(self, value):
        """Valida que el nombre no esté vacío"""
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre es requerido.")
        return value.strip()


class SuscriptorPublicoSerializer(serializers.ModelSerializer):
    """Serializer público para suscripciones (solo campos necesarios)"""
    
    class Meta:
        model = Suscriptor
        fields = [
            'nombre', 'email', 
            'suscrito_editorials', 'suscrito_issues', 'suscrito_madeinarg',
            'suscrito_news', 'suscrito_club_pompa'
        ]
    
    def validate_email(self, value):
        """Valida email para suscripción pública"""
        value = value.lower().strip()
        
        # Verificar si ya existe un suscriptor activo con este email
        if Suscriptor.objects.filter(email=value, activo=True).exists():
            raise serializers.ValidationError("Ya estás suscrito con este email.")
        
        return value
    
    def validate_nombre(self, value):
        """Valida nombre para suscripción pública"""
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("El nombre debe tener al menos 2 caracteres.")
        return value.strip()
    
    def create(self, validated_data):
        """Crear suscriptor con valores por defecto"""
        # Si no se especifican preferencias, suscribir a todo
        if not any([
            'suscrito_editorials' in validated_data,
            'suscrito_issues' in validated_data,
            'suscrito_madeinarg' in validated_data,
            'suscrito_news' in validated_data,
            'suscrito_club_pompa' in validated_data,
        ]):
            validated_data.update({
                'suscrito_editorials': True,
                'suscrito_issues': True,
                'suscrito_madeinarg': True,
                'suscrito_news': True,
                'suscrito_club_pompa': True,
            })
        
        return super().create(validated_data)


class NewsletterSerializer(serializers.ModelSerializer):
    """Serializer para gestión de newsletters (solo para admin)"""
    contenido_titulo = serializers.CharField(source='contenido.titulo', read_only=True)
    contenido_categoria = serializers.CharField(source='contenido.categoria', read_only=True)
    contenido_autor = serializers.CharField(source='contenido.autor.nombre', read_only=True)
    
    class Meta:
        model = Newsletter
        fields = [
            'id', 'contenido', 'fecha_envio', 'enviado_exitosamente',
            'total_enviados', 'total_errores', 'log_errores',
            'contenido_titulo', 'contenido_categoria', 'contenido_autor'
        ]
        extra_kwargs = {
            'fecha_envio': {'read_only': True},
            'enviado_exitosamente': {'read_only': True},
            'total_enviados': {'read_only': True},
            'total_errores': {'read_only': True},
            'log_errores': {'read_only': True},
        }


class DesuscripcionSerializer(serializers.Serializer):
    """Serializer para manejar desuscripciones"""
    token = serializers.UUIDField(required=True)
    motivo = serializers.CharField(max_length=500, required=False, allow_blank=True)
    
    def validate_token(self, value):
        """Valida que el token de desuscripción existe"""
        try:
            suscriptor = Suscriptor.objects.get(token_desuscripcion=value, activo=True)
            return value
        except Suscriptor.DoesNotExist:
            raise serializers.ValidationError("Token de desuscripción inválido o ya utilizado.")


class SuscriptorEstadisticasSerializer(serializers.Serializer):
    """Serializer para estadísticas de suscriptores (solo para admin)"""
    total_suscriptores = serializers.IntegerField()
    total_activos = serializers.IntegerField()
    total_inactivos = serializers.IntegerField()
    suscripciones_por_mes = serializers.DictField()
    suscripciones_por_categoria = serializers.DictField()
    nuevos_esta_semana = serializers.IntegerField()
    nuevos_este_mes = serializers.IntegerField()


class ActualizarPreferenciasSerializer(serializers.ModelSerializer):
    """Serializer para actualizar preferencias de suscripción"""
    token = serializers.UUIDField(write_only=True, required=True)
    
    class Meta:
        model = Suscriptor
        fields = [
            'token', 'nombre',
            'suscrito_editorials', 'suscrito_issues', 'suscrito_madeinarg',
            'suscrito_news', 'suscrito_club_pompa'
        ]
    
    def validate_token(self, value):
        """Valida el token y obtiene el suscriptor"""
        try:
            self.suscriptor = Suscriptor.objects.get(token_desuscripcion=value, activo=True)
            return value
        except Suscriptor.DoesNotExist:
            raise serializers.ValidationError("Token inválido.")
    
    def update(self, instance, validated_data):
        """Actualiza las preferencias del suscriptor"""
        validated_data.pop('token', None)  # Remover el token
        return super().update(instance, validated_data)