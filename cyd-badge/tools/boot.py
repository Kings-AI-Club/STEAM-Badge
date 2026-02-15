"""
ESP32 CYD Conference Badge - Boot file.
Initializes hardware on startup.
"""
import gc
gc.collect()
print("CYD Badge booting...")
print(f"Free memory: {gc.mem_free()} bytes")
