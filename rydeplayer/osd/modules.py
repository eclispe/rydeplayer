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
import rydeplayer.longmynd
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

# module that displays the current MER
class mer(generic):
    def __init__ (self, theme, drawCallback, rect):
        super().__init__(theme, drawCallback, rect)
        self.rect = rect.copy()
        self.renderedbox = None
        self.mer = None
        self.staticText = "dB MER" # static unit text
        self.staticTextSurface = None
        self.dynamicTextRect = None

    def updateVal(self, newval):
        self.mer = newval.getMer()
        self.redraw()

    def redraw(self, rects = None, deferRedraw = False):
        # if the layout needs recalcuating because its new, moved or changed size
        if(self.renderedbox is None or self.renderedbox != self.rect):
            self.surface.fill(self.theme.colours.transparent)
            meterbar = pygame.Rect((0,0),(self.rect.height*0.25, self.rect.height)) # placeholder space for a meter
            meterbar.right = self.rect.width
            textwidth = self.rect.width - meterbar.width # total width available for the text
            staticfontsize = self.theme.fontSysSizeOptimize(self.staticText, textwidth*0.8, 'freesans')
            staticfont = pygame.font.SysFont('freesans', staticfontsize) # font for the static unit text
            dynamicfontsize = self.theme.fontSysSizeOptimize("25.5", textwidth*0.8, 'freesans')
            self.dynamicfont = pygame.font.SysFont('freesans', dynamicfontsize) # font for the actual MER value
            textheight = staticfont.get_linesize() + self.dynamicfont.get_linesize()
            self.textbox = pygame.Rect((0,0), (textwidth, textheight))
            self.textbox.centery=self.rect.height/2 # center the box containing the text vertically in the bigger box
            self.staticTextSurface = self.theme.outlineFontRender(self.staticText, staticfont, self.theme.colours.white, self.theme.colours.black, 1)
            staticTextRect = self.staticTextSurface.get_rect()
            staticTextRect.bottom = self.textbox.bottom
            staticTextRect.centerx = self.textbox.centerx
            self.surface.blit(self.staticTextSurface, staticTextRect)
            self.renderedbox = self.rect.copy()
        # render the main MER value if it is set
        if(self.mer is not None):
            if(self.dynamicTextRect is not None):
                self.surface.fill(self.theme.colours.transparent, self.dynamicTextRect)
            dynamicTextSurface = self.theme.outlineFontRender(str(self.mer), self.dynamicfont, self.theme.colours.white, self.theme.colours.black, 1)
            self.dynamicTextRect = dynamicTextSurface.get_rect()
            self.dynamicTextRect.top = self.textbox.top
            self.dynamicTextRect.centerx = self.textbox.centerx
            self.surface.blit(dynamicTextSurface, self.dynamicTextRect)
        super().redraw(rects, deferRedraw)

# module that displays an icon when muted
class mute(generic):
    def __init__ (self, theme, drawCallback, rect):
        self.mute = False
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
        # track the current rendered value, to check for rerender
        self.renderedPresetName = ""
        self.renderedProvider = ""
        self.renderedService = ""
        self.presetNameRect = None
        self.providerRect = None
        self.serviceRect = None

    def updateVal(self, newval):
        if(isinstance(newval, rydeplayer.longmynd.tunerStatus)):
            self.provider = newval.getProvider()
            self.service = newval.getService()
        elif(isinstance(newval, str)):
            self.presetName = newval
        self.redraw()

    def redraw(self, rects = None, deferRedraw = False):
        drawAll = False
        if self.renderedbox is None or self.renderedbox != self.rect:
            drawAll = True
            self.surface.fill(self.theme.colours.backgroundMenu)
            contentbox = pygame.Rect((self.rect.height*0.1,self.rect.height*0.1),(self.rect.width-(self.rect.height*0.2), self.rect.height*0.8)) # main content box
            self.presetNameRect = pygame.Rect((contentbox.left+self.rect.height*0.1, contentbox.top),(contentbox.width-(self.rect.height*0.2), contentbox.height/3))
            self.providerRect = pygame.Rect((self.presetNameRect.x, self.presetNameRect.bottom),(self.presetNameRect.width, contentbox.height/3))
            self.serviceRect = pygame.Rect((self.providerRect.x, self.providerRect.bottom),(self.providerRect.width, contentbox.height/3))
            serviceDetailsBox = pygame.Rect((contentbox.x,self.providerRect.y),(contentbox.width, self.providerRect.height+self.serviceRect.height)) # main content box
            self.surface.fill(self.theme.colours.white, serviceDetailsBox)
            self.largeFont = pygame.font.SysFont('freesans', self.theme.fontSysSizeOptimizeHeight(contentbox.height/3, 'freesans')) # font for the large program details

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
            serviceTextRect.top = self.serviceRect.top;
            serviceTextRect.left = self.serviceRect.left
            self.surface.fill(self.theme.colours.white, self.serviceRect)
            self.surface.blit(serviceTextSurface, serviceTextRect, pygame.Rect((0,0),self.serviceRect.size))

        super().redraw(rects, deferRedraw)
