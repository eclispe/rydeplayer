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

import enum, os, stat, subprocess, pty, select, copy, fcntl, collections, time, socket, queue, threading
import rydeplayer.common
import rydeplayer.sources.common
import pyftdi.ftdi
import pyftdi.usbtools
import pyftdi.eeprom

class DVBTVersionEnum(enum.Enum):
    DVBT = enum.auto()
    DVBT2 = enum.auto()

def genDVBTModulationEnum():
    # generate enum for all DVB-T and DVB-T2 modulations
    members = {}
    for fftopt in {'2K':'2', '8K':'8'}.items():
        for constopt in {'QPSK':'Q', '16 QAM':'16', '64 QAM':'64'}.items():
            for fecopt in {'1/2':'1_2', '2/3':'2_3', '3/4':'3_4', '5/6':'5_6', '7/8':'7_8'}.items():
                for guardopt in {'1/4':'1_4', '1/8':'1_8', '1/16':'1_16', '1/32':'1_32'}.items():
                    enumid = "T_" + fftopt[1] + "_" + constopt[1] + "_" + fecopt[1] + "_" + guardopt[1]
                    enumnicename = "DVB-T " + fftopt[0] + " " + constopt[0] + " " + fecopt[0] + " " + guardopt[0]
                    members[enumid]=(enum.auto(), enumnicename)

    for fftopt in {'1K':'1', '2K':'2', '4K':'4', '8K':'8', '16K':'16', '32K':'32'}.items():
        for constopt in {'QPSK':'Q', '16 QAM':'16', '64 QAM':'64', '256 QAM':'256'}.items():
            for fecopt in {'1/2':'1_2', '3/5':'3_5', '2/3':'2_3', '3/4':'3_4', '4/5':'4_5', '5/6':'5_6', '6/7':'6_7', '8/9':'8/9'}.items():
                for guardopt in {'1/4':'1_4', '19/128':'19_128', '1/8':'1_8', '19/256':'19_256', '1/16':'1_16', '1/32':'1_32', '1/128':'1_128'}.items():
                    enumid = "T2_" + fftopt[1] + "_" + constopt[1] + "_" + fecopt[1] + "_" + guardopt[1]
                    enumnicename = "DVB-T2 " + fftopt[0] + " " + constopt[0] + " " + fecopt[0] + " " + guardopt[0]
                    members[enumid]=(enum.auto(), enumnicename)
    return rydeplayer.sources.common.sourceModeEnum("DVBTModulationEnum",members)

DVBTModulationEnum = genDVBTModulationEnum()

# Container for tuner status data with change callbacks
class tunerStatus(rydeplayer.sources.common.sourceStatus):
    def __init__(self):
        super().__init__()
        self.ssi = None
        self.sqi = None
        self.snr = None
        self.per = None
        self.bw = None

    def setSSI(self, newval):
        if(isinstance(newval, float)):
            if self.ssi != newval:
                self.ssi = newval
                self.onChangeFire()
                return True
            else:
                return False
        elif(isinstance(newval, int)):
            if self.ssi != float(newval):
                self.ssi = float(newval)
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setSQI(self, newval):
        if(isinstance(newval, float)):
            if self.sqi != newval:
                self.sqi = newval
                self.onChangeFire()
                return True
            else:
                return False
        elif(isinstance(newval, int)):
            if self.sqi != float(newval):
                self.sqi = float(newval)
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setSNR(self, newval):
        if(isinstance(newval, float)):
            if self.snr != newval:
                self.snr = newval
                self.onChangeFire()
                return True
            else:
                return False
        elif(isinstance(newval, int)):
            if self.snr != float(newval):
                self.snr = float(newval)
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setPER(self, newval):
        if(isinstance(newval, float)):
            if self.per != newval:
                self.per = newval
                self.onChangeFire()
                return True
            else:
                return False
        elif(isinstance(newval, int)):
            if self.per != float(newval):
                self.per = float(newval)
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setDVBVersion(self, newval):
        if(isinstance(newval, DVBTVersionEnum) or newval is None):
            if(newval != self.dvbVersion):
                self.dvbVersion = newval
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setModcode(self, newval):
        if isinstance(newval, modPartialType):
            newMod = None
            if self.dvbVersion is None:
                newMod = None
            else:
                if newval.asEnumString() in DVBTModulationEnum._member_names_:
                    newMod = DVBTModulationEnum[newval.asEnumString()]
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

    def setBW(self, newval):
        if(isinstance(newval, float)):
            if self.bw != newval:
                self.bw = newval
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def getSSI(self):
        return self.ssi
    
    def getSQI(self):
        return self.sqi

    def getSNR(self):
        return self.snr

    def getPER(self):
        return self.per

    def getBW(self):
        return self.bw

    def getSignalLevelMeta(self):
        def processVal(newval):
            return newval.getSNR()
        return self.meterConfig("dB SNR","", processVal)

    def getSignalReportMeta(self):
        def processVal(newval):
            return newval.getSQI()
        return self.meterConfig("% SQI","", processVal)

    def getSignalBandwidthMeta(self):
        def processVal(newval):
            return newval.getBW()
        return self.numericConfig("Hz",3, processVal)

    def setStatusToMatch(self, fromStatus):
        changed = super().setStatusToMatch(fromStatus)
        newSSI = fromStatus.getSSI()
        if self.ssi != newSSI:
            self.ssi = newSSI
            changed = True
        newSQI = fromStatus.getSQI()
        if self.sqi != newSQI:
            self.sqi = newSQI
            changed = True
        newSNR = fromStatus.getSNR()
        if self.snr != newSNR:
            self.snr = newSNR
            changed = True
        newPER = fromStatus.getPER()
        if self.per != newPER:
            self.per = newPER
            changed = True
        newBW = fromStatus.getBW()
        if self.bw != newBW:
            self.bw = newBW
            changed = True
        if changed:
            self.onChangeFire()

