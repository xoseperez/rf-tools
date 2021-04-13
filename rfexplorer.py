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
FREQ_CENTER = 868.1
FREQ_SPAN = 11.2
DBM_MIN = -120
DBM_MAX = 0

#---------------------------------------------------------
# Command line arguments
#---------------------------------------------------------

def arguments():

    epilog = """
Usage examples:

Monitor and print peaks from 862.5 to 873.7 for 60 seconds
    python {0} -c 868.1 -s 11.2 -t 60

Plot range of frequencies in real time
    python {0} -m plot

(c) 2019 Xose Pérez (@xoseperez)""".format(sys.argv[0])

    # Parse command line options
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=textwrap.dedent(epilog))
    parser.add_argument("-m", dest="mode", help="output mode", choices=['peak', 'swipe', 'plot'], default="peak")
    parser.add_argument("-r", dest="reset", help="reset RF Explorer", action='store_true')
    parser.add_argument("-c", dest="freq_center", type=float, help="frequency center", default=FREQ_CENTER)
    parser.add_argument("-s", dest="freq_span", type=float, help="frequency span", default=FREQ_SPAN)
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

    def header(self):
        print("timestamp,frequency,amplitude")
    
    def row(self):
        nIndex = self.objAnalyzer.SweepData.Count - 1
        objSweepTemp = self.objAnalyzer.SweepData.GetData(nIndex)
        nStep = objSweepTemp.GetPeakStep()
        fAmplitudeDBM = objSweepTemp.GetAmplitude_DBM(nStep)
        fCenterFreq = objSweepTemp.GetFrequencyMHZ(nStep)
        timestamp = int(1000 * (time.time() - self.start))
        print("{0:06d},{1:.2f},{2:.1f}".format(timestamp, fCenterFreq, fAmplitudeDBM))

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

    # Connect
    if objRFE.connect():    

        # User requested a reset?
        if args.reset:
            objRFE.reset()
        
        # Request RF Explorer configuration
        objRFE.init()

        # If object is an analyzer, we can scan for received sweeps
        if (objRFE.IsAnalyzer()):     

            # Define frequency span
            objRFE.range(args.freq_center, args.freq_span)

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
