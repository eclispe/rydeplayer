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
import pyftdi.ftdi
import pyftdi.usbtools
import pyftdi.eeprom

class sources(enum.Enum):
    LONGMYND = enum.auto()

    def getSource(self):
        thisSource = rydeplayer.sources.common.source.getSource(self)
        if isinstance(thisSource,type) and issubclass(thisSource, rydeplayer.sources.common.source):
            return thisSource
        else:
            raise NotImplementedError

class source(object):
    @classmethod
    def getConfig(cls):
        raise NotImplementedError

    @classmethod
    def getBand(cls):
        raise NotImplementedError

    @classmethod
    def getNewStatus(cls):
        raise NotImplementedError

    @classmethod
    def getManager(cls):
        raise NotImplementedError

    @classmethod
    def getSource(cls, enum):
        # recurse over all subclasses looking for one that claims it handles the requested source
        for subcls in cls.__subclasses__():
            thisSource = subcls.getSource(enum)
            if isinstance(thisSource,type) and issubclass(thisSource, cls):
                return thisSource
        return False

class LOOffsetSideEnum(enum.Enum):
    HIGH = enum.auto()
    LOW = enum.auto()
    SUM = enum.auto()

class CodecEnum(enum.Enum):
    MP2  = (enum.auto(), "MPEG-2")
    MPA  = (enum.auto(), "MPA")
    AAC  = (enum.auto(), "AAC")
    H263 = (enum.auto(), "H.263")
    H264 = (enum.auto(), "H.264")
    H265 = (enum.auto(), "H.265")

    def __init__(self, enum, longName):
        self.longName = longName
    def __str__(self):
        return self.longName

class ftdiConfigs(enum.Enum):
    UNKNOWN = (enum.auto(), frozenset(), False)
    GENERAL = (enum.auto(), frozenset([
        ('channel_a_type', 'UART'),
        ('group_0_drive', 16),
        ('group_0_schmitt', False),
        ('group_0_slow_slew', False),
        ('group_1_drive', 16),
        ('group_1_schmitt', False),
        ('group_1_slow_slew', False),
        ('group_2_drive', 16),
        ('group_2_schmitt', False),
        ('group_2_slow_slew', False),
        ('group_3_drive', 16),
        ('group_3_schmitt', False),
        ('group_3_slow_slew', False),
        ('has_serial', True),
        ('in_isochronous', False),
        ('out_isochronous', False),
        ('product_id', 24592),
        ('suspend_dbus7', pyftdi.eeprom.FtdiEeprom.CFG1(0)),
        ('suspend_pull_down', False),
        ('type', 1792),
        ('vendor_id', 1027)
    ]), False)
    TUNER = (enum.auto(), GENERAL[1] | frozenset([
        ('channel_a_driver', 'D2XX'),
        ('channel_b_driver', 'D2XX'),
        ('channel_b_type', 'FIFO'),
        ('remote_wakeup', False),
        ('self_powered', True),
        ('power_max', 0)
    ]), False)
    TUNER256 = (enum.auto(), TUNER[1] | frozenset([
        ('chip', 86),
    ]), False)
    FACTORY = (enum.auto(), GENERAL[1] | frozenset([
        ('channel_a_driver', 'VCP'),
        ('channel_b_driver', 'VCP'),
        ('channel_b_type', 'UART'),
        ('chip', 86),
        ('power_max', 150),
        ('product', 'FT2232H MiniModule'),
        ('remote_wakeup', True),
        ('self_powered', False),
    ]), True)
    MINITIOUNER = (enum.auto(), TUNER256[1] | frozenset([
        ('product', 'USB <-> NIM tuner'),
    ]), True)
    MINITIOUNEREXPRESS = (enum.auto(), TUNER[1] | frozenset([
        ('chip', 70),
        ('product', 'MiniTiouner-Express'),
    ]), True)
    MINITIOUNER_S = (enum.auto(), TUNER256[1] | frozenset([
        ('product', 'MiniTiouner'),
    ]), True)
    MINITIOUNER_PRO_TS1 = (enum.auto(), TUNER256[1] | frozenset([
        ('product', 'MiniTiouner_Pro_TS1'),
    ]), True)
    MINITIOUNER_PRO_TS2 = (enum.auto(), TUNER256[1] | frozenset([
        ('product', 'MiniTiouner_Pro_TS2'),
    ]), True)
    KNUCKER = (enum.auto(), TUNER256[1] | frozenset([
        ('product', 'CombiTuner-Express'),
    ]), True)

    def __init__(self, enum, configset, canIdentify):
        self._configset = configset
        self._canIdentify = canIdentify

    @property
    def configSet(self):
        return self._configset

    @property
    def canIdentify(self):
        return self._canIdentify

