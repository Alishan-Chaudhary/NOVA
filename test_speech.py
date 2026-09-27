"""
Minimal standalone test to check if pyttsx3 can produce audio on this
machine at all, separate from the webcam/detection code.

Run:
    python test_speech.py
"""

import pyttsx3

print("Initializing speech engine...")
engine = pyttsx3.init()
engine.setProperty("rate", 140)
engine.setProperty("volume", 1.0)

print("Speaking test sentence now -- you should hear this through your speakers...")
engine.say("This is a test. Can you hear me speaking?")
engine.runAndWait()
print("Done. If you did not hear anything, the issue is with pyttsx3 itself on this machine.")
