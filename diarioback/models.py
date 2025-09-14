import os
import base64
import time
import random
import string
import uuid
import requests
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count, Max

def validate_positive(value):
    if value <= 0:
        raise ValidationError('El valor debe ser positivo.')


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', null=True, blank=True)
    nombre = models.CharField(max_length=255)
    apellido = models.CharField(max_length=255)
    foto_perfil = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    descripcion_usuario = models.TextField(blank=True, null=True)
    es_trabajador = models.BooleanField(default=False)


class Trabajador(models.Model):
    DEFAULT_FOTO_PERFIL_URL = 'https://example.com/default-profile.png'
    user_profile = models.OneToOneField(UserProfile, on_delete=models.CASCADE, null=True, blank=True)
    id = models.AutoField(primary_key=True)
    correo = models.EmailField(unique=False)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    foto_perfil = models.URLField(blank=True, null=True)
    foto_perfil_local = models.ImageField(upload_to='perfil/', blank=True, null=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    @property
    def descripcion_usuario(self):
        if self.user_profile:
            return self.user_profile.descripcion_usuario
        return None

    @descripcion_usuario.setter
    def descripcion_usuario(self, value):
        if self.user_profile:
            self.user_profile.descripcion_usuario = value
            self.user_profile.save()

    def puede_publicar(self):
        return True
    
    def puede_editar(self):
        return True
    
    def puede_eliminar(self):
        return True
    
    def puede_asignar_roles(self):
        return False

    def save(self, *args, **kwargs):
        old_instance = None
        if self.pk:
            try:
                old_instance = Trabajador.objects.get(pk=self.pk)
            except Trabajador.DoesNotExist:
                pass

        if not self.user_profile:
            self.user_profile = UserProfile.objects.create(
                nombre=self.nombre,
                apellido=self.apellido
            )

        self._handle_image('foto_perfil', 'foto_perfil_local')

        if not self.foto_perfil and not self.foto_perfil_local:
            self.foto_perfil = self.DEFAULT_FOTO_PERFIL_URL

        super().save(*args, **kwargs)

        if old_instance:
            self._delete_old_image(old_instance, 'foto_perfil')

    def _handle_image(self, image_field, image_local_field):
        image_local = getattr(self, image_local_field)
        image_url = getattr(self, image_field)

        if image_local and os.path.exists(image_local.path):
            uploaded_image_url = upload_to_imgbb(image_local.path)
            setattr(self, image_field, uploaded_image_url)
        elif image_url:
            setattr(self, image_field, image_url)
        else:
            setattr(self, image_field, self.DEFAULT_FOTO_PERFIL_URL)

    def _delete_old_image(self, old_instance, field_name):
        old_image_url = getattr(old_instance, field_name)
        new_image_url = getattr(self, field_name)
        if old_image_url and old_image_url != new_image_url:
            delete_from_imgbb(old_image_url)

    def get_foto_perfil(self):
        return self.foto_perfil_local.url if self.foto_perfil_local else self.foto_perfil or self.DEFAULT_FOTO_PERFIL_URL

    def __str__(self):
        return f'{self.nombre} {self.apellido}'


# Funciones para subir imágenes a ImgBB
IMGBB_API_KEY = 'a315981b1bce71916fb736816e14d90a'
IMGBB_UPLOAD_URL = 'https://api.imgbb.com/1/upload'

def upload_to_imgbb(image):
    """Sube una imagen a ImgBB y devuelve la URL"""
    try:
        if isinstance(image, InMemoryUploadedFile):
            image_data = image.read()
        elif isinstance(image, str) and os.path.isfile(image):
            with open(image, 'rb') as image_file:
                image_data = image_file.read()
        elif hasattr(image, 'path') and os.path.isfile(image.path):
            with open(image.path, 'rb') as image_file:
                image_data = image_file.read()
        else:
            image_data = image.read() if hasattr(image, 'read') else image

        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        payload = {
            'key': IMGBB_API_KEY,
            'image': image_base64
        }
        
        response = requests.post(IMGBB_UPLOAD_URL, data=payload)
        
        if response.status_code == 429:
            print("Error 429: Demasiadas solicitudes, esperando antes de reintentar...")
            time.sleep(60)
            return upload_to_imgbb(image)
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                return response_data['data']['url']
            else:
                error_message = response_data.get('error', {}).get('message', 'Error desconocido')
                print(f"Error al subir imagen a ImgBB: {error_message}")
        else:
            print(f"Error HTTP {response.status_code} al subir imagen a ImgBB")
            print(f"Respuesta: {response.text}")
        
    except Exception as e:
        print(f"Excepción al subir imagen a ImgBB: {str(e)}")
    
    return None

def delete_from_imgbb(image_url_or_id):
    """ImgBB no permite eliminar imágenes via API"""
    print(f"Advertencia: ImgBB no permite eliminar imágenes via API. Imagen: {image_url_or_id}")
    return True


# ESTADOS DE PUBLICACIÓN
class EstadoPublicacion(models.Model):
    BORRADOR = 'borrador'
    EN_PAPELERA = 'en_papelera'
    PUBLICADO = 'publicado'
    LISTO_PARA_EDITAR = 'listo_para_editar'

    ESTADO_CHOICES = [
        (BORRADOR, 'Borrador'),
        (EN_PAPELERA, 'En Papelera'),
        (PUBLICADO, 'Publicado'),
        (LISTO_PARA_EDITAR, 'Listo para editar'),
    ]

    nombre_estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default=BORRADOR,
    )

    def __str__(self):
        return self.get_nombre_estado_display()


