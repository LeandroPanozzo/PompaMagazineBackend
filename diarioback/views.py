from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework import generics
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.models import User
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, Max
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import uuid
import os

from .models import (
    ArtistaMadeInArg, Newsletter, ProductoMadeInArg, Suscriptor, TiendaMadeInArg, Trabajador, 
    UserProfile, Usuario, Contenido, EstadoPublicacion, 
    Publicidad, EspacioReferencia, ImagenLink, PasswordResetToken,
    incrementar_visitas_contenido, upload_to_imgbb, get_madeinarg_stats
)
from .serializers import (
    ActualizarPreferenciasSerializer, ArtistaMadeInArgListSerializer, ArtistaMadeInArgSerializer, DesuscripcionSerializer, NewsletterSerializer, 
    ProductoMadeInArgListSerializer, ProductoMadeInArgSerializer, SuscriptorPublicoSerializer, SuscriptorSerializer, 
    TiendaMadeInArgListSerializer, TiendaMadeInArgSerializer, 
    UserSerializer, UserRegistrationSerializer, LoginSerializer, 
    UserProfileSerializer, TrabajadorSerializer, UsuarioSerializer, 
    ContenidoSerializer, EstadoPublicacionSerializer, PublicidadSerializer, 
    EspacioReferenciaSerializer, ImagenLinkSerializer, 
    RequestPasswordResetSerializer, VerifyTokenSerializer, ResetPasswordSerializer, 
    EditorialsSerializer, IssuesSerializer, MadeInArgSerializer, 
    NewsSerializer, ClubPompaSerializer
)

User = get_user_model()


# ==================== VIEWSETS PRINCIPALES ====================

