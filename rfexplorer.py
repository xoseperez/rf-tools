#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import argparse
import textwrap

import matplotlib.pyplot as plt
from drawnow import *

from lib.RFExplorerComm import RFExplorerComm

#---------------------------------------------------------
# Configuration
#---------------------------------------------------------

BAUDRATE = 500000
DURATION = 60
FREQ_CENTER = 866.5
FREQ_SPAN = 7.0
FREQ_FROM = FREQ_CENTER - FREQ_SPAN / 2
FREQ_TO = FREQ_CENTER + FREQ_SPAN / 2
DBM_MIN = -120
DBM_MAX = 0

#---------------------------------------------------------
# Command line arguments
#---------------------------------------------------------

def arguments():

    epilog = """
Usage examples:

Monitor and print peaks from 863.0 to 870.0 for 60 seconds
    python {0} -f 863 -t 870 -d 60

Plot range of frequencies in real time
    python {0} -m plot

(c) 2019-2024 Xose Pérez (@xoseperez)""".format(sys.argv[0])

    # Parse command line options
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=textwrap.dedent(epilog))
    parser.add_argument("-m", dest="mode", help="output mode", choices=['peak', 'swipe', 'plot'], default="peak")
    parser.add_argument("-r", dest="reset", help="reset RF Explorer", action='store_true')
    parser.add_argument("-c", dest="freq_center", type=float, help="frequency center", default=None)
    parser.add_argument("-s", dest="freq_span", type=float, help="frequency span", default=FREQ_SPAN)
    parser.add_argument("-f", dest="freq_from", type=float, help="frequency start", default=None)
    parser.add_argument("-t", dest="freq_to", type=float, help="frequency start", default=None)
    parser.add_argument("-d", dest="duration", type=int, help="monitor for these many seconds (0 for non-stop)", default=DURATION)
    parser.add_argument("-p", dest="port", help="USB port to use, otherwise will try to find it", default=None)
    return parser.parse_args()

#---------------------------------------------------------
# Printer functions
#---------------------------------------------------------

class RFEPrinter(object):

    objAnalyzer = None
    start = time.time()

    def __init__(self, objAnalyzer):
        self.objAnalyzer = objAnalyzer
    
    def header(self):
        None

    def row(self):
        None

class PrintPeak(RFEPrinter):

    MM_SIZE = 10
    ring = [0] * MM_SIZE
    average = 0
    position = 0


    def header(self):
        print("timestamp,frequency,amplitude")
    
    def row(self):
        nIndex = self.objAnalyzer.SweepData.Count - 1
        objSweepTemp = self.objAnalyzer.SweepData.GetData(nIndex)
        nStep = objSweepTemp.GetPeakStep()
        fAmplitudeDBM = objSweepTemp.GetAmplitude_DBM(nStep)
        fCenterFreq = objSweepTemp.GetFrequencyMHZ(nStep)
        timestamp = int(1000 * (time.time() - self.start))
        print("%06d,%.2f,%.1f" % (timestamp, fCenterFreq, fAmplitudeDBM))

class PrintSwipe(RFEPrinter):

    def header(self):
        self.objAnalyzer.ProcessReceivedString(True)
        nIndex = self.objAnalyzer.SweepData.Count - 1
        objSweepTemp = self.objAnalyzer.SweepData.GetData(nIndex)
        sResult = ""
        for nStep in range(objSweepTemp.TotalSteps):
            sResult += str(',{0:.2f}'.format(objSweepTemp.GetFrequencyMHZ(nStep)))
        print("timestamp{0}".format(sResult))

    def row(self):
        nIndex = self.objAnalyzer.SweepData.Count - 1
        objSweepTemp = self.objAnalyzer.SweepData.GetData(nIndex)
        timestamp = int(1000 * (time.time() - startTime))
        sResult = ""
        for nStep in range(objSweepTemp.TotalSteps):
            sResult += str(',{:.1f}'.format(objSweepTemp.GetAmplitudeDBM(nStep, None, False)))
        print("{0:06d}{1}".format(timestamp, sResult))

