import asyncio
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, ttk
import mss
import av
import sounddevice as sd
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, AudioStreamTrack, RTCConfiguration, RTCIceServer
from PIL import Image, ImageTk

# ==== STUN ====
ICE_CONFIG = RTCConfiguration(
    iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
)

# ==== Глобальные переменные ====
pc = None
loop = asyncio.new_event_loop()
dc_holder = {"dc": None}
screen_sharing = False
mic_enabled = False
video_task = None
audio_task = None
screen_window = None
screen_label = None

# ==== Tkinter GUI ====
root = tk.Tk()
root.title("P2P Meeting")

# Chat
text_area = scrolledtext.ScrolledText(root, width=60, height=10)
text_area.pack(padx=10, pady=5)
entry = tk.Entry(root, width=50)
entry.pack(side=tk.LEFT, padx=10, pady=5)

def append_text(msg):
    text_area.insert(tk.END, msg + "\n")
    text_area.see(tk.END)

def send_message():
    dc = dc_holder["dc"]
    if dc and dc.readyState == "open":
        msg = entry.get()
        if msg:
            dc.send(msg)
            append_text("[Me]: " + msg)
            entry.delete(0, tk.END)
    else:
        append_text("[Error] DataChannel не открыт!")

send_btn = tk.Button(root, text="Send", command=send_message)
send_btn.pack(side=tk.LEFT, padx=5, pady=5)

# Video preview
video_label = tk.Label(root)
video_label.pack(padx=10, pady=5)

# Mic selection
mic_var = tk.StringVar()
mic_list = [d['name'] for d in sd.query_devices() if d['max_input_channels']>0]
if mic_list:
    mic_var.set(mic_list[0])
mic_dropdown = ttk.Combobox(root, values=mic_list, textvariable=mic_var)
mic_dropdown.pack(padx=5, pady=5)

# Offer / Answer поля
offer_text = tk.Text(root, height=10, width=60)
offer_text.pack(padx=10, pady=5)
answer_text = tk.Text(root, height=10, width=60)
answer_text.pack(padx=10, pady=5)

# ==== Видео трек ====
class ScreenTrack(VideoStreamTrack):
    def __init__(self, fps=8):
        super().__init__()
        self.sct = mss.mss()
        self.fps = fps

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        img = self.sct.grab(self.sct.monitors[1])
        frame = av.VideoFrame.from_image(img).reformat(format="yuv420p")
        frame.pts = pts
        frame.time_base = time_base
        await asyncio.sleep(1/self.fps)
        return frame

# ==== Микрофон ====
class MicTrack(AudioStreamTrack):
    def __init__(self, device=None):
        super().__init__()
        self.device = device

    async def recv(self):
        frames = sd.rec(1024, samplerate=48000, channels=1, dtype='int16', device=self.device)
        sd.wait()
        frame = av.AudioFrame.from_ndarray(frames.T, format='s16', layout='mono')
        frame.sample_rate = 48000
        return frame

# ==== P2P функции ====
def start_host():
    global pc
    pc = RTCPeerConnection(ICE_CONFIG)

    # DataChannel
    dc = pc.createDataChannel("chat")
    dc_holder["dc"] = dc

    @dc.on("message")
    def on_message(msg):
        root.after(0, append_text, "[Client]: " + msg)

    threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(host_coro(), loop), daemon=True).start()

async def host_coro():
    global pc, screen_sharing, mic_enabled, audio_task, video_task, screen_window, screen_label
    if screen_sharing:
        track = ScreenTrack()
        pc.addTrack(track)

        # Отображение своего экрана в отдельном окне
        if not screen_window:
            screen_window = tk.Toplevel()
            screen_window.title("Ваш экран")
            screen_label = tk.Label(screen_window)
            screen_label.pack()
        async def preview_loop():
            while True:
                frame = await track.recv()
                img = frame.to_image().resize((640,360))
                imgtk = ImageTk.PhotoImage(img)
                screen_label.imgtk = imgtk
                screen_label.config(image=imgtk)
        video_task = asyncio.create_task(preview_loop())

    if mic_enabled:
        for i,d in enumerate(sd.query_devices()):
            if d['name']==mic_var.get() and d['max_input_channels']>0:
                audio_track = MicTrack(i)
                pc.addTrack(audio_track)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Показать Offer в GUI
    offer_text.delete("1.0", tk.END)
    offer_text.insert(tk.END, json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}))
    append_text("Offer сгенерирован. Отправьте клиенту.")

