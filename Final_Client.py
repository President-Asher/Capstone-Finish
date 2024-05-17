import sys
import socket
import threading
import subprocess
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QLineEdit, 
                             QPushButton, QVBoxLayout, QTextBrowser, 
                             QInputDialog, QHBoxLayout)
from PyQt5.QtGui import QFont

class ClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.initUI()
        self.setupSocket()
        self.authenticate()

        self.receive_thread = threading.Thread(target=self.receive_messages)
        self.receive_thread.start()

    def initUI(self):
        self.setWindowTitle("Client Chat")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()

        self.initLogBrowser()
        self.initMessageEntry()
        self.initCameraButton()

        self.central_widget.setLayout(self.layout)

    def initLogBrowser(self):
        self.log_browser = QTextBrowser()
        self.log_browser.setStyleSheet("""
            background-color: #2E2E2E; 
            color: #00FF00; 
            font-size: 16px;
            border: none;
        """)
        self.log_browser.setFont(QFont("Courier", 12))
        self.layout.addWidget(self.log_browser)

    def initMessageEntry(self):
        self.entry_layout = QHBoxLayout()

        self.message_entry = QLineEdit()
        self.message_entry.setStyleSheet("""
            background-color: #3E3E3E; 
            color: #FFFFFF; 
            font-size: 16px; 
            padding: 5px;
        """)
        self.message_entry.setFont(QFont("Arial", 12))
        self.message_entry.setPlaceholderText("Type your message here...")
        self.message_entry.returnPressed.connect(self.send_message)
        self.entry_layout.addWidget(self.message_entry)

        self.send_button = QPushButton("Send")
        self.send_button.setStyleSheet("""
            background-color: #007ACC; 
            color: #FFFFFF; 
            font-size: 16px; 
            padding: 5px;
        """)
        self.send_button.setFont(QFont("Arial", 12))
        self.send_button.clicked.connect(self.send_message)
        self.entry_layout.addWidget(self.send_button)

        self.layout.addLayout(self.entry_layout)

    def initCameraButton(self):
        self.camera_button = QPushButton("Join Video Call - [Esc] to Exit")
        self.camera_button.setStyleSheet("""
            background-color: #FF4500; 
            color: #FFFFFF; 
            font-size: 16px; 
            padding: 10px;
        """)
        self.camera_button.setFont(QFont("Arial", 12))
        self.camera_button.clicked.connect(self.run_camera_script)
        self.layout.addWidget(self.camera_button)

    def run_camera_script(self):
        try:
            subprocess.Popen(['python', 'camera.py'])
        except Exception as e:
            self.log_browser.append(f"Error running camera script: {e}")

    def setupSocket(self):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect(('10.200.236.220', 5555))  # Change to the appropriate server IP and port
        self.authenticated = False
        self.username = None

    def authenticate(self):
        try:
            while not self.authenticated:
                password, ok = QInputDialog.getText(self, "Authentication", "Enter Password:", QLineEdit.Password)
                if not ok:
                    self.log_browser.append("Authentication cancelled.")
                    self.client_socket.close()
                    sys.exit()

                self.client_socket.send(password.encode('utf-8'))
                response = self.client_socket.recv(1024).decode('utf-8')
                if response == "AUTH_SUCCESS":
                    self.authenticated = True
                    self.log_browser.append("Authenticated successfully.")
                    self.choose_username()
                    return  # Exit the function to stop re-prompting
                else:
                    self.log_browser.append("Authentication failed. Try again.")
        except Exception as e:
            self.log_browser.append(f"Authentication error: {e}")
            self.client_socket.close()
            sys.exit()

    def choose_username(self):
        try:
            while not self.username:
                username, ok = QInputDialog.getText(self, "Username Selection", "Enter Username:")
                if not ok:
                    self.log_browser.append("Username selection cancelled.")
                    self.client_socket.close()
                    sys.exit()
                if username:
                    self.username = username
                    self.client_socket.send(f"USERNAME:{self.username}".encode('utf-8'))
                    self.log_browser.append(f"Username set to <span style='color:cyan;'>{self.username}</span>")
                else:
                    self.log_browser.append("Username cannot be empty. Please try again.")
        except Exception as e:
            self.log_browser.append(f"Error setting username: {e}")
            self.client_socket.close()
            sys.exit()

    def send_message(self):
        message = self.message_entry.text()
        if message:
            try:
                full_message = f"{self.username}: {message}"
                self.client_socket.send(full_message.encode('utf-8'))
                # Display the user's own message in a different color
                self.log_browser.append(f"<span style='color:cyan;'>{full_message}</span>")
                self.message_entry.clear()
            except Exception as e:
                self.log_browser.append(f"Error sending message: {e}")

    def receive_messages(self):
        while True:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message:
                    if message.startswith(f"{self.username}: "):
                        # If the message is from the user, display it in cyan (already handled in send_message)
                        pass
                    else:
                        self.log_browser.append(f"<span style='color:yellow;'>{message}</span>")
                    self.log_browser.verticalScrollBar().setValue(self.log_browser.verticalScrollBar().maximum())
            except Exception as e:
                self.log_browser.append(f"Error receiving message: {e}")
                self.client_socket.close()
                break

if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = ClientGUI()
    gui.show()
    sys.exit(app.exec_())
