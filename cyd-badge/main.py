"""
ESP32 CYD Conference Badge - Main entry point.
Initializes hardware and launches the menu.
"""
import gc
import time

gc.collect()

import badge_os
from badge_os import init_hardware, run_app

# Initialize hardware
init_hardware()

print("Badge OS ready. Free: {} bytes".format(gc.mem_free()))
print("FB mode: {}".format(badge_os.display._full_fb))

# Main loop: run menu, launch apps, return to menu
while True:
    gc.collect()

    try:
        # Import and run the menu
        from apps import menu
        badge_os._back_to_menu = False
        result = run_app(menu.update, menu.init, 15)

        if result is not None:
            # Launch the selected app
            gc.collect()
            mod = __import__("apps." + result)
            app_module = getattr(mod, result)
            badge_os._back_to_menu = False

            init_fn = getattr(app_module, 'init', None)
            fps = 25 if result == "tennis" else 10
            run_app(app_module.update, init_fn, fps)

            # Clean up the app module
            del app_module
            import sys
            mod_name = "apps." + result
            if mod_name in sys.modules:
                del sys.modules[mod_name]

    except KeyboardInterrupt:
        print("Interrupted — entering REPL")
        break
    except Exception as e:
        import sys
        sys.print_exception(e)
        badge_os.display.fill(badge_os.RED)
        badge_os.display.text("FATAL ERROR", 10, 10, badge_os.WHITE)
        badge_os.display.text(str(e)[:38], 10, 30, badge_os.WHITE)
        badge_os.display.text("Restarting...", 10, 50, badge_os.WHITE)
        if badge_os.display._full_fb:
            badge_os.display.show()
        time.sleep(3)

    gc.collect()
