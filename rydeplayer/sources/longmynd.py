#    Ryde Player provides a on screen interface and video player for Longmynd compatible tuners.
#    Copyright © 2021 Tim Clark
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

import enum, os, stat, subprocess, pty, select, copy, fcntl, collections, time, socket, queue, threading, bisect
import rydeplayer.common
import rydeplayer.sources.common
import pyftdi.ftdi
import pyftdi.usbtools
import pyftdi.eeprom

class inPortEnum(enum.Enum):
    TOP = enum.auto()
    BOTTOM = enum.auto()

class PolarityEnum(enum.Enum):
    NONE = enum.auto()
    HORIZONTAL = enum.auto()
    VERTICAL = enum.auto()

class DVBSVersionEnum(enum.Enum):
    DVBS = enum.auto()
    DVBS2 = enum.auto()

class DVBSModulationEnum(rydeplayer.sources.common.sourceModeEnum):
    S_1_2      = (enum.auto(), "DVB-S 1/2",          1.7)
    S_2_3      = (enum.auto(), "DVB-S 2/3",          3.3)
    S_3_4      = (enum.auto(), "DVB-S 3/4",          4.2)
    S_5_6      = (enum.auto(), "DVB-S 5/6",          5.1)
    S_6_7      = (enum.auto(), "DVB-S 6/7",          5.5)
    S_7_8      = (enum.auto(), "DVB-S 7/8",          5.8)
    S2_4_1_4   = (enum.auto(), "DVB-S2 QPSK 1/4",   -2.3)
    S2_4_1_3   = (enum.auto(), "DVB-S2 QPSK 1/3",   -1.2)
    S2_4_2_5   = (enum.auto(), "DVB-S2 QPSK 2/5",   -0.3)
    S2_4_1_2   = (enum.auto(), "DVB-S2 QPSK 1/2",    1.0)
    S2_4_3_5   = (enum.auto(), "DVB-S2 QPSK 3/5",    2.3)
    S2_4_2_3   = (enum.auto(), "DVB-S2 QPSK 2/3",    3.1)
    S2_4_3_4   = (enum.auto(), "DVB-S2 QPSK 3/4",    4.1)
    S2_4_4_5   = (enum.auto(), "DVB-S2 QPSK 4/5",    4.7)
    S2_4_5_6   = (enum.auto(), "DVB-S2 QPSK 5/6",    5.2)
    S2_4_8_9   = (enum.auto(), "DVB-S2 QPSK 8/9",    6.2)
    S2_4_9_10  = (enum.auto(), "DVB-S2 QPSK 9/10",   6.5)
    S2_8_3_5   = (enum.auto(), "DVB-S2 8PSK 3/5",    5.5)
    S2_8_2_3   = (enum.auto(), "DVB-S2 8PSK 2/3",    6.6)
    S2_8_3_4   = (enum.auto(), "DVB-S2 8PSK 3/4",    7.9)
    S2_8_5_6   = (enum.auto(), "DVB-S2 8PSK 5/6",    9.4)
    S2_8_8_9   = (enum.auto(), "DVB-S2 8PSK 8/9",    10.7)
    S2_8_9_10  = (enum.auto(), "DVB-S2 8PSK 9/10",   11.0)
    S2_16_2_3  = (enum.auto(), "DVB-S2 16APSK 2/3",  9.0)
    S2_16_3_4  = (enum.auto(), "DVB-S2 16APSK 3/4",  10.2)
    S2_16_4_5  = (enum.auto(), "DVB-S2 16APSK 4/5",  11.0)
    S2_16_5_6  = (enum.auto(), "DVB-S2 16APSK 5/6",  11.6)
    S2_16_8_9  = (enum.auto(), "DVB-S2 16APSK 8/9",  12.9)
    S2_16_9_10 = (enum.auto(), "DVB-S2 16APSK 9/10", 13.2)
    S2_32_3_4  = (enum.auto(), "DVB-S2 32APSK 3/4",  12.8)
    S2_32_4_5  = (enum.auto(), "DVB-S2 32APSK 4/5",  13.7)
    S2_32_5_6  = (enum.auto(), "DVB-S2 32APSK 5/6",  14.3)
    S2_32_8_9  = (enum.auto(), "DVB-S2 32APSK 8/9",  15.7)
    S2_32_9_10 = (enum.auto(), "DVB-S2 32APSK 9/10", 16.1)

    def __init__(self, enum, longName, threshold):
        self.longName = longName
        self.threshold = threshold