# MODELO BASE PARA CONTENIDO
class ContenidoBase(models.Model):
    """Modelo base abstracto para todo el contenido"""
    CATEGORIA_CHOICES = [
        ('editorials', 'Editorials'),
        ('issues', 'Issues'),
        ('madeinarg', 'MadeInArg'),
        ('news', 'News'),
        ('club_pompa', 'Club Pompa'),
    ]
    
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    titulo = models.CharField(max_length=500)
    autor = models.ForeignKey('Trabajador', on_delete=models.CASCADE, related_name='contenidos')
    fecha_publicacion = models.DateField()
    estado = models.ForeignKey('EstadoPublicacion', on_delete=models.SET_NULL, null=True)
    
    # Campos de imágenes (hasta 30 por contenido)
    imagen_1 = models.URLField(blank=True, null=True)
    imagen_1_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_2 = models.URLField(blank=True, null=True)
    imagen_2_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_3 = models.URLField(blank=True, null=True)
    imagen_3_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_4 = models.URLField(blank=True, null=True)
    imagen_4_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_5 = models.URLField(blank=True, null=True)
    imagen_5_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_6 = models.URLField(blank=True, null=True)
    imagen_6_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_7 = models.URLField(blank=True, null=True)
    imagen_7_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_8 = models.URLField(blank=True, null=True)
    imagen_8_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_9 = models.URLField(blank=True, null=True)
    imagen_9_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_10 = models.URLField(blank=True, null=True)
    imagen_10_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_11 = models.URLField(blank=True, null=True)
    imagen_11_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_12 = models.URLField(blank=True, null=True)
    imagen_12_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_13 = models.URLField(blank=True, null=True)
    imagen_13_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_14 = models.URLField(blank=True, null=True)
    imagen_14_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_15 = models.URLField(blank=True, null=True)
    imagen_15_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_16 = models.URLField(blank=True, null=True)
    imagen_16_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_17 = models.URLField(blank=True, null=True)
    imagen_17_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_18 = models.URLField(blank=True, null=True)
    imagen_18_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_19 = models.URLField(blank=True, null=True)
    imagen_19_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_20 = models.URLField(blank=True, null=True)
    imagen_20_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_21 = models.URLField(blank=True, null=True)
    imagen_21_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_22 = models.URLField(blank=True, null=True)
    imagen_22_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_23 = models.URLField(blank=True, null=True)
    imagen_23_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_24 = models.URLField(blank=True, null=True)
    imagen_24_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_25 = models.URLField(blank=True, null=True)
    imagen_25_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_26 = models.URLField(blank=True, null=True)
    imagen_26_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_27 = models.URLField(blank=True, null=True)
    imagen_27_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_28 = models.URLField(blank=True, null=True)
    imagen_28_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_29 = models.URLField(blank=True, null=True)
    imagen_29_local = models.ImageField(upload_to='images/', blank=True, null=True)
    imagen_30 = models.URLField(blank=True, null=True)
    imagen_30_local = models.ImageField(upload_to='images/', blank=True, null=True)
    
    # Contadores de visitas
    contador_visitas = models.PositiveIntegerField(default=0)
    contador_visitas_total = models.PositiveIntegerField(default=0)
    ultima_actualizacion_contador = models.DateTimeField(default=timezone.now)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        images_updated = self._process_images()
        if images_updated:
            super().save()
    
    def _process_images(self):
        """Procesa todas las imágenes, sube a ImgBB y actualiza URLs"""
        images_updated = False
        
        for i in range(1, 31):
            local_field_name = f'imagen_{i}_local'
            url_field_name = f'imagen_{i}'
            
            local_field = getattr(self, local_field_name)
            if local_field and hasattr(local_field, 'file'):
                imgur_url = upload_to_imgbb(local_field)
                if imgur_url:
                    setattr(self, url_field_name, imgur_url)
                    setattr(self, local_field_name, None)
                    images_updated = True
                    print(f"Imagen {i} subida a ImgBB: {imgur_url}")
        
        return images_updated
    
    def get_image_urls(self):
        """Retorna una lista de todas las URLs de imágenes disponibles"""
        image_urls = []
        for i in range(1, 31):
            image_field = getattr(self, f'imagen_{i}')
            if image_field:
                image_urls.append(image_field)
        return image_urls


