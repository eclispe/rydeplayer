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

import time, evdev, sys, os, yaml
import rydeplayer.common

class irHandset(object):
    def __init__(self, name, driver, buttons):
        self.name = name
        self.driver = driver
        self.buttons = buttons

    def getName(self):
        return self.name

    def getFriendlyName(self):
        return self.friendlyName

    def getDriver(self):
        return self.driver

    def getButtons(self):
        return self.buttons

    # cenerate the codemap for this handset from buttons
    def getCodemap(self):
        codemap={}
        if isinstance(self.buttons, dict):
            codesremaining = list(self.buttons.keys())
            for thisNavEvent in rydeplayer.common.navEvent:
                if thisNavEvent.name in self.buttons:
                    ircode = self.buttons[thisNavEvent.name]
                    if(isinstance(ircode, int)):
                        codemap[ircode]=thisNavEvent
                        codesremaining.remove(thisNavEvent.name)
                    else:
                        print("Bad IR code: "+str(ircode))
            if len(codesremaining) > 0:
                print("Unknown IR codes:")
                print(codesremaining)
        else:
            print("handset buttons is not a dict")
        return codemap

class irConfig(object):
    def __init__(self, config = None):
        self.handsetLib = {
            "mininec": irHandset("Mini NEC", "nec", {
                "POWER":0x4d,
                "UP":0x05,
                "DOWN":0x02,
                "LEFT":0x0a,
                "RIGHT":0x1e,
                "SELECT":0x40,
                "BACK":0x1c,
                "MENU":0x4c,
                "ZERO":0x12,
                "ONE":0x09,
                "TWO":0x1d,
                "THREE":0x1f,
                "FOUR":0x0d,
                "FIVE":0x19,
                "SIX":0x1b,
                "SEVEN":0x11,
                "EIGHT":0x15,
                "NINE":0x17,
            }),
        }
        self.irhandsets = ['mininec'] # list of handsets to load from library
        self.validDrivers = ['rc-5', 'rc-5-sx', 'jvc', 'sony', 'nec', 'sanyo', 'mce_kbd', 'rc-6', 'sharp', 'xmp', 'imon'] # list of valid drivers TODO: load from system automatically
        self.libraryPath = "/home/pi/handsets" # default handset library path
        self.repeatFirst=200 # how long to wait before starting to repeat
        self.repeatDelay=100 # while repeating how long between repeats
        self.repeatReset=400 # how long to wait with no repeats before resetting
        self.inconfig=None
   
    # parse a dict containing handsets
    def loadConfig(self, config):
        self.inconfig = config.copy()
        perfectConfig = True
        if isinstance(config, dict):
            if 'handsets' in config: # load handsets list
                if isinstance(config['handsets'] , list):
                    self.irhandsets = config['handsets']
                else:
                    print("IR handsets is not a list")
                    perfectConfig = False
            if 'libraryPath' in config: # load handset file from library directory
                if isinstance(config['libraryPath'] , str):
                    self.libraryPath = config['libraryPath']
                    if os.path.isdir(self.libraryPath):
                        self.loadLibrary(self.libraryPath)
                    else:
                        print("Library path does not exsist")
                else:
                    print("library path must be a string, ignoring")
                    perfectConfig = False
            else:
                print("No library path specified, checking previous/default location")
                if os.path.isdir(self.libraryPath):
                    self.loadLibrary(self.libraryPath)
                else:
                    print("Default path does not exsist")
            if 'repeatFirst' in config:
                if isinstance(config['repeatFirst'] , int):
                    self.repeatFirst = config['repeatFirst']
                else:
                    print("IR repeat first is invalid, ignoring")
                    perfectConfig = False
            if 'repeatDelay' in config:
                if isinstance(config['repeatDelay'] , int):
                    self.repeatDelay = config['repeatDelay']
                else:
                    print("IR repeat first is invalid, ignoring")
                    perfectConfig = False
            if 'repeatReset' in config:
                if isinstance(config['repeatReset'] , int):
                    self.repeatDelay = config['repeatReset']
                else:
                    print("IR repeat first is invalid, ignoring")
                    perfectConfig = False
        else:
            print("IR config invalid, ignoring")
            perfectConfig = False
        return perfectConfig

    # load handset library into object
    def loadLibrary(self, libraryPath):
        newLibrary = {}
        print(libraryPath)
        for filename in os.listdir(libraryPath):
            filepath = os.path.join(libraryPath, filename)
            handsetId, fileExt = os.path.splitext(filename)
            if os.path.isfile(filepath) and fileExt in ['.yaml', '.yml']:
                try:
                    with open(filepath, 'r') as ymlhandsetfile:
                        newHandset = self.loadHandset(yaml.load(ymlhandsetfile))
                        if isinstance(newHandset, irHandset):
                            newLibrary[handsetId] = newHandset
                except IOError as e:
                    print(e)
        if len(newLibrary) > 0:
            self.handsetLib = newLibrary
        else:
            print("New library empty, not updating")

    # parse a handset definition and return a handset object
    def loadHandset(self, handsetData):
        if isinstance(handsetData, dict):
            if 'buttons' in handsetData:
                if isinstance(handsetData['buttons'], dict):
                    if len(handsetData['buttons']) > 0:
                        if 'name' in handsetData:
                            if isinstance(handsetData['name'], str):
                                if 'driver' in handsetData:
                                    if isinstance(handsetData['driver'], str):
                                        if handsetData['driver'] in self.validDrivers:
                                            return irHandset(handsetData['name'], handsetData['driver'], handsetData['buttons'])
                                        else:
                                            print("Handset driver not recognised, skipping")
                                    else:
                                        print("Handset driver is not a string, skipping")
                                else:
                                    print("Handset driver missing, skipping")
                            else:
                                print("Handset name is not a string, skipping")
                        else:
                            print("Handset has no name, skipping")
                    else:
                        print("Handset button definitions are empty, skipping")
                else:
                    print("Handset buttons is not a dict, skipping")
            else:
                print("Handset has no button definitions")
        else:
            print("Handset file does not contain root dict, skipping")
        return False

    # generate and return a the codemap from the handsets list
    def getCodemap(self):
        codemap = {}
        for irhandset in self.irhandsets:
            if isinstance(irhandset, str):
                if irhandset in self.handsetLib:
                    if isinstance(self.handsetLib[irhandset], irHandset):
                        codemap.update(self.handsetLib[irhandset].getCodemap())
                    else:
                        print("handset list item is not a handset")
                else:
                    print("requested handset not found in library")
            else:
                print("irhandset is not a string, are you using the most recent file format?")

        return codemap

