#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
DBM_MIN = -80
DBM_MAX = 0
DBM_FILTER = 0
PLOT_LAST = 100
DEFAULT_FREQUENCY = 169

#---------------------------------------------------------
# Command line arguments
#---------------------------------------------------------

def arguments():

    epilog = """
Usage examples:

Plot the amplitude in real time
    python {0} -m plot -f 169 -o -20

(c) 2019-2021 Xose Pérez (@xoseperez)""".format(sys.argv[0])

    # Parse command line options
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=textwrap.dedent(epilog))
    parser.add_argument("-f", dest="freq", help="Center frequency", type=int, default=DEFAULT_FREQUENCY)
    parser.add_argument("-o", dest="offset", help="Offset in dB", type=float, default=0)
    parser.add_argument("-m", dest="mode", help="Output mode", choices=['peak', 'plot'], default="peak")
    parser.add_argument("-t", dest="threshold", help="Annotation threshold", type=int, default=DBM_FILTER)
    parser.add_argument("-d", dest="duration", type=int, help="Monitor for these many seconds (0 for non-stop)", default=DURATION)
    parser.add_argument("-p", dest="port", help="USB port to use, otherwise will try to find it", default=None)
    return parser.parse_args()

#---------------------------------------------------------
# Printer functions
#---------------------------------------------------------

class Color:
    DEFAULT = '\x1b[0m'
    GREY = '\x1b[1;37m'
    GREEN = '\x1b[1;32m'
    BLUE = '\x1b[1;34m'
    YELLOW = '\x1b[1;33m'
    RED = '\x1b[1;31m'
    MAGENTA = '\x1b[1;35m'
    CYAN = '\x1b[1;36m'

class PrinterBase(object):

    start = time.time()
    threshold = DBM_FILTER

    def __init__(self, threshold):
        self.threshold = threshold
        None

    def header(self):
        None

    def row(self, value):
        None

class PrintPeak(PrinterBase):

    default_color = Color.BLUE
    highlight_color = Color.YELLOW

    def header(self):
        print(Color.GREEN + "timestamp,amplitude" + self.default_color)
    
    def row(self, value):
        timestamp = int(1000 * (time.time() - self.start))
        color = self.highlight_color if value > self.threshold else self.default_color
        print(color + "{0:06d},{1:.1f}".format(timestamp, value) + self.default_color)

class PrintPlot(PrinterBase):

    x = []
    y = []
    peaks = []
    font = None

    def plotter(self):
        plt.ylim(DBM_MIN, DBM_MAX)
        plt.grid(True)
        plt.plot(self.x, self.y, 'r-')
        plt.xlabel('time (s)', fontdict=self.font)
        plt.ylabel('amplitude (dBm)', fontdict=self.font)
        for index in range(len(self.peaks)):
            peak = self.peaks[index]
            plt.text(peak.get("x"), peak.get("y") + 1, peak.get("text"), fontdict=self.font)

    def header(self):
        self.x = [0] * PLOT_LAST
        self.y = [DBM_MIN] * PLOT_LAST
        self.font = {'family': 'serif', 'color':  'darkred', 'weight': 'normal', 'size': 8 }
        plt.ion()

    def row(self, value):

        timestamp = time.time() - self.start

        self.x.append(timestamp)
        del self.x[0]
        self.y.append(value)
        del self.y[0]

        if value > self.threshold:
            peak = dict( x=timestamp, y=value, text="{0:.2f},{1:.1f}".format(timestamp, value))
            self.peaks.append(peak)

        if len(self.peaks) > 0:
            if self.peaks[0].get("x") < self.x[0]:
                del self.peaks[0]

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
        printer = PrintPeak(args.threshold)
    if args.mode == "plot":
        printer = PrintPlot(args.threshold)
    if printer == None:
        print("Invalid mode '{0}'".format(args.mode))
        sys.exit(1)
    printer.header()

    pattern = re.compile("\$([\s0-9.-]+).*\$")
    startTime = time.time()

    # Configure meter
    offset_sign = '-' if args.offset < 0 else '+'
    offset_int = abs(int(args.offset))
    offset_dec = abs(10*args.offset) - 10*offset_int
    message = "$%04d%s%02d.%1d#" % (args.freq, offset_sign, offset_int, offset_dec)
    ser.write(bytes(message, 'utf-8'))

    while ((args.duration == 0) or ((time.time() - startTime) < args.duration)):    
        try:
            line = ser.readline().decode('utf-8')
            result = pattern.match(line)
            if result:
                dbm = float(result.group(1).replace(" ", ""))
                printer.row(dbm)
        except UnicodeDecodeError:
            None

except KeyboardInterrupt:
    None

except Exception as obEx:
    print("Error: " + str(obEx))

if ser:
    ser.close()
