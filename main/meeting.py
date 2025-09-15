import socket
import threading
import tkinter as tk
from tkinter import messagebox

# Function to get local IP (note: for remote connections, use public IP)
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# Chat window class
class ChatWindow:
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
        message = self.message_entry.get()
        if message:
            self.message_entry.delete(0, tk.END)
            self.display_message(f"You: {message}")
            try:
                self.conn.send(message.encode('utf-8'))
            except:
                messagebox.showerror("Error", "Connection lost")
                self.root.quit()

    def receive_messages(self):
        while True:
            try:
                message = self.conn.recv(1024).decode('utf-8')
                if message:
                    self.display_message(f"Peer: {message}")
                else:
                    break
            except:
                break
        messagebox.showerror("Error", "Connection closed")
        self.root.quit()

    def display_message(self, message):
        self.chat_log.config(state='normal')
        self.chat_log.insert(tk.END, message + "\n")
        self.chat_log.config(state='disabled')
        self.chat_log.see(tk.END)

# Host function
def host_room():
    host_win = tk.Toplevel(root)
    host_win.title("Hosting Room")

    port = 5555
    local_ip = get_local_ip()

    label = tk.Label(host_win, text=f"Room created. Your IP: {local_ip} Port: {port}\nShare this with your peer (use public IP if behind NAT)")
    label.pack(pady=10)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('', port))
    server.listen(1)

    conn, addr = server.accept()
    label.config(text=f"Connected to {addr}")

    chat_win = tk.Toplevel(root)
    chat_win.title("Chat")
    ChatWindow(chat_win, conn=conn, is_host=True)

    host_win.destroy()

# Join function
def join_room():
    join_win = tk.Toplevel(root)
    join_win.title("Join Room")

    tk.Label(join_win, text="Peer IP:").pack()
    ip_entry = tk.Entry(join_win)
    ip_entry.pack()

    tk.Label(join_win, text="Peer Port:").pack()
    port_entry = tk.Entry(join_win)
    port_entry.insert(0, "5555")
    port_entry.pack()

    def connect():
        ip = ip_entry.get()
        port = int(port_entry.get())
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect((ip, port))

            chat_win = tk.Toplevel(root)
            chat_win.title("Chat")
            ChatWindow(chat_win, conn=client)

            join_win.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")

    tk.Button(join_win, text="Connect", command=connect).pack(pady=10)

# Main window
root = tk.Tk()
root.title("P2P Chat")

tk.Button(root, text="Create Room", command=lambda: threading.Thread(target=host_room).start()).pack(pady=10)
tk.Button(root, text="Connect to Room", command=join_room).pack(pady=10)

root.mainloop()





