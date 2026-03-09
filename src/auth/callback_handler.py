"""OAuth callback handler for Strava authentication."""

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, Callable
import webbrowser


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""
    
    # Class variables to share state
    auth_code: Optional[str] = None
    auth_error: Optional[str] = None
    callback_received = threading.Event()

    def do_GET(self):
        """Handle GET request from OAuth callback."""
        # Parse the callback URL
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        # Extract code or error
        if "code" in query_params:
            CallbackHandler.auth_code = query_params["code"][0]
            response_html = """
            <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>✓ Authentication Successful!</h1>
                <p>You can close this window and return to GetTracks.</p>
            </body>
            </html>
            """
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(response_html.encode())
            CallbackHandler.callback_received.set()
            
        elif "error" in query_params:
            CallbackHandler.auth_error = query_params.get("error_description", ["Unknown error"])[0]
            response_html = f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>✗ Authentication Failed</h1>
                <p>Error: {CallbackHandler.auth_error}</p>
                <p>You can close this window and try again.</p>
            </body>
            </html>
            """
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(response_html.encode())
            CallbackHandler.callback_received.set()

    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class OAuthCallbackServer:
    """Simple HTTP server to handle OAuth callbacks."""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the callback server in a background thread."""
        CallbackHandler.auth_code = None
        CallbackHandler.auth_error = None
        CallbackHandler.callback_received.clear()
        
        self.server = HTTPServer(("127.0.0.1", self.port), CallbackHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        """Stop the callback server."""
        if self.server:
            self.server.shutdown()
            if self.thread:
                self.thread.join(timeout=2)

    def wait_for_callback(self, timeout: int = 300) -> Optional[str]:
        """Wait for OAuth callback and return the auth code."""
        received = CallbackHandler.callback_received.wait(timeout=timeout)
        if not received:
            return None
        
        if CallbackHandler.auth_error:
            raise Exception(f"OAuth error: {CallbackHandler.auth_error}")
        
        return CallbackHandler.auth_code
