import sys
import socket
import threading
import logging
import random
import hashlib
import asyncio
import subprocess
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLineEdit, QPushButton,
    QVBoxLayout, QTextBrowser, QTabWidget, QListWidget, QMessageBox
)
from PyQt5.QtCore import Qt

# Setting up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Server Monitor")
        self.setup_ui()

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('10.200.236.221', 5555))  # Bind to all interfaces
        self.server.listen(5)

        self.clients = {}  
        self.authenticated_clients = {}  

        self.log_browser.append("Server started...")

        self.accept_thread = threading.Thread(target=self.accept_clients)
        self.accept_thread.daemon = True  # Allows thread to exit when main program exits
        self.accept_thread.start()

        # WebRTC signaling server
        self.signaling_server = web.Application()
        self.signaling_server.router.add_post('/offer', self.offer)
        self.signaling_runner = web.AppRunner(self.signaling_server)
        asyncio.ensure_future(self.start_signaling_server())

    def setup_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        self.log_tab = QWidget()
        self.client_tab = QWidget()

        self.tabs.addTab(self.log_tab, "Log")
        self.tabs.addTab(self.client_tab, "Clients")

        self.setup_log_tab()
        self.setup_client_tab()

        # Add button to run camera.py
        self.camera_button = QPushButton("Join Video Call - [Esc] to Exit")
        self.camera_button.clicked.connect(self.run_camera_script)
        self.layout.addWidget(self.camera_button)

    def setup_log_tab(self):
        self.log_layout = QVBoxLayout(self.log_tab)
        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet("background-color: black; color: green; font-size: 16px;")
        self.log_layout.addWidget(self.log_browser)

        self.message_entry = QLineEdit()
        self.message_entry.setStyleSheet("color: white; font-size: 16px;")
        self.message_entry.returnPressed.connect(self.send_server_message)
        self.log_layout.addWidget(self.message_entry)

        self.send_button = QPushButton("Send Message")
        self.send_button.clicked.connect(self.send_server_message)
        self.log_layout.addWidget(self.send_button)

    def setup_client_tab(self):
        self.client_layout = QVBoxLayout(self.client_tab)
        self.client_list = QListWidget()
        self.client_layout.addWidget(self.client_list)

        self.kick_button = QPushButton("Kick Client")
        self.kick_button.clicked.connect(self.kick_client)
        self.client_layout.addWidget(self.kick_button)

    async def start_signaling_server(self):
        await self.signaling_runner.setup()
        site = web.TCPSite(self.signaling_runner, '0.0.0.0', 8080)
        await site.start()
        self.log_browser.append("WebRTC signaling server started on port 8080...")

    async def offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        self.clients[pc] = params["client_id"]

        @pc.on("datachannel")
        def on_datachannel(channel):
            @channel.on("message")
            async def on_message(message):
                logging.info(f"Received message from {params['client_id']}: {message}")
                for other_pc in self.clients:
                    if other_pc != pc:
                        await other_pc.send(message)

        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            await self.send_ice_candidate(params["client_id"], candidate)

        @pc.on("track")
        def on_track(track):
            logging.info(f"Received track: {track.kind}")
            pc.addTrack(track)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return web.json_response({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })

    async def send_ice_candidate(self, client_id, candidate):
        # Implementation for sending ICE candidates to the client
        pass

    def accept_clients(self):
        while True:
            try:
                client_socket, addr = self.server.accept()
                logging.info(f"Accepted connection from {addr}")
                client_color = "#{:06x}".format(random.randint(0, 0xFFFFFF))

                client_handler = threading.Thread(target=self.handle_client, args=(client_socket, addr, client_color))
                client_handler.daemon = True
                client_handler.start()
            except Exception as e:
                logging.error(f"Error accepting clients: {e}")

    def handle_client(self, client_socket, client_address, client_color):
        if self.authenticate(client_socket, client_address):
            self.clients[client_socket] = client_address
            receive_thread = threading.Thread(target=self.receive, args=(client_socket, client_address, client_color))
            receive_thread.daemon = True
            receive_thread.start()

    def authenticate(self, client_socket, client_address):
        try:
            client_socket.send("PASSWORD:".encode('utf-8'))
            password = client_socket.recv(1024).decode('utf-8')
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if hashed_password == hashlib.sha256("MCCTC".encode()).hexdigest():  # Store hashed password securely
                self.authenticated_clients[client_socket] = client_address
                self.update_client_list()
                client_socket.send("AUTH_SUCCESS".encode('utf-8'))
                return True
            else:
                client_socket.send("AUTH_FAIL".encode('utf-8'))
                client_socket.close()
                return False
        except Exception as e:
            logging.error(f"Authentication error with {client_address}: {e}")
            return False

    def receive(self, client_socket, client_address, client_color):
        try:
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                logging.info(f"Received from {client_address}: {data}")

                self.broadcast_message(data, client_socket)

                message = f"<span style='color:{client_color}'>Received from {client_address}: {data}</span>"
                self.log_browser.append(message)
                self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())
        except Exception as e:
            logging.error(f"Error receiving data from {client_address}: {e}")
        finally:
            self.disconnect_client(client_socket, client_address)

    def broadcast_message(self, message, sender_socket):
        for client in self.authenticated_clients.keys():
            if client != sender_socket:
                try:
                    client.send(message.encode('utf-8'))
                except Exception as e:
                    logging.error(f"Error broadcasting message to a client: {e}")

    def send_server_message(self):
        message = self.message_entry.text()
        if message:
            self.broadcast_message(message, None)
            server_message = f"<span style='color:green'>Server Message: {message}</span>"
            self.log_browser.append(server_message)
            self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())
            self.message_entry.clear()

    def update_client_list(self):
        self.client_list.clear()
        for client_address in self.authenticated_clients.values():
            self.client_list.addItem(f"{client_address}")

    def kick_client(self):
        selected_items = self.client_list.selectedItems()
        if selected_items:
            selected_item = selected_items[0]
            client_info = selected_item.text()

            for client_socket, client_address in list(self.authenticated_clients.items()):
                if f"{client_address}" == client_info:
                    client_socket.send("KICK".encode('utf-8'))
                    client_socket.close()
                    del self.authenticated_clients[client_socket]
                    self.update_client_list()
                    self.log_browser.append(f"<span style='color:red'>Kicked client: {client_address}</span>")
                    self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())
                    break

    def disconnect_client(self, client_socket, client_address):
        client_socket.close()
        if client_socket in self.authenticated_clients:
            del self.authenticated_clients[client_socket]
            self.update_client_list()
            self.log_browser.append(f"<span style='color:red'>Client disconnected: {client_address}</span>")
            self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())

    def run_camera_script(self):
        try:
            subprocess.Popen(["python", "camera.py"])
        except Exception as e:
            logging.error(f"Failed to run camera.py: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ServerGUI()
    gui.show()
    sys.exit(app.exec_())
