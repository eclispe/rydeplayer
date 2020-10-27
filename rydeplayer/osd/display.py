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

import pydispmanx, pygame
import rydeplayer.longmynd
import rydeplayer.common
import enum, queue, socket, threading

# Enum containing a list of all possible modules
class AvailableModules(enum.Enum):
    MUTE = enum.auto()
    MER = enum.auto()
    REPORT = enum.auto()
    PROGRAM = enum.auto()

# Enum containing configurable timer lengths
class TimerLength(enum.Enum):
    PROGRAMTRIGGER = enum.auto()
    USERTRIGGER = enum.auto()

# Group of modules and layout parameters
class Group(object):
    def __init__(self, theme, controller):
        self.theme = theme
        self.controller = controller
        self.modules = {}

    # enable, disable and move modules to match this group
    def activate(self):
        moduleLayoutChanged = False
        for moduleName, module in self.controller.getModules().items():
            if moduleName in self.modules:
                if module.setRect(self.modules[moduleName], True):
                    moduleLayoutChanged = True
                if module.setEnabled(True):
                    moduleLayoutChanged = True
            elif module.setEnabled(False):
                moduleLayoutChanged = True
        if moduleLayoutChanged:
            self.controller.updateLayer()

    # Set the layout details of this group
    def setModules(self, modules):
        self.modules = modules

    def getEnabledModules(self):
        return self.modules.keys()

# Store and parse OSD config
class Config(object):
    def __init__(self, theme):
        self.theme = theme
        self.activeGroup={AvailableModules.MUTE:None, AvailableModules.MER:None, AvailableModules.PROGRAM:None}
        self.inactiveGroup={AvailableModules.MUTE:None}
        self.timers={TimerLength.PROGRAMTRIGGER: 5, TimerLength.USERTRIGGER: 5}

    def getActiveGroup(self):
        return self.activeGroup

    def getInactiveGroup(self):
        return self.inactiveGroup

    def getTimerLength(self, timer):
        if isinstance(timer, TimerLength) and timer in self.timers:
            return self.timers[timer]
        else:
            return None
   
    # Parse OSD config from config file format
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            if 'active' in config:
                tmpPerfectConfig, tmpGroupConfig = self._loadGroup(config['active'])
                if tmpGroupConfig is not None:
                    self.activeGroup = tmpGroupConfig
                perfectConfig = perfectConfig and tmpPerfectConfig
            if 'inactive' in config:
                tmpPerfectConfig, tmpGroupConfig = self._loadGroup(config['inactive'])
                if tmpGroupConfig is not None:
                    self.inactiveGroup = tmpGroupConfig
                perfectConfig = perfectConfig and tmpPerfectConfig
            if 'timers' in config:
                if isinstance(config['timers'], dict):
                    unusedtimers = list(config['timers'].keys())
                    for thisTimer in TimerLength:
                        if thisTimer.name in config['timers']:
                            timerLength = config['timers'][thisTimer.name]
                            if timerLength is None:
                                self.timers[thisTimer] = None
                                unusedtimers.remove(thisTimer.name)
                            else:
                                if isinstance(timerLength, int):
                                    timerLength = float(timerLength)
                                if isinstance(timerLength, float):
                                    if timerLength >= 0:
                                        self.timers[thisTimer] = timerLength
                                        unusedtimers.remove(thisTimer.name)
                                    else:
                                        print("Timers must be 0 or greater")
                                        perfectConfig = False
                                else:
                                    print("Timer is not a number or null, skipping")
                                    perfectConfig = False
                    if len(unusedtimers) > 0:
                        print("Unknown timers")
                        print(unusedtimers)
                else:
                    print("GPIO timers is not a map, skipping")
                    perfectConfig = False
        else:
            print("OSD config not valid, skipping")
            perfectConfig = False
        return perfectConfig

    # helper to load OSD groups
    def _loadGroup(self, config):
        perfectConfig = True
        acceptableConfig = True
        newConfig = {}
        if not isinstance(config, dict):
            perfectConfig = False
            acceptableConfig = False
        else:
            modulesRemaining = list(config.keys())
            for moduleId in AvailableModules:
                if moduleId.name in config:
                    if config[moduleId.name] is None:
                        newConfig[moduleId] = None
                    else:
                        newConfig[moduleId] = self._parseConfigRect(config[moduleId.name])
        if acceptableConfig:
            return (perfectConfig, newConfig)
        return (perfectConfig, None)

    # helper for rectangle parser to check values are in the range 0-1 for edge or -0.5 to 0.5 for center
    def _checkScaleRange(self, collection, index, edge=True):
        if index in collection:
            value = collection[index]
            if isinstance(value, int): #convert ints to float, fixes 0 and 1
                value = float(value)
            if isinstance(value, float):
                if edge and value >= 0 and value <= 1:
                    return True
                elif (not edge) and value >= -0.5 and value <= 0.5:
                    return True
        return False

    # helper that parses a relative size rectangle and returns an absolute size rectangle
    def _parseConfigRect(self, config):
        if config is None:
            return None
        elif isinstance(config, dict):
            outRect = None
            if 'datum' in config:
                if str(config['datum']).upper() in rydeplayer.common.datumCornerEnum.__members__.keys():
                    if self._checkScaleRange(config, 'x', str(config['datum']).upper() in ["TR", "TL", "CR", "CL", "BR", "BL"]):
                        if self._checkScaleRange(config, 'y', str(config['datum']).upper() in ["TR", "TC", "TR", "BR", "BC", "BL"]):
                            if self._checkScaleRange(config, 'w', True):
                                if self._checkScaleRange(config, 'h', True):
                                    outRect = self.theme.relativeRect(rydeplayer.common.datumCornerEnum.__members__[str(config['datum']).upper()], config['x'], config['y'], config['w'], config['h'])
                                else:
                                    print("Invalid or missing height value, using defaults")
                            else:
                                print("Invalid or missing width value, using defaults")
                        else:
                            print("Invalid or missing y value, using defaults")
                    else:
                        print("Invalid or missing x value, using defaults")
                else:
                    print("Invalid datum, using defaults")
            else:
                print("No Datum specified, using defaults")
            if outRect is None:
                print("Invalid module location, using default")
            return outRect
        else:
            print("Group module config not null or valid config, assuming null")
            return None

