"""HTTP server using Python's built-in http.server module."""

import json
import os
import re
import uuid
import shutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional, Tuple

from . import services

ATTACHMENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "attachments")


class APIHandler(BaseHTTPRequestHandler):
    """Request handler for the API."""

    def _set_headers(self, status_code: int = 200, content_type: str = "application/json"):
        """Set response headers."""
        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data: Any, status_code: int = 200):
        """Send JSON response."""
        self._set_headers(status_code)
        self.wfile.write(json.dumps(data, indent=2, default=str).encode())

    def _send_error(self, message: str, status_code: int = 400):
        """Send error response."""
        self._send_json({"error": message}, status_code)

    def _get_body(self) -> Dict[str, Any]:
        """Parse JSON body from request."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        return json.loads(body.decode())

    def _parse_path(self) -> Tuple[str, Dict[str, str]]:
        """Parse URL path and query parameters."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        return path, query

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self._set_headers(204)

    def do_GET(self):
        """Handle GET requests."""
        path, query = self._parse_path()

        try:
            # Root endpoint
            if path == "/" or path == "":
                self._send_json({
                    "name": "FY27 Appropriations Tracker API",
                    "version": "1.0.0",
                    "docs": "/docs"
                })

            # Simple docs page
            elif path == "/docs":
                self._set_headers(200, "text/html")
                self.wfile.write(self._get_docs_html().encode())

            # List requests
            elif path == "/api/requests":
                requests = services.list_requests(
                    fiscal_year=int(query["fy"]) if "fy" in query else None,
                    request_type=query.get("type"),
                    subcommittee=query.get("subcommittee"),
                    status=query.get("status"),
                    skip=int(query.get("skip", 0)),
                    limit=int(query.get("limit", 100))
                )
                self._send_json(requests)

            # Get single request
            elif re.match(r"^/api/requests/(\d+)$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)$", path).group(1))
                request = services.get_request(request_id)
                if request:
                    self._send_json(request)
                else:
                    self._send_error("Request not found", 404)

            # Get CPF details
            elif re.match(r"^/api/requests/(\d+)/cpf$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)/cpf$", path).group(1))
                cpf = services.get_cpf_details(request_id)
                if cpf:
                    self._send_json(cpf)
                else:
                    self._send_error("CPF details not found", 404)

            # List eligible accounts
            elif path == "/api/eligible-accounts":
                accounts = services.list_eligible_accounts(
                    subcommittee=query.get("subcommittee"),
                    active_only=query.get("active_only", "true").lower() != "false"
                )
                self._send_json(accounts)

            # Get single eligible account
            elif re.match(r"^/api/eligible-accounts/(\d+)$", path):
                account_id = int(re.match(r"^/api/eligible-accounts/(\d+)$", path).group(1))
                account = services.get_eligible_account(account_id)
                if account:
                    self._send_json(account)
                else:
                    self._send_error("Account not found", 404)

            # Dashboard summary
            elif path == "/api/dashboard/summary":
                fy = int(query.get("fy", 2027))
                summary = services.get_dashboard_summary(fy)
                self._send_json(summary)

            else:
                self._send_error("Not found", 404)

        except Exception as e:
            self._send_error(str(e), 500)

    def do_POST(self):
        """Handle POST requests."""
        path, query = self._parse_path()

        try:
            # Create request
            if path == "/api/requests":
                data = self._get_body()
                request = services.create_request(data)
                self._send_json(request, 201)

            # Create/update CPF details
            elif re.match(r"^/api/requests/(\d+)/cpf$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)/cpf$", path).group(1))
                data = self._get_body()
                cpf = services.create_or_update_cpf_details(request_id, data)
                if cpf:
                    self._send_json(cpf, 201)
                else:
                    self._send_error("Request not found", 404)

            # Validate CPF
            elif re.match(r"^/api/requests/(\d+)/cpf/validate$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)/cpf/validate$", path).group(1))
                result = services.validate_cpf(request_id)
                self._send_json(result)

            # Select CPF
            elif re.match(r"^/api/requests/(\d+)/cpf/select$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)/cpf/select$", path).group(1))
                slot = int(query["slot"]) if "slot" in query else None
                cpf = services.select_cpf(request_id, slot)
                self._send_json(cpf)

            # Upload attachment
            elif re.match(r"^/api/requests/(\d+)/attachments$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)/attachments$", path).group(1))
                attachment = self._handle_file_upload(request_id)
                if attachment:
                    self._send_json(attachment, 201)
                else:
                    self._send_error("Upload failed", 400)

            else:
                self._send_error("Not found", 404)

        except ValueError as e:
            self._send_error(str(e), 400)
        except Exception as e:
            self._send_error(str(e), 500)

    def do_PATCH(self):
        """Handle PATCH requests."""
        path, query = self._parse_path()

        try:
            # Update request
            if re.match(r"^/api/requests/(\d+)$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)$", path).group(1))
                data = self._get_body()
                request = services.update_request(request_id, data)
                if request:
                    self._send_json(request)
                else:
                    self._send_error("Request not found", 404)

            else:
                self._send_error("Not found", 404)

        except ValueError as e:
            self._send_error(str(e), 400)
        except Exception as e:
            self._send_error(str(e), 500)

    def do_DELETE(self):
        """Handle DELETE requests."""
        path, query = self._parse_path()

        try:
            # Delete request
            if re.match(r"^/api/requests/(\d+)$", path):
                request_id = int(re.match(r"^/api/requests/(\d+)$", path).group(1))
                if services.delete_request(request_id):
                    self._send_json({"message": "Deleted"})
                else:
                    self._send_error("Request not found", 404)

            else:
                self._send_error("Not found", 404)

        except Exception as e:
            self._send_error(str(e), 500)

    def _handle_file_upload(self, request_id: int) -> Optional[Dict[str, Any]]:
        """Handle multipart file upload."""
        # Check request exists
        request = services.get_request(request_id)
        if not request:
            return None

        content_type = self.headers.get("Content-Type", "")

        # Parse multipart boundary
        if "multipart/form-data" not in content_type:
            raise ValueError("Content-Type must be multipart/form-data")

        boundary = None
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[9:].strip('"')
                break

        if not boundary:
            raise ValueError("No boundary in Content-Type")

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        # Parse multipart data (simplified)
        boundary_bytes = f"--{boundary}".encode()
        parts = body.split(boundary_bytes)

        file_data = None
        original_filename = "file"
        attachment_type = "other"

        for part in parts:
            if b"Content-Disposition" not in part:
                continue

            # Parse headers
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            headers = part[:header_end].decode(errors="ignore")
            content = part[header_end + 4:]

            # Remove trailing boundary markers
            if content.endswith(b"--\r\n"):
                content = content[:-4]
            elif content.endswith(b"\r\n"):
                content = content[:-2]

            if 'name="file"' in headers or 'name="attachment"' in headers:
                file_data = content
                # Extract filename
                match = re.search(r'filename="([^"]+)"', headers)
                if match:
                    original_filename = match.group(1)

            elif 'name="attachment_type"' in headers:
                attachment_type = content.decode().strip()

        if not file_data:
            raise ValueError("No file data found")

        # Save file
        request_dir = os.path.join(ATTACHMENTS_DIR, str(request_id))
        os.makedirs(request_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}_{original_filename}"
        file_path = os.path.join(request_dir, filename)

        with open(file_path, "wb") as f:
            f.write(file_data)

        # Save to database
        from .database import get_db
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO attachments (
                    request_id, filename, original_filename, file_path,
                    file_size, attachment_type
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                request_id, filename, original_filename, file_path,
                len(file_data), attachment_type
            ))

            attachment_id = cursor.lastrowid

            # Increment support letters if applicable
            if attachment_type == "cpf_support_letter":
                services.increment_support_letters(request_id)

            cursor.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,))
            return services.dict_from_row(cursor.fetchone())

    def _get_docs_html(self) -> str:
        """Generate simple HTML documentation."""
        return """<!DOCTYPE html>
<html>
<head>
    <title>FY27 Appropriations Tracker API</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        h1 { color: #1a365d; }
        h2 { color: #2c5282; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-top: 40px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #e2e8f0; padding: 12px; text-align: left; }
        th { background: #f7fafc; }
        code { background: #edf2f7; padding: 2px 6px; border-radius: 4px; font-family: 'Consolas', monospace; }
        pre { background: #1a202c; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; }
        .method { display: inline-block; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; margin-right: 8px; }
        .get { background: #c6f6d5; color: #22543d; }
        .post { background: #bee3f8; color: #2a4365; }
        .patch { background: #fef3c7; color: #744210; }
        .delete { background: #fed7d7; color: #822727; }
    </style>
</head>
<body>
    <h1>FY27 Appropriations Tracker API</h1>
    <p>A Tier Two appropriations tracking system for CPF, Programmatic, and Language requests.</p>

    <h2>Requests</h2>
    <table>
        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
        <tr><td><span class="method post">POST</span></td><td><code>/api/requests</code></td><td>Create a new request</td></tr>
        <tr><td><span class="method get">GET</span></td><td><code>/api/requests</code></td><td>List requests (filters: fy, type, subcommittee, status)</td></tr>
        <tr><td><span class="method get">GET</span></td><td><code>/api/requests/{id}</code></td><td>Get a single request</td></tr>
        <tr><td><span class="method patch">PATCH</span></td><td><code>/api/requests/{id}</code></td><td>Update a request</td></tr>
        <tr><td><span class="method delete">DELETE</span></td><td><code>/api/requests/{id}</code></td><td>Delete a request</td></tr>
    </table>

    <h2>CPF Details</h2>
    <table>
        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
        <tr><td><span class="method post">POST</span></td><td><code>/api/requests/{id}/cpf</code></td><td>Create/update CPF details</td></tr>
        <tr><td><span class="method get">GET</span></td><td><code>/api/requests/{id}/cpf</code></td><td>Get CPF details</td></tr>
        <tr><td><span class="method post">POST</span></td><td><code>/api/requests/{id}/cpf/validate</code></td><td>Validate CPF compliance</td></tr>
        <tr><td><span class="method post">POST</span></td><td><code>/api/requests/{id}/cpf/select</code></td><td>Select CPF for funding (15 cap)</td></tr>
    </table>

    <h2>Attachments</h2>
    <table>
        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
        <tr><td><span class="method post">POST</span></td><td><code>/api/requests/{id}/attachments</code></td><td>Upload attachment (multipart/form-data)</td></tr>
    </table>

    <h2>Dashboard</h2>
    <table>
        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
        <tr><td><span class="method get">GET</span></td><td><code>/api/dashboard/summary</code></td><td>Get summary statistics (filter: fy)</td></tr>
    </table>

    <h2>Eligible Accounts</h2>
    <table>
        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
        <tr><td><span class="method get">GET</span></td><td><code>/api/eligible-accounts</code></td><td>List eligible CPF accounts</td></tr>
        <tr><td><span class="method get">GET</span></td><td><code>/api/eligible-accounts/{id}</code></td><td>Get single account</td></tr>
    </table>

    <h2>Example: Create a CPF Request</h2>
    <pre>curl -X POST http://localhost:8080/api/requests \\
  -H "Content-Type: application/json" \\
  -d '{
    "request_type": "cpf",
    "subcommittee": "transportation_hud",
    "title": "Downtown Transit Hub",
    "requested_amount": 2500000
  }'</pre>

    <h2>Subcommittees</h2>
    <p><code>agriculture</code>, <code>commerce_justice_science</code>, <code>defense</code>, <code>energy_water</code>,
       <code>financial_services_general_government</code>, <code>homeland_security</code>, <code>interior_environment</code>,
       <code>labor_hhs_education</code>, <code>legislative_branch</code>, <code>milcon_va</code>,
       <code>state_foreign_operations</code>, <code>transportation_hud</code></p>

    <h2>Request Types</h2>
    <p><code>cpf</code> (Community Project Funding), <code>programmatic</code>, <code>language</code></p>
</body>
</html>"""

    def log_message(self, format, *args):
        """Custom log format."""
        print(f"[{self.log_date_time_string()}] {args[0]}")


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Run the HTTP server."""
    server = HTTPServer((host, port), APIHandler)
    print(f"Server running at http://localhost:{port}")
    print(f"API docs at http://localhost:{port}/docs")
    print("Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
