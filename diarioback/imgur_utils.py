import os
import requests
import time
from django.core.files.uploadedfile import InMemoryUploadedFile

# Imgur API configuration
IMGUR_CLIENT_ID = '8e1f77de3869736'
IMGUR_UPLOAD_URL = 'https://api.imgur.com/3/image'
IMGUR_DELETE_URL = 'https://api.imgur.com/3/image/{hash}'

def upload_to_imgur(image):
    """
    Sube una imagen a Imgur y devuelve la URL de la imagen
    
    Args:
        image: Puede ser un objeto InMemoryUploadedFile, una ruta a un archivo,
               o un archivo abierto en modo binario
    
    Returns:
        str: URL de la imagen en Imgur, o None si falló la subida
    """
    headers = {
        'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'
    }
    
    try:
        if isinstance(image, InMemoryUploadedFile):
            # Si es un archivo subido en memoria (desde un formulario)
            image_data = image.read()
            files = {'image': image_data}
        elif isinstance(image, str) and os.path.isfile(image):
            # Si es una ruta a un archivo
            with open(image, 'rb') as image_file:
                image_data = image_file.read()
                files = {'image': image_data}
        else:
            # Si es un archivo ya abierto o cualquier otro objeto que pueda ser leído
            image_data = image.read() if hasattr(image, 'read') else image
            files = {'image': image_data}
        
        # Intentar subir la imagen a Imgur
        response = requests.post(
            IMGUR_UPLOAD_URL,
            headers=headers,
            files=files
        )
        
        # Manejar errores comunes
        if response.status_code == 429:  # Too Many Requests
            print("Error 429: Demasiadas solicitudes, esperando antes de reintentar...")
            time.sleep(60)  # Esperar 60 segundos antes de reintentar
            return upload_to_imgur(image)  # Reintentar la carga
        
        # Verificar respuesta
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success'):
                return response_data['data']['link']
            else:
                print(f"Error al subir imagen a Imgur: {response_data.get('data', {}).get('error')}")
        else:
            print(f"Error HTTP {response.status_code} al subir imagen a Imgur")
        
    except Exception as e:
        print(f"Excepción al subir imagen a Imgur: {str(e)}")
    
    return None

def delete_from_imgur(image_url):
    """
    Elimina una imagen de Imgur usando su URL
    
    Args:
        image_url (str): URL de la imagen en Imgur
    
    Returns:
        bool: True si la eliminación fue exitosa, False en caso contrario
    """
    # Extraer el hash de la imagen desde la URL
    try:
        # La URL de Imgur tiene el formato: https://i.imgur.com/HASH.ext
        image_hash = image_url.split('/')[-1].split('.')[0]
        
        headers = {
            'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'
        }
        
        # Realizar la solicitud DELETE a la API de Imgur
        delete_url = IMGUR_DELETE_URL.format(hash=image_hash)
        response = requests.delete(delete_url, headers=headers)
        
        if response.status_code == 200:
            response_data = response.json()
            return response_data.get('success', False)
        else:
            print(f"Error HTTP {response.status_code} al eliminar imagen de Imgur")
            return False
            
    except Exception as e:
        print(f"Excepción al eliminar imagen de Imgur: {str(e)}")
        return False