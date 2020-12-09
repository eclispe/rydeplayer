#    Ryde Player provides a on screen interface and video player for Longmynd compatible tuners.
#    Copyright © 2020 Tim Clark
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

class inPortEnum(enum.Enum):
    TOP = enum.auto()
    BOTTOM = enum.auto()

class PolarityEnum(enum.Enum):
    NONE = enum.auto()
    HORIZONTAL = enum.auto()
    VERTICAL = enum.auto()

class LOOffsetSideEnum(enum.Enum):
    HIGH = enum.auto()
    LOW = enum.auto()
    SUM = enum.auto()

class DVBVersionEnum(enum.Enum):
    DVBS = enum.auto()
    DVBS2 = enum.auto()

class DVBModulationEnum(enum.Enum):
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
    def __str__(self):
        return self.longName

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

class tunerBand(object):
    def __init__(self):
        self.freq = 0
        self.loside = LOOffsetSideEnum.LOW
        self.pol = PolarityEnum.NONE
        self.port = inPortEnum.TOP
        self.gpioid = 0

    def setBand(self, freq, loside, pol, port, gpioid):
        self.freq = freq
        self.loside = loside
        self.pol = pol
        self.port = port
        self.gpioid = gpioid

    def loadBand(self, config):
        configUpdated = False
        perfectConfig = True
        if not isinstance(config, dict):
            print("Band invalid, skipping")
            perfectConfig = False
        else:
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

        return perfectConfig

    def getFrequency(self):
        return self.freq

    def getLOSide(self):
        return self.loside

    def getPolarity(self):
        return self.pol

    def getInputPort(self):
        return self.port

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
            return NotImplemented
        else:
            return self.freq == other.freq and self.loside == other.loside and self.pol == other.pol and self.port == other.port and self.gpioid == other.gpioid
    
    def __hash__(self):
        return hash((self.freq, self.loside, self.pol, self.port, self.gpioid))

# Stores the a tuner integer and its limits
class tunerConfigInt(rydeplayer.common.validTracker):
    def __init__(self, value, minval, maxval):
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
        super().__init__(value >= minval and value <= maxval and self.validRange)

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

    def copyConfig(self):
        return tunerConfigInt(self.value, self.minval, self.maxval)

    def __str__(self):
        return str(self.value)

# Stores a list of tuner integers which share limits
class tunerConfigIntList(rydeplayer.common.validTracker):
    def __init__(self, value, minval, maxval, single):
        initialConfig = tunerConfigInt(value, minval, maxval)
        initialConfig.addValidCallback(self.checkValid)
        # List must never be empty
        self.values = [initialConfig]
        self.minval = minval
        self.maxval = maxval
        self.single = single
        # Initalise valid tracker with current valid status
        super().__init__(self.values[0].isValid())
   
    def append(self, newval):
        newConfig = tunerConfigInt(newval, self.minval, self.maxval)
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

    def getValues(self):
        values = []
        for valueOb in self.values:
            values.append(valueOb.getValue())
        return values

    # produce a deep copy of the list
    def copyConfig(self):
        newConfig=tunerConfigIntList(self.values[0].getValue(), self.values[0].getMinValue(), self.values[0].getMaxValue(), self.single)
        for valueOb in self.values[1:]:
            newConfig.append(valueOb.getValue())
        return newConfig

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
        return other.isSingle == self.isSingle and other.getValues() == self.getValues()

    def __hash__(self):
        return hash((tuple(self.getValues()), self.isSingle()))

