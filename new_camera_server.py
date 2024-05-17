import socket
import threading
import cv2
import pickle
import struct

# Server configuration
server_ip = '10.200.236.221'
server_port = 5000
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((server_ip, server_port))
server_socket.listen(5)

clients = []
lock = threading.Lock()

def broadcast_frame(client_id, frame):
    with lock:
        for client_socket in clients:
            try:
                data = pickle.dumps((client_id, frame))
                message = struct.pack("Q", len(data)) + data
                client_socket.sendall(message)
            except:
                clients.remove(client_socket)

def handle_client(client_socket, client_id):
    data = b""
    payload_size = struct.calcsize("Q")
    while True:
        try:
            while len(data) < payload_size:
                packet = client_socket.recv(4*1024)
                if not packet:
                    break
                data += packet

            if len(data) >= payload_size:
                packed_msg_size = data[:payload_size]
                data = data[payload_size:]
                msg_size = struct.unpack("Q", packed_msg_size)[0]

                while len(data) < msg_size:
                    data += client_socket.recv(4*1024)

                frame_data = data[:msg_size]
                data = data[msg_size:]

                frame = pickle.loads(frame_data)
                broadcast_frame(client_id, frame)
        except Exception as e:
            print(f"Error: {e}")
            break

    with lock:
        if client_socket in clients:
            clients.remove(client_socket)
    client_socket.close()

def start_server():
    print("Server started...")
    client_id_counter = 0
    while True:
        try:
            client_socket, addr = server_socket.accept()
            print(f"Connection from {addr}")
            with lock:
                clients.append(client_socket)
                client_id = client_id_counter
                client_id_counter += 1
            threading.Thread(target=handle_client, args=(client_socket, client_id)).start()
        except Exception as e:
            print(f"Server accept error: {e}")

if __name__ == "__main__":
    start_server()
