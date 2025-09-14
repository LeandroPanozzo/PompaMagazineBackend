from django.contrib import admin
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.utils.html import format_html
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from django import forms
from .models import (
    Trabajador, Usuario, Contenido, EstadoPublicacion, Publicidad, 
    UserProfile, EspacioReferencia, ImagenLink, ContenidoVisita, PasswordResetToken
)

# --- Función helper para verificar permisos de admin ---
def es_admin_completo(user):
    """Verifica si el usuario tiene permisos de administración completos"""
    return user.is_superuser or user.is_staff

# --- Signal para asignar permisos automáticamente a usuarios staff ---
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def asignar_permisos_staff(sender, instance, **kwargs):
    """Asigna todos los permisos a usuarios con is_staff=True"""
    if instance.is_staff and not instance.is_superuser:
        # Obtener todos los permisos disponibles
        all_permissions = Permission.objects.all()
        # Asignar todos los permisos al usuario
        instance.user_permissions.set(all_permissions)
        print(f"Permisos asignados a {instance.username}")

# --- Clase base para todos los ModelAdmin con permisos de staff ---
class StaffPermissionMixin:
    """Mixin que otorga todos los permisos a usuarios staff"""
    
    def has_module_permission(self, request):
        return es_admin_completo(request.user)
    
    def has_view_permission(self, request, obj=None):
        return es_admin_completo(request.user)
    
    def has_add_permission(self, request):
        return es_admin_completo(request.user)

    def has_change_permission(self, request, obj=None):
        return es_admin_completo(request.user)

    def has_delete_permission(self, request, obj=None):
        return es_admin_completo(request.user)

# --- Restricciones de permisos para User y Group ---
class UserAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Asignar permisos si es staff pero no superuser
        if obj.is_staff and not obj.is_superuser:
            all_permissions = Permission.objects.all()
            obj.user_permissions.set(all_permissions)

class GroupAdmin(StaffPermissionMixin, admin.ModelAdmin):
    pass

# Desregistrar los modelos por defecto y registrarlos con las restricciones
admin.site.unregister(User)
admin.site.unregister(Group)
admin.site.register(User, UserAdmin)
admin.site.register(Group, GroupAdmin)

# --- Administración de los modelos personalizados ---

class TrabajadorForm(forms.ModelForm):
    foto_perfil_temp = forms.ImageField(
        required=False, 
        label="Foto de Perfil",
        help_text="La imagen será subida automáticamente a ImgBB"
    )
    
    class Meta:
        model = Trabajador
        fields = ['nombre', 'apellido', 'user', 'foto_perfil_temp']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance and instance.foto_perfil:
            self.fields['foto_perfil_temp'].help_text += f"<br>Imagen actual: <a href='{instance.foto_perfil}' target='_blank'>{instance.foto_perfil}</a>"

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if not instance.user_profile:
            # Crear nuevo UserProfile
            instance.user_profile = UserProfile.objects.create(
                nombre=instance.nombre,
                apellido=instance.apellido,
                es_trabajador=True
            )
        else:
            # Actualizar UserProfile existente con los nuevos datos
            instance.user_profile.nombre = instance.nombre
            instance.user_profile.apellido = instance.apellido
            if not instance.user_profile.es_trabajador:
                instance.user_profile.es_trabajador = True
            instance.user_profile.save()

        foto_temp = self.cleaned_data.get('foto_perfil_temp')
        if foto_temp:
            instance.foto_perfil_local = foto_temp

        if commit:
            instance.save()
            
        return instance