# container class for itemized modulation types
class modPartialType(object):
    def __init__(self, default=None):
        if default is not None:
            self.mod=default[0]
            self.fft=default[1]
            self.const=default[2]
            self.fec=default[3]
            self.guard=default[4]
        else:
            self.mod=None
            self.fft=None
            self.const=None
            self.fec=None
            self.guard=None
    def asTuple(self):
        return (self.mod, self.fft, self.const, self.fec, self.guard)
    def asEnumString(self):
        # return the name of the relevent enum member 
        modstrparts = []
        modveropts = {'DVB-T':'T', 'DVB-T2':'T2'}
        if self.mod in modveropts:
            modstrparts.append(modveropts[self.mod])
        else:
            return False
        modfftopts = {'1K':'1', '2K':'2', '4K':'4', '8K':'8', '16K':'16', '32K':'32'}
        if self.fft in modfftopts:
            modstrparts.append(modfftopts[self.fft])
        else:
            return False
        modconstopts = {'QPSK':'Q', '16 QAM':'16', '64 QAM':'64', '256 QAM':'256'}
        if self.const in modconstopts:
            modstrparts.append(modconstopts[self.const])
        else:
            return False
        modfecopts = {'1/2':'1_2', '3/5':'3_5', '2/3':'2_3', '3/4':'3_4', '4/5':'4_5', '5/6':'5_6', '6/7':'6_7', '7/8':'7_8', '8/9':'8/9'}
        if self.fec in modfecopts:
            modstrparts.append(modfecopts[self.fec])
        else:
            return False
        modguardopts = {'1/4':'1_4', '19/128':'19_128', '1/8':'1_8', '19/256':'19_256', '1/16':'1_16', '1/32':'1_32', '1/128':'1_128'}
        if self.guard in modguardopts:
            modstrparts.append(modguardopts[self.guard])
        else:
            return False
        return '_'.join(modstrparts)
    def __repr__(self):
        return self.__class__.__qualname__+"("+repr(self.asTuple())+")"
    def __eq__(self, other):
        return other.asTuple() == self.asTuple()

