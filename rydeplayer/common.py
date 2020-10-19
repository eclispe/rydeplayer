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
    UP     = (enum.auto(), None)
    DOWN   = (enum.auto(), None)
    LEFT   = (enum.auto(), None)
    RIGHT  = (enum.auto(), None)
    SELECT = (enum.auto(), None)
    BACK   = (enum.auto(), None)
    MENU   = (enum.auto(), None)
    POWER  = (enum.auto(), None)
    MUTE   = (enum.auto(), None)
    OSDOFF = (enum.auto(), None)
    OSDON  = (enum.auto(), None)
    ZERO   = (enum.auto(), 0)
    ONE    = (enum.auto(), 1)
    TWO    = (enum.auto(), 2)
    THREE  = (enum.auto(), 3)
    FOUR   = (enum.auto(), 4)
    FIVE   = (enum.auto(), 5)
    SIX    = (enum.auto(), 6)
    SEVEN  = (enum.auto(), 7)
    EIGHT  = (enum.auto(), 8)
    NINE   = (enum.auto(), 9)

    def __init__(self, enum, numericVal):
        self.numericVal = numericVal
    def __str__(self):
        return str(self.name)
    def isNumeric(self):
        return self.numericVal is not None
    @property
    def numericValue(self):
        return self.numericVal

class shutdownBehavior(enum.Enum):
    APPSTOP = enum.auto()
    APPREST = enum.auto()
    SYSSTOP = enum.auto()
    SYSREST = enum.auto()

# Enum defining box corners to be used as datums
class datumCornerEnum(enum.Enum):
    TR = enum.auto()
    TL = enum.auto()
    BR = enum.auto()
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
