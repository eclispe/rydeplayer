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

import enum

class navEvent(enum.Enum):
    UP     = (enum.auto(), 'UP',     None)
    DOWN   = (enum.auto(), 'DOWN',   None)
    LEFT   = (enum.auto(), 'LEFT',   None)
    RIGHT  = (enum.auto(), 'RIGHT',  None)
    SELECT = (enum.auto(), 'SELECT', None)
    BACK   = (enum.auto(), 'BACK',   None)
    MENU   = (enum.auto(), 'MENU',   None)
    POWER  = (enum.auto(), 'POWER',  None)
    MUTE   = (enum.auto(), 'MUTE',   None)
    VOLU   = (enum.auto(), 'VOL+',   None)
    VOLD   = (enum.auto(), 'VOL-',   None)
    CHANU  = (enum.auto(), 'CHAN+',  None)
    CHAND  = (enum.auto(), 'CHAN-',  None)
    OSDOFF = (enum.auto(), 'OSDOFF', None)
    OSDON  = (enum.auto(), 'OSDON',  None)
    OSDTOG = (enum.auto(), 'OSDTOG', None)
    ZERO   = (enum.auto(), 'ZERO',   0)
    ONE    = (enum.auto(), 'ONE',    1)
    TWO    = (enum.auto(), 'TWO',    2)
    THREE  = (enum.auto(), 'THREE',  3)
    FOUR   = (enum.auto(), 'FOUR',   4)
    FIVE   = (enum.auto(), 'FIVE',   5)
    SIX    = (enum.auto(), 'SIX',    6)
    SEVEN  = (enum.auto(), 'SEVEN',  7)
    EIGHT  = (enum.auto(), 'EIGHT',  8)
    NINE   = (enum.auto(), 'NINE',   9)

    def __init__(self, enum, name, numericVal):
        self.numericVal = numericVal
        self.rawname = name
    def __str__(self):
        return str(self.name)
    def isNumeric(self):
        return self.numericVal is not None
    @property
    def numericValue(self):
        return self.numericVal
    @property
    def rawName(self):
        return self.rawname

class shutdownBehavior(enum.Enum):
    APPSTOP = enum.auto()
    APPREST = enum.auto()
    SYSSTOP = enum.auto()
    SYSREST = enum.auto()

# Enum defining box corners to be used as datums
class datumCornerEnum(enum.Enum):
    TR = enum.auto()
    TC = enum.auto()
    TL = enum.auto()
    CR = enum.auto()
    CC = enum.auto()
    CL = enum.auto()
    BR = enum.auto()
    BC = enum.auto()
    BL = enum.auto()

class validTracker(object):
    def __init__(self, initValid):
        self.valid = initValid
        self.validChangeCallbacks = []

    def addValidCallback(self, callback):
        self.validChangeCallbacks.append(callback)

    def removeValidCallback(self, callback):
        self.validChangeCallbacks.remove(callback)
    
    def updateValid(self, newValid):
        if newValid != self.valid:
            self.valid = newValid
            for callback in self.validChangeCallbacks:
                callback()

    def isValid(self):
        return self.valid
