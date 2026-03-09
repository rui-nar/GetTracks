#!/usr/bin/env python3
"""Test script for Strava OAuth flow with real credentials."""

import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
from src.config.settings import Config
from src.auth.oauth import OAuth2Session
from src.api.strava_client import StravaAPI


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler to catch OAuth callback."""

    def do_GET(self):
        """Handle GET request with authorization code."""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Parse the query parameters
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if 'code' in params:
            self.server.auth_code = params['code'][0]
            response_html = """
            <html>
            <body>
            <h1>Authorization Successful!</h1>
            <p>You can close this window and return to the terminal.</p>
            </body>
            </html>
            """
        else:
            self.server.auth_code = None
            response_html = """
            <html>
            <body>
            <h1>Authorization Failed</h1>
            <p>No authorization code received.</p>
            </body>
            </html>
            """

        self.wfile.write(response_html.encode())
        self.server.shutdown()


def test_oauth_flow():
    """Test the complete OAuth flow."""
    print("🔐 Testing Strava OAuth Flow")
    print("=" * 40)

    # Load config
    try:
        config = Config()
        if not config.validate_strava_config():
            print("❌ Error: Strava client_id or client_secret not configured!")
            print("Please check your config.json file.")
            return
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return

    # Create OAuth session
    try:
        oauth = OAuth2Session(config)
        print("✅ OAuth session created successfully")
    except Exception as e:
        print(f"❌ Error creating OAuth session: {e}")
        return

    # Get authorization URL
    auth_url = oauth.authorization_url()
    print(f"🔗 Authorization URL: {auth_url}")

    # Start local server to catch callback
    server = HTTPServer(('localhost', 8000), OAuthCallbackHandler)
    server.auth_code = None

    print("\n🌐 Opening browser for authorization...")
    print("Please authorize the app in your browser, then return here.")

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    print("⏳ Waiting for authorization callback...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("❌ Server interrupted")
        return

    # Check if we got the code
    if server.auth_code:
        print(f"✅ Authorization code received: {server.auth_code[:20]}...")

        # Exchange code for token
        try:
            token_data = oauth.exchange_code(server.auth_code)
            print("✅ Token exchange successful!")
            print(f"Access Token: {token_data.get('access_token')[:20]}...")
            print(f"Refresh Token: {token_data.get('refresh_token')[:20]}...")

            # Test API client
            print("\n🔌 Testing Strava API client...")
            api = StravaAPI(config)
            api.set_token(token_data)

            # Try to get activities
            try:
                activities = api.get_activities(per_page=5)
                print(f"✅ Successfully fetched {len(activities)} activities!")
                if activities:
                    print(f"Sample activity: {activities[0].get('name', 'Unknown')}")
            except Exception as e:
                print(f"❌ Error fetching activities: {e}")

        except Exception as e:
            print(f"❌ Error exchanging code for token: {e}")
    else:
        print("❌ No authorization code received")


if __name__ == "__main__":
    test_oauth_flow()