class combiTunerManager(object):
    def __init__(self, config, sourceConfig):
        # path to the combituner binary
        self.ctpath = sourceConfig.binpath
        self.mediaFIFOfilename = sourceConfig.mediapath
        #TODO: add error handling here
        if(not os.path.exists(self.mediaFIFOfilename)):
            os.mkfifo(self.mediaFIFOfilename)
            print("made")
        elif(not stat.S_ISFIFO(os.stat(self.mediaFIFOfilename).st_mode)):
            print("media pipe is not a fifo")
        self.vlcMediaFd = os.open(self.mediaFIFOfilename, flags=os.O_NONBLOCK|os.O_RDONLY) # an open file descriptor to pass to vlc (or another player)
        rpipe, self.stdoutWritefd = pty.openpty() # a pty for interacting with combituners STDOUT, couldn't get pipes to work
        flags = fcntl.fcntl(rpipe, fcntl.F_GETFL)
        flags |= os.O_NONBLOCK
        fcntl.fcntl(rpipe, fcntl.F_SETFL, flags)
        self.stdoutReadfd = os.fdopen(rpipe, 'r')
        self.process = None
        self.statelog = [] # log of important things from CombiTuners STDOUT
        self.ctlog = [] # a complete CombiTuner output log, for debugging
        self.ctrunning = False
        self.ctlocked = False
        self.activeConfig = config.copyConfig()
        self.lastState = { 'locked':None, 'modcode': modPartialType() }
        self.changeRefState = copy.deepcopy(self.lastState)
        self.stateMonotonic = 0
        self.tunerStatus = tunerStatus()
        # state type for the core combituner state
        self.coreStateType = collections.namedtuple('coreState', ['isRunning', 'isStarted', 'isLocked', 'monotonicState'])

    def reconfig(self, config):
        """reconfigures CombiTuner"""
        if(isinstance(config, rydeplayer.sources.common.tunerConfig) and config != self.activeConfig):
            self.activeConfig = config.copyConfig()
            print(self.activeConfig)
            self.restart()
    def remedia(self):
        os.close(self.vlcMediaFd)
        self.vlcMediaFd = os.open(self.mediaFIFOfilename, flags=os.O_NONBLOCK, mode=os.O_RDONLY) # an open file descriptor to pass to vlc (or another player)
    def getMediaFd(self):
        return self.vlcMediaFd
    def getFDs(self):
        return [self.stdoutReadfd]
    def getStatus(self):
        return self.tunerStatus
    def handleFD(self, fd):
        """handles a file descriptor that has data to read"""
        fdCallbacks = dict()
        fdCallbacks[self.stdoutReadfd] = self.processStdout
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
        if(self.process != None and self.ctrunning):# and self.statusrecv):
            polled = self.process.poll()
            return polled==None
        else:
            return False
    def isLocked(self):
        """returns if CombiTuner is locked on to a signal
        This does not mean it can be decoded, signal level may still be too low
        """
        if(self.isRunning()):
            print("state:"+str(self.lastState))
            if(self.lastState['locked']):
                return True
            else:
                return False
        else:
            return False
    def getMonotonicState(self):
        return self.stateMonotonic
    
    def processStdout(self):
        """track the state of combituner from its STDOUT"""
        rawnewlines = self.stdoutReadfd.readlines()
        stop = False
        for rawnewline in rawnewlines:
            newline = rawnewline.rstrip()
            self.ctlog.append(newline)
            if not stop:
                # Lines that are expected from CombiTuner for it to be considered "Started"
                goodlines = set([
                        "[GetChipId] chip id:AVL6862",
                        "[GetFamilyId] Family ID:0x4955",
                        "[AVL_Init] AVL_Initialize Booted!",
                        "[AVL_Init] ok",
                        "[DVB_Tx_tuner_Lock] Tuner locked!",
                        ])
                # Not running, tuner probably not powered, stop and output
                if newline.lstrip().startswith("Failed to Init demod!"):
                    stop=True
                # its probably crashed, stop and output
                elif newline.rstrip().endswith(",Err."):
                    # you get this error when no signal present so its fine
                    if not newline.lstrip().startswith("[DVBTx_Channel_ScanLock_Example] DVBTx channel scan is fail,Err."):
                        stop=True
                elif newline.lstrip().startswith("locked"):
                    self.ctlocked = True
                elif newline.lstrip().startswith("Unlocked"):
                    self.ctlocked = False
                    self.lastState['modcode']= modPartialType()
                elif newline.lstrip().startswith("MOD"):
                    rawtype,rawval = newline.lstrip().rstrip().split(':',1)
                    if rawval.lstrip() in ['DVB-T', 'DVB-T2']:
                        self.lastState['modcode'].mod = rawval.lstrip()
                        if rawval.lstrip() == 'DVB-T':
                            self.tunerStatus.setDVBVersion(DVBTVersionEnum.DVBT)
                        if rawval.lstrip() == 'DVB-T2':
                            self.tunerStatus.setDVBVersion(DVBTVersionEnum.DVBT2)
                    else:
                        self.tunerStatus.setDVBVersion(None)
                elif newline.lstrip().startswith("FFT"):
                    rawtype,rawval = newline.lstrip().rstrip().split(':',1)
                    if rawval.lstrip() in ['1K', '2K', '4K', '8K', '16K', '32K']:
                        self.lastState['modcode'].fft = rawval.lstrip()
                elif newline.lstrip().startswith("Const"):
                    rawtype,rawval = newline.lstrip().rstrip().split(':',1)
                    if rawval.lstrip() in ['QPSK', '16 QAM', '64 QAM', '256 QAM']:
                        self.lastState['modcode'].const = rawval.lstrip()
                elif newline.lstrip().startswith("FEC"):
                    rawtype,rawval = newline.lstrip().rstrip().split(':',1)
                    if rawval.lstrip() in ['1/2', '3/5', '2/3', '3/4', '4/5', '5/6', '6/7', '7/8', '8/9']:
                        self.lastState['modcode'].fec = rawval.lstrip()
                elif newline.lstrip().startswith("Guard"):
                    rawtype,rawval = newline.lstrip().rstrip().split(':',1)
                    if rawval.lstrip() in ['1/4', '19/128', '1/8', '19/256', '1/16', '1/32', '1/128']:
                        self.lastState['modcode'].guard = rawval.lstrip()
                elif newline.lstrip().startswith("SSI"):
                    rawtype,rawval = newline.lstrip().rstrip().split(' is ',1)
                    self.tunerStatus.setSSI(float(rawval))
                elif newline.lstrip().startswith("SQI"):
                    rawtype,rawval = newline.lstrip().rstrip().split(' is ',1)
                    self.tunerStatus.setSQI(float(rawval))
                elif newline.lstrip().startswith("SNR"):
                    rawtype,rawval = newline.lstrip().rstrip().split(' is ',1)
                    self.tunerStatus.setSNR(float(rawval))
                elif newline.lstrip().startswith("PER"):
                    rawtype,rawval = newline.lstrip().rstrip().split(' is ',1)
                    self.tunerStatus.setPER(float(rawval))
                elif newline.lstrip().startswith("[AVL_LockChannel_T] Freq is "):
                    statparts = newline[20:].rstrip().split(', ',2)
                    for statpart in statparts:
                        name,value = statpart.split(" is ", 1)
                        if name == "Freq":
                            cleanvalue = int(value.rstrip()[:-4])*1000
                            self.tunerStatus.setFreq(cleanvalue)
                        elif name == "Bandwidth":
                            cleanvalue = float(value.rstrip()[:-4])*1000
                            self.tunerStatus.setBW(cleanvalue)
                else:
                    statusupdated = False
                    for goodline in goodlines:
                        if newline.lstrip().startswith(goodline):
                            self.statelog.append(goodline)
                            statusupdated = True
                    if statusupdated:
                        reqlines = goodlines.copy()
                        for line in self.statelog:
                            if line in reqlines:
                                reqlines.remove(line)
                        if len(reqlines)<1:
                            self.ctrunning = True
                            print("ct started")
                self.lastState['locked'] = self.ctlocked
                if self.lastState != self.changeRefState : # if the signal parameters have changed
                    self.tunerStatus.setModcode(self.lastState['modcode'])
                    self.stateMonotonic += 1
                    self.changeRefState = copy.deepcopy(self.lastState)

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
                self.ctlog.append("Zombie: "+newline)
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
            self.ctlog.append(newline)

        self.stdoutReadfd.close()
        #open a clean buffer ready for the restart

        rpipe, self.stdoutWritefd = pty.openpty()
        flags = fcntl.fcntl(rpipe, fcntl.F_GETFL)
        flags |= os.O_NONBLOCK
        fcntl.fcntl(rpipe, fcntl.F_SETFL, flags)
        self.stdoutReadfd = os.fdopen(rpipe, 'r')
        self.process = None
        #TODO: parse this and display a meaningful message on screen
        if dumpOutput:
            for logline in self.ctlog:
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
            self.ctlog.append(newline)
        self.stdoutReadfd.close()
        os.close(self.vlcMediaFd)

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
                validTuners = [rydeplayer.sources.common.ftdiConfigs.COMBITUNER.configSet]
                foundDevice = None
                for device in devices:
                    if devices[device] in validTuners:
                        foundDevice = device
                        break
                if foundDevice is not None:
                    print("start")
                    self.ctrunning = False
                    self.ctlocked = False