@admin.register(Trabajador)
class TrabajadorAdmin(StaffPermissionMixin, admin.ModelAdmin):
    form = TrabajadorForm
    
    list_display = (
        'correo', 'nombre', 'apellido', 'user_link', 'mostrar_foto_perfil', 
        'total_contenidos', 'permisos_display'
    )
    search_fields = ('correo', 'nombre', 'apellido', 'user__username', 'user__email')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'user')
        }),
        ('Foto de Perfil', {
            'fields': ('foto_perfil_temp',),
            'description': 'La imagen se subirá automáticamente a ImgBB al guardar'
        }),
        ('Permisos', {
            'fields': (),
            'description': 'Todos los trabajadores tienen permisos de editor por defecto (publicar, editar, eliminar)'
        }),
    )

    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(f'<a href="{url}">{obj.user}</a>')
    
    user_link.short_description = 'Usuario'

    def mostrar_foto_perfil(self, obj):
        if obj.foto_perfil:
            return format_html('<img src="{}" style="max-height: 50px;">', obj.foto_perfil)
        elif obj.foto_perfil_local:
            return format_html('<img src="{}" style="max-height: 50px;">', obj.foto_perfil_local.url)
        return "No tiene foto de perfil"
    
    mostrar_foto_perfil.short_description = 'Foto de Perfil'

    def total_contenidos(self, obj):
        return obj.contenidos.count()
    
    total_contenidos.short_description = 'Total Contenidos'

    def permisos_display(self, obj):
        permisos = []
        if obj.puede_publicar():
            permisos.append("Publicar")
        if obj.puede_editar():
            permisos.append("Editar")
        if obj.puede_eliminar():
            permisos.append("Eliminar")
        return ", ".join(permisos) if permisos else "Sin permisos"
    
    permisos_display.short_description = 'Permisos'

    def save_model(self, request, obj, form, change):
        if obj.user and obj.user.email:
            obj.correo = obj.user.email
        super().save_model(request, obj, form, change)

@admin.register(Usuario)
class UsuarioAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('correo', 'nombre_usuario', 'esta_subscrito')
    search_fields = ('correo', 'nombre_usuario')
    list_filter = ('esta_subscrito',)

@admin.register(UserProfile)
class UserProfileAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'user', 'es_trabajador')
    search_fields = ('nombre', 'apellido', 'user__username', 'user__email')
    list_filter = ('es_trabajador',)

# Inlines para Contenido
class EspacioReferenciaInline(admin.TabularInline):
    model = EspacioReferencia
    extra = 1
    fields = ('orden', 'texto_mostrar', 'url')
    ordering = ('orden',)

class ImagenLinkInline(admin.TabularInline):
    model = ImagenLink
    extra = 1
    fields = ('numero_imagen', 'url_tienda', 'texto_descripcion')
    ordering = ('numero_imagen',)

