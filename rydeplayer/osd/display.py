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
import enum

# Enum containing a list of all possible modules
class AvailableModules(enum.Enum):
    MUTE = enum.auto()
    MER = enum.auto()

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
        self.activeGroup={AvailableModules.MUTE:None, AvailableModules.MER:None}
        self.inactiveGroup={AvailableModules.MUTE:None}

    def getActiveGroup(self):
        return self.activeGroup

    def getInactiveGroup(self):
        return self.inactiveGroup
   
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
            print(config)
            print(newConfig)
            return (perfectConfig, newConfig)
        return (perfectConfig, None)

    # helper for rectangle parser to check values are in the range 0-1
    def _checkScaleRange(self, collection, index):
        if index in collection:
            value = collection[index]
            if isinstance(value, int): #convert ints to float, fixes 0 and 1
                value = float(value)
            if isinstance(value, float):
                if value >= 0 and value <= 1:
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
                    if self._checkScaleRange(config, 'x'):
                        if self._checkScaleRange(config, 'y'):
                            if self._checkScaleRange(config, 'w'):
                                if self._checkScaleRange(config, 'h'):
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
        # Initalise groups
        self.activeGroup = Group(self.theme, self)
        self.activeGroup.setModules(config.getActiveGroup())
        self.inactiveGroup = Group(self.theme, self)
        self.inactiveGroup.setModules(config.getInactiveGroup())
        # Start with inactive group displayed
        self.inactiveGroup.activate()
        self.activePriority = None
    
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
    def activate(self, priority):
        if self.activePriority is None or self.activePriority > priority:
            self.activeGroup.activate()
            self.activePriority = priority

    # Activate the OSD inactive group if it wasn't activated by a higer priority in the first place
    def deactivate(self, priority):
        if self.activePriority is not None and self.activePriority >= priority:
            self.inactiveGroup.activate()
            self.activePriority = None
    
    # Destroy the layer on shutdown
    def __del__(self):
        del(self.surface)
        del(self.dispmanxlayer)