#                    self.autoresetdetect = False
                    self.statelog=[]
                    self.ctlog=[]
                    freqstr = str(self.activeConfig.band.mapReqToTune(self.activeConfig.freq.getValue()))
                    bwstr = str(self.activeConfig.bw.getValue())
                    args = [self.ctpath, '-m', 'dvbt', '-f', freqstr, '-b', bwstr, '-n', self.mediaFIFOfilename]


                    print(args)
                    self.process = subprocess.Popen(args, stdout=self.stdoutWritefd, stderr=subprocess.STDOUT, bufsize=0)
#                    self.tunerStatus.onChangeFire()
                else:
                    print("No CombiTuner USB module found")
            else:
                print("CombiTuner already running")
        else:
            print("Can't start, config invalid")
    def restart(self):
        if self.process is not None:
            time.sleep(0.2)
            self.stop()
        self.start()

class config(object):
    def __init__(self, binpath = '/home/pi/combituner/CombiTunerExpress', mediapath = '/home/pi/ctmedia'):
        self.binpath = binpath
        self.mediapath = mediapath

    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            if 'binpath' in config:
                if isinstance(config['binpath'], str):
                    self.binpath = config['binpath']
                    # TODO: check this path is valid
                else:
                    print("Invalid CombiTuner binary path")
                    perfectConfig = False
            if 'mediapath' in config:
                if isinstance(config['mediapath'], str):
                    self.mediapath = config['mediapath']
                else:
                    print("Invalid CombiTuner media FIFO path")
                    perfectConfig = False
        else:
            print("Invalid CombiTuner config")
            perfectConfig = False
        return perfectConfig

