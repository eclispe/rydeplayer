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

import pygame
import rydeplayer.sources.common
from PIL import Image

# Generic OSD display module
class generic(object):
    def __init__(self, theme, drawCallback, rect):
        self.theme = theme
        self.drawCallback = drawCallback
        self.defaultRect = rect
        self.rect = self.defaultRect.copy()
        self.surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        self.enabled = False
        self._circlecache = {}

    def getRect(self):
        return self.rect

    # resize the module with a new rect
    def setRect(self, newrect, deferRedraw = False):
        oldrect = self.rect.copy()
        if newrect is None:
            newrect = self.defaultRect.copy() # so we don't have to rely on something not changing it
        if newrect != oldrect:
            self.rect = newrect
            self.surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
            # pass the old rect too to make sure it is painted out
            self.redraw([oldrect, newrect], deferRedraw=deferRedraw)
            return True
        else:
            return False

    def getSurface(self):
        return self.surface

    def setEnabled(self, enabled, deferRedraw = False):
        if(self.enabled != enabled):
            self.enabled = enabled
            self.redraw(deferRedraw=deferRedraw)
            return True
        else:
            return False

    def getEnabled(self):
        return self.enabled

    def updateVal(self, newval):
        self.redraw()

    def redraw(self, rects = None, deferRedraw = False):
        if(self.drawCallback is not None):
            if(rects is None):
                self.drawCallback(self, deferRedraw = deferRedraw)
            else:
                self.drawCallback(self, rects, deferRedraw = deferRedraw)

# generic module for displaying a small numeric value
class meterDisplay(generic):
    def __init__ (self, theme, drawCallback, rect):
        super().__init__(theme, drawCallback, rect)
        self.rect = rect.copy()
        self.renderedbox = None
        self.value = None
        self.renderedValue = None
        self.staticTextSurface = None
        self.dynamicTextRect = None
        self.meterConfig = None
        self.renderedMeterConfig = None

    def redraw(self, rects = None, deferRedraw = False):
        # if the layout needs recalcuating because its new, moved or changed size
        if(self.renderedbox is None or self.renderedbox != self.rect or self.meterConfig != self.renderedMeterConfig):
            self.surface.fill(self.theme.colours.transparent)
            self.renderedMeterConfig = self.meterConfig
            if(self.meterConfig is not None):
                meterbar = pygame.Rect((0,0),(self.rect.height*0.25, self.rect.height)) # placeholder space for a meter
                meterbar.right = self.rect.width
                textwidth = self.rect.width - meterbar.width # total width available for the text
                staticfontsize = self.theme.fontSysSizeOptimize(self.renderedMeterConfig.staticText, textwidth*0.8, 'freesans')
                staticfont = self.theme.fontLib.SysFont('freesans', staticfontsize) # font for the static unit text
                dynamicfontsize = self.theme.fontSysSizeOptimize("25.5", textwidth*0.8, 'freesans')
                self.dynamicfont = self.theme.fontLib.SysFont('freesans', dynamicfontsize) # font for the actual report value
                textheight = staticfont.get_linesize() + self.dynamicfont.get_linesize()
                self.textbox = pygame.Rect((0,0), (textwidth, textheight))
                self.textbox.centery=self.rect.height/2 # center the box containing the text vertically in the bigger box
                self.staticTextSurface = self.theme.outlineFontRender(self.renderedMeterConfig.staticText, staticfont, self.theme.colours.white, self.theme.colours.black, 1)
                staticTextRect = self.staticTextSurface.get_rect()
                staticTextRect.bottom = self.textbox.bottom
                staticTextRect.centerx = self.textbox.centerx
                self.surface.blit(self.staticTextSurface, staticTextRect)
                self.renderedbox = self.rect.copy()

        if(self.meterConfig is not None):
            self.renderedValue = self.value
            if(self.dynamicTextRect is not None):
                self.surface.fill(self.theme.colours.transparent, self.dynamicTextRect)
            if self.value is None:
                valueText = "-"
            else:
                valueText = self.renderedMeterConfig.prefixText + str(self.value)
            dynamicTextSurface = self.theme.outlineFontRender(valueText, self.dynamicfont, self.theme.colours.white, self.theme.colours.black, 1)
            self.dynamicTextRect = dynamicTextSurface.get_rect()
            self.dynamicTextRect.top = self.textbox.top
            self.dynamicTextRect.centerx = self.textbox.centerx
            self.surface.blit(dynamicTextSurface, self.dynamicTextRect)
        super().redraw(rects, deferRedraw)

    def updateVal(self, newval):
        if self.meterConfig is not None:
            self.value = self.meterConfig.processValueFunc(newval)
        else:
            self.vale = None
        self.redraw()