class PrintPlot(RFEPrinter):

    y = []
    x = []
    h = []
    peak = DBM_MIN
    text = None
    peak_freq = 0
    font = None

    def plotter(self):
        plt.ylim(DBM_MIN, DBM_MAX)
        plt.grid(True)
        plt.plot(self.x, self.h, 'k-', alpha=0.2)
        plt.plot(self.x, self.y, 'r-')
        plt.xlabel('frequency (MHz)', fontdict=self.font)
        plt.ylabel('amplitude (dBm)', fontdict=self.font)
        plt.text(self.peak_freq, self.peak+1, self.text, fontdict=self.font)

    def header(self):
        self.objAnalyzer.ProcessReceivedString(True)
        nIndex = self.objAnalyzer.SweepData.Count - 1
        objSweepTemp = self.objAnalyzer.SweepData.GetData(nIndex)
        self.x = [0] * objSweepTemp.TotalSteps
        for nStep in range(objSweepTemp.TotalSteps):
            self.x[nStep] = objSweepTemp.GetFrequencyMHZ(nStep)
        self.y = [DBM_MIN] * objSweepTemp.TotalSteps
        self.h = [DBM_MIN] * objSweepTemp.TotalSteps
        self.font = {'family': 'serif', 'color':  'darkred', 'weight': 'normal', 'size': 8 }
        plt.ion()

    def row(self):
        nIndex = self.objAnalyzer.SweepData.Count - 1
        objSweepTemp = self.objAnalyzer.SweepData.GetData(nIndex)
        for nStep in range(objSweepTemp.TotalSteps):
            value = objSweepTemp.GetAmplitudeDBM(nStep, None, False)
            self.y[nStep] = value
            if value > self.h[nStep]:
                self.h[nStep] = value
                if value > self.peak:
                    self.peak = value
                    self.peak_freq = objSweepTemp.GetFrequencyMHZ(nStep)
                    self.text = "{0:.2f},{1:.1f}".format(self.peak_freq, value)

        drawnow(self.plotter)

#---------------------------------------------------------
# Main processing loop
#---------------------------------------------------------

try:

    # Parse arguments
    args = arguments()

    # Initialize object and thread
    objRFE = RFExplorerComm()   
    objRFE.AutoConfigure = False

    # Frequecy span
    center = args.freq_center
    span = args.freq_span
    if not center:
        start = args.freq_from or FREQ_FROM
        end = args.freq_to or FREQ_TO
        if end > start:
            center = (start + end) / 2
            span = end - start
        else:
            center = FREQ_CENTER

    # Connect
    if objRFE.connect(args.port, BAUDRATE):    

        # User requested a reset?
        if args.reset:
            objRFE.reset()
        
        # Request RF Explorer configuration
        objRFE.init()

        # If object is an analyzer, we can scan for received sweeps
        if (objRFE.IsAnalyzer()):     

            # Define frequency span
            objRFE.range(center, span)

            # Get mode printer
            printer = None
            if args.mode == "peak":
                printer = PrintPeak(objRFE)
            if args.mode == "swipe":
                printer = PrintSwipe(objRFE)
            if args.mode == "plot":
                printer = PrintPlot(objRFE)
            if printer == None:
                print("Invalid mode '{0}'".format(args.mode))
                sys.exit(1)
            printer.header()
            
            # Process until we complete scan time
            last = 0
            startTime = time.time()

            while ((args.duration == 0) or ((time.time() - startTime) < args.duration)):    

                # Process all received data from device 
                objRFE.ProcessReceivedString(True)

                # Print data if received new sweep only
                if (objRFE.SweepData.Count > last):
                    last = objRFE.SweepData.Count
                    printer.row()

        else:
            print("Error: Device connected is a Signal Generator. \nPlease, connect a Spectrum Analyzer")
    
    else:
        print("Not Connected")

except KeyboardInterrupt:
    None

except Exception as obEx:
    print("Error: " + str(obEx))

#---------------------------------------------------------
# Close object and release resources
#---------------------------------------------------------

objRFE.Close()    #Finish the thread and close port
objRFE = None 