# MODELO PARA ESPACIOS DE REFERENCIA
class EspacioReferencia(models.Model):
    """Espacios de referencia para mostrar links con texto personalizado"""
    contenido = models.ForeignKey('Contenido', on_delete=models.CASCADE, related_name='espacios_referencia')
    texto_descriptivo = models.CharField(max_length=200, help_text="Texto descriptivo (ej: 'Photographer', 'Fashion Stylist')", blank=True, null=True)
    texto_mostrar = models.CharField(max_length=200, help_text="Texto que se mostrará como link (ej: 'FFLORENC')")
    url = models.URLField(help_text="URL a la que debe dirigir el link")
    orden = models.PositiveIntegerField(default=1, help_text="Orden de aparición")
    
    class Meta:
        ordering = ['orden']
        verbose_name = "Espacio de Referencia"
        verbose_name_plural = "Espacios de Referencia"
    
    def __str__(self):
        if self.texto_descriptivo:
            return f"{self.texto_descriptivo}: {self.texto_mostrar} -> {self.url}"
        return f"{self.texto_mostrar} -> {self.url}"


# DEFINIR SUBCATEGORÍAS FUERA DE LA CLASE
SUBCATEGORIAS_MADEINARG = [
    ('calzado', 'Calzado'),
    ('indumentaria', 'Indumentaria'),
    ('accesorios', 'Accesorios'),
    ('otro', 'Otro (Artistas)'),
]


# MODELO PRINCIPAL DE CONTENIDO
class Contenido(ContenidoBase):
    """Modelo principal que maneja todas las categorías de contenido"""
    
    # Campos específicos para ISSUES
    numero_issue = models.PositiveIntegerField(null=True, blank=True, help_text="Solo para Issues")
    nombre_modelo = models.CharField(max_length=200, blank=True, null=True, help_text="Solo para Issues")
    subtitulo_issue = models.TextField(blank=True, null=True, help_text="Solo para Issues")
    frase_final_issue = models.TextField(blank=True, null=True, help_text="Solo para Issues")
    video_youtube_issue = models.URLField(blank=True, null=True, help_text="Solo para Issues")
    
    # Imágenes de backstage para Issues (30 adicionales)
    backstage_1 = models.URLField(blank=True, null=True)
    backstage_1_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_2 = models.URLField(blank=True, null=True)
    backstage_2_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_3 = models.URLField(blank=True, null=True)
    backstage_3_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_4 = models.URLField(blank=True, null=True)
    backstage_4_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_5 = models.URLField(blank=True, null=True)
    backstage_5_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_6 = models.URLField(blank=True, null=True)
    backstage_6_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_7 = models.URLField(blank=True, null=True)
    backstage_7_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_8 = models.URLField(blank=True, null=True)
    backstage_8_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_9 = models.URLField(blank=True, null=True)
    backstage_9_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_10 = models.URLField(blank=True, null=True)
    backstage_10_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_11 = models.URLField(blank=True, null=True)
    backstage_11_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_12 = models.URLField(blank=True, null=True)
    backstage_12_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_13 = models.URLField(blank=True, null=True)
    backstage_13_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_14 = models.URLField(blank=True, null=True)
    backstage_14_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_15 = models.URLField(blank=True, null=True)
    backstage_15_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_16 = models.URLField(blank=True, null=True)
    backstage_16_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_17 = models.URLField(blank=True, null=True)
    backstage_17_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_18 = models.URLField(blank=True, null=True)
    backstage_18_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_19 = models.URLField(blank=True, null=True)
    backstage_19_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_20 = models.URLField(blank=True, null=True)
    backstage_20_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_21 = models.URLField(blank=True, null=True)
    backstage_21_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_22 = models.URLField(blank=True, null=True)
    backstage_22_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_23 = models.URLField(blank=True, null=True)
    backstage_23_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_24 = models.URLField(blank=True, null=True)
    backstage_24_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_25 = models.URLField(blank=True, null=True)
    backstage_25_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_26 = models.URLField(blank=True, null=True)
    backstage_26_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_27 = models.URLField(blank=True, null=True)
    backstage_27_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_28 = models.URLField(blank=True, null=True)
    backstage_28_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_29 = models.URLField(blank=True, null=True)
    backstage_29_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    backstage_30 = models.URLField(blank=True, null=True)
    backstage_30_local = models.ImageField(upload_to='backstage/', blank=True, null=True)
    
    # Campos específicos para MADEINARG
    subcategoria_madeinarg = models.CharField(max_length=20, choices=SUBCATEGORIAS_MADEINARG, blank=True, null=True)
    subtitulo_madeinarg = models.TextField(blank=True, null=True, help_text="Solo para MadeInArg")
    tags_marcas = models.TextField(blank=True, null=True, help_text="Tags de marcas separados por comas")
    
    # Campos específicos para NEWS
    subtitulos_news = models.TextField(blank=True, null=True, help_text="Múltiples subtítulos para News")
    contenido_news = models.TextField(blank=True, null=True, help_text="Contenido de texto para News")
    video_youtube_news = models.URLField(blank=True, null=True, help_text="Video de YouTube para News")
    
    def save(self, *args, **kwargs):
        if self.categoria == 'issues' and not self.numero_issue:
            ultimo_issue = Contenido.objects.filter(categoria='issues').aggregate(
                Max('numero_issue')
            )['numero_issue__max']
            self.numero_issue = (ultimo_issue or 0) + 1
        
        super().save(*args, **kwargs)
        
        if self.categoria == 'issues':
            backstage_updated = self._process_backstage_images()
            if backstage_updated:
                super().save()
    
    def _process_backstage_images(self):
        """Procesa las imágenes de backstage para Issues"""
        images_updated = False
        
        for i in range(1, 31):
            local_field_name = f'backstage_{i}_local'
            url_field_name = f'backstage_{i}'
            
            local_field = getattr(self, local_field_name)
            if local_field and hasattr(local_field, 'file'):
                imgbb_url = upload_to_imgbb(local_field)
                if imgbb_url:
                    setattr(self, url_field_name, imgbb_url)
                    setattr(self, local_field_name, None)
                    images_updated = True
                    print(f"Backstage {i} subida a ImgBB: {imgbb_url}")
        
        return images_updated
    
    def get_backstage_urls(self):
        """Retorna una lista de todas las URLs de backstage disponibles"""
        backstage_urls = []
        for i in range(1, 31):
            backstage_field = getattr(self, f'backstage_{i}')
            if backstage_field:
                backstage_urls.append(backstage_field)
        return backstage_urls
    
    def get_tags_marcas_list(self):
        """Convierte los tags de marcas en una lista"""
        if self.tags_marcas:
            return [tag.strip() for tag in self.tags_marcas.split(',') if tag.strip()]
        return []
    
    def __str__(self):
        categoria_display = dict(self.CATEGORIA_CHOICES).get(self.categoria, self.categoria)
        if self.categoria == 'issues' and self.numero_issue:
            return f"{categoria_display} #{self.numero_issue}: {self.titulo}"
        return f"{categoria_display}: {self.titulo}"
    
    class Meta:
        ordering = ['-fecha_publicacion']
        verbose_name = "Contenido"
        verbose_name_plural = "Contenidos"