# Formulario personalizado para Contenido
class ContenidoForm(forms.ModelForm):
    class Meta:
        model = Contenido
        fields = '__all__'
        widgets = {
            'contenido_news': forms.Textarea(attrs={'rows': 10}),
            'subtitulos_news': forms.Textarea(attrs={'rows': 4}),
            'subtitulo_issue': forms.Textarea(attrs={'rows': 4}),
            'subtitulo_madeinarg': forms.Textarea(attrs={'rows': 4}),
            'frase_final_issue': forms.Textarea(attrs={'rows': 3}),
            'tags_marcas': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Separar tags con comas'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Mostrar solo campos relevantes según la categoría
        if self.instance and self.instance.categoria:
            self.setup_fields_for_category()

    def setup_fields_for_category(self):
        categoria = self.instance.categoria
        
        # Ocultar campos irrelevantes según la categoría
        if categoria != 'issues':
            for field in ['numero_issue', 'nombre_modelo', 'subtitulo_issue', 'frase_final_issue', 'video_youtube_issue']:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
            # Ocultar campos de backstage
            for i in range(1, 31):
                backstage_field = f'backstage_{i}'
                if backstage_field in self.fields:
                    self.fields[backstage_field].widget = forms.HiddenInput()
        
        if categoria != 'madeinarg':
            for field in ['subcategoria_madeinarg', 'subtitulo_madeinarg', 'tags_marcas']:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()
        
        if categoria != 'news':
            for field in ['subtitulos_news', 'contenido_news', 'video_youtube_news']:
                if field in self.fields:
                    self.fields[field].widget = forms.HiddenInput()

@admin.register(Contenido)
class ContenidoAdmin(StaffPermissionMixin, admin.ModelAdmin):
    form = ContenidoForm
    inlines = [EspacioReferenciaInline, ImagenLinkInline]
    
    list_display = (
        'titulo_corto',
        'categoria',
        'autor_link',
        'fecha_publicacion',
        'estado_badge',
        'contador_visitas',
        'contador_visitas_total',
        'mostrar_imagen_principal'
    )
    
    list_filter = (
        'categoria',
        'estado',
        'autor',
        'fecha_publicacion',
        'subcategoria_madeinarg'
    )
    
    search_fields = ('titulo', 'contenido_news', 'tags_marcas', 'nombre_modelo')
    date_hierarchy = 'fecha_publicacion'
    ordering = ['-fecha_publicacion']
    
    def get_fieldsets(self, request, obj=None):
        """Devuelve fieldsets dinámicos según la categoría"""
        base_fieldsets = [
            ('Información Principal', {
                'fields': ('categoria', 'titulo', 'autor', 'fecha_publicacion', 'estado')
            })
        ]
        
        if obj and obj.categoria:
            if obj.categoria == 'issues':
                base_fieldsets.extend([
                    ('Datos de Issue', {
                        'fields': ('numero_issue', 'nombre_modelo', 'subtitulo_issue', 'frase_final_issue', 'video_youtube_issue')
                    }),
                    ('Imágenes Backstage', {
                        'fields': tuple(f'backstage_{i}' for i in range(1, 11)),
                        'classes': ('collapse',)
                    })
                ])
            
            elif obj.categoria == 'madeinarg':
                base_fieldsets.append(
                    ('Datos de MadeInArg', {
                        'fields': ('subcategoria_madeinarg', 'subtitulo_madeinarg', 'tags_marcas')
                    })
                )
            
            elif obj.categoria == 'news':
                base_fieldsets.append(
                    ('Datos de News', {
                        'fields': ('subtitulos_news', 'contenido_news', 'video_youtube_news')
                    })
                )
        else:
            # Si no hay objeto (creación), mostrar todos los campos específicos colapsados
            base_fieldsets.extend([
                ('Datos de Issue', {
                    'fields': ('numero_issue', 'nombre_modelo', 'subtitulo_issue', 'frase_final_issue', 'video_youtube_issue'),
                    'classes': ('collapse',)
                }),
                ('Datos de MadeInArg', {
                    'fields': ('subcategoria_madeinarg', 'subtitulo_madeinarg', 'tags_marcas'),
                    'classes': ('collapse',)
                }),
                ('Datos de News', {
                    'fields': ('subtitulos_news', 'contenido_news', 'video_youtube_news'),
                    'classes': ('collapse',)
                })
            ])
        
        # Agregar fieldsets comunes
        base_fieldsets.extend([
            ('Imágenes Principales', {
                'fields': tuple(f'imagen_{i}' for i in range(1, 11)),
                'classes': ('collapse',)
            }),
            ('Estadísticas', {
                'fields': ('contador_visitas', 'contador_visitas_total', 'ultima_actualizacion_contador'),
                'classes': ('collapse',)
            })
        ])
        
        return base_fieldsets
    
    def titulo_corto(self, obj):
        if len(obj.titulo) > 50:
            return obj.titulo[:50] + '...'
        return obj.titulo
    titulo_corto.short_description = 'Título'
    
    def autor_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.autor.user.id])
        return format_html(f'<a href="{url}">{obj.autor.nombre} {obj.autor.apellido}</a>')
    autor_link.short_description = 'Autor'
    
    def estado_badge(self, obj):
        if not obj.estado:
            return format_html('<span style="color: gray;">Sin estado</span>')
        
        colors = {
            'publicado': 'green',
            'borrador': 'orange',
            'en_papelera': 'red',
            'listo_para_editar': 'blue'
        }
        color = colors.get(obj.estado.nombre_estado, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.estado.get_nombre_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def mostrar_imagen_principal(self, obj):
        if obj.imagen_1:
            return format_html('<img src="{}" style="max-height: 50px;">', obj.imagen_1)
        return "Sin imagen"
    mostrar_imagen_principal.short_description = 'Imagen Principal'
    
    readonly_fields = ('contador_visitas_total', 'ultima_actualizacion_contador')
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        
        # Auto-generar número de issue
        if obj and obj.categoria == 'issues' and obj.numero_issue:
            readonly.append('numero_issue')
            
        return readonly

    actions = ['reset_total_counter', 'cambiar_a_publicado', 'cambiar_a_borrador']

    def reset_total_counter(self, request, queryset):
        if es_admin_completo(request.user):
            count = queryset.update(contador_visitas_total=0, contador_visitas=0)
            self.message_user(
                request,
                f'Se resetearon los contadores de {count} contenidos.'
            )
        else:
            self.message_user(
                request,
                'Solo los administradores pueden resetear contadores.',
                level='ERROR'
            )
    reset_total_counter.short_description = "Resetear contadores"

    def cambiar_a_publicado(self, request, queryset):
        try:
            estado_publicado = EstadoPublicacion.objects.get(nombre_estado='publicado')
            count = queryset.update(estado=estado_publicado)
            self.message_user(
                request,
                f'Se cambió el estado de {count} contenidos a "Publicado".'
            )
        except EstadoPublicacion.DoesNotExist:
            self.message_user(
                request,
                'No se encontró el estado "Publicado". Créalo primero.',
                level='ERROR'
            )
    cambiar_a_publicado.short_description = "Cambiar a Publicado"

    def cambiar_a_borrador(self, request, queryset):
        try:
            estado_borrador = EstadoPublicacion.objects.get(nombre_estado='borrador')
            count = queryset.update(estado=estado_borrador)
            self.message_user(
                request,
                f'Se cambió el estado de {count} contenidos a "Borrador".'
            )
        except EstadoPublicacion.DoesNotExist:
            self.message_user(
                request,
                'No se encontró el estado "Borrador". Créalo primero.',
                level='ERROR'
            )
    cambiar_a_borrador.short_description = "Cambiar a Borrador"

@admin.register(EstadoPublicacion)
class EstadoPublicacionAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('nombre_estado', 'get_nombre_display', 'contenidos_count')
    search_fields = ('nombre_estado',)
    
    def get_nombre_display(self, obj):
        return obj.get_nombre_estado_display()
    get_nombre_display.short_description = 'Nombre para mostrar'
    
    def contenidos_count(self, obj):
        return Contenido.objects.filter(estado=obj).count()
    contenidos_count.short_description = 'Contenidos con este estado'

@admin.register(EspacioReferencia)
class EspacioReferenciaAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('contenido', 'texto_mostrar', 'url', 'orden')
    search_fields = ('texto_mostrar', 'contenido__titulo')
    list_filter = ('contenido__categoria',)
    ordering = ('contenido', 'orden')

@admin.register(ImagenLink)
class ImagenLinkAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('contenido', 'numero_imagen', 'texto_descripcion', 'url_tienda')
    search_fields = ('texto_descripcion', 'contenido__titulo')
    list_filter = ('contenido__categoria', 'numero_imagen')
    ordering = ('contenido', 'numero_imagen')

@admin.register(ContenidoVisita)
class ContenidoVisitaAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('contenido', 'fecha', 'ip_address')
    list_filter = ('fecha', 'contenido__categoria')
    search_fields = ('contenido__titulo', 'ip_address')
    date_hierarchy = 'fecha'
    ordering = ['-fecha']
    
    def has_add_permission(self, request):
        return False  # No permitir crear visitas manualmente

@admin.register(Publicidad)
class PublicidadAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('tipo_anuncio', 'fecha_inicio', 'fecha_fin', 'contenido', 'impresiones', 'clics')
    search_fields = ('tipo_anuncio', 'contenido__titulo')
    list_filter = ('fecha_inicio', 'fecha_fin', 'contenido__categoria')
    date_hierarchy = 'fecha_inicio'

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(StaffPermissionMixin, admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at', 'used', 'is_token_valid')
    list_filter = ('used', 'created_at')
    search_fields = ('user__username', 'user__email', 'token')
    readonly_fields = ('token', 'created_at', 'expires_at')
    
    def is_token_valid(self, obj):
        return obj.is_valid()
    is_token_valid.short_description = 'Token Válido'
    is_token_valid.boolean = True

    def has_add_permission(self, request):
        return False  # Los tokens se crean automáticamente

# Personalización del admin site
admin.site.site_header = "Administración de Contenido"
admin.site.site_title = "Admin Panel"
admin.site.index_title = "Panel de Administración"

# Comando de management para asignar permisos a usuarios staff existentes
"""
Para crear el comando, guarda esto en: management/commands/asignar_permisos_staff.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Permission

class Command(BaseCommand):
    help = 'Asigna todos los permisos a usuarios con is_staff=True'

    def handle(self, *args, **options):
        staff_users = User.objects.filter(is_staff=True, is_superuser=False)
        all_permissions = Permission.objects.all()
        
        for user in staff_users:
            user.user_permissions.set(all_permissions)
            self.stdout.write(
                self.style.SUCCESS(f'Permisos asignados a {user.username}')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'Se procesaron {staff_users.count()} usuarios staff')
        )
"""