class sourceStatus(object):
    def __init__(self):
        self.onChangeCallbacks = []
        self.meterConfig = collections.namedtuple('meterConfig', ["staticText", "prefixText", "processValueFunc"])
        self.numericConfig = collections.namedtuple('numericConfig', ["staticUnits", "unitMagnitude", "processValueFunc"])

    def addOnChangeCallback(self, callback):
        self.onChangeCallbacks.append(callback)

    def removeOnChangeCallback(self, callback):
        self.onChangeCallbacks.remove(callback)

    def addCallbacksFrom(self, fromconfig):
        fromCallbacks = fromconfig.onChangeCallbacks
        toCallbacks = fromCallbacks.copy()
        self.onChangeCallbacks.extend(toCallbacks)

    def onChangeFire(self):
        for callback in self.onChangeCallbacks:
            callback(self)

    def getSignalLevelMeta(self):
        return None

    def getSignalReportMeta(self):
        return None

    def getSignalSourceMeta(self):
        return None

    def getSignalBandwidthMeta(self):
        return None

    def setStatusToMatch(self, fromStatus):
        changed = False
        return changed

class tunerBand(object):
    _defaultSource = sources.LONGMYND
    def __init__(self):
        self.source = self._defaultSource
        self.freq = 0
        self.loside = LOOffsetSideEnum.LOW
        self.gpioid = 0
        self.dumpCache = {}
        self.dumpCache = self.dumpBand()
        self.tunerMinFreq=0
        self.tunerMaxFreq=0
        self.defaultfreq=0
        self.multiFreq=False

    def dumpBand(self):
        self.dumpCache['lofreq'] = self.freq
        self.dumpCache['loside'] = self.loside.name.upper()
        self.dumpCache['gpioid'] = self.gpioid
        return self.dumpCache

    @classmethod
    def getDefaultBand(cls):
        return cls._defaultSource.getSource().getBand()()

    @classmethod
    def loadBand(cls, config):
        configUpdated = False
        perfectConfig = True
        # load the default band if there is no config at all
        if not isinstance(config, dict):
            print("Band invalid, skipping")
            perfectConfig = False
            self = cls._defaultSource.getSource().getBand()()
        else:
            # parse and set source type
            source = cls._defaultSource
            if 'source' in config:
                if isinstance(config['source'], str):
                    sourceset = False
                    for sourceopt in rydeplayer.sources.common.sources:
                        if sourceopt.name == config['source'].upper():
                            source = sourceopt
                            sourceset = True
                            configUpdated = True
                            break
                    if not sourceset:
                        print("Source config invalid, skipping")
                        perfectConfig = False
                else:
                    print("Source config invalid, skipping")
                    perfectConfig = False
            # create band object from selected source
            subClassSuccess, self = source.getSource().getBand().loadBand(config)
            perfectConfig = perfectConfig and subClassSuccess
            # check lo frequency and side, both must be valid for either to be updated
            if 'lofreq' in config:
                if isinstance(config['lofreq'], int):
                    # lo frequency is valid, check side
                    if 'loside' in config:
                        if isinstance(config['loside'], str):
                            for losideopt in LOOffsetSideEnum:
                                if losideopt.name == config['loside'].upper():
                                    self.loside = losideopt
                                    self.freq = config['lofreq']
                                    configUpdated = True
                                    break
                        if not configUpdated:
                            print("Band LO side invalid, skipping frequency and LO side")
                            perfectConfig = False
                    else:
                        print("Band LO side missing, skipping frequency and LO side")
                        perfectConfig = False
                else:
                    print("LO frequency config invalid, skipping frequency and symbol rate")
                    perfectConfig = False
            else:
                print("LO frequency config missing, skipping frequency and symbol rate")
                perfectConfig = False
            if 'gpioid' in config:
                if isinstance(config['gpioid'], int):
                    if config['gpioid'] < 8 and config['gpioid'] >= 0:
                        self.gpioid = config['gpioid']
                        configUpdated = True
                    else:
                        print("GPIO ID config out of range, skipping")
                        perfectConfig = False
                else:
                    print("GPIO ID config invalid, skipping")
                    perfectConfig = False
            else:
                print("GPIO ID config missing, skipping")

        return (perfectConfig, self)
        
    def syncVars(self, oldVars):
        freqrange = (self.mapTuneToReq(self.tunerMinFreq), self.mapTuneToReq(self.tunerMaxFreq))
        varsUpdated = False
        newVars = dict()
        # reuse old var if its still valid
        if 'freq' in oldVars and (
                (isinstance(oldVars['freq'], tunerConfigIntList) and self.multiFreq) or
                (isinstance(oldVars['freq'], tunerConfigInt) and not self.multiFreq)
                ):
            newVars['freq'] = oldVars['freq']
            # update to new range
            newVars['freq'].setLimits(min(freqrange), max(freqrange))
        else:
            if self.multiFreq:
                newVars['freq'] = tunerConfigIntList(self.defaultfreq, min(freqrange), max(freqrange), True, 'kHz', 'Freq', 'Frequency')
                # map old value in if exists
                if 'freq' in oldVars and isinstance(oldVars['freq'], tunerConfigInt):
                    newVars['freq'].setSingleValue(oldVars['freq'].getValue())
            else:
                newVars['freq'] = tunerConfigInt(self.defaultfreq, min(freqrange), max(freqrange), 'kHz', 'Frequency')
                # map old value in if exists
                if 'freq' in oldVars and isinstance(oldVars['freq'], tunerConfigIntList):
                    newVars['freq'].setValue(oldVars['freq'].getValues()[0])

            varsUpdated = True
        #remove prerequisites from deleted vars
        removedVars = set(oldVars.keys())-set(newVars.keys())
        if len(removedVars) > 0:
            newVars['freq'].removePrereqs(removedVars)
            varsUpdated = True
        return (varsUpdated, newVars)

    def getSource(self):
        return self.source

    def getFrequency(self):
        return self.freq

    def getLOSide(self):
        return self.loside

    def getGPIOid(self):
        return self.gpioid

    # return tuner frequency from requested frequency
    def mapReqToTune(self, freq):
        if self.loside == LOOffsetSideEnum.LOW:
            return freq-self.freq
        elif self.loside == LOOffsetSideEnum.HIGH:
            return self.freq-freq
        elif self.loside == LOOffsetSideEnum.SUM:
            return freq+self.freq

    # return request frequency from tuner frequeny
    def mapTuneToReq(self, freq):
        if self.loside == LOOffsetSideEnum.LOW:
            return self.freq+freq
        elif self.loside == LOOffsetSideEnum.HIGH:
            return self.freq-freq
        elif self.loside == LOOffsetSideEnum.SUM:
            return freq-self.freq
    
    def getOffsetStr(self):
        output = ""
        if self.loside == LOOffsetSideEnum.HIGH:
            output += "+"
        else:
            output += "-"
        output += str(self.freq)
        return output

    def __eq__(self,other):
        # compare 2 bands
        if not isinstance(other,tunerBand):
            raise NotImplementedError
        else:
            return self.freq == other.freq and self.loside == other.loside and self.gpioid == other.gpioid
    
    def __hash__(self):
        return hash((self.freq, self.loside, self.gpioid))

