import socket
import sys
import threading

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

KEY_SIZE_BITS = 2048
BLOCK_SIZE = KEY_SIZE_BITS // 8 # 256 bytes
OAEP_HASH = hashes.SHA256
MAX_CHUNK = BLOCK_SIZE - 2 * OAEP_HASH.digest_size - 2 # 190 bytes


def oaep():
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=OAEP_HASH()),
        algorithm=OAEP_HASH(),
        label=None,
    )

# create a rsa key pair
def create_keys():
    """Create an RSA 2048 public/private key pair."""
    private_key = rsa.generate_private_key(public_exponent=65537,
                                           key_size=KEY_SIZE_BITS)
    return private_key, private_key.public_key()

# serialize public key to a pem string
def public_key_to_string(public_key):
    """Serialize a public key to a PEM string."""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode()

# load a public key from a pem string
def string_to_public_key(text):
    return serialization.load_pem_public_key(text.encode())

# encrypt messages using rsa
def encrypt_message(message, public_key):
    data = message.encode()
    ciphertext = b""
    for i in range(0, len(data), MAX_CHUNK):
        ciphertext += public_key.encrypt(data[i:i + MAX_CHUNK], oaep())
    return ciphertext

# decrypt messages using rsa
def decrypt_message(ciphertext, private_key):
    if len(ciphertext) == 0 or len(ciphertext) % BLOCK_SIZE != 0:
        raise ValueError("ciphertext is not a whole number of RSA blocks")

    plaintext = b""
    for i in range(0, len(ciphertext), BLOCK_SIZE):
        plaintext += private_key.decrypt(ciphertext[i:i + BLOCK_SIZE], oaep())
    return plaintext.decode()

# dictionary of clients
clients = {}
clients_lock = threading.Lock()

# build a response string from a status code
def build_response(status, lines=None):
    if not lines:
        return str(status)

    body = "\n".join(lines)
    return str(status) + "\n\n" + body

# send an unencrypted response
def send_plain(sock, text):
    sock.sendall(text.encode())

# encrypt a response with the public key and send it
def send_encrypted(sock, public_key, text):
    sock.sendall(encrypt_message(text, public_key))

# sends and encrypted message to one user
def send_to_user(username, status, lines=None):
    with clients_lock:
        entry = clients.get(username)
        if entry is None:
            return
        sock = entry["data"]
        key = entry["key"]
    try:
        send_encrypted(sock, key, build_response(status, lines))
    except (OSError, ValueError):
        pass

# sends an encrypted response to all logged-in users
def send_to_everyone(status, lines=None, skip_user=None):
    with clients_lock:
        recipients = list(clients.keys())

    for name in recipients:
        if name == skip_user:
            continue
        send_to_user(name, status, lines)

# read an encrypted message from a socket
def recv_encrypted(sock):
    buffer = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            return None
        buffer += chunk
        if len(buffer) % BLOCK_SIZE == 0:
            return buffer
        
# report a failed login on the data socket, encrypted when the client's key is known
def send_login_failure(data_sock, client_public_key=None):
    try:
        if client_public_key is not None:
            send_encrypted(data_sock, client_public_key, build_response(500))
        else:
            send_plain(data_sock, build_response(500))
    except (OSError, ValueError):
        pass

# handle a login request from a client
def handle_login(message, data_sock, server_private_key):
    lines = message.split("\n")

    # drop the "login" keyword and any blank separator lines before the body
    body = [line for line in lines[1:] if line.strip() != ""]

    if len(body) < 2:
        print("Login requested by: <malformed request>")
        send_login_failure(data_sock)
        return None

    username = body[0].strip()
    key_text = "\n".join(body[1:])

    print("Login requested by:", username)

    if username == "":
        send_login_failure(data_sock)
        return None

    # validate the public key before registering anything
    try:
        client_public_key = string_to_public_key(key_text)
    except (ValueError, TypeError):
        send_login_failure(data_sock)
        return None

    with clients_lock:
        if username in clients:  # username must be unique
            send_login_failure(data_sock, client_public_key)
            return None
        clients[username] = {"data": data_sock, "key": client_public_key}

    # the join broadcast doubles as the login confirmation for the new user
    send_to_everyone(200, ["join", username])
    return username

