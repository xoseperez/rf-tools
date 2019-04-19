 #!/usr/bin/python

import os
import re
import sys
import glob
import time
import serial

def find_devices(vendor_id = None, product_id = None):
    """
    Looks for USB devices
    optionally filtering by with the provided vendor and product IDs
    """
    devices = []

    for dn in glob.glob('/sys/bus/usb/devices/*'):
        try:
            vid = int(open(os.path.join(dn, "idVendor" )).read().strip(), 16)
            pid = int(open(os.path.join(dn, "idProduct")).read().strip(), 16)
            if ((vendor_id is None) or (vid == vendor_id)) and ((product_id is None) or (pid == product_id)):
                dns = glob.glob(os.path.join(dn, os.path.basename(dn) + "*"))
                for sdn in dns:
                    for fn in glob.glob(os.path.join(sdn, "*")):
                        if re.search(r"\/ttyUSB[0-9]+$", fn):
                            devices.append(os.path.join("/dev", os.path.basename(fn)))
                        pass
                    pass
                pass
            pass
        except ( ValueError, TypeError, AttributeError, OSError, IOError ):
            pass
        pass

    return devices

ports = find_devices(0x1a86, 0x7523)
if len(ports) == 0:
    print("RF Power monitor not found")
    sys.exit(1)
port = ports[0]

ser = serial.Serial(
    port=port,
    baudrate=9600,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS,
    timeout=0
)

pattern = re.compile("\$([\s0-9.-]+).*\$")
max = -120
start = time.time()

print("timestamp,amplitude")

try:
    while True:
        line = ser.readline().decode('utf-8')
        result = pattern.match(line)
        if result:
            dbm = float(result.group(1).replace(" ", ""))
            if dbm > max:
                max = dbm
            t = int(1000 * (time.time() - start))
            print("{0:06d},{1}".format(t, dbm))

except KeyboardInterrupt:
    None

ser.close()