class tunerConfigGeneral(rydeplayer.common.validTracker):
    def __init__(self, initValid, longName, prereqConfigs = None):
        self.longName = longName
        if prereqConfigs is None:
            self.prereqConfigs = set()
        else:
            self.prereqConfigs = prereqConfigs
        super().__init__(initValid)

    def getLongName(self):
        return self.longName

    def getPrereqs(self):
        return self.prereqConfigs

    def addPrereqs(self, newPrereqs):
        return self.prereqConfigs.update(newPrereqs)

    def removePrereqs(self, oldPrereqs):
        return self.prereqConfigs.difference_update(oldPrereqs)

# Stores the a tuner integer and its limits
class tunerConfigInt(tunerConfigGeneral):
    def __init__(self, value, minval, maxval, units, longName, prereqConfigs=None):
        self.units = units
        self.value = value
        if minval >= 0:
            self.minval = minval
        else:
            self.minval = 0
        if maxval >= 0:
            self.maxval = maxval
            self.validRange = True
        else:
            self.validRange = False
        # Initalise valid tracker with current valid status

        super().__init__(initValid=(value >= minval and value <= maxval and self.validRange), longName=longName, prereqConfigs=prereqConfigs)

    def setValue(self, newval):
        if self.value != newval:
            self.value = newval
            self.updateValid(self.value >= self.minval and self.value <= self.maxval and self.validRange)

    def setLimits(self, newMin, newMax):
        if self.minval != newMin or self.maxval != newMax:
            if newMin >= 0:
                self.minval = newMin
            else:
                self.minval = 0
            if newMax >= 0:
                self.maxval = newMax
                self.validRange = True
            else:
                self.maxval = 0
                self.validRange = False
            self.updateValid(self.value >= self.minval and self.value <= self.maxval and self.validRange)

    def getValue(self):
        return self.value

    def getMinValue(self):
        return self.minval

    def getMaxValue(self):
        return self.maxval

    def getUnits(self):
        return self.units

    def copyConfig(self):
        return tunerConfigInt(self.value, self.minval, self.maxval, self.units, self.longName)

    # parse config file value and return new object using this one as a template
    def parseNew(self, config):
        newConf = self.copyConfig()
        perfectConfig = True
        updated = False
        if isinstance(config, int):
            newConf.setValue(config)
            updated=True
        else:
            print("Config invalid for var:"+self.shortName)
            perfectConfig = False
        if updated:
            return (perfectConfig, newConf)
        else:
            return (perfectConfig, None)

    # update this to match other config
    def updateToMatch(self, newVal):
        if isinstance(newVal, tunerConfigInt):
            self.setValue(newVal.getValue())
        else:
            raise NotImplementedError

    def __str__(self):
        return str(self.value)

    def __eq__(self, other):
        if not isinstance(other,tunerConfigInt):
            raise NotImplementedError
        else:
            return other.getValue() == self.getValue()

    def __hash__(self):
        return hash(self.getValue())