# On screen display controller
class Controller(object):
    def __init__(self, theme, config, longmyndStatus, player, tunerConfig):
        self.theme = theme
        self.config = config
        self.longmyndStatus = longmyndStatus
        self.player = player
        self.tunerConfig = tunerConfig
        # Create display layer
        self.dispmanxlayer = pydispmanx.dispmanxLayer(3)
        self.surface = pygame.image.frombuffer(self.dispmanxlayer, self.dispmanxlayer.size, 'RGBA')
        # Initialise modules
        self.modules = dict()
        self.modules[AvailableModules.MUTE]=rydeplayer.osd.modules.mute(self.theme, self.draw, theme.relativeRect(rydeplayer.common.datumCornerEnum.TR, 0.02, 0.02, 0.1, 0.1))
        self.player.addMuteCallback(self.modules[AvailableModules.MUTE].updateVal)
        self.modules[AvailableModules.MER]=rydeplayer.osd.modules.mer(self.theme, self.draw, theme.relativeRect(rydeplayer.common.datumCornerEnum.TR, 0.02, 0.14, 0.2, 0.15))
        self.longmyndStatus.addOnChangeCallback(self.modules[AvailableModules.MER].updateVal)
        self.modules[AvailableModules.REPORT]=rydeplayer.osd.modules.report(self.theme, self.draw, theme.relativeRect(rydeplayer.common.datumCornerEnum.TR, 0.02, 0.31, 0.2, 0.15))
        self.longmyndStatus.addOnChangeCallback(self.modules[AvailableModules.REPORT].updateVal)
        self.modules[AvailableModules.PROGRAM]=rydeplayer.osd.modules.program(self.theme, self.draw, theme.relativeRect(rydeplayer.common.datumCornerEnum.BC, 0, 0.02, 0.75, 0.2))
        self.longmyndStatus.addOnChangeCallback(self.modules[AvailableModules.PROGRAM].updateVal)
        self.tunerConfig.addCallbackFunction(self._updatePresetName)
        self._updatePresetName(self.tunerConfig)
        # Initalise groups
        self.activeGroup = Group(self.theme, self)
        self.activeGroup.setModules(config.getActiveGroup())
        self.inactiveGroup = Group(self.theme, self)
        self.inactiveGroup.setModules(config.getInactiveGroup())
        # Start with inactive group displayed
        self.inactiveGroup.activate()
        self.activePriority = None
        # socket to notify the main loop of a timer expire
        self.recvSockTimer, self.sendSockTimer = socket.socketpair()
        # thread safe queue to store the timer events
        self.timerEventQueue = queue.Queue()
        # timer thread
        self.timer = None

    def _updatePresetName(self, preset):
        self.modules[AvailableModules.PROGRAM].updateVal(self.player.getPresetName(preset))

    def getModules(self):
        return self.modules

    # Draw module on the screen, passed as callback to modules
    def draw(self, module, boxes = None, deferRedraw=False):
        # paint everything out
        if boxes is None:
            boxes = [module.getRect()]
        for box in boxes:
            self.surface.fill(self.theme.colours.transparent, box)
        # paint everything that is enabled back in
        blitPairs = []
        for module in self.modules.values():
            if module.getEnabled():
                modulerect = module.getRect()
                if modulerect.collidelist(boxes) >= 0:
                    modulesurface = module.getSurface()
                    for box in boxes:
                        blitPairs.append((modulesurface, modulerect.clip(box)))
        self.surface.blits(blitPairs)
        # Allow defering final update if multiple modules as being updated
        if not deferRedraw:
            self.dispmanxlayer.updateLayer()

    def updateLayer(self):
        self.dispmanxlayer.updateLayer()

    # Activate the OSD activated group if not already active at a higer priority
    def activate(self, priority, deactivateAfter = None):
        if self.activePriority is None or self.activePriority >= priority:
            # if handed a config file reference, dereference it first
            if isinstance(deactivateAfter, TimerLength):
                deactivateAfter = self.config.getTimerLength(deactivateAfter)
            # if the timer is 0 don't activate in the first place
            if deactivateAfter is None or float(deactivateAfter) != float(0):
                self.activeGroup.activate()
                self.activePriority = priority
                # set the deactivate timer
                if deactivateAfter is not None:
                    # cancel any old timers before setting the new one
                    if self.timer is not None:
                        self.timer.cancel()
                    self.timer = threading.Timer(deactivateAfter, self.asyncDeactivate, [priority])
                    self.timer.start()

    # Activate the OSD inactive group if it wasn't activated by a higer priority in the first place
    def deactivate(self, priority):
        if self.activePriority is not None and self.activePriority >= priority:
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None
            self.inactiveGroup.activate()
            self.activePriority = None

    # Threaded deactivate callback
    def asyncDeactivate(self, priority):
        self.timerEventQueue.put(priority)
        self.sendSockTimer.send(b"\x00")

    # fd for the timer notification socket
    def getFDs(self):
        return [self.recvSockTimer]

    # handle the fd
    def handleFD(self, fd):
        while not self.timerEventQueue.empty():
            fd.recv(1)
            deactivatePriority = self.timerEventQueue.get()
            self.deactivate(deactivatePriority)
        return False

    # Destroy the layer on shutdown
    def __del__(self):
        del(self.surface)
        del(self.dispmanxlayer)
