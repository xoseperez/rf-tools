 #!/usr/bin/python

import os
import re
import glob
import time

import RFExplorer

class RFExplorerComm(RFExplorer.RFECommunicator):

    VENDOR_ID = 0x10c4
    PRODUCT_ID = 0xea60

    def __init__(self):
        RFExplorer.RFECommunicator.__init__(self)

    def find(self):
        """
        Looks for RF Explorer device
        """
        devices = []

        for dn in glob.glob('/sys/bus/usb/devices/*'):
            try:
                vid = int(open(os.path.join(dn, "idVendor" )).read().strip(), 16)
                pid = int(open(os.path.join(dn, "idProduct")).read().strip(), 16)
                if ((vid == self.VENDOR_ID) and (pid == self.PRODUCT_ID)):
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

    def connect(self, port = None, baudrate = 500000):

        # Show valid serial ports
        self.GetConnectedPorts()

        # Find port
        if port == None:
            ports = self.find()
            if len(ports) > 0:
                port = ports[0]
        if port == None:
            return False

        # Connect to available port
        return self.ConnectPort(port, baudrate) 

    def reset(self):

        # Reset the unit to start fresh
        self.SendCommand("r")
    
        # Wait for unit to notify reset completed
        while(self.IsResetEvent):
            pass
        
        # Wait for unit to stabilize
        time.sleep(3)

    def init(self):

        #Request RF Explorer configuration
        self.SendCommand_RequestConfigData()

        #Wait to receive configuration and model details
        while(self.ActiveModel == RFExplorer.RFE_Common.eModel.MODEL_NONE):
            
            #Process the received configuration
            self.ProcessReceivedString(True)    

    def range(self, center, span):

        # Check limits
        local_span = span 
        if local_span > self.MaxSpanMHZ:
            local_span = self.MaxSpanMHZ
        local_start = center - span / 2
        local_stop = center + span / 2

        corrected = False
        if local_start < self.MinFreqMHZ:
            local_stop = local_stop + self.MinFreqMHZ - local_start
            local_start = self.MinFreqMHZ
            corrected = True
        if local_stop > self.MaxFreqMHZ:
            if not corrected:
                local_start = local_start + self.MaxFreqMHZ - local_stop 
            local_stop = self.MaxFreqMHZ
            local_span = local_stop - local_start
        
        self.SpanMHZ = local_span
        self.StartFrequencyMHZ = local_start
        self.UpdateDeviceConfig(local_start, local_stop)
        
        print("Frequency center: {0}MHz start: {1}MHz stop: {2}MHz span: {3}MHz".format(local_start + local_span / 2, local_start, local_stop, local_span))




