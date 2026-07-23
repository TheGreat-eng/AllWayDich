#!/usr/bin/env python3
# proxy.py — chạy bằng: python3 proxy.py
import http.server, ssl, urllib.request, urllib.error

TARGET = 'https://jira-qlsxpm.viettel.vn:32100'
PORT   = 8010

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_request(self):
        url = TARGET + self.path
        headers['X-Atlassian-Token'] = 'no-check'
        body = None
        if self.command in ('POST', 'PUT', 'PATCH'):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length) if length else None
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
            with urllib.request.urlopen(req, context=ctx) as r:
                self.send_response(r.status)
                for k, v in r.headers.items():
                    if k.lower() != 'transfer-encoding':
                        self.send_header(k, v)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(r.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(e.read())
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization,Content-Type,X-Atlassian-Token')
        self.end_headers()
    do_GET = do_POST = do_PUT = do_DELETE = do_request
    def log_message(self, fmt, *args): print(fmt % args)

print(f'Proxy đang chạy tại http://localhost:{PORT}')
http.server.HTTPServer(('localhost', PORT), ProxyHandler).serve_forever()