# handle a "who" request from a client
def handle_who(username):
    print("Who requested. Sending users.")
    with clients_lock:
        others = [name for name in clients if name != username]
    send_to_user(username, 200, ["who", ", ".join(others)])

# handle a broadcast message from one user to all others
def handle_broadcast(message, username):
    # everything after the "broadcast" keyword is the message text
    parts = message.split(" ", 1)
    text = parts[1] if len(parts) > 1 else ""

    print("Broadcast requested by", username)
    print("Message:", text)

    # each client gets its own encrypted copy
    send_to_everyone(200, ["broadcast", username, text])

# handle a private message from one user to another
def handle_private(message, username):
    parts = message.split(" ", 2)
    if len(parts) < 3 or parts[1].strip() == "" or parts[2] == "":
        send_to_user(username, 500)
        return

    recipient = parts[1].strip()
    text = parts[2]

    print("Private message from", username, "to", recipient)

    with clients_lock:
        known = recipient in clients

    if not known:
        send_to_user(username, 500)
        return

    send_to_user(recipient, 200, ["private", username, text])
    send_to_user(username, 200, ["sent", recipient])

# handle a single client connection on the control socket
def handle_client(control_sock, server_private_key, server_public_key):
    username = None
    data_listener = None
    data_sock = None

    try:
        raw = control_sock.recv(1024)
        if not raw:
            return

        first = raw.decode(errors="ignore").strip()
        if not first.lower().startswith("connect"):
            send_plain(control_sock, build_response(500))
            return

        print("Connection requested. Creating data socket")

        # bind to port 0 and let the OS choose a free port
        data_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        data_listener.bind(("", 0))
        data_listener.listen(1)
        data_port = data_listener.getsockname()[1]

        # reply on the control socket with the data port and public key
        reply = "200\n\n" + str(data_port) + "\n" + public_key_to_string(server_public_key)
        send_plain(control_sock, reply)

        data_listener.settimeout(30)
        data_sock, _ = data_listener.accept()
        data_listener.settimeout(None)

        while True:
            ciphertext = recv_encrypted(control_sock)
            if ciphertext is None:
                break

            print("Received encrypted message")

            try:
                message = decrypt_message(ciphertext, server_private_key).strip()
            except (ValueError, TypeError):
                # nobody to reply to safely unless logged in
                if username is not None:
                    send_to_user(username, 500)
                continue

            if message == "":
                continue

            command = message.split()[0].split("\n")[0].lower()

            if command == "login":
                if username is not None: # already logged in
                    send_to_user(username, 500)
                    continue

                username = handle_login(message, data_sock, server_private_key)
                if username is None:
                    # failure sent, keep the connection so the client can retry
                    continue

            elif username is None:
                # every other command requires a log in
                break

            elif command == "who":
                handle_who(username)

            elif command == "broadcast":
                handle_broadcast(message, username)

            elif command == "private":
                handle_private(message, username)

            elif command == "quit":
                print("Quit requested by", username)
                send_to_user(username, 200, ["quit"])
                break

            else:
                send_to_user(username, 500)

    except (OSError, ValueError):
        pass

    finally:
        if username is not None:
            with clients_lock:
                clients.pop(username, None)

        for sock in (data_sock, data_listener, control_sock):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass

# main entry point for the server
def main():
    if len(sys.argv) != 2:
        print("Usage: python server.py <control_port>")
        sys.exit(1)

    try:
        control_port = int(sys.argv[1])
    except ValueError:
        print("Port must be a number.")
        sys.exit(1)

    print("Starting server...")

    print("Creating RSA keypair")
    server_private_key, server_public_key = create_keys()
    print("RSA keypair created")

    print("Creating server socket")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("", control_port))
    server_socket.listen()

    print("Awaiting connections...")

    try:
        while True:
            control_sock, _ = server_socket.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(control_sock, server_private_key, server_public_key),
                daemon=True,
            )
            thread.start()
    except KeyboardInterrupt:
        pass
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()