# Container for tuner status data with change callbacks
class tunerStatus(rydeplayer.sources.common.sourceStatus):
    def __init__(self):
        super().__init__()
        self.mer = None
        self.sr = None
        self.agc1 = None
        self.agc2 = None
        self.powerInd = None

    def setMer(self, newval):
        if(isinstance(newval, float)):
            if self.mer != newval:
                self.mer = newval
                self.onChangeFire()
                return True
            else:
                return False
        elif(isinstance(newval, int)):
            if self.mer != float(newval):
                self.mer = float(newval)
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setDVBVersion(self, newval):
        if(isinstance(newval, DVBSVersionEnum) or newval is None):
            if(newval != self.dvbVersion):
                self.dvbVersion = newval
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setModcode(self, newval):
        dvbs = {
            0: DVBSModulationEnum.S_1_2,
            1: DVBSModulationEnum.S_2_3,
            2: DVBSModulationEnum.S_3_4,
            3: DVBSModulationEnum.S_5_6,
            4: DVBSModulationEnum.S_6_7,
            5: DVBSModulationEnum.S_7_8
            }
        dvbs2 = {
            1:  DVBSModulationEnum.S2_4_1_4,
            2:  DVBSModulationEnum.S2_4_1_3,
            3:  DVBSModulationEnum.S2_4_2_5,
            4:  DVBSModulationEnum.S2_4_1_2,
            5:  DVBSModulationEnum.S2_4_3_5,
            6:  DVBSModulationEnum.S2_4_2_3,
            7:  DVBSModulationEnum.S2_4_3_4,
            8:  DVBSModulationEnum.S2_4_4_5,
            9:  DVBSModulationEnum.S2_4_5_6,
            10: DVBSModulationEnum.S2_4_8_9,
            11: DVBSModulationEnum.S2_4_9_10,
            12: DVBSModulationEnum.S2_8_3_5,
            13: DVBSModulationEnum.S2_8_2_3,
            14: DVBSModulationEnum.S2_8_3_4,
            15: DVBSModulationEnum.S2_8_5_6,
            16: DVBSModulationEnum.S2_8_8_9,
            17: DVBSModulationEnum.S2_8_9_10,
            18: DVBSModulationEnum.S2_16_2_3,
            19: DVBSModulationEnum.S2_16_3_4,
            20: DVBSModulationEnum.S2_16_4_5,
            21: DVBSModulationEnum.S2_16_5_6,
            22: DVBSModulationEnum.S2_16_8_9,
            23: DVBSModulationEnum.S2_16_9_10,
            24: DVBSModulationEnum.S2_32_3_4,
            25: DVBSModulationEnum.S2_32_4_5,
            26: DVBSModulationEnum.S2_32_5_6,
            27: DVBSModulationEnum.S2_32_8_9,
            28: DVBSModulationEnum.S2_32_9_10
            }
        if(isinstance(newval, int)):
            newMod = None
            if(self.dvbVersion == DVBSVersionEnum.DVBS):
                if(newval in dvbs):
                    newMod = dvbs[newval]
                else:
                    return False
            elif(self.dvbVersion == DVBSVersionEnum.DVBS2):
                if(newval in dvbs2):
                    newMod = dvbs2[newval]
                else:
                    return False
            elif(self.dvbVersion is None):
                newMod = None
            else:
                return False
            if(newMod != self.modulation):
                self.modulation = newMod
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setSR(self, newval):
        if(isinstance(newval, float)):
            if self.sr != newval:
                self.sr = newval
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def updatePowerInd(self):
        agc1Lookup = collections.OrderedDict()
        agc1Lookup[1] = -70
        agc1Lookup[10] = -69
        agc1Lookup[21800] = -68
        agc1Lookup[25100] = -67
        agc1Lookup[27100] = -66
        agc1Lookup[28100] = -65
        agc1Lookup[28900] = -64
        agc1Lookup[29600] = -63
        agc1Lookup[30100] = -62
        agc1Lookup[30550] = -61
        agc1Lookup[31000] = -60
        agc1Lookup[31350] = -59
        agc1Lookup[31700] = -58
        agc1Lookup[32050] = -57
        agc1Lookup[32400] = -56
        agc1Lookup[32700] = -55
        agc1Lookup[33000] = -54
        agc1Lookup[33300] = -53
        agc1Lookup[33600] = -52
        agc1Lookup[33900] = -51
        agc1Lookup[34200] = -50
        agc1Lookup[34500] = -49
        agc1Lookup[34750] = -48
        agc1Lookup[35000] = -47
        agc1Lookup[35250] = -46
        agc1Lookup[35500] = -45
        agc1Lookup[35750] = -44
        agc1Lookup[36000] = -43
        agc1Lookup[36200] = -42
        agc1Lookup[36400] = -41
        agc1Lookup[36600] = -40
        agc1Lookup[36800] = -39
        agc1Lookup[37000] = -38
        agc1Lookup[37200] = -37
        agc1Lookup[37400] = -36
        agc1Lookup[37600] = -35
        agc1Lookup[37700] = -35

        agc2Lookup = collections.OrderedDict()
        agc2Lookup[182] = -71
        agc2Lookup[200] = -72
        agc2Lookup[225] = -73
        agc2Lookup[255] = -74
        agc2Lookup[290] = -75
        agc2Lookup[325] = -76
        agc2Lookup[360] = -77
        agc2Lookup[400] = -78
        agc2Lookup[450] = -79
        agc2Lookup[500] = -80
        agc2Lookup[560] = -81
        agc2Lookup[625] = -82
        agc2Lookup[700] = -83
        agc2Lookup[780] = -84
        agc2Lookup[880] = -85
        agc2Lookup[1000] = -86
        agc2Lookup[1140] = -87
        agc2Lookup[1300] = -88
        agc2Lookup[1480] = -89
        agc2Lookup[1660] = -90
        agc2Lookup[1840] = -91
        agc2Lookup[2020] = -92
        agc2Lookup[2200] = -93
        agc2Lookup[2380] = -94
        agc2Lookup[2560] = -95
        agc2Lookup[2740] = -96
        agc2Lookup[3200] = -97

        if self.agc1 is None or self.agc2 is None:
            newpwr = None
        else:
            if self.agc1 > 0:
                lookupDict = agc1Lookup
                lookupVal = self.agc1
            else:
                lookupDict = agc2Lookup
                lookupVal = self.agc2
            agcKeys = list(lookupDict.keys())
            # find where it would be inserted if it was a list
            agcIndex = bisect.bisect_left(agcKeys,lookupVal)
            # check if n or n-1 is closer
            if abs(agcKeys[agcIndex]-lookupVal) >= abs(agcKeys[agcIndex-1]-lookupVal):
                closestKey = agcKeys[agcIndex - 1]
            else:
                closestKey = agcKeys[agcIndex]
            newpwr = lookupDict[closestKey]
        if self.powerInd != newpwr:
            self.powerInd = newpwr
            self.onChangeFire()
            return True
        else:
            return False

    def setAGC1(self, newval):
        if(isinstance(newval, int)):
            if self.agc1 != newval:
                self.agc1 = newval
                return self.updatePowerInd()
            else:
                return False
        else:
            return False

    def setAGC2(self, newval):
        if(isinstance(newval, int)):
            if self.agc2 != newval:
                self.agc2 = newval
                return self.updatePowerInd()
            else:
                return False
        else:
            return False

    def getMer(self):
        return self.mer

    def getSR(self):
        return self.sr

    def getPowerInd(self):
        return self.powerInd

    def getPowerLevelMeta(self):
        def processVal(newval):
            return newval.getPowerInd()
        return self.meterConfig("dBm Power","", processVal)

    def getSignalLevelMeta(self):
        def processVal(newval):
            return newval.getMer()
        return self.meterConfig("dB MER","", processVal)

    def getSignalReportMeta(self):
        def processVal(newval):
            mod = newval.getModulation()
            if mod is None:
                return None
            else:
                mer = newval.getMer()
                return round(mer - mod.threshold,1)
        return self.meterConfig("dB Margin","D", processVal)

    def getSignalBandwidthMeta(self):
        def processVal(newval):
            return newval.getSR()
        return self.numericConfig("S",3, processVal)

    def setStatusToMatch(self, fromStatus):
        changed = super().setStatusToMatch(fromStatus)
        newMer = fromStatus.getMer()
        if self.mer != newMer:
            self.mer = newMer
            changed = True
        newSR = fromStatus.getSR()
        if self.sr != newSR:
            self.sr = newSR
            changed = True
        newPowerInd = fromStatus.getPowerInd()
        if self.powerInd != newPowerInd:
            self.powerInd = newPowerInd
            changed = True
        if changed:
            self.onChangeFire()