# module that displays the current power level
class powerLevel(meterDisplay):

    def updateVal(self, newval):
        self.meterConfig = newval.getPowerLevelMeta()
        super().updateVal(newval)

# module that displays the current signal level
class sigLevel(meterDisplay):

    def updateVal(self, newval):
        self.meterConfig = newval.getSignalLevelMeta()
        super().updateVal(newval)

# module that displays the current signal report also known as "D number"
class report(meterDisplay):

    def updateVal(self, newval):
        self.meterConfig = newval.getSignalReportMeta()
        super().updateVal(newval)

# module that displays the current volume
class volume(meterDisplay):
    def __init__ (self, theme, drawCallback, rect, initVolume ):
        super().__init__(theme, drawCallback, rect)
        def processVal(newVal):
            return newVal
        self.value = initVolume
        self.meterConfig = rydeplayer.sources.common.sourceStatus.meterConfig("% Vol", "", processVal)

    def updateVal(self, newval):
        super().updateVal(newval)

# module that displays an icon when muted
class mute(generic):
    def __init__ (self, theme, drawCallback, rect, initMute):
        self.mute = initMute
        self.origIcon = Image.open(theme.muteicon)
        self.iconSize = min(rect.size) # icon is sqauare, how long are its edges
        finalIcon = self.origIcon.resize((self.iconSize, self.iconSize), Image.ANTIALIAS)
        iconStr = finalIcon.tobytes("raw", "RGBA")
        self.iconSurface = pygame.image.fromstring(iconStr, finalIcon.size, "RGBA")
        super().__init__(theme, drawCallback, rect)

    def updateVal(self, newval):
        self.mute = newval
        self.redraw()

    def redraw(self, rects = None, deferRedraw = False):
        # module has changed size, resize the image to match the new size
        if(min(self.rect.size)!=self.iconSize):
            self.iconSize = min(self.rect.size)
            finalIcon = self.origIcon.resize((self.iconSize, self.iconSize), Image.ANTIALIAS)
            iconStr = finalIcon.tobytes("raw", "RGBA")
            self.iconSurface = pygame.image.fromstring(iconStr, finalIcon.size, "RGBA")
        # switch between transparent and the icon depending on mute state
        if(self.mute):
            self.surface.fill(self.theme.colours.transparent)
            self.surface.blit(self.iconSurface,(0,0))
        else:
            self.surface.fill(self.theme.colours.transparent)
        super().redraw(rects, deferRedraw)