# MODELO PARA LINKS DE IMAGEN EN MADEINARG
class ImagenLink(models.Model):
    """Links asociados a cada imagen en MadeInArg"""
    contenido = models.ForeignKey(Contenido, on_delete=models.CASCADE, related_name='imagen_links')
    numero_imagen = models.PositiveIntegerField(help_text="Número de imagen (1-30)")
    url_tienda = models.URLField(help_text="Link a la tienda/Instagram/etc")
    texto_descripcion = models.CharField(max_length=200, blank=True, help_text="Descripción opcional del producto")
    
    class Meta:
        unique_together = ['contenido', 'numero_imagen']
        ordering = ['numero_imagen']
    
    def __str__(self):
        return f"Imagen {self.numero_imagen} -> {self.url_tienda}"


# NUEVOS MODELOS PARA MADEINARG
class TiendaMadeInArg(models.Model):
    """Modelo para las tiendas en MadeInArg"""
    titulo = models.CharField(max_length=200, help_text="Nombre de la tienda")
    subtitulo = models.CharField(max_length=300, help_text="Descripción corta de la tienda")
    
    imagen_portada = models.URLField(blank=True, null=True)
    imagen_portada_local = models.ImageField(upload_to='tiendas/', blank=True, null=True)
    
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción detallada de la tienda")
    link_instagram = models.URLField(blank=True, null=True, help_text="Link de Instagram de la tienda")
    link_sitio_web = models.URLField(blank=True, null=True, help_text="Sitio web de la tienda")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activa = models.BooleanField(default=True, help_text="Si la tienda está activa")
    
    creado_por = models.ForeignKey('Trabajador', on_delete=models.CASCADE, related_name='tiendas_creadas')
    
    def save(self, *args, **kwargs):
        if self.imagen_portada_local and hasattr(self.imagen_portada_local, 'file'):
            uploaded_url = upload_to_imgbb(self.imagen_portada_local)
            if uploaded_url:
                self.imagen_portada = uploaded_url
                self.imagen_portada_local = None
        
        super().save(*args, **kwargs)
    
    def get_imagen_portada(self):
        """Retorna la URL de la imagen de portada"""
        return self.imagen_portada or '/static/img/default-tienda.jpg'
    
    def get_productos_por_categoria(self, categoria):
        """Retorna productos de una categoría específica"""
        return self.productos.filter(categoria=categoria, activo=True)
    
    def get_total_productos(self):
        """Retorna el total de productos activos"""
        return self.productos.filter(activo=True).count()
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Tienda MadeInArg"
        verbose_name_plural = "Tiendas MadeInArg"
    
    def __str__(self):
        return self.titulo


