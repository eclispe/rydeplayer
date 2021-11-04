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

import gpiozero, socket, queue, enum
import rydeplayer.common

class gpioEventType(enum.Enum):
    PRESS = enum.auto()
    UP = enum.auto()
    DOWN = enum.auto()

class gpioConfig(object):
    def __init__(self, config = None):
        self.maxPin = 27 # maximum pin number supported by the pi
        self.irpin = 17 # pin that the IR device uses, here to stop it being used
        self.pinButtonMap = {} # map of pin numbers to event objects
        self.pinSwitchLowMap = {} # map of pin numbers to low going event names for switches
        self.pinSwitchHighMap = {} # map of pin numbers to high going event names for switches
        self.rxGoodPin = None # pin to output the RX good signal on
        self.bandPins = [] # pins to output the band ID
        self.repeatFirst=200 # how long to wait before starting to repeat
        self.repeatDelay=100 # while repeating how long between repeats
        self.inconfig=None

    def loadPinMap(self, pins, destmap, invalidPins):
        perfectConfig = True
        if isinstance(pins , dict):
            pinsremaining = list(pins.keys())
            for thisNavEvent in rydeplayer.common.navEvent:
                if thisNavEvent.rawName in pins:
                    pinNo = pins[thisNavEvent.rawName]
                    if isinstance(pinNo, int):
                        if pinNo not in invalidPins: # make sure we aren't trying to use reserved pins
                            if pinNo <= self.maxPin: #check that the pin could exist
                                if pinNo not in destmap:
                                    destmap[pinNo] = thisNavEvent
                                    pinsremaining.remove(thisNavEvent.rawName)
                                else:
                                    print("Multiple events mapped to the same pin, skipping duplicates")
                            else:
                                print("Pin out of range")
                        else:
                            print("Can't use pins reserved for other uses")
                    else:
                        print("Pin is not an int, skipping")
            if len(pinsremaining) >0:
                print("Unknown events")
                print(pinsremainingremaining)
        else:
            print("GPIO pin map is not a map")
            perfectConfig = False
        return perfectConfig

    # parse a dict containing the GPIO config
    def loadConfig(self, config):
        self.inconfig = config.copy()
        perfectConfig = True
        if isinstance(config, dict):
            if 'rxGood' in config:
                if isinstance(config['rxGood'], int):
                    if config['rxGood'] != self.irpin: # make sure we aren't trying to use the ir pin
                        if config['rxGood'] not in self.pinButtonMap: # can't use the pin if its already a button
                            if config['rxGood'] not in self.bandPins: # can't use the pin if its already used for the band output
                                self.rxGoodPin = config['rxGood']
                            else:
                                print("RX pin is already being used for band output, check config")
                                perfectConfig = False
                        else:
                            print("RX pin is already being used for a button, check config")
                            perfectConfig = False
                    else:
                        print("RX pin can't use the IR pin, check config")
                        perfectConfig = False
                else:
                    print("RX good pin provided but not an int, skipping")
                    perfectConfig = False
            if 'band' in config:
                if isinstance(config['band'], list):
                    for pin in config['band']:
                        if isinstance(pin, int):
                            if pin != self.irpin: # can't use the IR pin
                                if pin != self.rxGoodPin: # can't use this pin as its already being used for RX good
                                    if pin not in self.pinButtonMap: # can't use a pin already in use for a button
                                        self.bandPins.append(pin)
                                    else:
                                        print("Band output pin is already being use for a button, abourting further band pins")
                                        perfectConfig = False
                                        break
                                else:
                                    print("Band output pin is already being used as RX good pin, aborting further band pins")
                                    perfectConfig = False
                                    break
                            else:
                                print("Band output pin can't use the IR pin, aborting further band pins")
                                perfectConfig = False
                                break
                        else:
                            print("Band output pin not an int, aboring further band pins")
                            perfectConfig = False
                            break
                else:
                    print("Band output pins provided but not a list, skipping")
                    perfectConfig = False
            if 'buttons' in config: # load gpio button map
                perfectConfig = perfectConfig and self.loadPinMap(config['buttons'], self.pinButtonMap, [self.irpin, self.rxGoodPin]+self.bandPins)
            if 'switches' in config: # load gpio switch map
                if isinstance(config['switches'], dict):
                    if 'highgoing' in config['switches']:
                        perfectConfig = perfectConfig and self.loadPinMap(config['switches']['highgoing'], self.pinSwitchHighMap, [self.irpin, self.rxGoodPin]+self.bandPins)
                    if 'lowgoing' in config['switches']:
                        perfectConfig = perfectConfig and self.loadPinMap(config['switches']['lowgoing'], self.pinSwitchLowMap, [self.irpin, self.rxGoodPin]+self.bandPins)
            if 'repeatFirst' in config:
                if isinstance(config['repeatFirst'] , int):
                    self.repeatFirst = config['repeatFirst']
                else:
                    print("GPIO repeat first is invalid, ignoring")
                    perfectConfig = False
            if 'repeatDelay' in config:
                if isinstance(config['repeatDelay'] , int):
                    self.repeatDelay = config['repeatDelay']
                else:
                    print("GPIO repeat first is invalid, ignoring")
                    perfectConfig = False
        else:
            print("GPIO config invalid, ignoring")
            perfectConfig = False
        return perfectConfig