class program(generic):
    def __init__ (self, theme, drawCallback, rect):
        super().__init__(theme, drawCallback, rect)
        self.theme = theme
        self.rect = rect.copy()
        self.renderedbox = None
        self.presetName = ""
        self.provider = ""
        self.service = ""
        self.modulation = None
        self.pids = {}
        # track the current rendered value, to check for rerender
        self.renderedPresetName = ""
        self.renderedProvider = ""
        self.renderedService = ""
        self.renderedPIDs = {}
        self.renderedModulation = None
        self.presetNameRect = None
        self.providerRect = None
        self.serviceRect = None
        self.modulationRect = None
        self.pidsRect = None

    def updateVal(self, newval):
        if(isinstance(newval, rydeplayer.sources.common.sourceStatus)):
            self.provider = newval.getProvider()
            self.service = newval.getService()
            self.modulation = newval.getModulation()
            self.pids = newval.getPIDs()
        elif(isinstance(newval, str)):
            self.presetName = newval
        self.redraw()

    def redraw(self, rects = None, deferRedraw = False):
        drawAll = False
        if self.renderedbox is None or self.renderedbox != self.rect:
            drawAll = True
            self.surface.fill(self.theme.colours.backgroundMenu)
            # left box
            contentboxleft = pygame.Rect((self.rect.height*0.15,self.rect.height*0.1),((self.rect.width-(self.rect.height*0.5))*0.6, self.rect.height*0.8)) # left content box
            self.presetNameRect = pygame.Rect((contentboxleft.left, contentboxleft.top),(contentboxleft.width, contentboxleft.height/3))
            self.providerRect = pygame.Rect((contentboxleft.x, self.presetNameRect.bottom),(contentboxleft.width, contentboxleft.height/3))
            self.serviceRect = pygame.Rect((contentboxleft.x, self.providerRect.bottom),(contentboxleft.width, contentboxleft.height/3))
            serviceDetailsBox = pygame.Rect((contentboxleft.x-self.rect.height*0.05,(contentboxleft.height/3)+contentboxleft.top),(contentboxleft.width+self.rect.height*0.1, (contentboxleft.height/3)*2))
            self.surface.fill(self.theme.colours.white, serviceDetailsBox)
            self.largeFont = self.theme.fontLib.SysFont('freesans', self.theme.fontSysSizeOptimizeHeight(contentboxleft.height/3, 'freesans')) # font for the large program details
            # right box
            contentboxright = pygame.Rect((contentboxleft.right+self.rect.height*0.2,self.rect.height*0.1),((self.rect.width-(self.rect.height*0.5))*0.4, self.rect.height*0.8)) # right content box
            self.modulationRect = pygame.Rect((contentboxright.x,contentboxright.top),(contentboxright.width, contentboxright.height/3))
            self.pidsRect = pygame.Rect((contentboxright.x,(contentboxright.height/3)+contentboxright.top),(contentboxright.width, (contentboxright.height/3)*2)) # 
            pidsColBox = pygame.Rect((self.pidsRect.x-self.rect.height*0.05,self.pidsRect.top),(self.pidsRect.width+self.rect.height*0.1, self.pidsRect.height)) # pids content box
            self.surface.fill(self.theme.colours.white, pidsColBox)
            self.smallFont = self.theme.fontLib.SysFont('freesans', self.theme.fontSysSizeOptimizeHeight(self.pidsRect.height/4, 'freesans')) # font for the large program details

        if drawAll or self.presetName != self.renderedPresetName:
            self.renderedPresetName = self.presetName
            presetNameTextSurface = self.largeFont.render(self.presetName, True, self.theme.colours.black)
            presetNameTextRect = presetNameTextSurface.get_rect()
            presetNameTextRect.top = self.presetNameRect.top;
            presetNameTextRect.left = self.presetNameRect.left
            self.surface.fill(self.theme.colours.backgroundMenu, self.presetNameRect)
            self.surface.blit(presetNameTextSurface, presetNameTextRect, pygame.Rect((0,0),self.presetNameRect.size))

        if drawAll or self.provider != self.renderedProvider:
            self.renderedProvider = self.provider
            providerTextSurface = self.largeFont.render(self.provider, True, self.theme.colours.black)
            providerTextRect = providerTextSurface.get_rect()
            providerTextRect.top = self.providerRect.top
            providerTextRect.left = self.providerRect.left
            self.surface.fill(self.theme.colours.white, self.providerRect)
            self.surface.blit(providerTextSurface, providerTextRect, pygame.Rect((0,0),self.providerRect.size))

        if drawAll or self.service != self.renderedService:
            self.renderedService = self.service
            serviceTextSurface = self.largeFont.render(self.service, True, self.theme.colours.black)
            serviceTextRect = serviceTextSurface.get_rect()
            serviceTextRect.top = self.serviceRect.top
            serviceTextRect.left = self.serviceRect.left
            self.surface.fill(self.theme.colours.white, self.serviceRect)
            self.surface.blit(serviceTextSurface, serviceTextRect, pygame.Rect((0,0),self.serviceRect.size))

        if drawAll or self.moulation != self.renderedModulation:
            self.renderedModulation = self.modulation
            if self.modulation is None:
                modstring = ""
            else:
                modstring = self.modulation.longName
            modulationTextSurface = self.smallFont.render(modstring, True, self.theme.colours.black)
            modulationTextRect = modulationTextSurface.get_rect()
            modulationTextRect.centery = self.modulationRect.centery;
            modulationTextRect.left = self.modulationRect.left
            self.surface.fill(self.theme.colours.backgroundMenu, self.modulationRect)
            self.surface.blit(modulationTextSurface, modulationTextRect, pygame.Rect((0,0),self.modulationRect.size))

        if drawAll or self.pids != self.renderedPIDs:
            self.renderedPIDs = self.pids
            self.surface.fill(self.theme.colours.white, self.pidsRect)
            rendered = 0
            nexttop = self.pidsRect.top
            pidlist = list(self.pids.keys())
            pidlist.sort()
            for pid in pidlist:
                codec = self.pids[pid]
                if len(self.pids) > 4 and rendered == 3:
                    pidstr = "+"+str(len(self.pids)-3)+" more"
                else:
                    pidstr = str(pid)+": "+str(codec)
                pidTextSurface = self.smallFont.render(pidstr, True, self.theme.colours.black)
                pidTextRect = pidTextSurface.get_rect()
                pidTextRect.top = nexttop
                nexttop = pidTextRect.bottom
                pidTextRect.left = self.pidsRect.left
                self.surface.blit(pidTextSurface, pidTextRect, pygame.Rect((0,0),self.pidsRect.size))
                rendered += 1
                if rendered >= 4:
                    break

        super().redraw(rects, deferRedraw)