class ProductoMadeInArg(models.Model):
    """Modelo para productos dentro de las tiendas"""
    
    CATEGORIA_CHOICES = [
        ('calzado', 'Calzado'),
        ('indumentaria', 'Indumentaria'),
        ('accesorios', 'Accesorios'),
    ]
    
    tienda = models.ForeignKey(TiendaMadeInArg, on_delete=models.CASCADE, related_name='productos')
    nombre = models.CharField(max_length=200, help_text="Nombre del producto")
    descripcion = models.TextField(blank=True, null=True, help_text="Descripción del producto")
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    
    imagen = models.URLField(blank=True, null=True)
    imagen_local = models.ImageField(upload_to='productos/', blank=True, null=True)
    
    link_producto = models.URLField(help_text="Link al producto (tienda online, Instagram, etc.)")
    
    precio = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Precio del producto")
    moneda = models.CharField(max_length=10, default='ARS', help_text="Moneda del precio")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=1, help_text="Orden de aparición en la tienda")
    
    def save(self, *args, **kwargs):
        if self.imagen_local and hasattr(self.imagen_local, 'file'):
            uploaded_url = upload_to_imgbb(self.imagen_local)
            if uploaded_url:
                self.imagen = uploaded_url
                self.imagen_local = None
        
        super().save(*args, **kwargs)
    
    def get_imagen(self):
        """Retorna la URL de la imagen del producto"""
        return self.imagen or '/static/img/default-producto.jpg'
    
    def get_precio_formatted(self):
        """Retorna el precio formateado"""
        if self.precio:
            return f"{self.moneda} ${self.precio:,.2f}"
        return None
    
    class Meta:
        ordering = ['orden', '-fecha_creacion']
        verbose_name = "Producto MadeInArg"
        verbose_name_plural = "Productos MadeInArg"
    
    def __str__(self):
        return f"{self.tienda.titulo} - {self.nombre}"


class ArtistaMadeInArg(models.Model):
    """Modelo para la sección 'Otro' - Promoción de artistas"""
    titulo = models.CharField(max_length=200, help_text="Nombre del artista o proyecto")
    subtitulo = models.CharField(max_length=300, help_text="Descripción corta del artista")
    descripcion = models.TextField(help_text="Descripción detallada del artista")
    
    video_youtube = models.URLField(blank=True, null=True, help_text="URL del video de YouTube")
    
    # Galería de imágenes (hasta 20 imágenes)
    imagen_1 = models.URLField(blank=True, null=True)
    imagen_1_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_2 = models.URLField(blank=True, null=True)
    imagen_2_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_3 = models.URLField(blank=True, null=True)
    imagen_3_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_4 = models.URLField(blank=True, null=True)
    imagen_4_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_5 = models.URLField(blank=True, null=True)
    imagen_5_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_6 = models.URLField(blank=True, null=True)
    imagen_6_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_7 = models.URLField(blank=True, null=True)
    imagen_7_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_8 = models.URLField(blank=True, null=True)
    imagen_8_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_9 = models.URLField(blank=True, null=True)
    imagen_9_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_10 = models.URLField(blank=True, null=True)
    imagen_10_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_11 = models.URLField(blank=True, null=True)
    imagen_11_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_12 = models.URLField(blank=True, null=True)
    imagen_12_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_13 = models.URLField(blank=True, null=True)
    imagen_13_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_14 = models.URLField(blank=True, null=True)
    imagen_14_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_15 = models.URLField(blank=True, null=True)
    imagen_15_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_16 = models.URLField(blank=True, null=True)
    imagen_16_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_17 = models.URLField(blank=True, null=True)
    imagen_17_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_18 = models.URLField(blank=True, null=True)
    imagen_18_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_19 = models.URLField(blank=True, null=True)
    imagen_19_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    imagen_20 = models.URLField(blank=True, null=True)
    imagen_20_local = models.ImageField(upload_to='artistas/', blank=True, null=True)
    
    # Links sociales
    link_instagram = models.URLField(blank=True, null=True, help_text="Instagram del artista")
    link_sitio_web = models.URLField(blank=True, null=True, help_text="Sitio web del artista")
    link_spotify = models.URLField(blank=True, null=True, help_text="Spotify del artista")
    link_otros = models.URLField(blank=True, null=True, help_text="Otro link relevante")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    creado_por = models.ForeignKey('Trabajador', on_delete=models.CASCADE, related_name='artistas_creados')
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        images_updated = self._process_images()
        if images_updated:
            super().save()
    
    def _process_images(self):
        """Procesa todas las imágenes de la galería"""
        images_updated = False
        
        for i in range(1, 21):
            local_field_name = f'imagen_{i}_local'
            url_field_name = f'imagen_{i}'
            
            local_field = getattr(self, local_field_name)
            if local_field and hasattr(local_field, 'file'):
                uploaded_url = upload_to_imgbb(local_field)
                if uploaded_url:
                    setattr(self, url_field_name, uploaded_url)
                    setattr(self, local_field_name, None)
                    images_updated = True
        
        return images_updated
    
    def get_imagenes_galeria(self):
        """Retorna lista de URLs de imágenes de la galería"""
        imagenes = []
        for i in range(1, 21):
            imagen = getattr(self, f'imagen_{i}')
            if imagen:
                imagenes.append(imagen)
        return imagenes
    
    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Artista MadeInArg"
        verbose_name_plural = "Artistas MadeInArg"
    
    def __str__(self):
        return self.titulo