class tunerConfig(rydeplayer.common.validTracker):
    def __init__(self):
        # default is QO-100 Beacon
        self.updateCallbacks = [] # function that is called when the config changes
        self.band = tunerBand()
        self.band.setBand(0, LOOffsetSideEnum.LOW, PolarityEnum.NONE, inPortEnum.TOP, 0)
        self.tunerMinFreq = 144000
        self.tunerMaxFreq = 2450000
        defaultfreq = 741500
        freqrange = (self.band.mapTuneToReq(self.tunerMinFreq), self.band.mapTuneToReq(self.tunerMaxFreq))
        self.freq = tunerConfigIntList(defaultfreq, min(freqrange), max(freqrange), True)
        self.freq.addValidCallback(self.updateValid)
        self.sr = tunerConfigIntList(1500, 33, 27500, True)
        self.sr.addValidCallback(self.updateValid)
        super().__init__(self.calcValid())
        self.setConfig(self.freq, self.sr, self.band)

    def setConfig(self, freq, sr, band):
        self.freq.removeValidCallback(self.updateValid)
        freq.addValidCallback(self.updateValid)
        self.freq = freq
        self.sr.removeValidCallback(self.updateValid)
        sr.addValidCallback(self.updateValid)
        self.sr = sr
        self.band = band
        freqrange = (self.band.mapTuneToReq(self.tunerMinFreq), self.band.mapTuneToReq(self.tunerMaxFreq))
        self.freq.setLimits(min(freqrange), max(freqrange))
        self.updateValid()
        self.runCallbacks()

    def setConfigToMatch(self, fromConfig):
        self.setFrequencies(fromConfig.freq.getValues())
        self.freq.setSingle(fromConfig.freq.isSingle())
        self.setSymbolRates(fromConfig.sr.getValues())
        self.sr.setSingle(fromConfig.sr.isSingle())
        self.setConfig(self.freq, self.sr, fromConfig.getBand())

    def loadConfig(self, config, bandLibrary = []):
        configUpdated = False
        perfectConfig = True
        if not isinstance(config, dict):
            print("Tuner config invalid, skipping")
            perfectConfig = False
        else:
            # check frequency and symbol rate, both must be valid for either to be updated
            newFreq = None
            newSR = None
            if 'freq' in config:
                if isinstance(config['freq'], int):
                    newFreq = config['freq']
                elif isinstance(config['freq'], list):
                    proposedFreqs = []
                    for propFreq in config['freq']:
                        if isinstance(propFreq, int):
                            proposedFreqs.append(propFreq)
                        else:
                            print("Some frequencies are invalid")
                            perfectConfig = False
                    if len(proposedFreqs) >0:
                        newFreq = proposedFreqs
                    else:
                        print("No valid frequencies provided, skipping frequency and symbol rate")
                        perfectConfig = False
                else:
                    print("Frequency config invalid, skipping frequency and symbol rate")
                    perfectConfig = False
            else:
                print("Frequency config missing, skipping frequency and symbol rate")
                perfectConfig = False
            if 'sr' in config:
                if isinstance(config['sr'], int):
                    newSR = config['sr']
                elif isinstance(config['sr'], list):
                    proposedSRs = []
                    for propSR in config['sr']:
                        if isinstance(propSR, int):
                            proposedSRs.append(propSR)
                        else:
                            print("Some symbol rates are invalid")
                            perfectConfig = False
                    if len(proposedSRs) >0:
                        newSR = proposedSRs
                    else:
                        print("No valid symbol rates provided, skipping frequency and symbol rate")
                        perfectConfig = False
                else:
                    print("Symbol rate config invalid, skipping frequency and symbol rate")
                    perfectConfig = False
            else:
                print("Symbol rate missing, skipping frequency and symbol rate")
                perfectConfig = False

            if newFreq is not None and newSR is not None:
                if isinstance(newFreq, list):
                   firstFreq = True
                   for thisNewFreq in newFreq:
                       if firstFreq:
                           firstFreq = False
                           self.freq.setSingleValue(thisNewFreq)
                           self.freq.setSingle(False)
                       else:
                           self.freq.append(thisNewFreq)
                else:
                    self.freq.setSingleValue(newFreq)
                if isinstance(newSR, list):
                   firstSR = True
                   for thisNewSR in newSR:
                       if firstSR:
                           firstSR = False
                           self.sr.setSingleValue(thisNewSR)
                           self.sr.setSingle(False)
                       else:
                           self.sr.append(thisNewSR)
                else:
                    self.sr.setSingleValue(newSR)
                configUpdated = True
            else:
                print("Symbol rate and/or frequency were invalid, skipping both")

            if 'band' in config:
                bandObject = tunerBand()
                if bandObject.loadBand(config['band']):
                    # dedupe band obects with library
                    if bandObject in bandLibrary:
                        bandObject = bandLibrary[bandLibrary.index(bandObject)]
                    self.band = bandObject
                else:
                    print("Could not load default band, skipping")
                    perfectConfig = False
            else:
                print("Band config missing, skipping")
                perfectConfig = False

        freqrange = (self.band.mapTuneToReq(self.tunerMinFreq), self.band.mapTuneToReq(self.tunerMaxFreq))
        self.freq.setLimits(min(freqrange), max(freqrange))
        if configUpdated: # run the callback if we chaged something
            self.runCallbacks()
        return perfectConfig

    def setFrequencies(self, newFreq):
        if isinstance(newFreq, collections.abc.Iterable):
           firstFreq = True
           for thisNewFreq in newFreq:
               if firstFreq:
                   firstFreq = False
                   self.freq.setSingleValue(thisNewFreq)
               else:
                   self.freq.append(thisNewFreq)
        else:
            self.freq.setSingleValue(newFreq)
        self.runCallbacks()

    def setSymbolRates(self, newSr):
        if isinstance(newSr, collections.abc.Iterable):
           firstSr = True
           for thisNewSr in newSr:
               if firstSr:
                   firstSr = False
                   self.sr.setSingleValue(thisNewSr)
               else:
                   self.sr.append(thisNewSr)
        else:
            self.sr.setSingleValue(newSr)
        self.runCallbacks()
    def setBand(self, newBand):
        self.band = newBand
        freqrange = (self.band.mapTuneToReq(self.tunerMinFreq), self.band.mapTuneToReq(self.tunerMaxFreq))
        self.freq.setLimits(min(freqrange), max(freqrange))
        self.runCallbacks()
    def getBand(self):
        return self.band
    def addCallbackFunction(self, newCallback):
        self.updateCallbacks.append(newCallback)
    def removeCallbackFunction(self, oldCallback):
        self.updateCallbacks.remove(oldCallback)
    def getCallbackFunctions(self):
        return self.updateCallbacks

    def updateValid(self):
        return super().updateValid(self.calcValid())

    def calcValid(self):
        newValid = True
        newValid = newValid and self.freq.isValid()
        newValid = newValid and self.sr.isValid()
        return newValid;

    def runCallbacks(self):
        for callback in self.updateCallbacks:
            callback(self)
    def copyConfig(self):
        # return a copy of the config details but with no callback connected
        newConfig = tunerConfig()
        newConfig.setConfig(self.freq.copyConfig(), self.sr.copyConfig(), self.band)
        return newConfig
    def __eq__(self,other):
        # compare 2 configs ignores the callback
        if not isinstance(other,tunerConfig):
            return NotImplemented
        else:
            return set(self.freq.getValues()) == set(other.freq.getValues()) and set(self.sr.getValues()) == set(other.sr.getValues()) and self.band == other.band
    def __hash__(self):
        return hash((self.freq, self.sr, self.band))

    def __str__(self):
        output = ""
        output += "Request Frequency: "+str(self.freq)+"\n"
        output += "        IF offset: "+self.band.getOffsetStr()+"\n"
        output += "      Symbol Rate: "+str(self.sr)+"\n"
        return output