class lmManager(object):
    def __init__(self, config, sourceConfig):
        # path to the longmynd binary
        self.lmpath = sourceConfig.binpath
        self.mediaFIFOfilename = sourceConfig.mediapath
        self.statusFIFOfilename = sourceConfig.statuspath
        self.tsTimeout = sourceConfig.tstimeout
        #TODO: add error handling here
        if(not os.path.exists(self.mediaFIFOfilename)):
            os.mkfifo(self.mediaFIFOfilename)
            print("made")
        elif(not stat.S_ISFIFO(os.stat(self.mediaFIFOfilename).st_mode)):
            print("media pipe is not a fifo")
        if(not os.path.exists(self.statusFIFOfilename)):
            os.mkfifo(self.statusFIFOfilename)
        elif(not stat.S_ISFIFO(os.stat(self.statusFIFOfilename).st_mode)):
            print("status pipe is not a fifo")
        self.vlcMediaFd =os.fdopen( os.open(self.mediaFIFOfilename, flags=os.O_NONBLOCK|os.O_RDONLY)) # an open file descriptor to pass to vlc (or another player)
#        self.vlcMediaFd = None
        self.statusFIFOfd = os.fdopen(os.open(self.statusFIFOfilename, flags=os.O_NONBLOCK|os.O_RDONLY), encoding="utf-8", errors="replace") # the status fifo file descriptor
        rpipe, self.stdoutWritefd = pty.openpty() # a pty for interacting with longmynds STDOUT, couldn't get pipes to work
        flags = fcntl.fcntl(rpipe, fcntl.F_GETFL)
        flags |= os.O_NONBLOCK
        fcntl.fcntl(rpipe, fcntl.F_SETFL, flags)
        self.stdoutReadfd = os.fdopen(rpipe, 'r')
        self.process = None
        self.statelog = [] # log of important things from longmynds STDOUT
        self.lmlog = [] # a complete longmmynd output log, for debugging
        self.lmstarted = False
        self.statusrecv = False
        self.activeConfig = config.copyConfig()
        self.hasPIDs = False
        self.pidCacheWait = True
        self.pidCacheFault = False
        self.pidCache = {}
        self.pidCachePair = (None,None)
        # for tracking LNA initialisation errors
        self.lnaIniting = False
        self.lnaErrorCount = 0
        self.autoresetdetect = False
        self.autoresetprogress = 0
        self.lastState = { 'state':None, 'provider': '', 'service': '', 'modcode': None, 'pids': {} }
        self.changeRefState = copy.deepcopy(self.lastState)
        self.stateMonotonic = 0
        self.tunerStatus = tunerStatus()
        # state type for the core longmynd state
        self.coreStateType = collections.namedtuple('coreState', ['isRunning', 'isStarted', 'isLocked', 'monotonicState'])

    def reconfig(self, config):
        """reconfigures longmynd"""
        if(isinstance(config, rydeplayer.sources.common.tunerConfig) and config != self.activeConfig):
            self.activeConfig = config.copyConfig()
            print(self.activeConfig)
            self.restart()
    def remedia(self):
        self.vlcMediaFd.close()
        self.vlcMediaFd =os.fdopen( os.open(self.mediaFIFOfilename, flags=os.O_NONBLOCK, mode=os.O_RDONLY)) # an open file descriptor to pass to vlc (or another player)
    def getMediaFd(self):
        return self.vlcMediaFd
    def getFDs(self):
        return [self.statusFIFOfd, self.stdoutReadfd]
    def getStatus(self):
        return self.tunerStatus
    def handleFD(self, fd):
        """handles a file descriptor that has data to read"""
        fdCallbacks = dict()
        fdCallbacks[self.stdoutReadfd] = self.processStdout
        fdCallbacks[self.statusFIFOfd] = self.processStatus
        if(fd in fdCallbacks):
            fdCallbacks[fd]()
    def getCoreState(self):
        """gets the core system state in a single call"""
        state = self.coreStateType(self.isRunning(), self.isStarted(), self.isLocked(), self.getMonotonicState())
        return state
    def isStarted(self):
        if(self.process != None):
            polled = self.process.poll()
            return polled==None
        else:
            return False
    def isRunning(self):
        if(self.process != None and self.lmstarted and self.statusrecv):
            polled = self.process.poll()
            return polled==None
        else:
            return False
    def isLocked(self):
        """returns if longmynd is locked on to a signal
        This does not mean it can be decoded, MER may still be too low
        """
        if(self.isRunning()):
            print("state:"+str(self.lastState))
            if(self.lastState['state'] in [3,4]):
                return True
            else:
                return False
        else:
            return False
    def getMonotonicState(self):
        return self.stateMonotonic
    
    def processStatus(self):
        """process the status FIFO data"""
        #TODO: handle more of the status messages
        lines =  self.statusFIFOfd.readlines()
        for line in lines:
            self.statusrecv = True
            if(line[0] == '$'):
                rawtype,rawval = line[1:].rstrip().split(',',1)
                msgtype = int(rawtype)
                if msgtype == 1: # State
                    if int(rawval) == 3:
                        self.tunerStatus.setDVBVersion(DVBSVersionEnum.DVBS)
                    elif int(rawval) == 4:
                        self.tunerStatus.setDVBVersion(DVBSVersionEnum.DVBS2)
                    else:
                        self.tunerStatus.setDVBVersion(None)
                    if not self.hasPIDs:
                        self.tunerStatus.setPIDs(self.pidCache)
                    self.hasPIDs = False
                    if self.lastState != self.changeRefState : # if the signal parameters have changed
                        self.stateMonotonic += 1
                        self.changeRefState = copy.deepcopy(self.lastState)
                    self.lastState['state'] = int(rawval)
                    if int(rawval) < 3: # if it is not locked, reset some state
                        self.lastState['provider'] = ""
                        self.lastState['service'] = ""
                        self.lastState['modcode'] = None
                        self.lastState['pids'] = {}
                    if self.lastState != self.changeRefState : # if the signal parameters have changed
                        self.stateMonotonic += 1
                        self.changeRefState = copy.deepcopy(self.lastState)
                elif msgtype == 6:
                    currentBand = self.activeConfig.getBand()
                    self.tunerStatus.setFreq(currentBand.mapTuneToReq(int(rawval)))
                elif msgtype == 9:
                    self.tunerStatus.setSR(float(rawval)/1000)
                elif msgtype == 12:
                    self.tunerStatus.setMer(float(rawval)/10)
                elif msgtype == 13:
                    self.tunerStatus.setProvider(str(rawval))
                    self.lastState['provider'] = rawval
                elif msgtype == 14:
                    self.tunerStatus.setService(str(rawval))
                    self.lastState['service'] = rawval
                elif msgtype == 18:
                    self.tunerStatus.setModcode(int(rawval))
                    self.lastState['modcode'] = int(rawval)
                elif msgtype == 26:
                    self.tunerStatus.setAGC1(int(rawval))
                elif msgtype == 27:
                    self.tunerStatus.setAGC2(int(rawval))

                # PID list accumulator
                if msgtype == 16: # ES PID
                    self.hasPIDs = True
                    self.pidCacheWait = False
                    if self.pidCachePair[0] == None:
                        self.pidCachePair = (int(rawval), self.pidCachePair[1])
                        if self.pidCachePair[1] != None:
                            self.pidCache[pidCachePair[0]] = pidCachePair[1]
                            self.pidCachePair = (None, None)
                    else:
                        self.pidCacheFault = True
                        print("pid cache fault")
                elif msgtype == 17: # ES Type
                    self.hasPIDs = True
                    self.pidCacheWait = False
                    if self.pidCachePair[1] == None:
                        self.pidCachePair = (self.pidCachePair[0], int(rawval))
                        if self.pidCachePair[0] != None:
                            self.pidCache[self.pidCachePair[0]] = self.pidCachePair[1]
                            self.pidCachePair = (None, None)
                    else:
                        self.pidCacheFault = True
                        print("pid cache fault")
                # update pid status once we have them all (uness there was a fault)
                elif not self.pidCacheWait:
                    if not self.pidCacheFault:
                        self.lastState['pids'] = self.pidCache
                        self.tunerStatus.setPIDs(self.pidCache)
                    self.pidCacheFault = False
                    self.pidCacheWait = True
                    self.pidCache = {}
                    self.pidCachePair= (None,None)
                if(msgtype in [1, 6, 9, 12]):
                    print(str(msgtype)+":"+rawval)

    def processStdout(self):
        """track the starup state of longmynd from its STDOUT"""
        rawnewlines = self.stdoutReadfd.readlines()
        stop = False
        for rawnewline in rawnewlines:
            newline = rawnewline.rstrip()
            self.lmlog.append(newline)
            if not stop:
                if(self.autoresetdetect):
                    if(newline.startswith("ERROR: Tuner set freq") and self.autoresetprogress == 1):
                        self.autoresetprogress = 2
                    elif(newline.startswith("ERROR: Failed to init Tuner") and self.autoresetprogress == 2):
                        self.autoresetprogress = 3
                    elif(newline.startswith("Flow: Caught tuner lock timeout,") and self.autoresetprogress == 3):
                        self.autoresetdetect = False
                        if("attempts at stv6120_init() remaining" in newline):
                            print("Longmynd reset")
                        else:
                            stop = True
                    else:
                        stop = True
                elif(newline.startswith("ERROR:")):
                    # its probably crashed, stop and output
                    # some errors are't critical while lna are initalising, might just be an old NIM
                    if(self.lnaIniting and newline.startswith("ERROR: i2c read reg8")):
                        self.lnaErrorCount += 1
                    elif(newline.startswith("ERROR: tuner wait on lock timed out") and not self.autoresetdetect):
                        self.autoresetdetect = True
                        self.autoresetprogress = 1
                    elif(not (self.lnaIniting and newline.startswith("ERROR: lna read"))):
                        stop = True
                elif(newline.lstrip().startswith("Flow:")):
                    flowline = (newline.lstrip()[6:])
                    if(flowline.startswith("LNA init")):
                        # start tracking LNA initalisation errors
                        self.lnaIniting = True
                        self.lnaErrorCount = 0
                elif(newline.lstrip().startswith("Status:")):
                    lnaLines = ['found new NIM with LNAs', 'found an older NIM with no LNA']
                    statusline = newline.lstrip()[8:]

                    if(statusline in lnaLines):
                        # stop tracking LNA initalisation errors and stop if there are more than expected errors
                        self.lnaIniting = False
                        self.lnaErrorCount = 0
                        if(self.lnaErrorCount > 1):
                            stop = True
                    self.statelog.append(statusline)
                    fifosopen = 0
                    usbopen = False
                    stvopen = False
                    tuneropen = False
                    lnasfound = 0
                    for line in self.statelog:
                        if(line == 'opened fifo ok'):
                            fifosopen += 1
                        elif(line.startswith('MPSSE')):
                            usbopen = True
                        elif(line.startswith('STV0910 MID')):
                            stvopen = True
                        elif(line.startswith('tuner:')):
                            tuneropen = True
                        elif(line in lnaLines):
                            lnasfound += 1
    
                    if(fifosopen==2 and usbopen and stvopen and tuneropen and lnasfound==2):
                        self.lmstarted = True
                        print("lm started")
        if stop:
            self.stop(True,True)

    def _communicate(self, timeout = None):
        if timeout is not None:
            endtime = time.monotonic() + timeout
        else:
            endtime = None
        minloop = 0.1
        catchTimeout = True
        while True:
            endloop = time.monotonic() + minloop
            if endtime is not None and endtime <= endloop:
                endloop = endtime
                catchTimeout = False
            rawnewlines = self.stdoutReadfd.readlines()
            for rawnewline in rawnewlines:
                newline = rawnewline.rstrip()
                self.lmlog.append("Zombie: "+newline)
            if catchTimeout:
                try:
                    self.process.wait(max(endloop-time.monotonic(),0))
                    break
                except subprocess.TimeoutExpired:
                    None
            else:
                self.process.wait(max(endloop-time.monotonic(),0))

    def stop(self, dumpOutput = False, waitfirst=False):
        if self.process is not None:
            #waitfirst is for if its crashed and we want to wait for it to die on its own so we get all the output
            if(waitfirst):
                try:
                    self._communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    dumpOutput=True
                    self.process.kill()
                    print("Killed during fatal")
                    self._communicate()
            else:
                self.process.terminate()
                try:
                    self._communicate(timeout=4)
                except subprocess.TimeoutExpired:
                    dumpOutput=True
                    self.process.kill()
                    print("Killed during requested")
                self._communicate()
        os.close(self.stdoutWritefd)
        #Drain the stdout buffer
        while True:
            try:
                rawnewline = self.stdoutReadfd.readline()
            except IOError as e:
                break
            newline = rawnewline.rstrip()
            self.lmlog.append(newline)

        self.stdoutReadfd.close()
        self.statusFIFOfd.close()
        #open a clean buffer ready for the restart

        self.statusFIFOfd = os.fdopen(os.open(self.statusFIFOfilename, flags=os.O_NONBLOCK, mode=os.O_RDONLY), encoding="utf-8", errors="replace")
        rpipe, self.stdoutWritefd = pty.openpty()
        flags = fcntl.fcntl(rpipe, fcntl.F_GETFL)
        flags |= os.O_NONBLOCK
        fcntl.fcntl(rpipe, fcntl.F_SETFL, flags)
        self.stdoutReadfd = os.fdopen(rpipe, 'r')
        self.process = None
        #TODO: parse this and display a meaningful message on screen
        if dumpOutput:
            for logline in self.lmlog:
                print(logline)

    def cleanup(self):
        os.close(self.stdoutWritefd)
        #Drain the stdout buffer
        while True:
            try:
                rawnewline = self.stdoutReadfd.readline()
            except IOError as e:
                break
            newline = rawnewline.rstrip()
            self.lmlog.append(newline)
        self.stdoutReadfd.close()
        self.statusFIFOfd.close()
        self.vlcMediaFd.close()

    def _fetchFtdiDevices(self):
        pyftdi.usbtools.UsbTools.flush_cache()
        foundDevices = pyftdi.ftdi.Ftdi.list_devices("ftdi://ftdi:2232h/1")
        devices = {}
        for deviceDesc in foundDevices:
            device = pyftdi.usbtools.UsbTools.get_device(deviceDesc[0])
            eeprom = pyftdi.eeprom.FtdiEeprom()
            eeprom.open(device)
            signature = []
            for prop in sorted(list(eeprom.properties)+['product']):
                signature.append((prop,getattr(eeprom, prop)))
            devices[deviceDesc]=frozenset(signature)
            eeprom.close()
            device.reset()
            pyftdi.usbtools.UsbTools.release_device(device)
        return devices

    def start(self):
        if self.activeConfig.isValid():
            if self.process == None :
                devices = self._fetchFtdiDevices()
                validTuners = [rydeplayer.sources.common.ftdiConfigs.MINITIOUNER.configSet, rydeplayer.sources.common.ftdiConfigs.MINITIOUNEREXPRESS.configSet, rydeplayer.sources.common.ftdiConfigs.MINITIOUNER_S.configSet, rydeplayer.sources.common.ftdiConfigs.MINITIOUNER_PRO_TS1.configSet, rydeplayer.sources.common.ftdiConfigs.MINITIOUNER_PRO_TS2.configSet]
                foundDevice = None
                for device in devices:
                    if devices[device] in validTuners:
                        foundDevice = device
                        break
                if foundDevice is not None:
                    print("start")
                    self.lmstarted = False
                    self.statusrecv = False
                    self.autoresetdetect = False
                    self.statelog=[]
                    self.lmlog=[]
                    args = [self.lmpath, '-t', self.mediaFIFOfilename, '-s', self.statusFIFOfilename, '-r', str(self.tsTimeout), '-u', str(foundDevice[0].bus), str(foundDevice[0].address)]
                    if self.activeConfig.band.getInputPort() == inPortEnum.BOTTOM:
                        args.append('-w')
                    if self.activeConfig.band.getPolarity() == PolarityEnum.HORIZONTAL:
                        args.extend(['-p', 'h'])
                    elif self.activeConfig.band.getPolarity() == PolarityEnum.VERTICAL:
                        args.extend(['-p', 'v'])

                    # generate frequency scan string
                    freqStrings = []
                    for freqVal in self.activeConfig.freq:
                        freqStrings.append(str(self.activeConfig.band.mapReqToTune(freqVal.getValue())))

                    # generate symbol rate scan string
                    srStrings = []
                    for srVal in self.activeConfig.sr:
                        srStrings.append(str(srVal.getValue()))

                    args.append(",".join(freqStrings))
                    args.append(",".join(srStrings))
                    print(args)
                    self.process = subprocess.Popen(args, stdout=self.stdoutWritefd, stderr=subprocess.STDOUT, bufsize=0)
                else:
                    print("No MiniTiouner USB module found")
            else:
                print("LM already running")
        else:
            print("Can't start, config invalid")
    def restart(self):
        if self.process is not None:
            if not self.statusrecv:
                time.sleep(0.2)
            self.stop()
        self.start()