# MODELO PARA TOKENS DE RECUPERACIÓN DE CONTRASEÑA
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=6, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
            
        super().save(*args, **kwargs)
    
    def is_valid(self):
        return not self.used and timezone.now() <= self.expires_at
    
    @staticmethod
    def generate_token():
        digits = string.digits
        token = ''.join(random.choice(digits) for _ in range(6))
        
        while PasswordResetToken.objects.filter(token=token).exists():
            token = ''.join(random.choice(digits) for _ in range(6))
            
        return token


# MANAGERS PERSONALIZADOS
class ContenidoManager(models.Manager):
    def editorials(self):
        return self.filter(categoria='editorials')
    
    def issues(self):
        return self.filter(categoria='issues')
    
    def madeinarg(self):
        return self.filter(categoria='madeinarg')
    
    def news(self):
        return self.filter(categoria='news')
    
    def club_pompa(self):
        return self.filter(categoria='club_pompa')
    
    def publicados(self):
        return self.filter(estado__nombre_estado='publicado')
    
    def por_categoria_y_publicados(self, categoria):
        return self.filter(categoria=categoria, estado__nombre_estado='publicado')

# Agregar el manager al modelo Contenido
Contenido.add_to_class('objects', ContenidoManager())


# MODELO DE VISITAS
class ContenidoVisita(models.Model):
    contenido = models.ForeignKey(Contenido, on_delete=models.CASCADE, related_name='visitas')
    fecha = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['contenido']),
        ]


# MODELOS MANTENIDOS DEL CÓDIGO ORIGINAL
class Usuario(models.Model):
    correo = models.EmailField(unique=True)
    nombre_usuario = models.CharField(max_length=100)
    contraseña = models.CharField(max_length=128)
    foto_perfil = models.URLField()
    esta_subscrito = models.BooleanField(default=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.nombre_usuario


class Publicidad(models.Model):
    tipo_anuncio = models.CharField(max_length=50)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    url_destino = models.URLField()
    impresiones = models.IntegerField()
    clics = models.IntegerField()
    contenido = models.ForeignKey(Contenido, on_delete=models.CASCADE, related_name='publicidades')

    def __str__(self):
        return f'{self.tipo_anuncio} - {self.fecha_inicio} a {self.fecha_fin}'


# SEÑALES DE DJANGO PARA LIMPIAR IMÁGENES
from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=Contenido)
def limpiar_imagenes_contenido(sender, instance, **kwargs):
    """Limpia las imágenes cuando se elimina un contenido"""
    for i in range(1, 31):
        url_field = getattr(instance, f'imagen_{i}')
        if url_field and ('ibb.co' in url_field or 'imgur.com' in url_field):
            delete_from_imgbb(url_field)
    
    if instance.categoria == 'issues':
        for i in range(1, 31):
            backstage_field = getattr(instance, f'backstage_{i}')
            if backstage_field and ('ibb.co' in backstage_field or 'imgur.com' in backstage_field):
                delete_from_imgbb(backstage_field)

@receiver(pre_delete, sender=TiendaMadeInArg)
def limpiar_imagenes_tienda(sender, instance, **kwargs):
    """Limpia la imagen de portada cuando se elimina una tienda"""
    if instance.imagen_portada and ('ibb.co' in instance.imagen_portada or 'imgur.com' in instance.imagen_portada):
        delete_from_imgbb(instance.imagen_portada)

@receiver(pre_delete, sender=ProductoMadeInArg)
def limpiar_imagenes_producto(sender, instance, **kwargs):
    """Limpia la imagen cuando se elimina un producto"""
    if instance.imagen and ('ibb.co' in instance.imagen or 'imgur.com' in instance.imagen):
        delete_from_imgbb(instance.imagen)

