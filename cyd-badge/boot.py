"""
ESP32 CYD Conference Badge - Boot file.
Includes safety delay for REPL access.
"""
import gc
import time

gc.collect()
print("CYD Badge booting...")
print("Free memory: {} bytes".format(gc.mem_free()))
print("Press Ctrl+C within 3 seconds to enter REPL...")
time.sleep(3)
print("Starting badge OS...")
