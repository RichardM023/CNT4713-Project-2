import socket
import threading
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

KEY_SIZE_BITS = 2048
BLOCK_SIZE = KEY_SIZE_BITS // 8
OAEP_HASH = hashes.SHA256
MAX_CHUNK = BLOCK_SIZE - 2 * OAEP_HASH.digest_size - 2


def oaep():
    return padding.OAEP(
        mgf=padding.MGF1(algorithm=OAEP_HASH()),
        algorithm=OAEP_HASH(),
        label=None
    )


def createKeys():
    privateKey = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE_BITS
    )
    publicKey = privateKey.public_key()
    return privateKey, publicKey


def publicKeyToString(publicKey):
    pem = publicKey.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return pem.decode()


def stringToPublicKey(publicKeyText):
    return serialization.load_pem_public_key(publicKeyText.encode())

def recvEncrypted(sock): #helper function for receiving the encrpyted data from the server
    buffer = b""

    while True:
        chunk = sock.recv(4096)

        if not chunk:
            return None

        buffer += chunk

        if len(buffer) % BLOCK_SIZE == 0:
            return buffer


def encryptMessage(message, publicKey):
    data = message.encode()
    encryptedMessage = b""

    for i in range(0, len(data), MAX_CHUNK):
        encryptedMessage += publicKey.encrypt(data[i:i + MAX_CHUNK], oaep())

    return encryptedMessage


def decryptMessage(encryptedMessage, privateKey):
    if len(encryptedMessage) == 0 or len(encryptedMessage) % BLOCK_SIZE != 0:
        raise ValueError("ciphertext is not a whole number of RSA blocks")

    decryptedMessage = b""

    for i in range(0, len(encryptedMessage), BLOCK_SIZE):
        decryptedMessage += privateKey.decrypt(
            encryptedMessage[i:i + BLOCK_SIZE],
            oaep()
        )

    return decryptedMessage.decode()


def listenForMessages(dataSocket, clientPrivateKey): #clientPrivateKey needs to be implemented into the listening thread
    while True:
        try:
            serverResponse = dataSocket.recv(1024).decode()

            if serverResponse == "":
                break

            serverMessage = serverResponse.splitlines()

            if len(serverMessage) == 0:
                continue

            if serverMessage[0] == "500":
                print("\n500 status code received.")
                print("> ", end="", flush=True)
                continue

            if len(serverMessage) >= 5 and serverMessage[2] == "Broadcast": #check for broadcast command
                senderName = serverMessage[3]
                messageText = serverMessage[4]

                if messageText.endswith(" all!"):
                    messageText = messageText[:-5]

                print()
                print("200 status code received.")
                print("Broadcast message from", senderName + ":", messageText)

            elif len(serverMessage) >= 5 and serverMessage[2] == "Private": #check for private command
                senderName = serverMessage[3]
                messageText = serverMessage[4]

                print()
                print("200 status code received. Message sent.")
                print(senderName + ":", messageText)

            elif len(serverMessage) >= 3: #check for who command
                connectedUsers = serverMessage[2]

                print()
                print("200 status code received. Users currently connected:", connectedUsers)

            else:
                print()
                print("200 status code received.")

            print("> ", end="", flush=True)

        except OSError:
            break

def main():
    print("Starting client....")

    clientSocket = None
    dataSocket = None
    receiverStarted = False

    clientPrivateKey, clientPublicKey = createKeys()
    serverPublicKey = None
    
    while True:
        userInput = input("> ").strip()

        if userInput == "":
            continue

        userParts = userInput.split()
        command = userParts[0].lower()

#connect command
#
#
        if command == "connect":
            if len(userParts) != 3:
                print("connect <ip> <port>")
                continue

            clientIp = userParts[1]

            try:
                clientPort = int(userParts[2])
            except ValueError:
                print("Port must be a number.")
                continue

            clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            try:
                clientSocket.connect((clientIp, clientPort)) # creating inital connection socket
                clientSocket.sendall(userInput.encode())

                serverResponse = clientSocket.recv(4096).decode()

                serverMessage = serverResponse.splitlines()

                if serverMessage[0] == "200": #checking for server response confirmation; Encrypt
                    dataPort = int(serverMessage[2])

                    serverPublicKeyText = "\n".join(serverMessage[3:])
                    serverPublicKey = stringToPublicKey(serverPublicKeyText)
                    

                    print(serverMessage[0], "status code received. Starting data connection on port", dataPort)

                    dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #creating data connection socket
                    dataSocket.connect((clientIp, dataPort))

                    print("Data connection established")

                else:
                    print("500 status code received.")

            except OSError:
                print("could not connect to server.")
                clientSocket.close()