# Stores a list of tuner integers which share limits
class tunerConfigIntList(tunerConfigGeneral):
    def __init__(self, value, minval, maxval, single, units, shortName, longName, prereqConfigs = None):
        initialConfig = tunerConfigInt(value, minval, maxval, units, shortName)
        initialConfig.addValidCallback(self.checkValid)
        self.units = units
        self.shortName = shortName

        # List must never be empty
        self.values = [initialConfig]
        self.minval = minval
        self.maxval = maxval
        self.single = single
        # Initalise valid tracker with current valid status
        super().__init__(initValid = self.values[0].isValid(), longName=longName, prereqConfigs=prereqConfigs)
   
    def append(self, newval):
        newConfig = tunerConfigInt(newval, self.minval, self.maxval, self.units, self.shortName)
        newConfig.addValidCallback(self.checkValid)
        self.values.append(newConfig)
        self.single=False
        self.checkValid()

    def setLimits(self, newMin, newMax):
        if self.minval != newMin or self.maxval != newMax:
            self.minval = newMin
            self.maxval = newMax
            for element in self.values:
                element.setLimits(newMin, newMax)
            self.checkValid()

    def checkValid(self):
        newValid = True
        for element in self.values:
            newValid = newValid and element.isValid()
        self.updateValid(newValid)

    # does this list enforce 1 value only
    def isSingle(self):
        return self.single

    # change single value enforcement
    def setSingle(self, newSingle):
        self.single=newSingle
        if self.single:
            del(self.values[1:])
        self.checkValid()

    # set to single value only and set that value
    def setSingleValue(self, newVal):
        self.setSingle(True)
        self.values[0].setValue(newVal)
        self.checkValid()

    def getMinValue(self):
        return self.minval

    def getMaxValue(self):
        return self.maxval

    def getShortName(self):
        return self.shortName

    def getValues(self):
        values = []
        for valueOb in self.values:
            values.append(valueOb.getValue())
        return values

    # produce a deep copy of the list
    def copyConfig(self):
        newConfig=tunerConfigIntList(self.values[0].getValue(), self.values[0].getMinValue(), self.values[0].getMaxValue(), self.single, self.units, self.shortName, self.longName, self.prereqConfigs)
        for valueOb in self.values[1:]:
            newConfig.append(valueOb.getValue())
        return newConfig

    # parse config file value and return new object using this one as a template
    def parseNew(self, config):
        newConf = self.copyConfig()
        perfectConfig = True
        updated = False
        if isinstance(config, int):
            newConf.setSingleValue(config)
            updated=True
        elif isinstance(config, list):
            firstVar = True
            for propFreq in config:
                if isinstance(propFreq, int):
                    updated = True
                    if firstVar:
                        newConf.setSingleValue(propFreq)
                        firstVar = False
                    else:
                        newConf.append(propFreq)
                else:
                    print("Some values invalid and skipped for var: "+self.shortName)
                    perfectConfig = False
            if not updated:
                print("No valid values provided for var: "+self.shortName)
                perfectConfig = False
        else:
            print("Config invalid for var:"+self.shortName)
            perfectConfig = False
        if updated:
            return (perfectConfig, newConf)
        else:
            return (perfectConfig, None)


    # update this to match other config
    def updateToMatch(self, newVal):
        if isinstance(newVal, tunerConfigIntList):
            newRawVal = newVal.getValues()
            self.setSingleValue(newRawVal[0])
            if not newVal.isSingle():
                self.setSingle(False)
                if len(newRawVal) > 1:
                    for thisVal in newRawVal[1:]:
                        self.append(thisVal)
        else:
            raise NotImplementedError

    def __len__(self):
        return len(self.values)

    def __getitem__(self, n):
        return self.values[n]

    def __delitem__(self, n):
        if len(self.values) > 1:
            self.values[n].removeValidCallback(self.checkValid)
            del(self.values[n])
            self.checkValid()
        else:
            raise KeyError("Can't remove only item in list")

    def __str__(self):
        outstrs = []
        for valueOb in self.values:
            outstrs.append(str(valueOb.getValue()))
        return ", ".join(outstrs)

    def __eq__(self, other):
        if not isinstance(other,tunerConfigIntList):
            raise NotImplementedError
        else:
            return other.isSingle() == self.isSingle() and other.getValues() == self.getValues()

    def __hash__(self):
        return hash((tuple(self.getValues()), self.isSingle()))