def set_answer():
    answer_json = answer_text.get("1.0", tk.END).strip()
    if not answer_json:
        append_text("Answer пустой!")
        return
    answer = json.loads(answer_json)
    asyncio.run_coroutine_threadsafe(
        pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"])),
        loop
    )
    append_text("P2P соединение установлено!")

def start_client():
    global pc
    pc = RTCPeerConnection(ICE_CONFIG)

    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            async def video_loop():
                while True:
                    frame = await track.recv()
                    img = frame.to_image().resize((640,360))
                    imgtk = ImageTk.PhotoImage(img)
                    video_label.imgtk = imgtk
                    video_label.config(image=imgtk)
            global video_task
            video_task = asyncio.create_task(video_loop())
        elif track.kind == "audio":
            root.after(0, append_text, "[Info] Audio track подключён")

    @pc.on("datachannel")
    def on_dc(channel):
        dc_holder["dc"] = channel
        @channel.on("message")
        def on_message(msg):
            root.after(0, append_text, "[Host]: " + msg)

    threading.Thread(target=lambda: asyncio.run_coroutine_threadsafe(client_coro(), loop), daemon=True).start()

async def client_coro():
    global pc
    offer_json = offer_text.get("1.0", tk.END).strip()
    if not offer_json:
        append_text("Ошибка: Offer пустой")
        return
    await pc.setRemoteDescription(RTCSessionDescription(**json.loads(offer_json)))

    if mic_enabled:
        for i,d in enumerate(sd.query_devices()):
            if d['name']==mic_var.get() and d['max_input_channels']>0:
                audio_track = MicTrack(i)
                pc.addTrack(audio_track)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    answer_text.delete("1.0", tk.END)
    answer_text.insert(tk.END, json.dumps({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}))
    append_text("Answer сгенерирован. Отправьте хосту.")

# ==== GUI кнопки ====
def toggle_screen():
    global screen_sharing
    screen_sharing = not screen_sharing
    btn_screen.config(text="Остановить шаринг" if screen_sharing else "Начать шаринг")
    append_text(f"Шаринг экрана {'включен' if screen_sharing else 'выключен'}")

def toggle_mic():
    global mic_enabled
    mic_enabled = not mic_enabled
    btn_mic.config(text="Отключить микрофон" if mic_enabled else "Включить микрофон")
    append_text(f"Микрофон {'включен' if mic_enabled else 'выключен'}")

def end_meeting():
    global pc, video_task, screen_window
    if pc:
        asyncio.run_coroutine_threadsafe(pc.close(), loop)
        pc = None
    if video_task:
        video_task.cancel()
        video_task = None
    if screen_window:
        screen_window.destroy()
        screen_window = None
    append_text("Встреча завершена.")

btn_screen = tk.Button(root, text="Начать шаринг экрана", command=toggle_screen)
btn_screen.pack(side=tk.LEFT, padx=5, pady=5)
btn_mic = tk.Button(root, text="Включить микрофон", command=toggle_mic)
btn_mic.pack(side=tk.LEFT, padx=5, pady=5)
btn_host = tk.Button(root, text="Создать комнату", command=start_host)
btn_host.pack(side=tk.LEFT, padx=5, pady=5)
btn_client = tk.Button(root, text="Подключиться", command=start_client)
btn_client.pack(side=tk.LEFT, padx=5, pady=5)
btn_set_answer = tk.Button(root, text="Применить Answer", command=set_answer)
btn_set_answer.pack(side=tk.LEFT, padx=5, pady=5)
btn_end = tk.Button(root, text="Завершить встречу", command=end_meeting)
btn_end.pack(side=tk.LEFT, padx=5, pady=5)

# ==== Запуск asyncio loop в отдельном потоке ====
def start_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=start_loop, args=(loop,), daemon=True).start()

root.mainloop()