#quit command
#
#
        elif command == "quit":
            if clientSocket is None or dataSocket is None:
                print("You must connect first.")
                continue

            if serverPublicKey is None:
                print("You must connect first.")
                continue

            encryptedCommand = encryptMessage(userInput, serverPublicKey)
            clientSocket.sendall(encryptedCommand) #send to server

            encryptedResponse = recvEncrypted(dataSocket) #receive response

            if encryptedResponse is None:
                print("500 status code received.") #check for response
                continue

            print("Received encrypted message") #client confirmation

            serverResponse = decryptMessage(encryptedResponse, clientPrivateKey)
            serverMessage = serverResponse.splitlines() 

            if len(serverMessage) > 0 and serverMessage[0] == "200":
                print("200 status code received.")
            else:
                print("500 status code received.")

            clientSocket.close()
            dataSocket.close()
            break

#login command
# 
#             
        elif command == "login":
            if clientSocket is None or dataSocket is None:
                print("You must connect first.")
                continue

            if serverPublicKey is None:
                 print("You must connect first.")
                 continue

            if len(userParts) != 2:
                     print("login <username>")
                     continue

            username = userParts[1]
            clientPublicKeyText = publicKeyToString(clientPublicKey)

            loginMessage = "login\n\n" + username + "\n" + clientPublicKeyText #message being sent to the server formatted with they key

            encryptedLogin = encryptMessage(loginMessage, serverPublicKey) # encrypt the login message using the server's public key

            clientSocket.sendall(encryptedLogin) # send encrypted login over the control socket

            encryptedResponse = recvEncrypted(dataSocket)

            if encryptedResponse is None:
                print("500 status code received.")
                continue

            print("Received encrypted message")

            serverResponse = decryptMessage(encryptedResponse, clientPrivateKey)
            serverMessage = serverResponse.splitlines() #receive response from server

            if len(serverMessage) > 0 and serverMessage[0] == "200": #check server message formatting
                print("200 status code received. Login successful")

#Bring listener thread back for project 3

                if receiverStarted == False:
                    thread = threading.Thread(
                        target=listenForMessages, args=(dataSocket, clientPrivateKey),daemon=True)
                    thread.start()
                    receiverStarted = True
            else:
                    print("500 status code received.")

#who command
#    
#    
        elif command == "who":
            if clientSocket is None or dataSocket is None:
                 print("You must connect first.")
                 continue

            if serverPublicKey is None:
                print("You must connect first.")
                continue

            if len(userParts) != 1: #check for formatting
                print("who")
                continue

            encryptedCommand = encryptMessage(userInput, serverPublicKey)       
            clientSocket.sendall(encryptedCommand) #send to server 

#broadcast command
#
#
        elif command == "broadcast":
            if clientSocket is None or dataSocket is None:
                 print("You must connect first.")
                 continue

            if serverPublicKey is None:
                print("You must connect first.")
                continue
            
            if len(userParts) < 2: #check for formatting
                print("broadcast <message>")
                continue

            encryptedCommand = encryptMessage(userInput, serverPublicKey)
            clientSocket.sendall(encryptedCommand) #send to server

#private command
#
#
        elif command == "private":
             if clientSocket is None or dataSocket is None:
                 print("You must connect first.")
                 continue

             if serverPublicKey is None:
                 print("You must connect first.")
                 continue
             
             if len(userParts) < 3: #check for formatting
                  print("private <username> <message>")
                  continue
             
             encryptedCommand = encryptMessage(userInput, serverPublicKey)
             clientSocket.sendall(encryptedCommand) #send to server


        else:
            print("Unknown command.")


if __name__ == "__main__":
    main()