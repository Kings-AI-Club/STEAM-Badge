esptool.py --chip esp32 --port /dev/cu.usbserial-1220 erase_flash  
esptool.py --chip esp32 --port /dev/cu.usbserial-1220 --baud 460800 write_flash -z 0x1000 '/Users/arona/Downloads/ESP32 Generic v1.27.0.bin'
mpremote cp cyd-badge/boot.py :                                                                                                             
mpremote cp cyd-badge/main.py :                 
mpremote cp cyd-badge/badge_os.py :                 
mpremote cp cyd-badge/badge_config.py :
mpremote cp -r cyd-badge/drivers :
mpremote cp -r cyd-badge/fonts :
mpremote cp -r cyd-badge/apps :
mpremote cp -r cyd-badge/resources :
mpremote reset