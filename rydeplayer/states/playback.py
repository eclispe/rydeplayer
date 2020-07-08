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

import pydispmanx, pygame, enum

class States(enum.Enum):
    PLAYING = enum.auto()
    LOCKED = enum.auto()
    NOLOCK = enum.auto()
    NOLONGMYND = enum.auto()

# manager for full screen plyback state messages
class StateDisplay(object):
    def __init__(self, theme):
        self.theme = theme
        self.state = None
        # setup display layers for behind and infront of the video layer
        self.frontDispmanxlayer = pydispmanx.dispmanxLayer(2)
        self.backDispmanxlayer = pydispmanx.dispmanxLayer(0)
        self.frontSurface = pygame.image.frombuffer(self.frontDispmanxlayer, self.frontDispmanxlayer.size, 'RGBA')
        self.backSurface = pygame.image.frombuffer(self.backDispmanxlayer, self.backDispmanxlayer.size, 'RGBA')
        self.setState(States.NOLONGMYND)
        self.frontDispmanxlayer.updateLayer()
    
    # redraw a fullscreen display with a multiline message over it
    def drawMessage(self, displayText, surface):
        lineSurfaces = []
        # work out how wide the lines are and prep their surfaces
        maxLineWidth = 0;
        for line in displayText.split("\n"):
            lineSurface=self.theme.fonts.playStateTitle.render(line, True, self.theme.colours.black)
            maxLineWidth = max(maxLineWidth, lineSurface.get_width())
            lineSurfaces.append(lineSurface)
        textSurface = pygame.Surface((maxLineWidth, self.theme.fonts.playStateTitle.get_linesize()*len(lineSurfaces)), pygame.SRCALPHA)
        starty = 0;
        # draw the surfaces
        for lineSurface in lineSurfaces:
            linesurfacerect = lineSurface.get_rect()
            linesurfacerect.centerx = textSurface.get_width()/2
            linesurfacerect.top = starty
            starty += self.theme.fonts.playStateTitle.get_linesize()
            textSurface.blit(lineSurface, linesurfacerect)
        textsurfacerect = textSurface.get_rect()
        textsurfacerect.center=surface.get_rect().center
        surface.blit(textSurface, textsurfacerect)

    # update the state and redraw the message if required
    def setState(self, newState):
        if(newState != self.state):
            self.state = newState
            if(newState == States.LOCKED):
                self.backSurface.fill(self.theme.colours.backgroundPlayState)
                self.drawMessage("Locked\nNo Video", self.backSurface)
                self.backDispmanxlayer.updateLayer()
                self.frontSurface.fill(self.theme.colours.transparent)
            else:
                self.frontSurface.fill(self.theme.colours.backgroundPlayState)
                displayText = "ERROR\nNOT FOUND"
                if(newState == States.NOLONGMYND):
                    displayText = "LongMynd\nNot Loaded"
                elif(newState == States.NOLOCK):
                    displayText = "Not\nLocked"
                self.drawMessage(displayText, self.frontSurface)
            self.frontDispmanxlayer.updateLayer()
            return True
        else:
            return False

    def __del__(self):
        del(self.frontSurface)
        del(self.backSurface)
        del(self.frontDispmanxlayer)
        del(self.backDispmanxlayer)
