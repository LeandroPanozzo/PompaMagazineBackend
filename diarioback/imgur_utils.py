import requests
import time
import os
import base64
from django.core.files.uploadedfile import InMemoryUploadedFile

# Constantes de ImgBB
IMGBB_API_KEY = 'a315981b1bce71916fb736816e14d90a'
IMGBB_UPLOAD_URL = 'https://api.imgbb.com/1/upload'

def upload_to_imgbb(image):
    """
    Sube una imagen a ImgBB y devuelve la URL
    
    Args:
        image: Puede ser un objeto InMemoryUploadedFile, una ruta a un archivo,
               o un archivo abierto en modo binario
    
    Returns:
        str: URL de la imagen en ImgBB, o None si falló la subida
    """
    try:
        # Prepara los datos según el tipo de entrada
        if isinstance(image, InMemoryUploadedFile):
            # Si es un archivo subido en memoria (desde un formulario)
            image_data = image.read()
        elif isinstance(image, str) and os.path.isfile(image):
            # Si es una ruta a un archivo
            with open(image, 'rb') as image_file:
                image_data = image_file.read()
        elif hasattr(image, 'path') and os.path.isfile(image.path):
            # Si es un campo ImageField de Django
            with open(image.path, 'rb') as image_file:
                image_data = image_file.read()
        else:
            # Si es un archivo ya abierto o cualquier otro objeto que pueda ser leído
            image_data = image.read() if hasattr(image, 'read') else image

        # Convertir imagen a base64 para ImgBB
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Datos para la petición
        payload = {
            'key': IMGBB_API_KEY,
            'image': image_base64
        }
        
        # Intentar subir la imagen a ImgBB
        response = requests.post(
            IMGBB_UPLOAD_URL,
            data=payload
        )
        
        # Manejar límites de peticiones (429 Too Many Requests)
        if response.status_code == 429:
            print("Error 429: Demasiadas solicitudes, esperando antes de reintentar...")
            time.sleep(60)  # Esperar 60 segundos antes de reintentar
            return upload_to_imgbb(image)  # Reintentar la carga
        
        # Verificar respuesta
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                # ImgBB devuelve la URL directa de la imagen
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
    """
    NOTA: ImgBB no proporciona una API pública para eliminar imágenes.
    Las imágenes solo pueden ser eliminadas desde el panel de control web.
    
    Esta función existe para mantener compatibilidad con el código existente,
    pero no realiza ninguna acción real de eliminación.
    
    Args:
        image_url_or_id: URL de la imagen o ID de ImgBB (no utilizado)
    
    Returns:
        bool: Siempre devuelve True para evitar errores en el código existente
    """
    print(f"Advertencia: ImgBB no permite eliminar imágenes via API. Imagen: {image_url_or_id}")
    # ImgBB no tiene API pública para eliminar imágenes
    # Las imágenes se eliminan automáticamente después del tiempo de expiración configurado
    # o manualmente desde el panel de control web
    return True


# Funciones de compatibilidad para mantener el código existente funcionando
def upload_to_imgur(image):
    """
    Función de compatibilidad que redirige a ImgBB
    Para mantener el código existente sin cambios
    """
    return upload_to_imgbb(image)


def delete_from_imgur(image_url):
    """
    Función de compatibilidad que redirige a la función de ImgBB
    Para mantener el código existente sin cambios
    """
    return delete_from_imgbb(image_url)


# También actualizar las constantes por compatibilidad
IMGUR_CLIENT_ID = IMGBB_API_KEY  # Para compatibilidad con código existente
IMGUR_UPLOAD_URL = IMGBB_UPLOAD_URL  # Para compatibilidad con código existente