@receiver(pre_delete, sender=ArtistaMadeInArg)
def limpiar_imagenes_artista(sender, instance, **kwargs):
    """Limpia las imágenes de la galería cuando se elimina un artista"""
    for i in range(1, 21):
        imagen = getattr(instance, f'imagen_{i}')
        if imagen and ('ibb.co' in imagen or 'imgur.com' in imagen):
            delete_from_imgbb(imagen)


# FUNCIONES DE UTILIDAD
def incrementar_visitas_contenido(contenido_instance, ip_address=None):
    """Función para incrementar visitas de contenido"""
    if timezone.now() - contenido_instance.ultima_actualizacion_contador > timedelta(days=7):
        contenido_instance.contador_visitas = 0
        contenido_instance.ultima_actualizacion_contador = timezone.now()
        contenido_instance.save()

    if ip_address:
        hace_5_minutos = timezone.now() - timedelta(minutes=5)
        visita_reciente = ContenidoVisita.objects.filter(
            contenido=contenido_instance,
            ip_address=ip_address,
            fecha__gte=hace_5_minutos
        ).exists()
        
        if visita_reciente:
            return False

    ContenidoVisita.objects.create(
        contenido=contenido_instance,
        ip_address=ip_address
    )
    
    contenido_instance.contador_visitas += 1
    contenido_instance.contador_visitas_total += 1
    contenido_instance.save(update_fields=['contador_visitas', 'contador_visitas_total'])
    
    return True


def get_madeinarg_stats():
    """Retorna estadísticas generales de MadeInArg"""
    stats = {
        'total_tiendas': TiendaMadeInArg.objects.filter(activa=True).count(),
        'total_productos': ProductoMadeInArg.objects.filter(activo=True).count(),
        'total_artistas': ArtistaMadeInArg.objects.filter(activo=True).count(),
        'productos_por_categoria': {},
        'tiendas_con_mas_productos': []
    }
    
    for categoria, nombre in ProductoMadeInArg.CATEGORIA_CHOICES:
        count = ProductoMadeInArg.objects.filter(categoria=categoria, activo=True).count()
        stats['productos_por_categoria'][categoria] = {
            'count': count,
            'nombre': nombre
        }
    
    tiendas_top = TiendaMadeInArg.objects.filter(activa=True).annotate(
        num_productos=Count('productos', filter=Q(productos__activo=True))
    ).order_by('-num_productos')[:5]
    
    stats['tiendas_con_mas_productos'] = [
        {
            'id': tienda.id,
            'titulo': tienda.titulo,
            'productos_count': tienda.num_productos
        }
        for tienda in tiendas_top
    ]
    
    return stats


def obtener_imagen_portada(contenido):
    """Obtiene la primera imagen disponible para usar como portada"""
    return contenido.imagen_1 or '/static/img/default-image.jpg'


def obtener_resumen_contenido(contenido, max_chars=150):
    """Obtiene un resumen del contenido según su tipo"""
    if contenido.categoria == 'news' and contenido.contenido_news:
        texto = contenido.contenido_news
    elif contenido.categoria == 'issues' and contenido.subtitulo_issue:
        texto = contenido.subtitulo_issue
    elif contenido.categoria == 'madeinarg' and contenido.subtitulo_madeinarg:
        texto = contenido.subtitulo_madeinarg
    else:
        texto = contenido.titulo
    
    if len(texto) > max_chars:
        return texto[:max_chars] + '...'






from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import threading

class Suscriptor(models.Model):
    """Modelo para almacenar suscriptores del newsletter"""
    nombre = models.CharField(max_length=100, help_text="Nombre del suscriptor")
    email = models.EmailField(unique=True, help_text="Email del suscriptor")
    fecha_suscripcion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True, help_text="Si la suscripción está activa")
    token_desuscripcion = models.UUIDField(default=uuid.uuid4, unique=True, help_text="Token para desuscribirse")
    
    # Preferencias de categorías (opcional)
    suscrito_editorials = models.BooleanField(default=True)
    suscrito_issues = models.BooleanField(default=True) 
    suscrito_madeinarg = models.BooleanField(default=True)
    suscrito_news = models.BooleanField(default=True)
    suscrito_club_pompa = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-fecha_suscripcion']
        verbose_name = "Suscriptor"
        verbose_name_plural = "Suscriptores"
    
    def __str__(self):
        return f"{self.nombre} - {self.email}"
    
    def esta_suscrito_a_categoria(self, categoria):
        """Verifica si el suscriptor está suscrito a una categoría específica"""
        categoria_map = {
            'editorials': self.suscrito_editorials,
            'issues': self.suscrito_issues,
            'madeinarg': self.suscrito_madeinarg, 
            'news': self.suscrito_news,
            'club_pompa': self.suscrito_club_pompa,
        }
        return categoria_map.get(categoria, True)


