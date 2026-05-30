"""
Test am thanh EyeGuard
Chay: python test_sound.py
"""

import time
import sys


print("=" * 50)
print("  EYEGUARD – KIEM TRA AM THANH")
print("=" * 50)


# ── Test 1: winsound (Windows built-in) ──────────────────
print("\n[Test 1] winsound.Beep (Windows built-in)...")
try:
    import winsound
    print("  → winsound OK, dang phat...")
    winsound.Beep(1000, 500)   # 1000Hz, 500ms
    print("  → Co nghe tieng BEEP khong? (y/n): ", end="")
    ans = input().strip().lower()
    if ans == "y":
        print("  ✓ winsound hoat dong!")
    else:
        print("  ✗ Khong nghe – thu phuong phap khac")
except Exception as e:
    print(f"  ✗ winsound loi: {e}")

time.sleep(0.5)

# ── Test 2: pygame ────────────────────────────────────────
print("\n[Test 2] pygame mixer...")
try:
    import pygame
    import numpy as np

    pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
    print("  → pygame OK, dang phat...")

    sample_rate = 44100
    freq        = 880
    dur         = 0.5
    t    = np.linspace(0, dur, int(sample_rate * dur), False)
    wave = (np.sin(2 * np.pi * freq * t) * 32767 * 0.8).astype(np.int16)
    sound = pygame.sndarray.make_sound(wave)
    sound.play()
    pygame.time.wait(600)

    print("  → Co nghe tieng khong? (y/n): ", end="")
    ans = input().strip().lower()
    if ans == "y":
        print("  ✓ pygame hoat dong!")
    else:
        print("  ✗ Khong nghe")

except ImportError:
    print("  ✗ Chua cai pygame – chay: pip install pygame")
except Exception as e:
    print(f"  ✗ pygame loi: {e}")

time.sleep(0.5)

# ── Test 3: playsound ─────────────────────────────────────
print("\n[Test 3] playsound...")
try:
    from playsound import playsound
    import os
    # Dung file WAV he thong Windows
    wav = r"C:\Windows\Media\notify.wav"
    if os.path.exists(wav):
        print(f"  → Phat file: {wav}")
        playsound(wav, block=False)
        time.sleep(1.5)
        print("  → Co nghe tieng khong? (y/n): ", end="")
        ans = input().strip().lower()
        if ans == "y":
            print("  ✓ playsound + WAV hoat dong!")
    else:
        print("  → Khong tim thay file WAV he thong")
except ImportError:
    print("  ✗ Chua cai playsound – chay: pip install playsound")
except Exception as e:
    print(f"  ✗ playsound loi: {e}")

time.sleep(0.5)

# ── Test 4: winsound PlaySound file WAV ──────────────────
print("\n[Test 4] winsound.PlaySound voi file WAV he thong...")
try:
    import winsound
    import os

    wav_files = [
        r"C:\Windows\Media\notify.wav",
        r"C:\Windows\Media\Windows Notify.wav",
        r"C:\Windows\Media\Windows Ding.wav",
        r"C:\Windows\Media\chord.wav",
    ]

    played = False
    for wav in wav_files:
        if os.path.exists(wav):
            print(f"  → Phat: {wav}")
            winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_ASYNC)
            time.sleep(2)
            played = True
            print("  → Co nghe khong? (y/n): ", end="")
            ans = input().strip().lower()
            if ans == "y":
                print(f"  ✓ PlaySound WAV hoat dong!")
                print(f"  → Duong dan file: {wav}")
            break

    if not played:
        print("  → Khong tim thay file WAV he thong")

except Exception as e:
    print(f"  ✗ Loi: {e}")

# ── Ket qua ───────────────────────────────────────────────
print("\n" + "=" * 50)
print("  Gui ket qua cho Claude de sua notification_manager.py")
print("  Cho biet Test nao hoat dong (1/2/3/4)")
print("=" * 50)