class tunerConfig(rydeplayer.common.validTracker):
    def __init__(self):
        self.updateCallbacks = [] # function that is called when the config changes
        self.varChangeCallbacks = [] # function that is called when the config changes
        self.band = tunerBand.getDefaultBand()
        varsChanged, self.vars = self.band.syncVars({})
        # any var that supports validity should update the validity of this when its own changes
        for key in self.vars:
            if isinstance(self.vars[key], rydeplayer.common.validTracker):
                self.vars[key].addValidCallback(self.updateValid)
        super().__init__(self.calcValid())
        self.updateValid()
        self.runCallbacks()

    def __getattr__(self, name):
        if name not in self.vars:
            raise AttributeError
        else:
            return self.vars[name]

    # update this tuner config to match the provided one
    def setConfigToMatch(self, fromConfig):
        self.setBand(fromConfig.getBand())
        fromVars = fromConfig.getVars()
        for thisVar in self.vars:
            self.vars[thisVar].updateToMatch(fromVars[thisVar])
        self.updateValid()
        self.runCallbacks()

    def loadConfig(self, config, bandLibrary = []):
        configUpdated = False
        perfectConfig = True
        if not isinstance(config, dict):
            print("Tuner config invalid, skipping")
            perfectConfig = False
        else:
            # load the band first so we can work out whaat the other fields are
            if 'band' in config:
                bandParseSuccess, bandObject = rydeplayer.sources.common.tunerBand.loadBand(config['band'])
                if bandParseSuccess:
                    # dedupe band obects with library
                    if bandObject in bandLibrary:
                        bandObject = bandLibrary[bandLibrary.index(bandObject)]
                    self.setBand(bandObject)
                    configUpdated = True
                else:
                    print("Could not load default band, skipping")
                    perfectConfig = False
            else:
                print("Band config missing, skipping")
                perfectConfig = False
            # parse all vars
            newVars = {}
            for varKey in self.vars:
                if varKey in config:
                    parsePerfectConfig, newVar = self.vars[varKey].parseNew(config[varKey])
                    perfectConfig = perfectConfig or parsePerfectConfig
                    if newVar is not None:
                        newVars[varKey] = newVar
            # only store vars who's prerequisites parsed validly
            for newVar in newVars:
                allPrereqsFound = True
                for prereq in newVars[newVar].getPrereqs():
                    if prereq not in newVars:
                        allPrereqsFound = False
                        print("Prerequsite '"+prereq+"' not found but required by '"+newVar+"'")
                        break
                if allPrereqsFound:
                    self.vars[newVar].updateToMatch(newVars[newVar])
                    configUpdated = True
        if configUpdated: # run the callback if we chaged something
            self.runCallbacks()
        return perfectConfig

    def setBand(self, newBand):
        self.band = newBand
        varsChanged, newVars = self.band.syncVars(self.vars)
        if varsChanged:
            # update the validity trackers to only be on current vars
            for key in self.vars:
                if isinstance(self.vars[key], rydeplayer.common.validTracker):
                    self.vars[key].removeValidCallback(self.updateValid)
            for key in newVars:
                if isinstance(newVars[key], rydeplayer.common.validTracker):
                    newVars[key].addValidCallback(self.updateValid)
            self.vars = newVars
            self.runVarChangeCallbacks()
        self.runCallbacks()
    def getBand(self):
        return self.band

    def addCallbackFunction(self, newCallback):
        self.updateCallbacks.append(newCallback)
    def removeCallbackFunction(self, oldCallback):
        self.updateCallbacks.remove(oldCallback)
    def getCallbackFunctions(self):
        return self.updateCallbacks
    
    def addVarChangeCallbackFunction(self, newCallback):
        self.varChangeCallbacks.append(newCallback)
    def removeVarChangeCallbackFunction(self, oldCallback):
        self.varChangeCallbacks.remove(oldCallback)
    def getVarChangeCallbackFunctions(self):
        return self.varChangeCallbacks

    def getVars(self):
        return self.vars

    def updateValid(self):
        return super().updateValid(self.calcValid())

    def calcValid(self):
        newValid = True
        for key in self.vars:
            newValid = newValid and self.vars[key].isValid()
        return newValid;

    def runCallbacks(self):
        for callback in self.updateCallbacks:
            callback(self)

    def runVarChangeCallbacks(self):
        for callback in self.varChangeCallbacks:
            callback(self)

    def copyConfig(self):
        # return a copy of the config details but with no callback connected
        newConfig = tunerConfig()
        newConfig.setConfigToMatch(self)
        return newConfig
    def __eq__(self,other):
        # compare 2 configs ignores the callback
        if not isinstance(other,tunerConfig):
            return False
        else:
            if self.band != other.band or set(self.vars.keys())!=set(other.vars.keys()):
                return False
            else:
                for key in self.vars:
                    if self.vars[key]!=other.vars[key]:
                        return False
                return True
    def __hash__(self):
        return hash((frozenset(self.vars.items()), self.band))

    def __str__(self):
        toDisplay = {'IF offset': self.band.getOffsetStr()}
        maxNameLen = len('IF offset')
        for key in self.vars:
            varname = self.vars[key].getLongName()
            maxNameLen = max(maxNameLen,len(varname))
            toDisplay[varname]=str(self.vars[key])
        output = ""
        for key in toDisplay:
            output += key.rjust(maxNameLen)+": "+toDisplay[key]+"\n"
        #TODO: display band info
        return output

