import socket
import threading

def listenForMessages(dataSocket):
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

                serverResponse = clientSocket.recv(1024).decode()

                serverMessage = serverResponse.splitlines()

                if serverMessage[0] == "200": #checking for server response confirmation
                    dataPort = int(serverMessage[-1])

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
             clientSocket.sendall(userInput.encode())

             serverResponse = dataSocket.recv(1024).decode().strip()

             if serverResponse == "200":
                    print(serverMessage[0], "status code received")

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

            if len(userParts) != 2:
                     print("login <username>")
                     continue
                
            clientSocket.sendall(userInput.encode())

            serverResponse = dataSocket.recv(1024).decode().strip()

            if serverResponse == "200":
                    print(serverMessage[0], "status code received. Login successful")
#I commnented out the listener thread due to possible conflict it could have with the context required for project 2
#Since it could receive the file before  it reachs the correct command and cause errors.

          #  if receiverStarted == False:
          #           thread = threading.Thread(
           #          target=listenForMessages, args=(dataSocket,),daemon=True)
           #          thread.start()
           #          receiverStarted = True

            else:
                    print("500 status code received.")

#who command
#    
#    
        elif command == "who":
            if clientSocket is None or dataSocket is None:
                 print("You must connect first.")
                 continue
                   
            clientSocket.sendall(userInput.encode())#send to server

 #           serverResponse = dataSocket.recv(1024).decode()
  #          serverMessage = serverResponse.splitlines()

   #         if serverMessage[0] == "200":
    #             connectedUsers = serverMessage[-1]
     #            print("200 status code received. Users currently connected:", connectedUsers)
                
      #      else:
       #          print("500 status code received.")   

#broadcast command
#
#
        elif command == "broadcast":
            if clientSocket is None or dataSocket is None:
                 print("You must connect first.")
                 continue
            
            if len(userParts) < 2:
                print("broadcast <message>")
                continue

            clientSocket.sendall(userInput.encode())

 #           serverResponse = dataSocket.recv(1024).decode()
  #          serverMessage = serverResponse.splitlines()
#
   #         statusCode = serverMessage[0]

 #           if statusCode == "200":
  #               messageType = serverMessage[2]
   #              senderName = serverMessage[3]
    #             messsageText = serverMessage[4]

     #            if messsageText. endswith(" all!"):
      #                messsageText = messsageText[:-5]

       #          print(statusCode, "status code received.")
        #         print(messageType, "message from", senderName, ":", messsageText)

         #   else:
          #      print("500 status code received")
#private command
#
#
        elif command == "private":
             if clientSocket is None or dataSocket is None:
                 print("You must connect first.")
                 continue
             
             if len(userParts) < 3:
                  print("private <username> <message>")
                  continue
             
             clientSocket.sendall(userInput.encode())

      #       serverResponse = dataSocket.recv(1024).decode()
       #      serverMessage = serverResponse.splitlines()

        #     statusCode = serverMessage[0]

         #    if statusCode == "200":
          #        print("200 status code received. Message sent.")

           #  else:
            #      print("500 status code received.")

# Project 2 
# Requests a list of files currently stored on the server.
# The server responds with 200 and a comma-separated list of filenames.
        elif command == "list":
             if clientSocket is None or dataSocket is None:
                  print("You must connect first.")
                  continue
             
             if len(userParts) != 1:
                  print("list")
                  continue
             
             clientSocket.sendall(userInput.encode())

             serverResponse = dataSocket.recv(1024).decode()
             serverMessage = serverResponse.splitlines()

             if serverMessage[0] == "200":
                  if len(serverMessage) >= 3:
                       print("200 status code received. Files:", serverMessage[2])
                  else:
                       print("200 status code received.")
             else:
                 print("500 status code received.")


# dele command
# Requests the server to delete a file by filename.
# The server responds with 200 if the file was deleted or 500 if it failed.
        elif command == "dele":
             if clientSocket is None or dataSocket is None:
                  print("You must connect first.")
                  continue
             
             if len(userParts) != 2:
                  print("dele <filename>")
                  continue
             
             clientSocket.sendall(userInput.encode())

             serverResponse = dataSocket.recv(1024).decode().strip()

             if serverResponse == "200":
                  print("200 status code received. File deleted.")
             else:
                  print("500 status code received.")


# stor command
# Uploads a local file from the client to the server.
# The command is sent through the control socket and the file contents are sent through the data socket.
        elif command == "stor":
             if clientSocket is None or dataSocket is None:
                  print("You must connect first.")
                  continue
             
             if len(userParts) != 2:
                  print("stor <filename>")
                  continue
             
             filename = userParts[1]

             try:
                  file = open(filename, "rb")
                  fileData = file.read()
                  file.close()
             except OSError:
                  continue
             
             clientSocket.sendall(userInput.encode())
             dataSocket.sendall(fileData)

             serverResponse = dataSocket.recv(1024).decode().strip()

             if serverResponse == "200":
                  print("200 status code received. File Sent.")
             else:
                  print("500 status code received.")



# retr command
# Requests a file from the server and saves the received file contents on the client side.
# The filename is sent through the control socket and the file data comes back through the data socket.
        elif command == "retr":
            if clientSocket is None or dataSocket is None:
                print("You must connect first.")
                continue

            if len(userParts) != 2:
                print("retr <filename>")
                continue

            filename = userParts[1].strip()

            clientSocket.sendall(userInput.encode())

            serverResponse = dataSocket.recv(4096)

            if serverResponse.decode(errors="ignore").startswith("500"):
                print("500 status code received.")
                continue

            newFilename = "downloaded_" + filename

            file = open(newFilename, "wb")
            file.write(serverResponse)
            file.close()

            print("File retrieved.")           
             
        else:
            print("Unknown command.")

if __name__ == "__main__":
    main()