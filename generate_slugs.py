# Guarda este script como generate_slugs.py en el mismo directorio que manage.py

import os
import django

# Corregir el nombre del módulo de configuración (parece ser un error tipográfico)
# El error original mostraba que intentaba importar 'diario_back_apo' cuando probablemente
# el nombre correcto es 'diario_back_api'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'diario_back_api.settings')

# Intentar setup Django
try:
    django.setup()
except Exception as e:
    print(f"Error al configurar Django: {e}")
    print("\nSolución recomendada:")
    print("1. Verifica que el nombre del módulo de configuración sea correcto")
    print("2. Instala las dependencias faltantes con pip:")
    print("   pip install psycopg2-binary")
    print("   o")
    print("   pip install psycopg")
    print("\nEjecutando diagnóstico adicional...")
    
    # Verifica si las dependencias están instaladas
    try:
        import psycopg2
        print("✓ psycopg2 está instalado correctamente")
    except ImportError:
        print("✗ psycopg2 no está instalado")
    
    try:
        import psycopg
        print("✓ psycopg está instalado correctamente")
    except ImportError:
        print("✗ psycopg no está instalado")
    
    exit(1)

# Si llegamos hasta aquí, Django se configuró correctamente
from django.utils.text import slugify

# Intenta importar el modelo Noticia
try:
    # Verificar primero la estructura del proyecto para determinar la ubicación correcta del modelo
    from django.apps import apps
    app_configs = apps.get_app_configs()
    print("Apps disponibles:")
    for app in app_configs:
        print(f" - {app.name}")
    
    # Intenta importar el modelo (ajusta la ruta según sea necesario)
    # Prueba primero con la importación directa
    try:
        from noticia.models import Noticia
        print("Modelo Noticia importado correctamente desde 'noticia.models'")
    except ImportError:
        # Si falla, prueba otras posibles ubicaciones
        try:
            from diario.models import Noticia
            print("Modelo Noticia importado correctamente desde 'diario.models'")
        except ImportError:
            # Si falla nuevamente, intenta descubrir el modelo dinámicamente
            noticia_model = None
            for app in app_configs:
                try:
                    noticia_model = apps.get_model(app.label, 'Noticia')
                    print(f"Modelo Noticia encontrado en la app '{app.label}'")
                    break
                except LookupError:
                    continue
            
            if noticia_model:
                Noticia = noticia_model
            else:
                raise ImportError("No se pudo encontrar el modelo Noticia en ninguna app")

    def generate_slugs_for_all_news():
        """
        Genera y actualiza los slugs para todas las noticias existentes.
        Útil para ejecutar cuando se implementa por primera vez la funcionalidad de slugs.
        """
        print("Generando slugs para todas las noticias existentes...")
        
        # Obtener todas las noticias que no tienen slug
        noticias_sin_slug = Noticia.objects.filter(slug__isnull=True) | Noticia.objects.filter(slug='')
        count = noticias_sin_slug.count()
        
        print(f"Se encontraron {count} noticias sin slug.")
        
        # Diccionario para rastrear slugs usados
        used_slugs = {}
        
        # Procesar cada noticia
        for i, noticia in enumerate(noticias_sin_slug, 1):
            # Limitar el título a 40 caracteres para evitar slugs demasiado largos
            truncated_title = noticia.nombre_noticia[:40] if len(noticia.nombre_noticia) > 40 else noticia.nombre_noticia
            base_slug = slugify(truncated_title)
            
            # Asegurar unicidad del slug
            slug = base_slug
            counter = 1
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Guardar el slug usado
            used_slugs[slug] = True
            
            # Actualizar la noticia
            noticia.slug = slug
            noticia.url = f"/noticia/{noticia.pk}/{slug}/"
            noticia.save(update_fields=['slug', 'url'])
            
            if i % 100 == 0 or i == count:
                print(f"Procesadas {i}/{count} noticias...")
        
        print("¡Proceso completado! Slugs generados para todas las noticias.")

    if __name__ == "__main__":
        generate_slugs_for_all_news()

except Exception as e:
    print(f"Error al ejecutar el script: {e}")