class config(object):
    def __init__(self, binpath = '/home/pi/longmynd/longmynd', mediapath = '/home/pi/lmmedia', statuspath = '/home/pi/lmstatus', tstimeout = 5000):
        self.binpath = binpath
        self.mediapath = mediapath
        self.statuspath = statuspath
        self.tstimeout = tstimeout

    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            if 'binpath' in config:
                if isinstance(config['binpath'], str):
                    self.binpath = config['binpath']
                    # TODO: check this path is valid
                else:
                    print("Invalid longmynd binary path")
                    perfectConfig = False
            if 'mediapath' in config:
                if isinstance(config['mediapath'], str):
                    self.mediapath = config['mediapath']
                else:
                    print("Invalid longmynd media FIFO path")
                    perfectConfig = False
            if 'statuspath' in config:
                if isinstance(config['statuspath'], str):
                    self.statuspath = config['statuspath']
                else:
                    print("Invalid longmynd status FIFO path")
                    perfectConfig = False
            if 'tstimeout' in config:
                if isinstance(config['tstimeout'], int):
                    self.tstimeout = config['tstimeout']
                else:
                    print("Invalid longmynd TS timeout")
                    perfectConfig = False
        else:
            print("Invalid longmynd config")
            perfectConfig = False
        return perfectConfig

