import json
import socket
import threading


LIGHT_STATE_PROPS = ["power", "bright", "color_mode", "ct", "rgb", "hue", "sat", "name", "fw_ver"]


class YeelightClient:
    def __init__(self):
        self.host = ""
        self.port = 55443
        self.command_sock = None
        self.listener = None
        self.command_id = 1
        self.lock = threading.Lock()

    def configure(self, host, port):
        self.host = str(host).strip()
        self.port = int(port)

    def close(self):
        with self.lock:
            if self.command_sock:
                try:
                    self.command_sock.close()
                except Exception:
                    pass
            if self.listener:
                try:
                    self.listener.close()
                except Exception:
                    pass
            self.command_sock = None
            self.listener = None

    def command_socket(self):
        if self.command_sock is None:
            sock = socket.create_connection((self.host, self.port), timeout=1.5)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.command_sock = sock
        return self.command_sock

    def send(self, method, params):
        payload = json.dumps(
            {"id": self.command_id, "method": method, "params": params},
            separators=(",", ":"),
        ).encode("utf-8") + b"\r\n"
        self.command_id += 1

        with self.lock:
            sock = self.command_socket()
            try:
                sock.sendall(payload)
            except OSError:
                self.command_sock = None
                sock = self.command_socket()
                sock.sendall(payload)
            self._drain_response(sock)

    def _drain_response(self, sock):
        previous_timeout = sock.gettimeout()
        try:
            sock.settimeout(0.03)
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    self.command_sock = None
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
        except (OSError, TimeoutError):
            pass
        finally:
            try:
                sock.settimeout(previous_timeout)
            except OSError:
                pass

    def query_properties(self, properties):
        with self.lock:
            command_id = self.command_id
            self.command_id += 1

        payload = json.dumps(
            {"id": command_id, "method": "get_prop", "params": list(properties)},
            separators=(",", ":"),
        ).encode("utf-8") + b"\r\n"

        with socket.create_connection((self.host, self.port), timeout=2.0) as sock:
            sock.settimeout(2.0)
            sock.sendall(payload)
            chunks = []
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break

        response = b"".join(chunks).decode("utf-8", "replace").strip()
        if not response:
            raise RuntimeError("灯具没有返回状态。")

        data = json.loads(response.splitlines()[0])
        if "error" in data:
            message = data["error"].get("message", "未知错误")
            raise RuntimeError(message)
        return data.get("result", [])
