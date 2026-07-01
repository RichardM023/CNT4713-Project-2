import socket
import sys
import threading

clients = {}

# sends a response to a single client
def send_response(sock, status, data=None):
    if data is None:
        message = str(status)
    else:
        message = str(status) + "\n\n" + data
    sock.sendall(message.encode())

# send same message to every logged in user
def send_to_everyone(status, data):
    for sock in list(clients.values()):
        try:
            send_response(sock, status, data)
        except OSError:
            pass

# send a message to everone expcept one user
def send_to_others(status, data, skip_user):
    for name in list(clients.keys()):
        if name == skip_user:
            continue
        try:
            send_response(clients[name], status, data)
        except OSError:
            pass

# handles one client from start to finish
def handle_client(control_sock, data_listener):
    username = None
    data_sock = None

    try:
        data_sock, _ = data_listener.accept()
        # keep reading commands until client disconnects
        while True:
            raw = control_sock.recv(1024)
            if not raw:
                break 

            message = raw.decode().strip()
            if message == "":
                continue

            words = message.split()
            command = words[0].lower()

            # login command
            if command == "login":
                if len(words) > 1:
                    requested_name = words[1]
                else:
                    requested_name = ""

                print("Login requested by:", requested_name)

                # reject empty names or names in use
                if requested_name == "" or requested_name in clients:
                    send_response(data_sock, 500)
                    continue

                # register user
                username = requested_name
                clients[username] = data_sock
                send_response(data_sock, 200)


            # who
            elif command == "who":
                print("Who requested. Sending users.")
                user_list = ", ".join(clients.keys())
                send_response(data_sock, 200, user_list)

            # broadcast
            elif command == "broadcast":
                # everything after the word "broadcast" is the message
                if " " in message:
                    text = message.split(" ", 1)[1]
                else:
                    text = ""

                if username is not None:
                    sender = username
                else:
                    sender = "unknown"

                print("Broadcast requested by", sender)
                print("Message:", text)

                send_to_everyone(200, "Broadcast\n" + sender + "\n" + text)

            # private
            elif command == "private":
                # needs to pass in private "username" "message"
                if len(words) < 3:
                    send_response(data_sock, 500)
                    continue

                # split into 3 pieces: "private", recipient, and the text
                pieces = message.split(" ", 2)
                recipient = pieces[1]
                text = pieces[2]

                if username is not None:
                    sender = username
                else:
                    sender = "unknown"

                print("Private message from", sender, "to", recipient)

                # if recipient is not logged in, send error back to sender
                if recipient not in clients:
                    send_response(data_sock, 500)
                    continue

                # send the message to the recipient, then confirm to the sender
                send_response(clients[recipient], 200,
                              "Private\n" + sender + "\n" + text)
                send_response(data_sock, 200)

            # quit
            elif command == "quit":
                if username is not None:
                    print("Quit requested by", username)
                else:
                    print("Quit requested by client")
                send_response(data_sock, 200)
                break

            # unknown command
            else:
                send_response(data_sock, 500)

    except OSError:
        pass  # a socket error means the client is disconnected

    finally:
        # remove the user and tell everyone they left
        if username is not None:
            if username in clients:
                del clients[username] 
                
        # close all sockets for that client
        for sock in (data_sock, control_sock, data_listener):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


def main():
    # The control port is given on the command line 8991
    if len(sys.argv) != 2:
        print("Usage: python server.py <control_port>")
        sys.exit(1)

    try:
        control_port = int(sys.argv[1])
    except ValueError:
        print("Port must be a number.")
        sys.exit(1)

    print("Starting server...")
    print("Creating server socket")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("", control_port))
    server_socket.listen()

    print("Awaiting connections...")

    try:
        while True:
            # wait for a new client to connect on the control port
            control_sock, _ = server_socket.accept()

            raw = control_sock.recv(1024)
            if not raw:
                control_sock.close()
                continue

            first_command = raw.decode().strip().split()[0].lower()

            # the first thing a client must send is "connect"
            if first_command != "connect":
                send_response(control_sock, 500)
                control_sock.close()
                continue

            print("Connection requested. Creating data socket")

            # create a new socket just for sending data to this client
            # binding to port 0 lets the OS pick any free port for us
            data_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            data_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            data_listener.bind(("", 0))
            data_listener.listen(1)

            # tell client which port to connect to
            data_port = data_listener.getsockname()[1]
            send_response(control_sock, 200, str(data_port))

            # handle the client in its own thread to support multiple concourrnt clients
            client_thread = threading.Thread(
                target=handle_client,
                args=(control_sock, data_listener),
                daemon=True)
            client_thread.start()

    except KeyboardInterrupt:
        pass
    finally:
        server_socket.close()


if __name__ == "__main__":
    main()