# Events to send to source thread
class eventsToThread(enum.Enum):
    RECONFIG = enum.auto()
    START = enum.auto()
    RESTART = enum.auto()
    SHUTDOWN = enum.auto()

# Event to receive from source thread
class eventsFromThread(enum.Enum):
    NEWFULLSTATUS = enum.auto()
    NEWCORESTATE = enum.auto()

# threaded wrapper around source
class sourceManagerThread(object):
    def __init__(self, config, sourceConfigs):
        self.sourceConfigs = sourceConfigs
        self.sourceStatus = None
        self._threadSetup(config)
        self.coreStateMain = self.coreStateThread
        self.thread.start()

    def _threadSetup(self, config):
        # socket and queue to communicate to source thread
        self.toRecvSock, self.toSendSock = socket.socketpair()
        self.toEventQueue = queue.Queue()
        # socket and queue to communicate from source thread
        self.fromRecvSock, self.fromSendSock = socket.socketpair()
        self.fromEventQueue = queue.Queue()
        self.currentSource = config.getBand().getSource()
        newSourceStatus = self.currentSource.getSource().getNewStatus()()
        if self.sourceStatus is not None:
            newSourceStatus.addCallbacksFrom(self.sourceStatus)
        self.sourceStatus = newSourceStatus
#        self.sourceMan = rydeplayer.sources.longmynd.lmManager(config, sourceConfigs[self.currentSource])
        self.sourceMan = self.currentSource.getSource().getManager()(config, self.sourceConfigs[self.currentSource])
        self.sourceMan.getStatus().addOnChangeCallback(self.statusCallbackThread)
        # trackers for the state in and out of the thread
        self.coreStateThread = self.sourceMan.getCoreState()
        # create and start thread
        self.thread = threading.Thread(target=self.threadLoop, daemon=True)
        self.sourceStatus.onChangeFire()

    def reconfig(self, config):
        if config.getBand().getSource() == self.currentSource:
            self.toEventQueue.put((eventsToThread.RECONFIG, config.copyConfig()))
            self.toSendSock.send(b"\x00")
        else:
            # replace thread when source changes
            self.shutdown()
            self._threadSetup(config)
            self.thread.start()
            self.start()

    def remedia(self):
        self.sourceMan.remedia()

    def getMediaFd(self):
        return self.sourceMan.getMediaFd()
    def getMainFDs(self):
        return [self.fromRecvSock]
    def getThreadFDs(self):
        return self.sourceMan.getFDs() + [self.toRecvSock]
    def getFDs(self):
        return self.getMainFDs()
    def getStatus(self):
        return self.sourceStatus

    def statusCallbackThread(self, newStatus):
        self.fromEventQueue.put((eventsFromThread.NEWFULLSTATUS, newStatus.copyStatus()))
        self.fromSendSock.send(b"\x00")

    def handleMainFD(self, fd):
        # handle events coming from the source thread
        newStatus = None
        while not self.fromEventQueue.empty():
            fd.recv(1) # there should always be the same number of chars in the socket as items in the queue
            queueCommand, queueArg = self.fromEventQueue.get()
            if queueCommand == eventsFromThread.NEWFULLSTATUS:
                newStatus = queueArg
            elif queueCommand == eventsFromThread.NEWCORESTATE:
                self.coreStateMain = queueArg
        if newStatus is not None:
            self.sourceStatus.setStatusToMatch(newStatus)

    def handleThreadFD(self, fd):
        # handle events inside the source thread
        quit = False
        if fd == self.toRecvSock:
            newconfig = None
            while not self.toEventQueue.empty():
                fd.recv(1) # there should always be the same number of chars in the socket as items in the queue
                queueCommand, queueArg = self.toEventQueue.get()
                if queueCommand == eventsToThread.RECONFIG:
                    newconfig = queueArg
                elif queueCommand == eventsToThread.START:
                    self.sourceMan.start()
                elif queueCommand == eventsToThread.RESTART:
                    self.sourceMan.restart()
                elif queueCommand == eventsToThread.SHUTDOWN:
                    self.sourceMan.stop()
                    quit = True
            if newconfig is not None and not quit:
                self.sourceMan.reconfig(newconfig)

        elif fd in self.sourceMan.getFDs():
            self.sourceMan.handleFD(fd)
        return quit

    def handleFD(self, fd):
        if fd in self.getMainFDs():
            self.handleMainFD(fd)

    def getCoreState(self):
        return self.coreStateMain

    def start(self):
        self.toEventQueue.put((eventsToThread.START, None))
        self.toSendSock.send(b"\x00")

    def restart(self):
        self.toEventQueue.put((eventsToThread.RESTART, None))
        self.toSendSock.send(b"\x00")

    def shutdown(self):
        self.toEventQueue.put((eventsToThread.SHUTDOWN, None))
        self.toSendSock.send(b"\x00")
        self.thread.join()
        # cleanup things source normally has a version of open
        self.sourceMan.cleanup()
        self.toRecvSock.close()
        self.toSendSock.close()
        self.fromRecvSock.close()
        self.fromSendSock.close()

    def threadLoop(self):
        # thread main loop
        quit = False
        while not quit:
            fds = self.getThreadFDs()
            r, w, x = select.select(fds, [], [])
            for fd in r:
                quit = self.handleThreadFD(fd)
                if quit:
                    break
            newCoreState = self.sourceMan.getCoreState()
            if newCoreState != self.coreStateThread:
                self.coreStateThread = newCoreState
                self.fromEventQueue.put((eventsFromThread.NEWCORESTATE, newCoreState))
                self.fromSendSock.send(b"\x00")
