from django.shortcuts import redirect

class WebAuthnDomainMiddleware:
    """
    W3C WebAuthn / FIDO2 specification strictly requires a valid domain string
    for the Relying Party (RP ID) and forbids raw IPv4/IPv6 addresses like 127.0.0.1.
    
    When accessing locally via 127.0.0.1, this middleware automatically and
    transparently redirects requests to localhost:<port> so that browser
    biometric sensors (Touch ID, Windows Hello, Android fingerprint) function
    without 'invalid domain' errors.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host()
        if host.startswith('127.0.0.1'):
            new_host = host.replace('127.0.0.1', 'localhost', 1)
            new_url = f"{request.scheme}://{new_host}{request.get_full_path()}"
            return redirect(new_url)
        return self.get_response(request)
