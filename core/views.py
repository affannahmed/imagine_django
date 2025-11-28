from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import socket

@require_http_methods(["GET"])
def root_endpoint(request):
    """
    Returns server IP and port for cPanel discovery
    """
    # Get server IP (your public IP)
    server_ip = "44.222.48.230"
    server_port = "8000"
    
    response_url = f"http://{server_ip}:{server_port}"
    
    return response_url