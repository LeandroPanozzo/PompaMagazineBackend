#!/usr/bin/env bash
# Exit on error
set -o errexit

# Modify this line as needed for your package manager (pip, poetry, etc.)
pip install -r requirements.txt

# Convert static asset files
python manage.py collectstatic --no-input

# Apply any outstanding database migrations
python manage.py migrate

# Crear estados de publicación
echo "from diarioback.models import EstadoPublicacion; states = [('borrador', 'Borrador'), ('en_papelera', 'En Papelera'), ('publicado', 'Publicado'), ('listo_para_editar', 'Listo para editar')]; [EstadoPublicacion.objects.get_or_create(nombre_estado=code) for code, name in states]" | python manage.py shell


#creacion de usuario admin 
#export DJANGO_SUPERUSER_USERNAME=admin
#export DJANGO_SUPERUSER_EMAIL=test@test.com
#export DJANGO_SUPERUSER_PASSWORD=test132465798
#python manage.py createsuperuser --no-input