# Container for tuner status data with change callbacks
class tunerStatus(object):
    def __init__(self):
        self.onChangeCallbacks = []
        self.mer = None
        self.provider = ""
        self.service = ""
        self.dvbVersion = None
        self.modulation = None
        self.pids = {}
        self.freq = None
        self.sr = None

    def addOnChangeCallback(self, callback):
        self.onChangeCallbacks.append(callback)

    def removeOnChangeCallback(self, callback):
        self.onChangeCallbacks.remove(callback)

    def onChangeFire(self):
        for callback in self.onChangeCallbacks:
            callback(self)

    def setProvider(self, newval):
        if(isinstance(newval, str)):
            if self.provider != newval:
                self.provider = newval
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

    def setService(self, newval):
        if(isinstance(newval, str)):
            if self.service != newval:
                self.service = newval
                self.onChangeFire()
                return True
            else:
                return False
        else:
            return False

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
        if(isinstance(newval, DVBVersionEnum) or newval is None):
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
            0: DVBModulationEnum.S_1_2,
            1: DVBModulationEnum.S_2_3,
            2: DVBModulationEnum.S_3_4,
            3: DVBModulationEnum.S_5_6,
            4: DVBModulationEnum.S_6_7,
            5: DVBModulationEnum.S_7_8
            }
        dvbs2 = {
            1:  DVBModulationEnum.S2_4_1_4,
            2:  DVBModulationEnum.S2_4_1_3,
            3:  DVBModulationEnum.S2_4_2_5,
            4:  DVBModulationEnum.S2_4_1_2,
            5:  DVBModulationEnum.S2_4_3_5,
            6:  DVBModulationEnum.S2_4_2_3,
            7:  DVBModulationEnum.S2_4_3_4,
            8:  DVBModulationEnum.S2_4_4_5,
            9:  DVBModulationEnum.S2_4_5_6,
            10: DVBModulationEnum.S2_4_8_9,
            11: DVBModulationEnum.S2_4_9_10,
            12: DVBModulationEnum.S2_8_3_5,
            13: DVBModulationEnum.S2_8_2_3,
            14: DVBModulationEnum.S2_8_3_4,
            15: DVBModulationEnum.S2_8_5_6,
            16: DVBModulationEnum.S2_8_8_9,
            17: DVBModulationEnum.S2_8_9_10,
            18: DVBModulationEnum.S2_16_2_3,
            19: DVBModulationEnum.S2_16_3_4,
            20: DVBModulationEnum.S2_16_4_5,
            21: DVBModulationEnum.S2_16_5_6,
            22: DVBModulationEnum.S2_16_8_9,
            23: DVBModulationEnum.S2_16_9_10,
            24: DVBModulationEnum.S2_32_3_4,
            25: DVBModulationEnum.S2_32_4_5,
            26: DVBModulationEnum.S2_32_5_6,
            27: DVBModulationEnum.S2_32_8_9,
            28: DVBModulationEnum.S2_32_9_10
            }
        if(isinstance(newval, int)):
            newMod = None
            if(self.dvbVersion == DVBVersionEnum.DVBS):
                if(newval in dvbs):
                    newMod = dvbs[newval]
                else:
                    return False
            elif(self.dvbVersion == DVBVersionEnum.DVBS2):
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

    def setPIDs(self, newval):
        codecmap = {
             2:CodecEnum.MP2,
             3:CodecEnum.MPA,
             4:CodecEnum.MPA,
            15:CodecEnum.AAC,
            16:CodecEnum.H263,
            27:CodecEnum.H264,
            32:CodecEnum.MPA,
            36:CodecEnum.H265,
            }
        newPIDs = {}
        for pid, codec in newval.items():
            if codec in codecmap:
                newPIDs[pid] = codecmap[codec]
            else:
                newPIDs[pid] = str(codec)+"?"
        if self.pids != newPIDs:
            self.pids = newPIDs
            self.onChangeFire()
            return True
        else:
           return False

    def setFreq(self, newval):
        if(isinstance(newval, int)):
            if self.freq != newval:
                self.freq = newval
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

    def getMer(self):
        return self.mer

    def getDVBVersion(self):
        return self.dvbVersion

    def getModulation(self):
        return self.modulation

    def getPIDs(self):
        return self.pids

    def getProvider(self):
        return self.provider

    def getService(self):
        return self.service

    def getFreq(self):
        return self.freq

    def getSR(self):
        return self.sr

    def copyStatus(self):
        newstatus = tunerStatus()
        newstatus.setStatusToMatch(self)
        return newstatus

    def setStatusToMatch(self, fromStatus):
        changed = False
        newMer = fromStatus.getMer()
        if self.mer != newMer:
            self.mer = newMer
            changed = True
        newMod = fromStatus.getModulation()
        if self.modulation != newMod:
            self.modulation = newMod
            changed = True
        newDVBversion = fromStatus.getDVBVersion()
        if self.dvbVersion != newDVBversion:
            self.dvbVersion = newDVBversion
            changed = True
        newPIDs = {}
        for pid, codec in fromStatus.getPIDs().items():
            newPIDs[pid] = codec
        if self.pids != newPIDs:
            self.pids = newPIDs
            changed = True
        newProvider = fromStatus.getProvider()
        if self.provider != newProvider:
            self.provider = newProvider
            changed = True
        newService = fromStatus.getService()
        if self.service != newService:
            self.service = newService
            changed = True
        newFreq = fromStatus.getFreq()
        if self.freq != newFreq:
            self.freq = newFreq
            changed = True
        newSR = fromStatus.getSR()
        if self.sr != newSR:
            self.sr = newSR
            changed = True
        if changed:
            self.onChangeFire()

