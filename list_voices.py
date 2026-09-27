"""
Lists every text-to-speech voice installed on this Windows PC, with the
exact ID string needed to use it with main.py's --voice flag.

Run:
    python list_voices.py
"""

import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty("voices")

print(f"Found {len(voices)} voice(s) on this system:\n")

for i, voice in enumerate(voices):
    print(f"[{i}] Name: {voice.name}")
    print(f"    ID:   {voice.id}")
    print(f"    Languages: {voice.languages}")
    print()

print("To use one of these voices, copy its ID and run:")
print('    python main.py --voice "PASTE_ID_HERE"')