class band(rydeplayer.sources.common.tunerBand):
    def __init__(self):
        self.source = rydeplayer.sources.common.sources.LONGMYND
        self.pol = PolarityEnum.NONE
        self.port = inPortEnum.TOP
        super().__init__()
        self.multiFreq=True
        self.tunerMinFreq = 144000
        self.tunerMaxFreq = 2450000
        self.defaultfreq = 741500

    def dumpBand(self):
        super().dumpBand()
        self.dumpCache['pol'] = self.pol.name.upper()
        self.dumpCache['port'] = self.port.name.upper()
        return self.dumpCache

    @classmethod
    def loadBand(cls, config):
        perfectConfig = True
        # create a new instance of this class
        self = cls()
        if 'pol' in config:
            if isinstance(config['pol'], str):
                polset = False
                for polopt in PolarityEnum:
                    if polopt.name == config['pol'].upper():
                        self.pol = polopt
                        polset = True
                        configUpdated = True
                        break
                if not polset:
                    print("Polarity config invalid, skipping")
                    perfectConfig = False
            else:
                print("Polarity config invalid, skipping")
                perfectConfig = False
        else:
            print("Polarity config missing, skipping")
            perfectConfig = False
        if 'port' in config:
            if isinstance(config['port'], str):
                portset = False
                for portopt in inPortEnum:
                    if portopt.name == config['port'].upper():
                        self.port = portopt
                        polset = True
                        configUpdated = True
                        break
                if not polset:
                    print("Input port config invalid, skipping")
                    perfectConfig = False
            else:
                print("Input port config invalid, skipping")
                perfectConfig = False
        else:
            print("Input port config missing, skipping")
            perfectConfig = False
        return (perfectConfig, self)

    # takes a current set of vars and adjusts them to be compatible with this sub band
    def syncVars(self, oldVars):
        # remove keys this class handles and pass all others to the superclass to process
        updated, newVars = super().syncVars({key:oldVars[key] for key in oldVars if key!='sr'})
        # sync prerequisites
        if updated:
            newVars['freq'].addPrereqs({'sr'})
        # keep old sr if it exsisted or create a new one
        if 'sr' in oldVars and isinstance(oldVars['sr'], rydeplayer.sources.common.tunerConfigIntList):
            newVars['sr'] = oldVars['sr']
            # remove prerequisites from to deleted vars
            removedVars = set(oldVars.keys())-set(newVars.keys())
            if len(removedVars) > 0:
                newVars['sr'].removePrereqs(removedVars)
                varsUpdated = True
        else:
            newVars['sr'] = newVars['sr'] = rydeplayer.sources.common.tunerConfigIntList(1500, 33, 27500, True, 'kS', 'SR', 'Symbol Rate', {'freq'})
            updated = True
        return (updated, newVars)

    def getPolarity(self):
        return self.pol

    def getInputPort(self):
        return self.port

    def __eq__(self, other):
        #compare 2 longmynd bands
        if not isinstance(other, self.__class__):
            return False
        else:
            comp = super().__eq__(other) and self.pol == other.pol and self.port == other.port
            return comp

    def __hash__(self):
        return hash((super().__hash__(), self.pol, self.port))

class source(rydeplayer.sources.common.source):
    @classmethod
    def getConfig(cls):
        return config

    @classmethod
    def getBand(cls):
        return band

    @classmethod
    def getNewStatus(cls):
        return tunerStatus

    @classmethod
    def getManager(cls):
        return lmManager

    @classmethod
    def getSource(cls, enum):
        if enum == rydeplayer.sources.common.sources.LONGMYND:
            return cls
        else:
            return False