class Newsletter(models.Model):
    """Modelo para gestionar envíos de newsletter"""
    contenido = models.ForeignKey('Contenido', on_delete=models.CASCADE, related_name='newsletters')
    fecha_envio = models.DateTimeField(auto_now_add=True)
    enviado_exitosamente = models.BooleanField(default=False)
    total_enviados = models.PositiveIntegerField(default=0)
    total_errores = models.PositiveIntegerField(default=0)
    log_errores = models.TextField(blank=True, null=True, help_text="Log de errores durante el envío")
    
    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = "Newsletter"
        verbose_name_plural = "Newsletters"
    
    def __str__(self):
        return f"Newsletter: {self.contenido.titulo} - {self.fecha_envio.strftime('%d/%m/%Y %H:%M')}"
    
    def enviar_newsletter(self):
        """Envía el newsletter a todos los suscriptores activos"""
        suscriptores = Suscriptor.objects.filter(
            activo=True
        ).filter(
            **{f'suscrito_{self.contenido.categoria}': True}
        )
        
        enviados = 0
        errores = 0
        log_errores = []
        
        for suscriptor in suscriptores:
            try:
                self._enviar_email_individual(suscriptor)
                enviados += 1
            except Exception as e:
                errores += 1
                log_errores.append(f"{suscriptor.email}: {str(e)}")
        
        self.total_enviados = enviados
        self.total_errores = errores
        self.log_errores = "\n".join(log_errores)
        self.enviado_exitosamente = errores == 0
        self.save()
        
        return {'enviados': enviados, 'errores': errores}
    
    def _enviar_email_individual(self, suscriptor):
        """Envía email a un suscriptor individual - Versión simplificada"""
        categoria_display = dict(self.contenido.CATEGORIA_CHOICES).get(
            self.contenido.categoria, 
            self.contenido.categoria.title()
        )
        
        # Mensaje simple en texto plano
        mensaje = f"""
    Hola {suscriptor.nombre},

    Tenemos nuevo contenido en {categoria_display}:

    Título: {self.contenido.titulo}
    Autor: {self.contenido.autor.nombre if self.contenido.autor else 'N/A'}
    Fecha: {self.contenido.fecha_publicacion}

    Lee el contenido completo en: {getattr(settings, 'SITE_URL', 'https://diarioelgobierno.ar')}/contenido/{self.contenido.id}

    --
    Diario El Gobierno
    diarioelgobiernoargentina@gmail.com

    Para desuscribirte: {getattr(settings, 'SITE_URL', 'https://diarioelgobierno.ar')}/desuscribirse/{suscriptor.token_desuscripcion}
    """
        
        # Enviar email simple
        send_mail(
            subject=f"Nuevo contenido en {categoria_display}: {self.contenido.titulo}",
            message=mensaje,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@diarioelgobierno.ar'),
            recipient_list=[suscriptor.email],
            fail_silently=False,
        )


# Agregar este método a tu modelo Contenido existente
# En la clase Contenido, agregar este método:

def enviar_newsletter_automatico(self):
    """Envía newsletter automáticamente cuando se publica contenido"""
    # Solo enviar si el estado es 'publicado' y no se ha enviado antes
    if (self.estado and self.estado.nombre_estado == 'publicado' and 
        not hasattr(self, '_newsletter_enviado')):
        
        # Crear el newsletter
        newsletter = Newsletter.objects.create(contenido=self)
        
        # Enviar en un hilo separado para no bloquear
        def enviar_async():
            newsletter.enviar_newsletter()
        
        thread = threading.Thread(target=enviar_async)
        thread.daemon = True
        thread.start()
        
        # Marcar como enviado para evitar duplicados
        self._newsletter_enviado = True

# Modificar el método save de Contenido para incluir el envío automático:
# En la clase Contenido, modificar el método save():

def save(self, *args, **kwargs):
    # Verificar si es una actualización de estado a 'publicado'
    es_nueva_publicacion = False
    if self.pk:
        try:
            contenido_anterior = Contenido.objects.get(pk=self.pk)
            if (contenido_anterior.estado and 
                contenido_anterior.estado.nombre_estado != 'Publicado' and
                self.estado and self.estado.nombre_estado == 'Publicado'):
                es_nueva_publicacion = True
        except Contenido.DoesNotExist:
            pass
    else:
        # Nuevo contenido que se publica directamente
        if self.estado and self.estado.nombre_estado == 'publicado':
            es_nueva_publicacion = True
    
    # Llamar al save original
    super().save(*args, **kwargs)
    
    # Procesar imágenes (código existente)
    if self.categoria == 'issues':
        backstage_updated = self._process_backstage_images()
        if backstage_updated:
            super().save()
    
    # Enviar newsletter si es una nueva publicación
    if es_nueva_publicacion:
        self.enviar_newsletter_automatico()