# module that displays the a numeric value with units
class numericDisplay(generic):
    def __init__ (self, theme, drawCallback, rect):
        super().__init__(theme, drawCallback, rect)
        self.rect = rect.copy()
        self.renderedbox = None
        self.value = None
        self.dynamicTextRect = None
        self.numericConfig = None

    def updateVal(self, newval):
        if self.numericConfig is not None:
            newvalue = self.numericConfig.processValueFunc(newval)
            if newvalue is not None:
                newvalueround = round(newvalue)
                if newvalueround != self.value:
                    self.value = newvalueround
                    self.redraw()
            else:
                self.value = None
                self.redraw()

        else:
            self.value = None
            self.redraw()

    def redraw(self, rects = None, deferRedraw = False):
        # if the layout needs recalcuating because its new, moved or changed size
        if self.renderedbox is None or self.renderedbox != self.rect:
            self.surface.fill(self.theme.colours.transparent)
            dynamicfontsize = self.theme.fontSysSizeOptimizeHeight(self.rect.height, 'freesans')
            self.dynamicfont = self.theme.fontLib.SysFont('freesans', dynamicfontsize) # font for value to be displayed
            self.renderedbox = self.rect.copy()
        # render a blank if it is not set
        if self.value is None or self.numericConfig is None:
            valuestr = ""
        else:
            magUnit = "k"
            valuestr = str(self.value)+magUnit+self.numericConfig.staticUnits
        if self.dynamicTextRect is not None :
            self.surface.fill(self.theme.colours.transparent, self.dynamicTextRect)
        dynamicTextSurface = self.theme.outlineFontRender(valuestr, self.dynamicfont, self.theme.colours.white, self.theme.colours.black, 1)
        self.dynamicTextRect = dynamicTextSurface.get_rect()
        self.dynamicTextRect.centery = self.rect.height/2
        self.dynamicTextRect.right = self.rect.width
        self.surface.blit(dynamicTextSurface, self.dynamicTextRect)
        super().redraw(rects, deferRedraw)

# module that displays the current frequency
class freq(numericDisplay):
    def __init__ (self, theme, drawCallback, rect):
        super().__init__(theme, drawCallback, rect)

    def updateVal(self, newval):
        self.numericConfig = newval.getSignalSourceMeta()
        super().updateVal(newval)

# module that displays the current symbol rate
class bw(numericDisplay):
    def __init__ (self, theme, drawCallback, rect):
        super().__init__(theme, drawCallback, rect)

    def updateVal(self, newval):
        self.numericConfig = newval.getSignalBandwidthMeta()
        super().updateVal(newval)