class ContenidoViewSet(viewsets.ModelViewSet):
    """ViewSet principal para manejo de todo el contenido"""
    queryset = Contenido.objects.select_related('autor', 'estado').prefetch_related(
        'espacios_referencia', 'imagen_links'
    )
    serializer_class = ContenidoSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['fecha_publicacion', 'contador_visitas', 'contador_visitas_total']
    ordering = ['-fecha_publicacion']
    search_fields = ['titulo', 'tags_marcas', 'contenido_news', 'nombre_modelo']
    lookup_field = 'pk'
    lookup_value_regex = r'[0-9]+(?:-[a-zA-Z0-9-_]+)?'
    
    def get_permissions(self):
        """Permisos personalizados por acción"""
        # Acciones que deben ser públicas (sin autenticación)
        public_actions = [
            'list', 'retrieve', 'editorials', 'issues', 'madeinarg', 
            'news', 'club_pompa', 'mas_vistas', 'mas_leidas', 
            'recientes', 'destacados', 'estadisticas_visitas', 'buscar'
        ]
        
        if self.action in public_actions:
            return [AllowAny()]
        elif self.action in ['create', 'update', 'partial_update', 'destroy', 'duplicar', 'cambiar_estado', 'upload_image']:
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """Personaliza el queryset basado en parámetros de consulta"""
        queryset = self.queryset.all()
        
        # Filtros específicos
        filters = {
            'categoria': 'categoria',
            'autor': 'autor_id',
            'subcategoria': 'subcategoria_madeinarg',
            'numero_issue': 'numero_issue',
        }
        
        for param, field in filters.items():
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})
        
        # Filtro por estado usando el nombre del estado
        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado__nombre_estado=estado)
        
        # Filtros de fecha
        fecha_desde = self.request.query_params.get('fecha_desde')
        if fecha_desde:
            queryset = queryset.filter(fecha_publicacion__gte=fecha_desde)
        
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_hasta:
            queryset = queryset.filter(fecha_publicacion__lte=fecha_hasta)
        
        # Filtro por tags (para MadeInArg)
        tags = self.request.query_params.get('tags')
        if tags:
            tags_list = [tag.strip() for tag in tags.split(',')]
            query = Q()
            for tag in tags_list:
                query |= Q(tags_marcas__icontains=tag)
            queryset = queryset.filter(query)
        
        return queryset.distinct()

    def get_serializer_class(self):
        """Retorna serializer específico según categoría"""
        serializer_map = {
            'editorials': EditorialsSerializer,
            'issues': IssuesSerializer,
            'madeinarg': MadeInArgSerializer,
            'news': NewsSerializer,
            'club_pompa': ClubPompaSerializer,
        }
        
        # Para acciones específicas de categoría
        if hasattr(self, 'action_categoria'):
            return serializer_map.get(self.action_categoria, ContenidoSerializer)
        
        # Para create/update, usar el serializer basado en el dato de entrada
        if self.action in ['create', 'update', 'partial_update']:
            data = getattr(self.request, 'data', {})
            categoria = data.get('categoria')
            if categoria in serializer_map:
                return serializer_map[categoria]
        
        return ContenidoSerializer

    def get_serializer_context(self):
        """Añade contexto adicional al serializer"""
        context = super().get_serializer_context()
        context['include_autor'] = True
        return context

    def perform_create(self, serializer):
        """Personaliza la creación de contenido"""
        # Asignar autor automáticamente si es trabajador
        if hasattr(self.request.user, 'trabajador'):
            serializer.save(autor=self.request.user.trabajador)
        else:
            # Intentar obtener trabajador del usuario
            try:
                trabajador = Trabajador.objects.get(user=self.request.user)
                serializer.save(autor=trabajador)
            except Trabajador.DoesNotExist:
                raise ValidationError("Solo los trabajadores pueden crear contenido")

    def retrieve(self, request, *args, **kwargs):
        """Override retrieve para incrementar visitas"""
        instance = self.get_object()
        
        # Obtener IP del cliente
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Incrementar contador de visitas
        incrementar_visitas_contenido(instance, ip_address=ip)
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def get_object(self):
        """Soporte para pk o formato pk-slug en la URL"""
        pk_value = self.kwargs.get(self.lookup_field)
        
        if pk_value and '-' in str(pk_value):
            # Extraer solo la parte numérica si está en formato 'id-slug'
            pk = str(pk_value).split('-', 1)[0]
        else:
            pk = pk_value
        
        try:
            pk = int(pk)
        except (ValueError, TypeError):
            raise NotFound("ID de contenido inválido")
        
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=pk)
        self.check_object_permissions(self.request, obj)
        return obj

    # ==================== ACCIONES ESPECÍFICAS POR CATEGORÍA ====================
    
    @action(detail=False, methods=['get'])
    def editorials(self, request):
        """Retorna contenido de tipo Editorials"""
        self.action_categoria = 'editorials'
        queryset = self.get_queryset().filter(categoria='editorials')
        return self._get_filtered_content(request, queryset)

    @action(detail=False, methods=['get'])
    def issues(self, request):
        """Retorna contenido de tipo Issues"""
        self.action_categoria = 'issues'
        queryset = self.get_queryset().filter(categoria='issues')
        return self._get_filtered_content(request, queryset)

    @action(detail=False, methods=['get'])
    def madeinarg(self, request):
        """Retorna contenido de tipo MadeInArg"""
        self.action_categoria = 'madeinarg'
        queryset = self.get_queryset().filter(categoria='madeinarg')
        
        # Filtro adicional por subcategoría
        subcategoria = request.query_params.get('subcategoria')
        if subcategoria and subcategoria != 'ver_todo':
            queryset = queryset.filter(subcategoria_madeinarg=subcategoria)
        
        return self._get_filtered_content(request, queryset)

    @action(detail=False, methods=['get'])
    def news(self, request):
        """Retorna contenido de tipo News"""
        self.action_categoria = 'news'
        queryset = self.get_queryset().filter(categoria='news')
        return self._get_filtered_content(request, queryset)

    @action(detail=False, methods=['get'])
    def club_pompa(self, request):
        """Retorna contenido de tipo Club Pompa"""
        self.action_categoria = 'club_pompa'
        queryset = self.get_queryset().filter(categoria='club_pompa')
        return self._get_filtered_content(request, queryset)

    # ==================== ACCIONES DE ESTADÍSTICAS ====================

    @action(detail=False, methods=['get'])
    def mas_vistas(self, request):
        """Retorna el contenido más visto de la semana pasada"""
        limit = self._get_limit_from_request(request, 10)
        hace_una_semana = timezone.now() - timedelta(days=7)
        
        contenido_mas_visto = self.get_queryset().filter(
            estado__nombre_estado='publicado',
            ultima_actualizacion_contador__gte=hace_una_semana
        ).order_by('-contador_visitas')[:limit]
        
        serializer = self.get_serializer(contenido_mas_visto, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def mas_leidas(self, request):
        """Retorna el contenido más leído de todos los tiempos"""
        limit = self._get_limit_from_request(request, 10)
        
        contenido_mas_leido = self.get_queryset().filter(
            estado__nombre_estado='publicado'
        ).order_by('-contador_visitas_total')[:limit]
        
        serializer = self.get_serializer(contenido_mas_leido, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def recientes(self, request):
        """Retorna el contenido más reciente"""
        limit = self._get_limit_from_request(request, 10)
        categoria = request.query_params.get('categoria')
        
        queryset = self.get_queryset().filter(estado__nombre_estado='publicado')
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        contenido_reciente = queryset.order_by('-fecha_publicacion')[:limit]
        serializer = self.get_serializer(contenido_reciente, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def destacados(self, request):
        """Retorna contenido destacado para carruseles"""
        limit = self._get_limit_from_request(request, 12)
        categoria = request.query_params.get('categoria')
        
        queryset = self.get_queryset().filter(estado__nombre_estado='publicado')
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        contenido_destacado = queryset.order_by('-contador_visitas_total')[:limit]
        serializer = self.get_serializer(contenido_destacado, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def estadisticas_visitas(self, request):
        """Retorna estadísticas generales de visitas"""
        categoria = request.query_params.get('categoria')
        queryset = self.get_queryset().filter(estado__nombre_estado='publicado')
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        
        stats = queryset.aggregate(
            total_visitas_semanales=Sum('contador_visitas'),
            total_visitas_historicas=Sum('contador_visitas_total'),
            promedio_visitas_semanales=Avg('contador_visitas'),
            promedio_visitas_historicas=Avg('contador_visitas_total'),
            max_visitas_semanales=Max('contador_visitas'),
            max_visitas_historicas=Max('contador_visitas_total'),
            total_contenido=Count('id')
        )
        
        return Response(stats)

    # ==================== ACCIONES DE BÚSQUEDA ====================

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        """Búsqueda avanzada de contenido"""
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response(
                {"error": "Se requiere el parámetro 'q' para la búsqueda"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Búsqueda en múltiples campos
        search_query = (
            Q(titulo__icontains=query) |
            Q(contenido_news__icontains=query) |
            Q(subtitulos_news__icontains=query) |
            Q(tags_marcas__icontains=query) |
            Q(nombre_modelo__icontains=query) |
            Q(subtitulo_madeinarg__icontains=query)
        )
        
        queryset = self.get_queryset().filter(
            search_query,
            estado__nombre_estado='publicado'
        )
        
        return self._get_filtered_content(request, queryset)

    # ==================== ACCIONES ADMINISTRATIVAS ====================

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def duplicar(self, request, pk=None):
        """Duplica un contenido existente"""
        original = self.get_object()
        
        # Crear una copia
        original.pk = None
        original.titulo = f"Copia de {original.titulo}"
        original.fecha_publicacion = timezone.now().date()
        original.contador_visitas = 0
        original.contador_visitas_total = 0
        
        # Cambiar estado a borrador
        try:
            borrador_estado = EstadoPublicacion.objects.get(nombre_estado='borrador')
            original.estado = borrador_estado
        except EstadoPublicacion.DoesNotExist:
            pass
        
        original.save()
        
        serializer = self.get_serializer(original)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de publicación de un contenido"""
        contenido = self.get_object()
        nuevo_estado_id = request.data.get('estado_id')
        
        if not nuevo_estado_id:
            return Response(
                {'error': 'Se requiere estado_id'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            nuevo_estado = EstadoPublicacion.objects.get(pk=nuevo_estado_id)
            contenido.estado = nuevo_estado
            contenido.save()
            return Response({
                'success': True, 
                'nuevo_estado': nuevo_estado.nombre_estado
            })
        except EstadoPublicacion.DoesNotExist:
            return Response(
                {'error': 'Estado no encontrado'}, 
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def upload_image(self, request):
        """Sube una imagen a ImgBB"""
        if 'image' not in request.FILES:
            return Response(
                {'error': 'No se encontró archivo de imagen'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image = request.FILES['image']
        
        # Verificar tipo de archivo
        allowed_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
        if not image.name.lower().endswith(allowed_extensions):
            return Response({
                'error': f'Tipo de archivo no soportado. Formatos permitidos: {", ".join(allowed_extensions)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Subir a ImgBB
        uploaded_url = upload_to_imgbb(image)
        
        if uploaded_url:
            return Response({
                'success': True, 
                'url': uploaded_url,
                'message': 'Imagen subida exitosamente'
            })
        else:
            return Response({
                'error': 'Error al subir la imagen'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ==================== MÉTODOS AUXILIARES ====================

    def _get_filtered_content(self, request, queryset):
        """Método auxiliar para filtrar contenido con parámetros comunes"""
        # Filtrar por estado publicado por defecto
        estado = request.query_params.get('estado', 'publicado')
        if estado == 'publicado':
            queryset = queryset.filter(estado__nombre_estado='publicado')
        elif estado != 'todos':
            queryset = queryset.filter(estado__nombre_estado=estado)
        
        # Aplicar ordenamiento
        ordering = request.query_params.get('ordering', '-fecha_publicacion')
        if ordering:
            queryset = queryset.order_by(ordering)
        
        # Aplicar límite
        limit = self._get_limit_from_request(request)
        if limit:
            queryset = queryset[:limit]
        
        # Paginación
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _get_limit_from_request(self, request, default=None):
        """Método auxiliar para obtener el límite de los parámetros de consulta"""
        limit = request.query_params.get('limit', default)
        if limit:
            try:
                limit_int = int(limit)
                return max(1, min(limit_int, 100))  # Limitar entre 1 y 100
            except ValueError:
                return default
        return default
    
    def update(self, request, *args, **kwargs):
        """Override update para manejar FormData correctamente"""
        
        # DEBUG: Log de datos recibidos
        print("=== DEBUG UPDATE CONTENIDO (VIEWSET ONLY) ===")
        print("Request data keys:", list(request.data.keys()))
        print("Request FILES keys:", list(request.FILES.keys()) if hasattr(request, 'FILES') else "No FILES")
        
        # Procesar datos recibidos para evitar arrays
        processed_data = {}
        for key, value in request.data.items():
            # Si el valor es una lista con un solo elemento, extraerlo
            if isinstance(value, list) and len(value) == 1:
                processed_data[key] = value[0]
            else:
                processed_data[key] = value
            print(f"Processed {key}: {processed_data[key]} (type: {type(processed_data[key])})")

        # Obtener la instancia
        instance = self.get_object()
        print(f"Updating instance ID: {instance.id}")
        
        # Importar modelos necesarios
        from .models import Trabajador, EstadoPublicacion, EspacioReferencia
        from rest_framework import status
        import json
        
        try:
            # Procesar campos básicos manualmente
            if 'categoria' in processed_data:
                instance.categoria = processed_data['categoria']
                print(f"Set categoria: {processed_data['categoria']}")
            
            if 'titulo' in processed_data:
                instance.titulo = processed_data['titulo']
                print(f"Set titulo: {processed_data['titulo']}")
            
            if 'fecha_publicacion' in processed_data:
                instance.fecha_publicacion = processed_data['fecha_publicacion']
                print(f"Set fecha_publicacion: {processed_data['fecha_publicacion']}")
            
            # Manejar autor
            if 'autor' in processed_data:
                try:
                    autor_id = int(processed_data['autor'])
                    autor = Trabajador.objects.get(pk=autor_id)
                    instance.autor = autor
                    print(f"Set autor: {autor}")
                except (ValueError, Trabajador.DoesNotExist) as e:
                    print(f"Error setting autor: {e}")
                    return Response({
                        'error': f'Invalid autor: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Manejar estado
            if 'estado' in processed_data:
                try:
                    estado_id = int(processed_data['estado'])
                    estado = EstadoPublicacion.objects.get(pk=estado_id)
                    instance.estado = estado
                    print(f"Set estado: {estado}")
                except (ValueError, EstadoPublicacion.DoesNotExist) as e:
                    print(f"Error setting estado: {e}")
                    return Response({
                        'error': f'Invalid estado: {str(e)}'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Manejar otros campos específicos por categoría
            other_fields = [
                'numero_issue', 'nombre_modelo', 'subtitulo_issue', 'frase_final_issue',
                'video_youtube_issue', 'subcategoria_madeinarg', 'subtitulo_madeinarg',
                'tags_marcas', 'subtitulos_news', 'contenido_news', 'video_youtube_news'
            ]
            
            for field in other_fields:
                if field in processed_data:
                    value = processed_data[field]
                    
                    # Conversión especial para numero_issue
                    if field == 'numero_issue':
                        if value == '' or value is None:
                            value = None
                        else:
                            try:
                                value = int(value)
                            except ValueError:
                                value = None
                    
                    setattr(instance, field, value)
                    print(f"Set {field}: {value}")
            
            # Manejar archivos de imagen
            for i in range(1, 31):
                image_field = f'imagen_{i}_local'
                if image_field in request.FILES:
                    setattr(instance, image_field, request.FILES[image_field])
                    print(f"Set {image_field}")
                
                backstage_field = f'backstage_{i}_local'
                if backstage_field in request.FILES:
                    setattr(instance, backstage_field, request.FILES[backstage_field])
                    print(f"Set {backstage_field}")
            
            # GUARDAR LA INSTANCIA PRIMERO
            instance.save()
            print("Instance saved successfully")
            
            # AHORA manejar espacios_referencia completamente separado
            if 'espacios_referencia' in processed_data:
                espacios_data = processed_data['espacios_referencia']
                
                # Si es string JSON, parsear
                if isinstance(espacios_data, str):
                    try:
                        espacios_list = json.loads(espacios_data)
                        print(f"Parsed espacios_referencia JSON: {espacios_list}")
                    except json.JSONDecodeError as e:
                        print(f"Error parsing espacios_referencia JSON: {e}")
                        return Response({
                            'error': 'Invalid espacios_referencia JSON format'
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    espacios_list = espacios_data
                
                # Eliminar espacios existentes
                deleted_count = instance.espacios_referencia.count()
                instance.espacios_referencia.all().delete()
                print(f"Deleted {deleted_count} existing espacios_referencia")
                
                # Crear nuevos espacios
                created_count = 0
                if espacios_list and isinstance(espacios_list, list):
                    for idx, espacio_data in enumerate(espacios_list):
                        if (espacio_data.get('texto_mostrar', '').strip() and 
                            espacio_data.get('url', '').strip()):
                            
                            nuevo_espacio = EspacioReferencia.objects.create(
                                contenido=instance,
                                texto_descriptivo=espacio_data.get('texto_descriptivo', '') or '',
                                texto_mostrar=espacio_data.get('texto_mostrar', '').strip(),
                                url=espacio_data.get('url', '').strip(),
                                orden=espacio_data.get('orden', idx + 1)
                            )
                            created_count += 1
                            print(f"Created EspacioReferencia: {nuevo_espacio}")
                
                print(f"Created {created_count} new espacios_referencia")
            
            # IMPORTANTE: Devolver respuesta manual sin usar serializer problemático
            # Construir respuesta manualmente
            response_data = {
                'id': instance.id,
                'categoria': instance.categoria,
                'titulo': instance.titulo,
                'fecha_publicacion': str(instance.fecha_publicacion),
                'autor': instance.autor.id if instance.autor else None,
                'estado': instance.estado.id if instance.estado else None,
                'contador_visitas': instance.contador_visitas,
                'contador_visitas_total': instance.contador_visitas_total,
            }
            
            # Agregar campos específicos si existen
            if hasattr(instance, 'numero_issue') and instance.numero_issue:
                response_data['numero_issue'] = instance.numero_issue
            if hasattr(instance, 'nombre_modelo') and instance.nombre_modelo:
                response_data['nombre_modelo'] = instance.nombre_modelo
            if hasattr(instance, 'subtitulo_madeinarg') and instance.subtitulo_madeinarg:
                response_data['subtitulo_madeinarg'] = instance.subtitulo_madeinarg
            if hasattr(instance, 'tags_marcas') and instance.tags_marcas:
                response_data['tags_marcas'] = instance.tags_marcas
            if hasattr(instance, 'contenido_news') and instance.contenido_news:
                response_data['contenido_news'] = instance.contenido_news
            
            # Agregar espacios_referencia a la respuesta
            espacios = []
            for espacio in instance.espacios_referencia.all():
                espacios.append({
                    'id': espacio.id,
                    'texto_descriptivo': espacio.texto_descriptivo,
                    'texto_mostrar': espacio.texto_mostrar,
                    'url': espacio.url,
                    'orden': espacio.orden
                })
            response_data['espacios_referencia_display'] = espacios
            
            print("Update completed successfully")
            return Response(response_data)
            
        except Exception as e:
            print(f"Error during custom update: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': f'Error updating content: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== VIEWSETS PARA MADEINARG ====================

class TiendaMadeInArgViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de tiendas en MadeInArg - FILTRADO MEJORADO"""
    queryset = TiendaMadeInArg.objects.prefetch_related('productos')
    serializer_class = TiendaMadeInArgSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['fecha_creacion', 'titulo']
    ordering = ['-fecha_creacion']
    search_fields = ['titulo', 'subtitulo', 'descripcion']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'destacadas', 'productos_por_categoria', 'con_productos_categoria']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset.all()
        
        # Filtrar solo tiendas activas por defecto
        activas_solo = self.request.query_params.get('activas', 'true')
        if activas_solo.lower() == 'true':
            queryset = queryset.filter(activa=True)
        
        # NUEVO: Filtrar tiendas que tengan productos de una categoría específica
        categoria = self.request.query_params.get('categoria')
        if categoria and categoria in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            queryset = queryset.filter(
                productos__categoria=categoria,
                productos__activo=True
            ).distinct().annotate(
                productos_categoria_count=Count(
                    'productos', 
                    filter=Q(productos__categoria=categoria, productos__activo=True)
                )
            )
        
        # Filtrar por creador
        creador = self.request.query_params.get('creador')
        if creador:
            queryset = queryset.filter(creado_por_id=creador)
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return TiendaMadeInArgListSerializer
        return TiendaMadeInArgSerializer

    def perform_create(self, serializer):
        """Asignar trabajador automáticamente"""
        if hasattr(self.request.user, 'trabajador'):
            serializer.save(creado_por=self.request.user.trabajador)
        else:
            try:
                trabajador = Trabajador.objects.get(user=self.request.user)
                serializer.save(creado_por=trabajador)
            except Trabajador.DoesNotExist:
                raise ValidationError("Solo los trabajadores pueden crear tiendas")

    @action(detail=True, methods=['get'])
    def productos_por_categoria(self, request, pk=None):
        """Retorna productos de una tienda organizados por categoría"""
        tienda = self.get_object()
        categoria = request.query_params.get('categoria')
        
        if categoria and categoria in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            productos = tienda.get_productos_por_categoria(categoria)
            serializer = ProductoMadeInArgSerializer(productos, many=True)
            return Response({
                'categoria': categoria,
                'productos': serializer.data
            })
        else:
            # Retornar todos los productos organizados por categoría
            result = {}
            for cat_value, cat_name in ProductoMadeInArg.CATEGORIA_CHOICES:
                productos = tienda.get_productos_por_categoria(cat_value)
                result[cat_value] = {
                    'nombre': cat_name,
                    'productos': ProductoMadeInArgSerializer(productos, many=True).data
                }
            return Response(result)

    @action(detail=False, methods=['get'])
    def con_productos_categoria(self, request):
        """NUEVO: Retorna tiendas que tienen productos de una categoría específica"""
        categoria = request.query_params.get('categoria')
        limit = int(request.query_params.get('limit', 20))
        
        if not categoria or categoria not in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            return Response(
                {'error': 'Categoría requerida y debe ser válida'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tiendas = TiendaMadeInArg.objects.filter(
            activa=True,
            productos__categoria=categoria,
            productos__activo=True
        ).distinct().annotate(
            productos_categoria=Count(
                'productos', 
                filter=Q(productos__categoria=categoria, productos__activo=True)
            )
        ).order_by('-productos_categoria')[:limit]
        
        # Agregar información de productos de esa categoría
        result_data = []
        for tienda in tiendas:
            tienda_data = TiendaMadeInArgListSerializer(tienda).data
            tienda_data['productos_categoria'] = tienda.productos_categoria
            result_data.append(tienda_data)
        
        return Response({
            'categoria': categoria,
            'categoria_nombre': dict(ProductoMadeInArg.CATEGORIA_CHOICES)[categoria],
            'tiendas': result_data
        })

    @action(detail=False, methods=['get'])
    def destacadas(self, request):
        """Retorna tiendas destacadas (con más productos) - RESPETA FILTROS"""
        limit = int(request.query_params.get('limit', 6))
        categoria = request.query_params.get('categoria')
        
        if categoria and categoria in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            # Tiendas destacadas de una categoría específica
            tiendas = TiendaMadeInArg.objects.filter(
                activa=True,
                productos__categoria=categoria,
                productos__activo=True
            ).distinct().annotate(
                num_productos_categoria=Count(
                    'productos', 
                    filter=Q(productos__categoria=categoria, productos__activo=True)
                )
            ).order_by('-num_productos_categoria')[:limit]
        else:
            # Tiendas destacadas generales
            tiendas = TiendaMadeInArg.objects.filter(activa=True).annotate(
                num_productos=Count('productos', filter=Q(productos__activo=True))
            ).order_by('-num_productos')[:limit]
        
        serializer = TiendaMadeInArgListSerializer(tiendas, many=True)
        return Response(serializer.data)


class ProductoMadeInArgViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de productos en MadeInArg - FILTRADO MEJORADO"""
    queryset = ProductoMadeInArg.objects.select_related('tienda')
    serializer_class = ProductoMadeInArgSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['fecha_creacion', 'orden', 'nombre', 'precio']
    ordering = ['orden', '-fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'destacados', 'por_categoria']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset.all()
        
        # Filtrar solo productos activos por defecto
        activos_solo = self.request.query_params.get('activos', 'true')
        if activos_solo.lower() == 'true':
            queryset = queryset.filter(activo=True, tienda__activa=True)
        
        # FILTRO POR CATEGORÍA - CRÍTICO PARA EL FUNCIONAMIENTO
        categoria = self.request.query_params.get('categoria')
        if categoria and categoria in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            queryset = queryset.filter(categoria=categoria)
            print(f"Filtrando productos por categoría: {categoria}")  # Debug
        
        # Filtro por tienda
        tienda = self.request.query_params.get('tienda')
        if tienda:
            queryset = queryset.filter(tienda_id=tienda)
        
        # Filtrar por rango de precios
        precio_min = self.request.query_params.get('precio_min')
        if precio_min:
            try:
                queryset = queryset.filter(precio__gte=float(precio_min))
            except ValueError:
                pass
        
        precio_max = self.request.query_params.get('precio_max')
        if precio_max:
            try:
                queryset = queryset.filter(precio__lte=float(precio_max))
            except ValueError:
                pass
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductoMadeInArgListSerializer
        return ProductoMadeInArgSerializer

    @action(detail=False, methods=['get'])
    def por_categoria(self, request):
        """Retorna productos organizados por categoría - MEJORADO"""
        tienda_id = request.query_params.get('tienda')
        categoria_especifica = request.query_params.get('categoria')  # NUEVO
        limit = int(request.query_params.get('limit', 20))
        
        if categoria_especifica and categoria_especifica in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            # Si se pide una categoría específica, solo devolver esa
            queryset = self.get_queryset().filter(categoria=categoria_especifica)
            if tienda_id:
                queryset = queryset.filter(tienda_id=tienda_id)
            
            productos = queryset[:limit]
            return Response({
                categoria_especifica: {
                    'nombre': dict(ProductoMadeInArg.CATEGORIA_CHOICES)[categoria_especifica],
                    'productos': ProductoMadeInArgListSerializer(productos, many=True).data
                }
            })
        else:
            # Devolver todas las categorías
            result = {}
            for categoria, nombre in ProductoMadeInArg.CATEGORIA_CHOICES:
                queryset = self.get_queryset().filter(categoria=categoria)
                if tienda_id:
                    queryset = queryset.filter(tienda_id=tienda_id)
                
                productos = queryset[:limit]
                result[categoria] = {
                    'nombre': nombre,
                    'productos': ProductoMadeInArgListSerializer(productos, many=True).data
                }
            
            return Response(result)

    @action(detail=False, methods=['get'])
    def destacados(self, request):
        """Retorna productos destacados - RESPETA FILTROS"""
        categoria = request.query_params.get('categoria')
        limit = int(request.query_params.get('limit', 12))
        
        queryset = self.get_queryset()
        if categoria and categoria in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            queryset = queryset.filter(categoria=categoria)
        
        productos = queryset.order_by('-fecha_creacion')[:limit]
        serializer = ProductoMadeInArgListSerializer(productos, many=True)
        return Response(serializer.data)


class ArtistaMadeInArgViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de artistas en MadeInArg"""
    queryset = ArtistaMadeInArg.objects.all()
    serializer_class = ArtistaMadeInArgSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['fecha_creacion', 'titulo']
    ordering = ['-fecha_creacion']
    search_fields = ['titulo', 'subtitulo', 'descripcion']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'destacados', 'con_video', 'galeria']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = self.queryset.all()
        
        # Filtrar solo artistas activos por defecto
        activos_solo = self.request.query_params.get('activos', 'true')
        if activos_solo.lower() == 'true':
            queryset = queryset.filter(activo=True)
        
        # Filtrar por creador
        creador = self.request.query_params.get('creador')
        if creador:
            queryset = queryset.filter(creado_por_id=creador)
        
        # Filtrar por si tiene video de YouTube
        con_video = self.request.query_params.get('con_video')
        if con_video and con_video.lower() == 'true':
            queryset = queryset.exclude(
                Q(video_youtube__isnull=True) | Q(video_youtube='')
            )
        
        return queryset

    def get_serializer_class(self):
        if self.action == 'list':
            return ArtistaMadeInArgListSerializer
        return ArtistaMadeInArgSerializer

    def perform_create(self, serializer):
        """Asignar trabajador automáticamente"""
        if hasattr(self.request.user, 'trabajador'):
            serializer.save(creado_por=self.request.user.trabajador)
        else:
            try:
                trabajador = Trabajador.objects.get(user=self.request.user)
                serializer.save(creado_por=trabajador)
            except Trabajador.DoesNotExist:
                raise ValidationError("Solo los trabajadores pueden crear contenido de artistas")

    @action(detail=False, methods=['get'])
    def destacados(self, request):
        """Retorna artistas destacados (más recientes)"""
        limit = int(request.query_params.get('limit', 6))
        
        artistas = self.get_queryset().order_by('-fecha_creacion')[:limit]
        serializer = ArtistaMadeInArgListSerializer(artistas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def con_video(self, request):
        """Retorna artistas que tienen video de YouTube"""
        limit = int(request.query_params.get('limit', 10))
        
        artistas = self.get_queryset().exclude(
            Q(video_youtube__isnull=True) | Q(video_youtube='')
        ).order_by('-fecha_creacion')[:limit]
        
        serializer = ArtistaMadeInArgListSerializer(artistas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cambiar_estado(self, request, pk=None):
        """Activar/desactivar un artista"""
        artista = self.get_object()
        estado = request.data.get('activo')
        
        if estado is not None:
            artista.activo = bool(estado)
            artista.save()
            return Response({'activo': artista.activo})
        
        return Response(
            {'error': 'Se requiere el campo "activo"'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['get'])
    def galeria(self, request, pk=None):
        """Retorna solo la galería de imágenes de un artista"""
        artista = self.get_object()
        imagenes = artista.get_imagenes_galeria()
        
        return Response({
            'artista_id': artista.id,
            'titulo': artista.titulo,
            'imagenes': imagenes
        })


# ==================== VIEWSET COMPLETO PARA MADEINARG ====================

class MadeInArgViewSet(viewsets.ViewSet):
    """ViewSet que maneja toda la funcionalidad de MadeInArg de forma integrada - MEJORADO"""
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def resumen(self, request):
        """Retorna un resumen completo de MadeInArg"""
        try:
            # Tiendas destacadas
            tiendas = TiendaMadeInArg.objects.filter(activa=True).annotate(
                num_productos=Count('productos', filter=Q(productos__activo=True))
            ).order_by('-num_productos')[:6]
            
            # Artistas recientes
            artistas = ArtistaMadeInArg.objects.filter(activo=True).order_by('-fecha_creacion')[:6]
            
            # Productos por categoría
            productos_por_categoria = {}
            for categoria, nombre in ProductoMadeInArg.CATEGORIA_CHOICES:
                productos = ProductoMadeInArg.objects.filter(
                    categoria=categoria, 
                    activo=True,
                    tienda__activa=True
                ).select_related('tienda').order_by('-fecha_creacion')[:8]
                
                productos_por_categoria[categoria] = {
                    'nombre': nombre,
                    'productos': ProductoMadeInArgListSerializer(productos, many=True).data
                }
            
            # Estadísticas
            stats = get_madeinarg_stats()
            
            return Response({
                'tiendas_destacadas': TiendaMadeInArgListSerializer(tiendas, many=True).data,
                'artistas_recientes': ArtistaMadeInArgListSerializer(artistas, many=True).data,
                'productos_por_categoria': productos_por_categoria,
                'estadisticas': stats
            })
        
        except Exception as e:
            return Response(
                {'error': f'Error al obtener resumen: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def categoria(self, request):
        """Retorna contenido de una categoría específica - MEJORADO PARA FILTRADO CORRECTO"""
        categoria = request.query_params.get('categoria')
        limit = int(request.query_params.get('limit', 20))
        
        if not categoria:
            return Response(
                {'error': 'Se requiere el parámetro categoria'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if categoria == 'otro':
            # Retornar artistas
            artistas = ArtistaMadeInArg.objects.filter(activo=True).order_by('-fecha_creacion')[:limit]
            return Response({
                'categoria': 'otro',
                'tipo': 'artistas',
                'nombre': 'Otro (Artistas)',
                'contenido': ArtistaMadeInArgListSerializer(artistas, many=True).data
            })
        elif categoria in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
            # Retornar tiendas que tienen productos de esta categoría CON CONTEO CORRECTO
            tiendas_con_productos = TiendaMadeInArg.objects.filter(
                activa=True,
                productos__categoria=categoria,
                productos__activo=True
            ).distinct().annotate(
                num_productos_categoria=Count('productos', filter=Q(
                    productos__categoria=categoria,
                    productos__activo=True
                ))
            ).order_by('-num_productos_categoria')[:limit]
            
            # Agregar el conteo de productos específicos de la categoría a cada tienda
            tiendas_data = []
            for tienda in tiendas_con_productos:
                tienda_serialized = TiendaMadeInArgListSerializer(tienda).data
                tienda_serialized['productos_categoria'] = tienda.num_productos_categoria
                tiendas_data.append(tienda_serialized)
            
            return Response({
                'categoria': categoria,
                'tipo': 'tiendas',
                'nombre': dict(ProductoMadeInArg.CATEGORIA_CHOICES)[categoria],
                'contenido': tiendas_data
            })
        else:
            return Response(
                {'error': 'Categoría no válida'}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Retorna estadísticas completas de MadeInArg"""
        try:
            stats = get_madeinarg_stats()
            return Response(stats)
        except Exception as e:
            return Response(
                {'error': f'Error al obtener estadísticas: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        """Búsqueda global en MadeInArg"""
        query = request.query_params.get('q', '').strip()
        categoria_filtro = request.query_params.get('categoria')  # NUEVO FILTRO
        
        if not query:
            return Response(
                {'error': 'Se requiere el parámetro q'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Buscar en tiendas
            tiendas_query = Q(titulo__icontains=query) | Q(subtitulo__icontains=query) | Q(descripcion__icontains=query)
            tiendas = TiendaMadeInArg.objects.filter(tiendas_query, activa=True)
            
            # Si hay filtro de categoría, solo tiendas que tengan productos de esa categoría
            if categoria_filtro and categoria_filtro in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
                tiendas = tiendas.filter(
                    productos__categoria=categoria_filtro,
                    productos__activo=True
                ).distinct()
            
            tiendas = tiendas[:10]
            
            # Buscar en productos
            productos_query = Q(nombre__icontains=query) | Q(descripcion__icontains=query)
            productos = ProductoMadeInArg.objects.filter(
                productos_query,
                activo=True,
                tienda__activa=True
            ).select_related('tienda')
            
            # Filtrar productos por categoría si se especifica
            if categoria_filtro and categoria_filtro in dict(ProductoMadeInArg.CATEGORIA_CHOICES):
                productos = productos.filter(categoria=categoria_filtro)
            
            productos = productos[:10]
            
            # Buscar en artistas
            artistas_query = Q(titulo__icontains=query) | Q(subtitulo__icontains=query) | Q(descripcion__icontains=query)
            artistas = ArtistaMadeInArg.objects.filter(artistas_query, activo=True)[:10]
            
            # Si se filtra por categoría de productos, no mostrar artistas
            if categoria_filtro and categoria_filtro != 'otro':
                artistas = []
            elif categoria_filtro == 'otro':
                # Solo artistas si se filtra por "otro"
                tiendas = []
                productos = []
            
            return Response({
                'query': query,
                'categoria_filtro': categoria_filtro,
                'tiendas': TiendaMadeInArgListSerializer(tiendas, many=True).data,
                'productos': ProductoMadeInArgListSerializer(productos, many=True).data,
                'artistas': ArtistaMadeInArgListSerializer(artistas, many=True).data
            })
        
        except Exception as e:
            return Response(
                {'error': f'Error en búsqueda: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ==================== FUNCIONES API ADICIONALES ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_image(request):
    """Función standalone para subida de imágenes"""
    if 'image' not in request.FILES:
        return Response(
            {'error': 'No se encontró archivo de imagen'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    image = request.FILES['image']
    
    # Validar tipo de archivo
    allowed_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
    if not image.name.lower().endswith(allowed_extensions):
        return Response({
            'error': f'Tipo de archivo no soportado. Formatos permitidos: {", ".join(allowed_extensions)}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validar tamaño de archivo (opcional - ej: 5MB max)
    max_size = 5 * 1024 * 1024  # 5MB
    if image.size > max_size:
        return Response({
            'error': 'El archivo es demasiado grande. Tamaño máximo: 5MB'
        }, status=status.HTTP_400_BAD_REQUEST)

    uploaded_url = upload_to_imgbb(image)

    if uploaded_url:
        return Response({
            'success': True, 
            'url': uploaded_url,
            'message': 'Imagen subida exitosamente'
        })
    else:
        return Response({
            'error': 'Error al subir la imagen'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==================== VIEWSETS AUXILIARES ====================

class TrabajadorViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de trabajadores"""
    queryset = Trabajador.objects.select_related('user', 'user_profile')
    serializer_class = TrabajadorSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated()]  # Solo puede editar su propio perfil
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = self.queryset.all()
        
        # Los usuarios solo pueden ver su propio perfil a menos que sean admin
        if not self.request.user.is_staff:
            try:
                trabajador = Trabajador.objects.get(user=self.request.user)
                queryset = queryset.filter(id=trabajador.id)
            except Trabajador.DoesNotExist:
                queryset = queryset.none()
        
        return queryset

    def perform_update(self, serializer):
        """Solo permitir actualizar el propio perfil"""
        if not self.request.user.is_staff:
            try:
                trabajador = Trabajador.objects.get(user=self.request.user)
                if serializer.instance.id != trabajador.id:
                    raise PermissionDenied("No puedes editar el perfil de otro trabajador")
            except Trabajador.DoesNotExist:
                raise PermissionDenied("No tienes un perfil de trabajador")
        
        serializer.save()


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de perfiles de usuario"""
    queryset = UserProfile.objects.select_related('user')
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Los usuarios solo pueden ver su propio perfil
        if self.request.user.is_staff:
            return self.queryset.all()
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Asignar automáticamente el usuario actual
        serializer.save(user=self.request.user)


class EstadoPublicacionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet de solo lectura para estados de publicación"""
    queryset = EstadoPublicacion.objects.all()
    serializer_class = EstadoPublicacionSerializer
    permission_classes = [IsAuthenticated]


# ==================== VIEWS DE AUTENTICACIÓN ====================

class RegisterView(APIView):
    """Vista para registro de usuarios"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                # Crear perfil de usuario automáticamente
                UserProfile.objects.create(
                    user=user,
                    nombre=user.first_name or '',
                    apellido=user.last_name or '',
                    es_trabajador=False
                )
                
                # Generar tokens
                refresh = RefreshToken.for_user(user)
                return Response({
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'user': UserSerializer(user).data
                }, status=status.HTTP_201_CREATED)
            
            except Exception as e:
                return Response(
                    {'error': f'Error al crear usuario: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """Vista para inicio de sesión"""
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Se requieren username y password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'error': 'Credenciales inválidas'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'Usuario inactivo'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        refresh = RefreshToken.for_user(user)
        
        # Verificar si el usuario es un trabajador
        try:
            trabajador = Trabajador.objects.get(user=user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_type': 'trabajador',
                'trabajador': TrabajadorSerializer(trabajador).data
            })
        except Trabajador.DoesNotExist:
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user_type': 'usuario',
                'user': UserSerializer(user).data
            })


class CurrentUserView(APIView):
    """Vista para obtener información del usuario actual"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        try:
            trabajador = Trabajador.objects.get(user=user)
            return Response({
                'isWorker': True,
                'user_type': 'trabajador',
                **TrabajadorSerializer(trabajador).data
            })
        except Trabajador.DoesNotExist:
            try:
                profile = UserProfile.objects.get(user=user)
                return Response({
                    'isWorker': False,
                    'user_type': 'usuario',
                    'profile': UserProfileSerializer(profile).data,
                    **UserSerializer(user).data
                })
            except UserProfile.DoesNotExist:
                # Crear perfil si no existe
                profile = UserProfile.objects.create(
                    user=user,
                    nombre=user.first_name or '',
                    apellido=user.last_name or '',
                    es_trabajador=False
                )
                return Response({
                    'isWorker': False,
                    'user_type': 'usuario',
                    'profile': UserProfileSerializer(profile).data,
                    **UserSerializer(user).data
                })


# ==================== VIEWS PARA RECUPERACIÓN DE CONTRASEÑA ====================

class RequestPasswordResetView(APIView):
    """Vista para solicitar recuperación de contraseña"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RequestPasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            try:
                email = serializer.validated_data['email']
                user = User.objects.get(email=email)
                
                # Eliminar tokens anteriores del usuario
                PasswordResetToken.objects.filter(user=user).delete()
                
                # Crear nuevo token
                token_obj = PasswordResetToken.objects.create(user=user)
                
                # Enviar email (configurar según tu configuración de email)
                subject = "Recuperación de contraseña"
                message = f"""
Hola {user.username},

Tu código de recuperación es: {token_obj.token}

Este código es válido por 24 horas.

Si no solicitaste este cambio, ignora este mensaje.
                """
                
                try:
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [email],
                        fail_silently=False,
                    )
                    
                    return Response({
                        "message": "Se ha enviado un correo con el código de recuperación."
                    }, status=status.HTTP_200_OK)
                
                except Exception as e:
                    return Response({
                        "error": "Error al enviar el correo. Inténtalo más tarde."
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            except Exception as e:
                return Response({
                    "error": "Error interno del servidor"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyTokenView(APIView):
    """Vista para verificar token de recuperación"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = VerifyTokenSerializer(data=request.data)
        if serializer.is_valid():
            return Response(
                {"message": "Token válido."}, 
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    """Vista para resetear contraseña"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            try:
                token = serializer.validated_data['token']
                password = serializer.validated_data['password']
                
                token_obj = PasswordResetToken.objects.get(token=token)
                
                if not token_obj.is_valid():
                    return Response({
                        "error": "Token inválido o expirado"
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Actualizar contraseña
                user = token_obj.user
                user.set_password(password)
                user.save()
                
                # Marcar token como usado
                token_obj.used = True
                token_obj.save()
                
                return Response({
                    "message": "Contraseña actualizada exitosamente."
                }, status=status.HTTP_200_OK)
            
            except PasswordResetToken.DoesNotExist:
                return Response({
                    "error": "Token inválido"
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({
                    "error": "Error interno del servidor"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)





# ==================== VIEWS ADMINISTRATIVAS ====================

class AdminDashboardView(APIView):
    """Vista para el dashboard administrativo"""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            # Estadísticas generales
            stats = {
                'usuarios': {
                    'total': User.objects.count(),
                    'activos': User.objects.filter(is_active=True).count(),
                    'trabajadores': Trabajador.objects.count(),
                },
                'contenido': {
                    'total': Contenido.objects.count(),
                    'publicado': Contenido.objects.filter(estado__nombre_estado='publicado').count(),
                    'borrador': Contenido.objects.filter(estado__nombre_estado='borrador').count(),
                    'por_categoria': {}
                },
                'madeinarg': get_madeinarg_stats(),
                'visitas': {
                    'total_semanal': Contenido.objects.aggregate(
                        total=Sum('contador_visitas')
                    )['total'] or 0,
                    'total_historico': Contenido.objects.aggregate(
                        total=Sum('contador_visitas_total')
                    )['total'] or 0,
                }
            }
            
            # Contenido por categoría
            for categoria, nombre in Contenido.CATEGORIA_CHOICES:
                count = Contenido.objects.filter(categoria=categoria).count()
                stats['contenido']['por_categoria'][categoria] = {
                    'count': count,
                    'nombre': nombre
                }
            
            return Response(stats)
        
        except Exception as e:
            return Response(
                {'error': f'Error al obtener estadísticas: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==================== FUNCIONES DE UTILIDAD ====================

def redirect_to_home(request):
    """Redireccionar a home"""
    return redirect('/home/')


# ==================== VIEWS GENÉRICAS DE SOLO LECTURA ====================

class EstadoPublicacionList(generics.ListAPIView):
    """Lista de estados de publicación"""
    queryset = EstadoPublicacion.objects.all()
    serializer_class = EstadoPublicacionSerializer
    permission_classes = [IsAuthenticated]


class TrabajadorList(generics.ListAPIView):
    """Lista de trabajadores (solo para admin)"""
    queryset = Trabajador.objects.select_related('user')
    serializer_class = TrabajadorSerializer
    permission_classes = [IsAdminUser]


# ==================== VIEWSETS HEREDADOS (MANTENER COMPATIBILIDAD) ====================

class UsuarioViewSet(viewsets.ModelViewSet):
    """ViewSet para Usuario (modelo legacy)"""
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated]


class PublicidadViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de publicidad"""
    queryset = Publicidad.objects.all()
    serializer_class = PublicidadSerializer
    permission_classes = [IsAuthenticated]


class EspacioReferenciaViewSet(viewsets.ModelViewSet):
    """ViewSet para espacios de referencia"""
    queryset = EspacioReferencia.objects.all()
    serializer_class = EspacioReferenciaSerializer
    permission_classes = [IsAuthenticated]


class ImagenLinkViewSet(viewsets.ModelViewSet):
    """ViewSet para links de imagen en MadeInArg"""
    queryset = ImagenLink.objects.all()
    serializer_class = ImagenLinkSerializer
    permission_classes = [IsAuthenticated]

# ==================== FUNCIONES AUXILIARES PARA ESTADÍSTICAS ====================

def get_madeinarg_stats():
    """Retorna estadísticas completas de MadeInArg"""
    try:
        # Estadísticas básicas
        total_tiendas = TiendaMadeInArg.objects.filter(activa=True).count()
        total_productos = ProductoMadeInArg.objects.filter(activo=True, tienda__activa=True).count()
        total_artistas = ArtistaMadeInArg.objects.filter(activo=True).count()
        
        # Productos por categoría
        productos_por_categoria = {}
        for categoria, nombre in ProductoMadeInArg.CATEGORIA_CHOICES:
            count = ProductoMadeInArg.objects.filter(
                categoria=categoria,
                activo=True,
                tienda__activa=True
            ).count()
            productos_por_categoria[categoria] = {
                'nombre': nombre,
                'count': count
            }
        
        # Tiendas con más productos
        tiendas_top = TiendaMadeInArg.objects.filter(activa=True).annotate(
            num_productos=Count('productos', filter=Q(productos__activo=True))
        ).order_by('-num_productos')[:3]
        
        # Productos más recientes
        productos_recientes = ProductoMadeInArg.objects.filter(
            activo=True,
            tienda__activa=True
        ).select_related('tienda').order_by('-fecha_creacion')[:5]
        
        return {
            'totales': {
                'tiendas': total_tiendas,
                'productos': total_productos,
                'artistas': total_artistas
            },
            'productos_por_categoria': productos_por_categoria,
            'tiendas_destacadas': [
                {
                    'titulo': t.titulo,
                    'num_productos': t.num_productos
                } for t in tiendas_top
            ],
            'productos_recientes': ProductoMadeInArgListSerializer(productos_recientes, many=True).data
        }
    
    except Exception as e:
        return {
            'error': f'Error al calcular estadísticas: {str(e)}',
            'totales': {'tiendas': 0, 'productos': 0, 'artistas': 0}
        }
    





# views.py - Agregar estas views a tu archivo existente

from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView


class SuscriptorViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de suscriptores"""
    queryset = Suscriptor.objects.all()
    serializer_class = SuscriptorSerializer
    filter_backends = [filters.OrderingFilter, filters.SearchFilter]
    ordering_fields = ['fecha_suscripcion', 'nombre', 'email']
    ordering = ['-fecha_suscripcion']
    search_fields = ['nombre', 'email']
    
    def get_permissions(self):
        """Permisos personalizados"""
        if self.action in ['suscribirse', 'desuscribirse', 'actualizar_preferencias']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        """Filtrar queryset según parámetros"""
        queryset = self.queryset.all()
        
        # Filtrar por estado activo
        activos = self.request.query_params.get('activos')
        if activos == 'true':
            queryset = queryset.filter(activo=True)
        elif activos == 'false':
            queryset = queryset.filter(activo=False)
        
        # Filtrar por categoría específica
        categoria = self.request.query_params.get('categoria')
        if categoria and categoria in ['editorials', 'issues', 'madeinarg', 'news', 'club_pompa']:
            campo_categoria = f'suscrito_{categoria}'
            queryset = queryset.filter(**{campo_categoria: True})
        
        return queryset
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def suscribirse(self, request):
        """Endpoint público para suscribirse al newsletter"""
        serializer = SuscriptorPublicoSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Verificar si existe un suscriptor inactivo con el mismo email
                email = serializer.validated_data['email']
                suscriptor_existente = Suscriptor.objects.filter(email=email).first()
                
                if suscriptor_existente:
                    if suscriptor_existente.activo:
                        return Response({
                            'error': 'Ya estás suscrito con este email'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        # Reactivar suscripción existente
                        for campo, valor in serializer.validated_data.items():
                            setattr(suscriptor_existente, campo, valor)
                        suscriptor_existente.activo = True
                        suscriptor_existente.fecha_suscripcion = timezone.now()
                        suscriptor_existente.save()
                        
                        return Response({
                            'success': True,
                            'message': f'¡Bienvenido de vuelta, {suscriptor_existente.nombre}! Tu suscripción ha sido reactivada.',
                            'suscriptor_id': suscriptor_existente.id
                        }, status=status.HTTP_200_OK)
                else:
                    # Crear nuevo suscriptor
                    suscriptor = serializer.save()
                    return Response({
                        'success': True,
                        'message': f'¡Gracias por suscribirte, {suscriptor.nombre}! Recibirás notificaciones sobre nuevo contenido.',
                        'suscriptor_id': suscriptor.id,
                        'token_desuscripcion': str(suscriptor.token_desuscripcion)
                    }, status=status.HTTP_201_CREATED)
                    
            except Exception as e:
                return Response({
                    'error': f'Error al procesar suscripción: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def desuscribirse(self, request):
        """Endpoint público para desuscribirse"""
        serializer = DesuscripcionSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                token = serializer.validated_data['token']
                motivo = serializer.validated_data.get('motivo', '')
                
                suscriptor = Suscriptor.objects.get(
                    token_desuscripcion=token,
                    activo=True
                )
                
                # Desactivar suscripción
                suscriptor.activo = False
                suscriptor.save()
                
                # Log del motivo si se proporciona
                if motivo:
                    print(f"Desuscripción - {suscriptor.email}: {motivo}")
                
                return Response({
                    'success': True,
                    'message': f'Te has desuscrito exitosamente, {suscriptor.nombre}. Lamentamos verte partir.'
                })
                
            except Suscriptor.DoesNotExist:
                return Response({
                    'error': 'Token de desuscripción inválido o ya utilizado'
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({
                    'error': f'Error al procesar desuscripción: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def actualizar_preferencias(self, request):
        """Endpoint para actualizar preferencias de suscripción"""
        serializer = ActualizarPreferenciasSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                suscriptor = serializer.suscriptor
                serializer.update(suscriptor, serializer.validated_data)
                
                return Response({
                    'success': True,
                    'message': 'Preferencias actualizadas exitosamente',
                    'preferencias': {
                        'editorials': suscriptor.suscrito_editorials,
                        'issues': suscriptor.suscrito_issues,
                        'madeinarg': suscriptor.suscrito_madeinarg,
                        'news': suscriptor.suscrito_news,
                        'club_pompa': suscriptor.suscrito_club_pompa,
                    }
                })
            except Exception as e:
                return Response({
                    'error': f'Error al actualizar preferencias: {str(e)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def estadisticas(self, request):
        """Estadísticas de suscriptores (solo admin)"""
        try:
            # Estadísticas básicas
            total_suscriptores = Suscriptor.objects.count()
            total_activos = Suscriptor.objects.filter(activo=True).count()
            total_inactivos = total_suscriptores - total_activos
            
            # Nuevos suscriptores
            hace_una_semana = timezone.now() - timedelta(days=7)
            hace_un_mes = timezone.now() - timedelta(days=30)
            
            nuevos_esta_semana = Suscriptor.objects.filter(
                fecha_suscripcion__gte=hace_una_semana
            ).count()
            
            nuevos_este_mes = Suscriptor.objects.filter(
                fecha_suscripcion__gte=hace_un_mes
            ).count()
            
            # Suscripciones por categoría
            suscripciones_por_categoria = {}
            for categoria, nombre in [
                ('editorials', 'Editorials'),
                ('issues', 'Issues'),
                ('madeinarg', 'Made in Argentina'),
                ('news', 'News'),
                ('club_pompa', 'Club Pompa'),
            ]:
                campo = f'suscrito_{categoria}'
                count = Suscriptor.objects.filter(activo=True, **{campo: True}).count()
                suscripciones_por_categoria[categoria] = {
                    'nombre': nombre,
                    'total': count
                }
            
            # Suscripciones por mes (últimos 6 meses)
            suscripciones_por_mes = {}
            for i in range(6):
                fecha_inicio = timezone.now().replace(day=1) - timedelta(days=30*i)
                fecha_fin = (fecha_inicio + timedelta(days=31)).replace(day=1)
                
                count = Suscriptor.objects.filter(
                    fecha_suscripcion__gte=fecha_inicio,
                    fecha_suscripcion__lt=fecha_fin
                ).count()
                
                mes_nombre = fecha_inicio.strftime('%B %Y')
                suscripciones_por_mes[mes_nombre] = count
            
            stats = {
                'total_suscriptores': total_suscriptores,
                'total_activos': total_activos,
                'total_inactivos': total_inactivos,
                'nuevos_esta_semana': nuevos_esta_semana,
                'nuevos_este_mes': nuevos_este_mes,
                'suscripciones_por_categoria': suscripciones_por_categoria,
                'suscripciones_por_mes': suscripciones_por_mes,
            }
            
            return Response(stats)
            
        except Exception as e:
            return Response({
                'error': f'Error al obtener estadísticas: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NewsletterViewSet(viewsets.ModelViewSet):
    """ViewSet para gestión de newsletters (solo admin)"""
    queryset = Newsletter.objects.select_related('contenido', 'contenido__autor')
    serializer_class = NewsletterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['fecha_envio']
    ordering = ['-fecha_envio']
    
    def get_queryset(self):
        """Filtrar newsletters"""
        queryset = self.queryset.all()
        
        # Filtrar por categoría de contenido
        categoria = self.request.query_params.get('categoria')
        if categoria:
            queryset = queryset.filter(contenido__categoria=categoria)
        
        # Filtrar por estado de envío
        exitoso = self.request.query_params.get('exitoso')
        if exitoso == 'true':
            queryset = queryset.filter(enviado_exitosamente=True)
        elif exitoso == 'false':
            queryset = queryset.filter(enviado_exitosamente=False)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def reenviar(self, request, pk=None):
        """Reenviar newsletter a suscriptores que tuvieron error"""
        newsletter = self.get_object()
        
        if newsletter.total_errores == 0:
            return Response({
                'error': 'Este newsletter no tuvo errores en el envío'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Crear nuevo newsletter para el reenvío
            nuevo_newsletter = Newsletter.objects.create(contenido=newsletter.contenido)
            resultado = nuevo_newsletter.enviar_newsletter()
            
            return Response({
                'success': True,
                'message': 'Newsletter reenviado exitosamente',
                'enviados': resultado['enviados'],
                'errores': resultado['errores']
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al reenviar: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def enviar_manual(self, request):
        """Enviar newsletter manualmente para un contenido"""
        contenido_id = request.data.get('contenido_id')
        
        if not contenido_id:
            return Response({
                'error': 'Se requiere contenido_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            contenido = get_object_or_404(Contenido, pk=contenido_id)
            
            # Verificar si ya se envió newsletter para este contenido
            if Newsletter.objects.filter(contenido=contenido).exists():
                return Response({
                    'error': 'Ya se envió newsletter para este contenido'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Crear y enviar newsletter
            newsletter = Newsletter.objects.create(contenido=contenido)
            resultado = newsletter.enviar_newsletter()
            
            return Response({
                'success': True,
                'message': 'Newsletter enviado exitosamente',
                'newsletter_id': newsletter.id,
                'enviados': resultado['enviados'],
                'errores': resultado['errores']
            })
            
        except Exception as e:
            return Response({
                'error': f'Error al enviar newsletter: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NewsletterPublicoView(APIView):
    """Views públicas para newsletter (sin autenticación)"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Información pública sobre el newsletter"""
        try:
            stats = {
                'total_suscriptores': Suscriptor.objects.filter(activo=True).count(),
                'categorias_disponibles': [
                    {'key': 'editorials', 'nombre': 'Editorials'},
                    {'key': 'issues', 'nombre': 'Issues'}, 
                    {'key': 'madeinarg', 'nombre': 'Made in Argentina'},
                    {'key': 'news', 'nombre': 'News'},
                    {'key': 'club_pompa', 'nombre': 'Club Pompa'},
                ],
                'mensaje': 'Únete a nuestro newsletter y mantente informado sobre todo el contenido de Diario El Gobierno'
            }
            return Response(stats)
        except Exception as e:
            return Response({
                'error': f'Error al obtener información: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)