import pygame
import threading
import subprocess
import time
import signal
import os
import psutil
from pydub import AudioSegment
import sounddevice as sd
import numpy as np

print("🔄 Initialisiere Podcast Recorder...")

# === Variablen ===
state = "START"
paused = False
running = True
intro_running = False
intro_skipped = False
stop_recording = False
audio_data_buffer = []
start_time = 0
done_timer_start = 0
select_loop_process = None
ffplay_process = None
device_error = False
selected_intro = ""
categories = [
    ("True Crime", "intro_true_crime.mp3"),
    ("Comedy", "intro_comedy.mp3"),
    ("Nachrichten", "intro_nachrichten.mp3"),
    ("Wissenschaft", "intro_wissenschaft.mp3"),
    ("Geschichte", "intro_geschichte.mp3"),
    ("Gesundheit", "intro_gesundheit.mp3"),
    ("Business", "intro_business.mp3"),
    ("Kultur", "intro_kultur.mp3"),
    ("Sport", "intro_sport.mp3"),
    ("DIREKT", None)
]

pygame.init()
screen = pygame.display.set_mode((1920, 1080), pygame.FULLSCREEN)
font = pygame.font.SysFont(None, 60)
clock = pygame.time.Clock()

def draw_button(text, rect, color):
    pygame.draw.rect(screen, color, rect)
    text_surf = font.render(text, True, (255, 255, 255))
    text_rect = text_surf.get_rect(center=rect.center)
    screen.blit(text_surf, text_rect)

def stop_ffplay():
    global ffplay_process
    try:
        subprocess.run(["killall", "-q", "ffplay"])
    except Exception:
        pass
    ffplay_process = None

def play_intro(intro_filename):
    global state, intro_running, ffplay_process
    stop_ffplay()

    if not os.path.exists(intro_filename):
        print(f"⚠️ Intro-Datei '{intro_filename}' nicht gefunden. Überspringe Intro.")
        state = "SELECT_INTRO"
        return

    print(f"▶️ Spiele Intro: {intro_filename}")
    intro_running = True
    state = "INTRO_PLAYING"
    try:
        ffplay_process = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", intro_filename], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ffplay_process.wait()
    except Exception as e:
        print(f"⚠️ Fehler beim Abspielen von Intro: {e}")

    intro_running = False
    if state == "INTRO_PLAYING":
        print("🧭 Intro zu Ende, wechsle zu SELECT_INTRO")
        state = "SELECT_INTRO"
    else:
        print("🛑 Intro wurde übersprungen oder Zustand verändert – kein automatischer Start der Aufnahme")

def start_select_loop():
    global select_loop_process
    if not os.path.exists("SELECTLOOP.mp3"):
        print("⚠️ SELECTLOOP.mp3 nicht gefunden.")
        return
    stop_select_loop()
    print("🔁 Starte Hintergrundmusik (Loop)...")
    select_loop_process = subprocess.Popen([
        "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-loop", "0", "SELECTLOOP.mp3"
    ])

def stop_select_loop():
    global select_loop_process
    if select_loop_process:
        print("🛑 Stoppe Hintergrundmusik (Loop).")
        select_loop_process.terminate()
        select_loop_process = None

def record_audio():
    global stop_recording, state, audio_data_buffer, start_time, done_timer_start
    if device_error:
        print("❌ Aufnahme nicht möglich – kein Audio-Gerät verfügbar.")
        return
    stop_ffplay()
    print("🔴 Starte Aufnahme...")
    audio_data_buffer = []
    start_time = time.time()

    def audio_callback(indata, frames, time_info, status):
        if indata is not None:
            audio_data_buffer.append(indata.copy())

    with sd.InputStream(samplerate=48000, channels=2, dtype="int16", callback=audio_callback):
        while not stop_recording:
            time.sleep(0.05)

    print("💾 Speichere Aufnahme...")
    full_recording = np.concatenate(audio_data_buffer, axis=0)
    audio_segment = AudioSegment(full_recording.tobytes(), frame_rate=48000, sample_width=2, channels=2)
    filename = time.strftime("Podcast_%Y%m%d_%H%M%S.mp3")
    audio_segment.export(filename, format="mp3")
    print(f"✅ Aufnahme gespeichert: {filename}")
    state = "DONE"
    done_timer_start = pygame.time.get_ticks()