# Events to send to longmynd thread
class eventsToThread(enum.Enum):
    RECONFIG = enum.auto()
    START = enum.auto()
    RESTART = enum.auto()
    SHUTDOWN = enum.auto()
# Event to receive from longmynd thread
class eventsFromThread(enum.Enum):
    NEWFULLSTATUS = enum.auto()
    NEWCORESTATE = enum.auto()
# threaded wrapper around longmynd
class lmManagerThread(object):
    def __init__(self, config, lmpath, mediaFIFOpath, statusFIFOpath, tsTimeout):
        # socket and queue to communicate to longmynd thread
        self.toRecvSock, self.toSendSock = socket.socketpair()
        self.toEventQueue = queue.Queue()
        # socket and queue to communicate from longmynd thread
        self.fromRecvSock, self.fromSendSock = socket.socketpair()
        self.fromEventQueue = queue.Queue()
        self.tunerStatus = tunerStatus()
        self.lmman = lmManager(config, lmpath, mediaFIFOpath, statusFIFOpath, tsTimeout)
        self.lmman.getStatus().addOnChangeCallback(self.statusCallbackThread)
        # trackers for the state in and out of the thread
        self.coreStateThread = self.lmman.getCoreState()
        self.coreStateMain = self.coreStateThread
        # create and start thread
        self.thread = threading.Thread(target=self.threadLoop, daemon=True)
        self.thread.start()
    def reconfig(self, config):
        self.toEventQueue.put((eventsToThread.RECONFIG, config.copyConfig()))
        self.toSendSock.send(b"\x00")
    def remedia(self):
        self.lmman.remedia()
    def getMediaFd(self):
        return self.lmman.getMediaFd()
    def getMainFDs(self):
        return [self.fromRecvSock]
    def getThreadFDs(self):
        return self.lmman.getFDs() + [self.toRecvSock]
    def getFDs(self):
        return self.getMainFDs()
    def getStatus(self):
        return self.tunerStatus
    def statusCallbackThread(self, newStatus):
        self.fromEventQueue.put((eventsFromThread.NEWFULLSTATUS, newStatus.copyStatus()))
        self.fromSendSock.send(b"\x00")
    def handleMainFD(self, fd):
        # handle events coming from the longmynd thread
        newStatus = None
        while not self.fromEventQueue.empty():
            fd.recv(1) # there should always be the same number of chars in the socket as items in the queue
            queueCommand, queueArg = self.fromEventQueue.get()
            if queueCommand == eventsFromThread.NEWFULLSTATUS:
                newStatus = queueArg
            elif queueCommand == eventsFromThread.NEWCORESTATE:
                self.coreStateMain = queueArg
        if newStatus is not None:
            self.tunerStatus.setStatusToMatch(newStatus)
    def handleThreadFD(self, fd):
        # handle events inside the longmynd thread
        quit = False
        if fd == self.toRecvSock:
            newconfig = None
            while not self.toEventQueue.empty():
                fd.recv(1) # there should always be the same number of chars in the socket as items in the queue
                queueCommand, queueArg = self.toEventQueue.get()
                if queueCommand == eventsToThread.RECONFIG:
                    newconfig = queueArg
                elif queueCommand == eventsToThread.START:
                    self.lmman.start()
                elif queueCommand == eventsToThread.RESTART:
                    self.lmman.restart()
                elif queueCommand == eventsToThread.SHUTDOWN:
                    self.lmman.stop()
                    quit = True
            if newconfig is not None and not quit:
                self.lmman.reconfig(newconfig)

        elif fd in self.lmman.getFDs():
            self.lmman.handleFD(fd)
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
            newCoreState = self.lmman.getCoreState()
            if newCoreState != self.coreStateThread:
                self.coreStateThread = newCoreState
                self.fromEventQueue.put((eventsFromThread.NEWCORESTATE, newCoreState))
                self.fromSendSock.send(b"\x00")

