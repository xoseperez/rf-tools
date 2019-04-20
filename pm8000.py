 #!/usr/bin/python

import os
import re
import sys
import glob
import time
import serial
import argparse 
import textwrap

import matplotlib.pyplot as plt
from drawnow import *

#---------------------------------------------------------
# Configuration
#---------------------------------------------------------

BAUDRATE = 9600
DURATION = 60
VENDOR_ID = 0x1a86
PRODUCT_ID = 0x7523
DBM_MIN = -50
DBM_MAX = 0
PLOT_LAST = 100

#---------------------------------------------------------
# Command line arguments
#---------------------------------------------------------

def arguments():

    epilog = """
Usage examples:

Plot the amplitude in real time
    python {0} -m plot

(c) 2019 Xose Pérez (@xoseperez)""".format(sys.argv[0])

    # Parse command line options
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=textwrap.dedent(epilog))
    parser.add_argument("-m", dest="mode", help="output mode", choices=['peak', 'plot'], default="peak")
    parser.add_argument("-d", dest="duration", type=int, help="monitor for these many seconds", default=DURATION)
    parser.add_argument("-p", dest="port", help="USB port to use, otherwise will try to find it", default=None)
    return parser.parse_args()

#---------------------------------------------------------
# Printer functions
#---------------------------------------------------------

class PrinterBase(object):

    start = time.time()

    def header(self):
        None

    def row(self, value):
        None

class PrintPeak(PrinterBase):

    def header(self):
        print("timestamp,amplitude")
    
    def row(self, value):
        timestamp = int(1000 * (time.time() - self.start))
        print("{0:06d},{1:.1f}".format(timestamp, value))

class PrintPlot(PrinterBase):

    x = []
    y = []

    def plotter(self):
        plt.ylim(DBM_MIN, DBM_MAX)
        plt.grid(True)
        plt.plot(self.x, self.y, 'r-')

    def header(self):
        self.x = [0] * PLOT_LAST
        self.y = [DBM_MIN] * PLOT_LAST
        plt.ion()

    def row(self, value):
        timestamp = time.time() - self.start
        self.x.append(timestamp)
        del self.x[0]
        self.y.append(value)
        del self.y[0]
        drawnow(self.plotter)

#---------------------------------------------------------
# Helper methods
#---------------------------------------------------------

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

#---------------------------------------------------------
# Main
#---------------------------------------------------------

ser = None

try:

    # Parse arguments
    args = arguments()

    port = args.port
    if port == None:
        ports = find_devices(VENDOR_ID, PRODUCT_ID)
        if len(ports) > 0:
            port = ports[0]
    if port == None:
        print("RF Power monitor not found")
        sys.exit(1)
    ser = serial.Serial(port=port, baudrate=BAUDRATE, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=0)

    # Get mode printer
    printer = None
    if args.mode == "peak":
        printer = PrintPeak()
    if args.mode == "plot":
        printer = PrintPlot()
    if printer == None:
        print("Invalid mode '{0}'".format(args.mode))
        sys.exit(1)
    printer.header()

    pattern = re.compile("\$([\s0-9.-]+).*\$")
    startTime = time.time()

    while ((time.time() - startTime) < args.duration):    
        line = ser.readline().decode('utf-8')
        result = pattern.match(line)
        if result:
            dbm = float(result.group(1).replace(" ", ""))
            printer.row(dbm)

except KeyboardInterrupt:
    None

except Exception as obEx:
    print("Error: " + str(obEx))

if ser:
    ser.close()