print("🚀 Starte Event Loop")
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            print(f"🖱 Klick erkannt bei: {mouse_pos} im Zustand {state}")
            if state == "START":
                if pygame.Rect(760, 490, 400, 100).collidepoint(mouse_pos):
                    print("👉 Start gedrückt")
                    state = "INTRO"
                    threading.Thread(target=play_intro, args=("intro.mp3",)).start()
            elif state == "INTRO_PLAYING":
                print("⏩ Intro übersprungen")
                if ffplay_process:
                    ffplay_process.terminate()
                    intro_running = False
                    state = "SELECT_INTRO"
            elif state == "SELECT_INTRO":
                print("🧠 Auswahlmenü sichtbar")
                button_width = 600
                button_height = 150
                spacing = 20
                if not select_loop_process:
                    start_select_loop()
                for i, (category, intro) in enumerate(categories):
                    row = i // 2
                    col = i % 2
                    rect_x = 160 + col * (button_width + spacing)
                    rect_y = 100 + row * (button_height + spacing)
                    button_rect = pygame.Rect(rect_x, rect_y, button_width, button_height)
                    if button_rect.collidepoint(mouse_pos):
                        print(f"🎯 Kategorie gewählt: {category}")
                        stop_select_loop()
                        if intro:
                            state = "PLAY_CATEGORY_INTRO"
                            threading.Thread(target=play_intro, args=(intro,)).start()
                        else:
                            state = "RECORDING"
                            threading.Thread(target=record_audio).start()
            elif state == "RECORDING":
                pause_rect = pygame.Rect(560, 600, 350, 150)
                stop_rect = pygame.Rect(1010, 600, 350, 150)
                if pause_rect.collidepoint(mouse_pos):
                    paused = not paused
                    print(f"⏸ Aufnahme {'pausiert' if paused else 'fortgesetzt'}")
                if stop_rect.collidepoint(mouse_pos):
                    stop_recording = True

    screen.fill((30, 30, 30))

    if device_error:
        warning_text = font.render("❌ Kein Audio-Gerät gefunden!", True, (255, 0, 0))
        warning_rect = warning_text.get_rect(center=(960, 540))
        screen.blit(warning_text, warning_rect)
    elif state == "START":
        draw_button("START", pygame.Rect(760, 490, 400, 100), (0, 128, 0))
    elif state == "INTRO_PLAYING":
        loading_text = font.render("🎵 Intro wird abgespielt... (Tippe zum Überspringen)", True, (255, 255, 255))
        loading_rect = loading_text.get_rect(center=(960, 540))
        screen.blit(loading_text, loading_rect)
    elif state == "SELECT_INTRO":
        button_width = 600
        button_height = 150
        spacing = 20
        for i, (category, _) in enumerate(categories):
            row = i // 2
            col = i % 2
            rect_x = 160 + col * (button_width + spacing)
            rect_y = 100 + row * (button_height + spacing)
            draw_button(category, pygame.Rect(rect_x, rect_y, button_width, button_height), (70, 70, 200))
    elif state == "RECORDING":
        recording_text = font.render("RECORDING", True, (255, 0, 0))
        screen.blit(recording_text, (850, 80))
        elapsed_time = time.time() - start_time
        remaining_time = max(0, 600 - int(elapsed_time))
        countdown_text = font.render(f"{remaining_time} Sek.", True, (255, 255, 255))
        screen.blit(countdown_text, (860, 200))
        bar_width, bar_height = 800, 20
        bar_x, bar_y = 560, 300
        pygame.draw.rect(screen, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height))
        progress_ratio = elapsed_time / 600
        progress_x = bar_x + int(bar_width * progress_ratio)
        pygame.draw.rect(screen, (255, 0, 0), (progress_x, bar_y - 10, 4, bar_height + 20))
        draw_button("PAUSE" if not paused else "FORTSETZEN", pygame.Rect(560, 600, 350, 150), (0, 0, 255))
        draw_button("STOP", pygame.Rect(1010, 600, 350, 150), (255, 0, 0))
    elif state == "DONE":
        done_text = font.render("Aufnahme gespeichert!", True, (0, 255, 0))
        done_rect = done_text.get_rect(center=(960, 540))
        screen.blit(done_text, done_rect)
        if pygame.time.get_ticks() - done_timer_start > 3000:
            state = "START"

    pygame.display.flip()
    clock.tick(30)

pygame.quit()
print("👋 Programm beendet.")