class band(rydeplayer.sources.common.tunerBandRF):
    def __init__(self):
        self.source = rydeplayer.sources.common.sources.COMBITUNER
        super().__init__()
        self.source = rydeplayer.sources.common.sources.COMBITUNER
        self.multiFreq = False
        self.tunerMinFreq = 44000
        self.tunerMaxFreq = 1002000
        self.defaultfreq = 474000

    def dumpBand(self):
        super().dumpBand()
        return self.dumpCache

    @classmethod
    def loadBand(cls, config):
        perfectConfig = True
        subClassSuccess, self = super(band, cls).loadBand(config)
        perfectConfig = perfectConfig and subClassSuccess
        return (perfectConfig, self)

    # takes a current set of vars and adjusts them to be compatible with this sub band
    def syncVars(self, oldVars):
        # remove keys this class handles and pass all others to the superclass to process
        updated, newVars = super().syncVars({key:oldVars[key] for key in oldVars if key!='bw'})
        # sync prerequisites
        if updated:
            newVars['freq'].addPrereqs({'bw'})
        # keep old sr if it exsisted or create a new one
        if 'bw' in oldVars and isinstance(oldVars['bw'], rydeplayer.sources.common.tunerConfigInt):
            newVars['bw'] = oldVars['bw']
            # remove prerequisites from to deleted vars
            removedVars = set(oldVars.keys())-set(newVars.keys())
            if len(removedVars) > 0:
                newVars['bw'].removePrereqs(removedVars)
                varsUpdated = True
        else:
            newVars['bw'] = newVars['bw'] = rydeplayer.sources.common.tunerConfigInt(8000, 150, 8000, 'kHz', 'Bandwidth', {'freq'})
            updated = True
        return (updated, newVars)

    def __eq__(self, other):
        #compare 2 combituner bands
        if not isinstance(other, self.__class__):
            return False
        else:
            comp = super().__eq__(other)
            return comp

    def __hash__(self):
        return super().__hash__()

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
        return combiTunerManager

    @classmethod
    def getSource(cls, enum):
        if enum == rydeplayer.sources.common.sources.COMBITUNER:
            return cls
        else:
            return False
