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

import gpiozero, socket, queue
import rydeplayer.common

class gpioConfig(object):
    def __init__(self, config = None):
        self.maxPin = 27 # maximum pin number supported by the pi
        self.irpin = 17 # pin that the IR device uses, here to stop it being used
        self.pinButtonMap = {} # map of pin numbers to event objects
        self.rxGoodPin = None # pin to output the RX good signal on
        self.repeatFirst=200 # how long to wait before starting to repeat
        self.repeatDelay=100 # while repeating how long between repeats
        self.inconfig=None
    
    # parse a dict containing the GPIO config
    def loadConfig(self, config):
        self.inconfig = config.copy()
        perfectConfig = True
        if isinstance(config, dict):
            if 'rxGood' in config:
                if isinstance(config['rxGood'], int):
                    if config['rxGood'] != self.irpin: # make sure we aren't trying to use the ir pin
                        if config['rxGood'] not in self.pinButtonMap: # can't use the pin if its already a button
                           self.rxGoodPin = config['rxGood']
                        else:
                            print("RX pin is already being used for a button, check config")
                    else:
                        print("RX pin can't use the IR pin, check config")
                        perfectConfig = False
                else:
                    print("RX good pin provided but not an int, skipping")
                    perfectConfig = False
            if 'buttons' in config: # load gpio button map
                if isinstance(config['buttons'] , dict):
                    buttonsremaining = list(config['buttons'].keys())
                    for thisNavEvent in rydeplayer.common.navEvent:
                        if thisNavEvent.name in config['buttons']:
                            pinNo = config['buttons'][thisNavEvent.name]
                            if isinstance(pinNo, int):
                                if pinNo != self.rxGoodPin: # make sure we aren't trying to use the rx good pin
                                    if pinNo != self.irpin: # make sure we aren't trying to use the ir pin
                                        if pinNo <= self.maxPin: #check that the pin coudl exsist
                                            if pinNo not in self.pinButtonMap:
                                                self.pinButtonMap[pinNo] = thisNavEvent
                                                buttonsremaining.remove(thisNavEvent.name)
                                            else:
                                                print("Multiple buttons mapped to the same pin, skipping duplicates")
                                        else:
                                            print("Pin out of range")
                                    else:
                                        print("Can't use the IR pin for a button")
                                else:
                                    print("Can't use the rx good pin for a button")
                            else:
                                print("Pin is not an int, skipping")
                    if len(buttonsremaining) >0:
                        print("Unknown buttons")
                        print(buttonsremaining)
                else:
                    print("GPIO button map is not a map")
                    perfectConfig = False
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
    def __init__(self, eventCallback, config):
        debounce = 0.01
        self.eventCallback = eventCallback
        self.config = config
        self.buttons = {}
        # create gpio button objects for each button and register callbacks for them
        for pin in self.config.pinButtonMap:
            thisbutton = gpiozero.Button(pin, bounce_time=debounce, hold_time = self.config.repeatFirst/1000)
            thisbutton.hold_repeat = self.config.repeatDelay/1000
            thisbutton.when_pressed = self.pressCallback
            thisbutton.when_held = self.pressCallback
            self.buttons[pin] = thisbutton
        self.rxGoodLED = None
        # create a gpio LED object for the status light if there is a pin defined
        if self.config.rxGoodPin is not None:
            self.rxGoodLED = gpiozero.LED(self.config.rxGoodPin)

        # socket to notify the main loop of a button press
        self.recvSock, self.sendSock = socket.socketpair()
        # thread save queue to store the actual events
        self.eventQueue = queue.Queue()

    # callback for the button presses
    # gpiozero docs are unclear but these appear to execute from a callback thread
    def pressCallback(self, button):
        if button.is_active:
            self.eventQueue.put(button.pin.number)
            self.sendSock.send(b"\x00")
    
    # fd for the notification socket
    def getFDs(self):
        return [self.recvSock]

    # handle the fd
    def handleFD(self, fd):
        while not self.eventQueue.empty():
            fd.recv(1) # there should always be the same number of chars in the socket as items in the queue
            eventPin = self.eventQueue.get()
            quit = False
            mappedEvent = self.config.pinButtonMap[eventPin]
            if(mappedEvent != None):
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
