from django.http import HttpResponse
import base64

class BasicAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Usuario y contraseña que quieres usar
        USERNAME = 'cyr'  # Cambia esto
        PASSWORD = 'cyr1506'  # Cambia esto
        
        if 'HTTP_AUTHORIZATION' in request.META:
            auth = request.META['HTTP_AUTHORIZATION'].split()
            if len(auth) == 2:
                if auth[0].lower() == "basic":
                    credentials = base64.b64decode(auth[1]).decode('utf-8')
                    username, password = credentials.split(':')
                    if username == USERNAME and password == PASSWORD:
                        return self.get_response(request)
        
        response = HttpResponse('No autorizado', status=401)
        response['WWW-Authenticate'] = 'Basic realm="Acceso restringido"'
        return response