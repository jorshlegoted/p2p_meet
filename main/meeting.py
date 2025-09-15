import socket
import threading
import tkinter as tk
from tkinter import messagebox

# Simple P2P text chat application for direct communication between two users
# Uses TCP sockets for safe and minimal peer-to-peer messaging
# Designed for educational purposes, no malicious intent

def get_local_ip():
    """Retrieve local IP address for display (use public IP for remote connections)"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)  # Add timeout to avoid hanging
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class ChatWindow:
    """Class to handle the chat interface and messaging"""
    def __init__(self, root, conn=None, is_host=False):
        self.root = root
        self.conn = conn
        self.is_host = is_host

        self.chat_log = tk.Text(root, state='disabled', width=50, height=20)
        self.chat_log.pack(padx=10, pady=10)

        self.message_entry = tk.Entry(root, width=50)
        self.message_entry.pack(padx=10, pady=5)
        self.message_entry.bind("<Return>", self.send_message)

        self.send_button = tk.Button(root, text="Send", command=self.send_message)
        self.send_button.pack(pady=5)

        if self.conn:
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

    def send_message(self, event=None):
        """Send a text message to the connected peer"""
        message = self.message_entry.get()
        if message:
            self.message_entry.delete(0, tk.END)
            self.display_message(f"You: {message}")
            try:
                self.conn.send(message.encode('utf-8'))
            except Exception as e:
                messagebox.showerror("Error", f"Connection lost: {e}")
                self.root.quit()

    def receive_messages(self):
        """Receive messages from the connected peer"""
        while True:
            try:
                message = self.conn.recv(1024).decode('utf-8')
                if message:
                    self.display_message(f"Peer: {message}")
                else:
                    break
            except Exception as e:
                messagebox.showerror("Error", f"Connection closed: {e}")
                break
        self.root.quit()

    def display_message(self, message):
        """Display a message in the chat log"""
        self.chat_log.config(state='normal')
        self.chat_log.insert(tk.END, message + "\n")
        self.chat_log.config(state='disabled')
        self.chat_log.see(tk.END)

def host_room():
    """Host a chat room and wait for a peer to connect"""
    host_win = tk.Toplevel(root)
    host_win.title("Hosting Room")

    port = 5555
    local_ip = get_local_ip()

    label = tk.Label(host_win, text=f"Room created. IP: {local_ip}, Port: {port}\nShare with peer (use public IP if behind NAT)")
    label.pack(pady=10)

    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.settimeout(60)  # Timeout to prevent hanging
        server.bind(('', port))
        server.listen(1)

        conn, addr = server.accept()
        label.config(text=f"Connected to {addr}")

        chat_win = tk.Toplevel(root)
        chat_win.title("Chat")
        ChatWindow(chat_win, conn=conn, is_host=True)

        host_win.destroy()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to host: {e}")
        host_win.destroy()

def join_room():
    """Connect to a peer's chat room"""
    join_win = tk.Toplevel(root)
    join_win.title("Join Room")

    tk.Label(join_win, text="Peer IP:").pack()
    ip_entry = tk.Entry(join_win)
    ip_entry.pack()

    tk.Label(join_win, text="Peer Port (default 5555):").pack()
    port_entry = tk.Entry(join_win)
    port_entry.insert(0, "5555")
    port_entry.pack()

    def connect():
        ip = ip_entry.get()
        try:
            port = int(port_entry.get())
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(10)  # Timeout for connection attempt
            client.connect((ip, port))

            chat_win = tk.Toplevel(root)
            chat_win.title("Chat")
            ChatWindow(chat_win, conn=client)

            join_win.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")

    tk.Button(join_win, text="Connect", command=connect).pack(pady=10)

# Main window for the P2P chat application
root = tk.Tk()
root.title("P2P Text Chat")

tk.Button(root, text="Create Room", command=lambda: threading.Thread(target=host_room).start()).pack(pady=10)
tk.Button(root, text="Connect to Room", command=join_room).pack(pady=10)

root.mainloop()





