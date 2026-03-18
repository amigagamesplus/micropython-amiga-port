# urequests — HTTP client for MicroPython AmigaOS port
# Supports HTTP/1.0 GET, POST, PUT, DELETE, HEAD
# No HTTPS (no TLS library available)

import socket


class Response:
    def __init__(self, f):
        self.raw = f
        self.encoding = "utf-8"
        self._cached = None
        self.status_code = None
        self.reason = None
        self.headers = {}

    def _read_headers(self):
        while True:
            line = self._read_line()
            if not line or line == b"\r\n":
                break
            if b":" in line:
                k, v = line.split(b":", 1)
                self.headers[k.decode().lower()] = v.strip().decode()

    def _read_line(self):
        line = b""
        while True:
            b = self.raw.recv(1)
            if not b:
                return line
            line = line + b
            if line.endswith(b"\n"):
                return line

    @property
    def text(self):
        return self.content.decode(self.encoding)

    @property
    def content(self):
        if self._cached is None:
            cl = self.headers.get("content-length")
            if cl:
                cl = int(cl)
                self._cached = b""
                while len(self._cached) < cl:
                    chunk = self.raw.recv(min(256, cl - len(self._cached)))
                    if not chunk:
                        break
                    self._cached = self._cached + chunk
            else:
                self._cached = b""
                while True:
                    chunk = self.raw.recv(256)
                    if not chunk:
                        break
                    self._cached = self._cached + chunk
            if self.raw:
                self.raw.close()
                self.raw = None
        return self._cached

    def json(self):
        import json
        return json.loads(self.text)

    def close(self):
        if self.raw:
            self.raw.close()
            self.raw = None


def request(method, url, data=None, json_data=None, headers=None):
    # Parse URL
    # Parse URL
    use_ssl = False
    if url.startswith("http://"):
        url = url[7:]
        port = 80
    elif url.startswith("https://"):
        url = url[8:]
        port = 443
        use_ssl = True
    else:
        raise ValueError("Unsupported protocol")

    # Separate host and path
    slash = url.find("/")
    if slash < 0:
        host = url
        path = "/"
    else:
        host = url[:slash]
        path = url[slash:]

    # Separate host and port
    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)

    # DNS + connect
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(addr)

    # Wrap with TLS if HTTPS
    if use_ssl:
        import ssl
        s = ssl.wrap_socket(s, server_hostname=host)

    # Build request
    s.send(b"%s %s HTTP/1.0\r\n" % (method, path))
    s.send(b"Host: %s\r\n" % host)

    if headers:
        for k in headers:
            s.send(b"%s: %s\r\n" % (k, headers[k]))

    if json_data is not None:
        import json
        data = json.dumps(json_data)
        s.send(b"Content-Type: application/json\r\n")

    if data:
        if isinstance(data, str):
            data = data.encode()
        s.send(b"Content-Length: %d\r\n" % len(data))

    s.send(b"\r\n")

    if data:
        s.send(data)

    # Parse response
    resp = Response(s)
    line = resp._read_line()
    # HTTP/1.0 200 OK\r\n
    parts = line.split(None, 2)
    resp.status_code = int(parts[1])
    resp.reason = parts[2].strip().decode() if len(parts) > 2 else ""
    resp._read_headers()

    return resp


def get(url, **kw):
    return request(b"GET", url, **kw)


def post(url, **kw):
    return request(b"POST", url, **kw)


def put(url, **kw):
    return request(b"PUT", url, **kw)


def delete(url, **kw):
    return request(b"DELETE", url, **kw)


def head(url, **kw):
    return request(b"HEAD", url, **kw)