class irManager(object):
    def __init__(self, app, config):
        self.app = app
        # find all the GPIO IR devices
        inputDevices = []
        for devicePath in evdev.list_devices():
            device = evdev.InputDevice(devicePath)
            if(device.name == 'gpio_ir_recv'):
                inputDevices.append({'deviceType':"GPIOIR", 'device':device})
                break
        if(len(inputDevices)<1):
            #TODO: throw a proper error
            print("No valid input devices found")
            sys.exit()
        # make a dict to return the device from its fd
        self.inputFdMap = {dev['device'].fd: dev for dev in inputDevices}
        self.lastcode=None
        self.repeatcount=0
        self.lasttime=time.monotonic()
        self.config = config
        self.codemap = config.getCodemap()

    def getFDs(self):
        return list(self.inputFdMap)

    # handle an fd
    def handleFD(self, fd):
        quit = False
        for event in self.inputFdMap[fd]['device'].read():
            eventtime = time.monotonic() # what time is it? for as a consistent datum for repeats
            if(event.type == 4):
                # is it a new keypress
                timesincelast = (eventtime-self.lasttime)*1000
                if(self.lastcode!=event.value or timesincelast>self.config.repeatReset):
                    # first keypress of a potential sequence
                    mappedEvent = self.mapIrEvent(event.value)
                    if(mappedEvent != None):
                        quit=self.stepSM(mappedEvent)
                    # start repeat seqence
                    self.lasttime = eventtime
                    self.repeatcount = 0
                    self.lastcode = event.value
                elif(timesincelast>self.config.repeatDelay and (self.repeatcount > 0 or timesincelast>self.config.repeatFirst)):
                    # repeating last keypress
                    mappedEvent = self.mapIrEvent(event.value)
                    if(mappedEvent != None):
                        quit=self.stepSM(mappedEvent)
                    self.lasttime = eventtime
                    self.repeatcount += 1
                    self.lastcode = event.value
            if quit:
                break
        return quit

    # map IR event into navEvent
    def mapIrEvent(self, incode):
        outcode = None
        if(incode in self.codemap):
            outcode = self.codemap[incode]
        return outcode

    # step the state machine with a navEvent
    def stepSM(self, code):
        self.app.get_event(code)
        if(self.app.done):
            self.app.cleanup()
            return True
        self.app.update()
        return False
