"""
ESP32 CYD Conference Badge - Main entry point.
Initializes hardware and launches the menu.
"""
import gc
import machine

gc.collect()

from badge_os import init_hardware, run_app, display, touch
import badge_os

# Initialize hardware
init_hardware()

# Main loop: run menu, launch apps, return to menu
while True:
    gc.collect()

    try:
        # Import and run the menu
        from apps import menu
        badge_os._back_to_menu = False
        result = run_app(menu.update, init_fn=menu.init, target_fps=20)

        if result is not None:
            # Launch the selected app
            gc.collect()
            app_module = __import__("apps." + result, fromlist=[result])
            badge_os._back_to_menu = False

            init_fn = getattr(app_module, 'init', None)
            run_app(app_module.update, init_fn=init_fn, target_fps=30)

            # Clean up the app module
            del app_module
            import sys
            mod_name = "apps." + result
            if mod_name in sys.modules:
                del sys.modules[mod_name]

    except Exception as e:
        import sys
        sys.print_exception(e)
        from badge_os import RED, WHITE
        display.fill(RED)
        display.text("FATAL ERROR", 10, 10, WHITE)
        display.text(str(e)[:38], 10, 30, WHITE)
        display.text("Restarting...", 10, 50, WHITE)
        display.show()
        import time
        time.sleep(3)

    gc.collect()