class gpioManager(object):
    def __init__(self, eventCallback, config, initialPreset):
        debounce = 0.01
        self.eventCallback = eventCallback
        self.config = config
        self.buttons = {}
        # create gpio button objects for each button and register callbacks for them
        for pin in set(self.config.pinButtonMap)|set(self.config.pinSwitchLowMap)|set(self.config.pinSwitchHighMap):
            thisbutton = gpiozero.Button(pin, bounce_time=debounce, hold_time = self.config.repeatFirst/1000)
            if pin in self.config.pinButtonMap:
                thisbutton.hold_repeat = self.config.repeatDelay/1000
                thisbutton.when_held = self.pressCallback
                if pin in self.config.pinSwitchHighMap:
                    thisbutton.when_pressed = self.downPressCallback
                else:
                    thisbutton.when_pressed = self.pressCallback
            elif pin in self.config.pinSwitchHighMap:
                thisbutton.when_pressed = self.downCallback
            if pin in self.config.pinSwitchLowMap:
                thisbutton.when_released = self.upCallback
            self.buttons[pin] = thisbutton

        self.rxGoodLED = None

        # create a gpio LED object for the status light if there is a pin defined
        if self.config.rxGoodPin is not None:
            self.rxGoodLED = gpiozero.LED(self.config.rxGoodPin)

        # create a list of gpio LED objects for the band bits

        self.bandPins = []
        for pin in self.config.bandPins:
            self.bandPins.append(gpiozero.LED(pin))

        self.gpioID = None
        self.setBandOutFromPreset(initialPreset)

        # socket to notify the main loop of a button press
        self.recvSock, self.sendSock = socket.socketpair()
        # thread save queue to store the actual events
        self.eventQueue = queue.Queue()

    # callback for the button presses
    # gpiozero docs are unclear but these appear to execute from a callback thread
    def pressCallback(self, button):
        if button.is_active:
            self.eventQueue.put((button.pin.number, gpioEventType.PRESS))
            self.sendSock.send(b"\x00")

    # callbacks for switch high going edge
    # gpiozero docs are unclear but these appear to execute from a callback thread
    def downCallback(self, button):
        if button.is_active:
            self.eventQueue.put((button.pin.number, gpioEventType.DOWN))
            self.sendSock.send(b"\x00")

    # callbacks for switch low going edge
    # gpiozero docs are unclear but these appear to execute from a callback thread
    def upCallback(self, button):
        if not button.is_active:
            self.eventQueue.put((button.pin.number, gpioEventType.UP))
            self.sendSock.send(b"\x00")

    # callback for pins that have down and press callbacks
    # gpiozero docs are unclear but these appear to execute from a callback thread
    def downPressCallback(self, button):
        self.downCallback(button)
        self.pressCallback(button)
    
    # fd for the notification socket
    def getFDs(self):
        return [self.recvSock]

    # handle the fd
    def handleFD(self, fd):
        while not self.eventQueue.empty():
            fd.recv(1) # there should always be the same number of chars in the socket as items in the queue
            eventPin, eventType = self.eventQueue.get()
            quit = False
            if eventType is gpioEventType.PRESS:
                mappedEvent = self.config.pinButtonMap[eventPin]
            elif eventType is gpioEventType.DOWN:
                mappedEvent = self.config.pinSwitchHighMap[eventPin]
            elif eventType is gpioEventType.UP:
                mappedEvent = self.config.pinSwitchLowMap[eventPin]
            if mappedEvent != None:
                quit=self.eventCallback(mappedEvent)
            if quit:
                break
        return quit
    
    # sets the RX good staus pin
    def setRXgood(self, newState):
        if self.rxGoodLED is not None and isinstance(self.rxGoodLED, gpiozero.LED):
            if newState:
                self.rxGoodLED.on()
            else:
                self.rxGoodLED.off()

    # sets band pins from the band in a preset
    def setBandOutFromPreset(self, newState):
        self.setBandOut(newState.getBand().getGPIOid())

    def setBandOut(self, newGPIOid):
        if newGPIOid != self.gpioID:
            self.gpioID = newGPIOid
            print("GPIO id: "+str(newGPIOid))
            for bit, pin in enumerate(self.bandPins):
                # bitwise bit extraction: shift by index, bitwise 'and' with 1 to throw away everything else
                bitVal = bool((newGPIOid >> bit) & 1)
                if bitVal:
                    pin.on()
                else:
                    pin.off()