class lmManager(object):
    def __init__(self, config, lmpath, mediaFIFOpath, statusFIFOpath, tsTimeout):
        # path to the longmynd binary
        self.lmpath = lmpath
        self.mediaFIFOfilename = mediaFIFOpath
        self.statusFIFOfilename = statusFIFOpath
        self.tsTimeout = tsTimeout
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
        self.statusFIFOfd = os.fdopen(os.open(self.statusFIFOfilename, flags=os.O_NONBLOCK|os.O_RDONLY)) # the status fifo file descriptor
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
        self.coreStateType = collections.namedtuple('coreState', ['isRunning', 'isLocked', 'monotonicState'])

    def reconfig(self, config):
        """reconfigures longmynd"""
        if(isinstance(config, tunerConfig) and config != self.activeConfig):
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
        state = self.coreStateType(self.isRunning(), self.isLocked(), self.getMonotonicState())
        return state
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
                        self.tunerStatus.setDVBVersion(DVBVersionEnum.DVBS)
                    elif int(rawval) == 4:
                        self.tunerStatus.setDVBVersion(DVBVersionEnum.DVBS2)
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

        self.statusFIFOfd = os.fdopen(os.open(self.statusFIFOfilename, flags=os.O_NONBLOCK, mode=os.O_RDONLY))
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
    def start(self):
        if self.activeConfig.isValid():
            if self.process == None :
                print("start")
                self.lmstarted = False
                self.statusrecv = False
                self.statelog=[]
                self.lmlog=[]
                args = [self.lmpath, '-t', self.mediaFIFOfilename, '-s', self.statusFIFOfilename, '-r', str(self.tsTimeout)]
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
                print("LM already running")
        else:
            print("Can't start, config invalid")
    def restart(self):
        if self.process is not None:
            if not self.statusrecv:
                time.sleep(0.2)
            self.stop()
        self.start()
