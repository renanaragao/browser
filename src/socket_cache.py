import select
import socket
import ssl

SOCKETS: dict[str, list[socket.socket]] = {}


class SocketCache:
    def __init__(self) -> None:
        pass

    def connect(self, scheme: str, host: str, port: int):
        self.scheme = scheme
        self.host = host
        self.port = port
        self.sock = self._get_socket()
        return self

    def send(self, data: bytes, flags: int = 0):
        assert self.sock is not None
        self.sock.sendall(data, flags)
        return self.sock.makefile("rb")

    def close(self, force: bool = False):
        if self.sock is None:
            return

        if force:
            self.sock.close()
            self._remove_socket(self.sock)
        # Se force=False (keep-alive), não fecha o socket: ele permanece aberto em SOCKETS!
        self.sock = None

    def _get_socket(self) -> socket.socket:
        key = self._get_key()
        sockets = SOCKETS.setdefault(key, [])

        # Procura um socket vivo no pool
        for s in list(sockets):
            if self._is_socket_alive(s):
                return s
            else:
                # Limpa sockets mortos do cache
                s.close()
                sockets.remove(s)

        # Se não encontrou nenhum vivo, cria um já conectado e guarda no cache
        s = self._create_socket()
        if len(sockets) < 6:
            sockets.append(s)
        return s

    def _create_socket(self) -> socket.socket:
        assert self.host is not None and self.port is not None
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        s.connect((self.host, self.port))

        if self.scheme == "https":
            ctx = ssl.create_default_context()
            s = ctx.wrap_socket(s, server_hostname=self.host)

        return s

    def _remove_socket(self, s: socket.socket):
        sockets = SOCKETS.get(self._get_key(), [])
        if s in sockets:
            sockets.remove(s)

    def _get_key(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    def _is_socket_alive(self, s: socket.socket) -> bool:
        try:
            readable, _, _ = select.select([s], [], [], 0)
            if readable:
                data = s.recv(1, socket.MSG_PEEK)
                if not data:
                    return False
            return True
        except (OSError, ssl.SSLError):
            return False
