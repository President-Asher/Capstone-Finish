import socket
import threading
import cv2
import pickle
import struct
import time

# Server configuration
server_ip = '10.200.236.221'  # Replace with server's IP address
server_port = 5000

def receive_frames(client_socket, stop_event):
    data = b""
    payload_size = struct.calcsize("Q")
    window_name = "Camera Feed"
    window_initialized = False
    frames = {}

    while not stop_event.is_set():
        try:
            while len(data) < payload_size:
                packet = client_socket.recv(4*1024)  # 4KB
                if not packet:
                    return
                data += packet

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]

            while len(data) < msg_size:
                data += client_socket.recv(4*1024)
            frame_data = data[:msg_size]
            data = data[msg_size:]

            client_id, frame = pickle.loads(frame_data)

            if not window_initialized:
                cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
                cv2.imshow(window_name, frame)
                window_initialized = True
            else:
                frames[client_id] = frame
                combined_frame = frames[0]
                for i in range(1, len(frames)):
                    combined_frame = cv2.hconcat([combined_frame, frames[i]])
                cv2.imshow(window_name, combined_frame)

            if cv2.waitKey(1) & 0xFF == 27:  # Esc key
                stop_event.set()
                break
        except Exception as e:
            print(f"Error: {e}")
            break

def send_frames(client_socket, stop_event):
    cap = cv2.VideoCapture(0)
    while not stop_event.is_set():
        try:
            ret, frame = cap.read()
            if not ret:
                break
            data = pickle.dumps(frame)
            message = struct.pack("Q", len(data)) + data
            client_socket.sendall(message)
        except Exception as e:
            print(f"Error: {e}")
            break

def connect_to_server():
    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((server_ip, server_port))
            print("Connected to server")

            stop_event = threading.Event()

            receive_thread = threading.Thread(target=receive_frames, args=(client_socket, stop_event))
            receive_thread.start()

            send_thread = threading.Thread(target=send_frames, args=(client_socket, stop_event))
            send_thread.start()

            receive_thread.join()
            send_thread.join()
            client_socket.close()
            break
        except Exception as e:
            print(f"Connection error: {e}")
            time.sleep(5)  # Wait for 5 seconds before trying to reconnect

if __name__ == "__main__":
    connect_to_server()
