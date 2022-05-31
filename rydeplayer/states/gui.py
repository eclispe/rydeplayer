#    Ryde Player provides a on screen interface and video player for Longmynd compatible tuners.
#    Copyright © 2021 Tim Clark
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

import pygame, math, enum, pydispmanx, functools
from PIL import Image
from ..common import navEvent

# Basic parent state
class States(object):
    def __init__(self, theme):
        self.done = False
        self.next = None
        self.quit = False
        self.previous = None
        self.theme = theme
    def update(self):
        None

# State that has another state machine inside it
class SuperStates(States):
    def __init__(self, theme):
        super().__init__(theme)
    def flip_state(self):
        self.state.done = False
        previous,self.state_name = self.state_name, self.state.next
        self.state.cleanup()
        self.state = self.state_dict[self.state_name]
        self.state.startup()
        self.state.previous = previous
    def update(self):
        if self.state.done:
            self.flip_state()
        self.state.update()
    def get_event(self, event):
        self.state.get_event(event)
    def setStateStack(self, stateStack):
        newState = stateStack.pop()
        if self.state_name != newState:
            self.state.next = newState
            self.state.done = True
            self.update()
        if len(stateStack) > 0 and isinstance(self.state, SuperStates):
            self.state.setStateStack(stateStack)
    def cleanup(self):
        if(not self.done):
            self.state.cleanup()

# a state that contains a surface
class StatesSurface(States):
    def get_surface(self):
        return self.surface
    def getSurfaceRects(self):
        return [self.surfacerect]
    def getBlitPairs(self):
        return [(self.surface, self.surfacerect)]

# SuperState with surface support
class SuperStatesSurface(SuperStates, StatesSurface):
    def redrawState(self, state, rects):
        for rect in rects:
            self.surface.fill(self.theme.colours.backgroundSubMenu, rect)
        self.surface.blits(state.getBlitPairs())
    def update(self):
        oldstate = self.state
        if isinstance(oldstate, StatesSurface):
            oldrects = oldstate.getSurfaceRects()
        super().update()
        if isinstance(oldstate, StatesSurface):
            self.redrawState(oldstate, oldrects)
        if isinstance(self.state, StatesSurface):
            self.redrawState(self.state, self.state.getSurfaceRects())

# Basic menu item that draws and navigates but nothing else
class MenuItem(StatesSurface):
    def __init__(self, theme, label, up, down, select, validTrack = None):
        super().__init__(theme)
        self.next = None
        self.done = False
        self.label = label
        self.validTrack = validTrack
        boxheight = self.theme.fonts.menuH1.size(label)[1]
        self.surface = pygame.Surface((self.theme.menuWidth*0.8, boxheight), pygame.SRCALPHA)
        self.textSurface = self.drawText(label)
        self.backColour = self.theme.colours.transparent
        self.surface.fill(self.backColour)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        #right align the text in the highligh box
        self.textrect.right = self.surface.get_width()
        self.surface.blit(self.textSurface, self.textrect)
        self.surfacerect = self.surface.get_rect()
        self.up = up
        self.down = down
        #what do do when it is "selected"
        self.select = select
        if validTrack is not None:
            validTrack.addValidCallback(self.redrawText)
    def drawText(self, label):
        textColour = self.theme.colours.black
        if not (self.validTrack is None or self.validTrack.isValid()):
            textColour = self.theme.colours.textError
        return self.theme.fonts.menuH1.render(label, True, textColour)
    def redraw(self):
        self.surface.fill(self.backColour)
        self.surface.blit(self.textSurface, self.textrect)
    def redrawText(self):
        self.textSurface = self.drawText(self.label)
        self.redraw()
    def cleanup(self):
        # repaint with transparent background
        self.backColour = self.theme.colours.transparent
        self.redraw()
    def startup(self):
        # repaint with highlighted background
        self.backColour = self.theme.colours.transpBack
        self.redraw()

    def get_event(self, event):
        if( event == navEvent.UP):
            if(self.up != None):
                self.next=self.up
                self.done=True
                return True
        elif( event == navEvent.DOWN):
            if(self.down != None):
                self.next=self.down
                self.done=True
                return True
        elif( event == navEvent.RIGHT or event == navEvent.SELECT):
            if(self.select != None):
                self.next=self.select
                self.done=True
                return True
        return False

# A basic menu item for submenus
class SubMenuItem(StatesSurface):
    def __init__(self, theme, label, up, down, select, validTrack = None):
        super().__init__(theme)
        self.next = None
        self.done = False
        self.label = label
        self.validTrack = validTrack
        self.up = up
        self.down = down
        # draw the surface
        boxheight = self.theme.fonts.menuH1.size(label)[1]
        boxminwidth = self.theme.fonts.menuH1.size(label)[0] + self.theme.menuWidth*0.2

        self.textSurface = self.drawText(label)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = boxheight/2
        self.textrect.left = self.theme.menuWidth*0.1
        self.backColour = self.theme.colours.transparent
        self.surface = pygame.Surface((boxminwidth, boxheight), pygame.SRCALPHA)
        self.surface.fill(self.backColour)
        self.surface.blit(self.textSurface, self.textrect)
        self.surfacerect = self.surface.get_rect()
        self.select = select
        if validTrack is not None:
            validTrack.addValidCallback(self.redrawText)
    def drawText(self, label):
        textColour = self.theme.colours.black
        if not (self.validTrack is None or self.validTrack.isValid()):
            textColour = self.theme.colours.textError
        return self.theme.fonts.menuH1.render(label, True, textColour)
    def redraw(self):
        self.surface.fill(self.backColour)
        self.surface.blit(self.textSurface, self.textrect)
    def redrawText(self):
        self.textSurface = self.drawText(self.label)
        self.redraw()
    def cleanup(self):
        self.backColour = self.theme.colours.transparent
        self.redraw()
    def startup(self):
        self.backColour = self.theme.colours.transpBack
        self.redraw()
    def get_event(self, event):
        if( event == navEvent.UP):
            if(self.up != None):
                self.next=self.up
                self.done=True
                return True
        elif( event == navEvent.DOWN):
            if(self.down != None):
                self.next=self.down
                self.done=True
                return True
        elif( event == navEvent.RIGHT or event == navEvent.SELECT):
            if(self.select != None):
                self.next=self.select
                self.done=True
                return True
        return False

# generic sub menu parent
class SubMenuGeneric(SuperStatesSurface):
    def __init__(self, theme, backState, state_dict, initstate):
        super().__init__(theme)
        # where to go back to
        self.next = backState
        self.top = 0
        self.left = 0
        self.done = False
        self.state_dict = state_dict
        self.initstate = initstate

    def cleanup(self):
        super().cleanup()
        self.surface.fill(self.theme.colours.transparent)

    def buildStates(self):
        # top of the first item
        boxheight = self.theme.menuHeight*0.01
        maxitemwidth = 0
        for menuState in self.state_dict.values():
            if(isinstance(menuState, SubMenuItem)):
                surfacewidth = menuState.get_surface().get_width()
                maxitemwidth = max(maxitemwidth, surfacewidth)
                rowheight = menuState.get_surface().get_height() + self.theme.menuHeight*0.01
                boxheight += rowheight
        boxwidth = maxitemwidth
        itemleft = self.left + boxwidth
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.surface.fill(self.theme.colours.backgroundMenu)
        self.surfacerect = self.surface.get_rect()
        self.surfacerect.top = self.top
        self.surfacerect.left = self.left
        drawnext = self.theme.menuHeight*0.01
        self.state_name = self.initstate
        return (drawnext, itemleft)

    def startup(self):
        (drawnext, itemleft) = self.buildStates()
        # align the menu items and sub items
        self.state = self.state_dict[self.state_name]
        for menuState in self.state_dict.values():
            if(isinstance(menuState, CharSeqSelect)):
                menuState.top = drawnext+self.top
                menuState.left = itemleft
            elif(isinstance(menuState, ListSelect)):
                menuState.surfacerect.top = drawnext+self.top
                menuState.surfacerect.left = itemleft
            elif(isinstance(menuState, SubMenuItem)):
                menuState.surfacerect.top = drawnext
                menuState.surfacerect.left = 0
                drawnext = menuState.surfacerect.bottom + self.theme.menuHeight*0.01
                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
        self.state.startup()

    def getSurfaceRects(self):
        # if its a sub menu return the rectangles for it to the p:arent for painting
        if(isinstance(self.state, ListSelect) or isinstance(self.state, CharSeqSelect) or  isinstance(self.state, SubMenuGeneric)):
            rectlist = [self.surfacerect]
            rectlist.extend(self.state.getSurfaceRects())
            return rectlist
        else:
            return [self.surfacerect]

    def getBlitPairs(self):
        # if its a sub menu return the surfaces directly to the parent for bliting
        if(isinstance(self.state, ListSelect) or isinstance(self.state, CharSeqSelect) or  isinstance(self.state, SubMenuGeneric)):
            pairlist = [(self.surface, self.surfacerect)]
            pairlist.extend(self.state.getBlitPairs())
            return pairlist
        else:
            return [(self.surface, self.surfacerect)]

    def redrawState(self, state, rects):
        # if its not a sub menu draw it onto the local surface
        if not (isinstance(self.state, ListSelect) or isinstance(self.state, CharSeqSelect) or isinstance(self.state, SubMenuGeneric)):
            super().redrawState(state, rects)

    def get_event(self, event):
        if self.state.get_event(event):
            return True
        else:
            if event == navEvent.BACK or event == navEvent.LEFT:
                self.done = True
                return True
            else:
                return False

# Simple menu item that executes a callback function when it is "selected"
class MenuItemFunction(MenuItem):
    def get_event(self, event):
        if( event == navEvent.UP):
            if(self.up != None):
                self.next=self.up
                self.done=True
                return True
        elif( event == navEvent.DOWN):
            if(self.down != None):
                self.next=self.down
                self.done=True
                return True
        elif( event == navEvent.SELECT):
            if(self.select != None):
                self.select()
                return True
        return False

# Simple menu item that executes a callback function when it is "selected"
class SubMenuItemFunction(SubMenuItem):
    def get_event(self, event):
        if( event == navEvent.UP):
            if(self.up != None):
                self.next=self.up
                self.done=True
                return True
        elif( event == navEvent.DOWN):
            if(self.down != None):
                self.next=self.down
                self.done=True
                return True
        elif( event == navEvent.SELECT):
            if(self.select != None):
                self.select()
                return True
        return False

# The submenu items for a ListSelect
class ListSelectItem(StatesSurface):
    def __init__(self, theme, label, up, down, boxwidth):
        super().__init__(theme)
        self.next = None
        self.done = False
        self.label = label
        self.up = up
        self.down = down
        # draw the surface
        boxheight = self.theme.fonts.menuH1.size(label)[1]
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.textSurface = self.theme.fonts.menuH1.render(label, True, self.theme.colours.black)
        self.surface.fill(self.theme.colours.transparent)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        self.textrect.left = self.theme.menuWidth*0.1
        self.surface.blit(self.textSurface, self.textrect)
        self.surfacerect = self.surface.get_rect()
    def cleanup(self):
        self.surface.fill(self.theme.colours.transparent)
        self.surface.blit(self.textSurface, self.textrect)
    def startup(self):
        self.surface.fill(self.theme.colours.transpBack)
        self.surface.blit(self.textSurface, self.textrect)
    def get_event(self, event):
        if( event == navEvent.UP):
            if(self.up != None):
                self.next=self.up
                self.done=True
                return True
        elif( event == navEvent.DOWN):
            if(self.down != None):
                self.next=self.down
                self.done=True
                return True
        return False

# ListSelect item which doesn't draw
class ListSelectItemNone(States):
    def __init__(self, theme, up, down):
        super().__init__(theme)
        self.next = None
        self.done = False
        self.up = up
        self.down = down
    def cleanup(self):
        None
    def startup(self):
        None
    def get_event(self, event):
        if( event == navEvent.UP):
            if(self.up != None):
                self.next=self.up
                self.done=True
                return True
        elif( event == navEvent.DOWN):
            if(self.down != None):
                self.next=self.down
                self.done=True
                return True
        return False

# a submenu that allows presents a list of options to be selected and runs a callback when the selection is updated
class ListSelect(SuperStatesSurface):
    def __init__(self, theme, backState, items, currentValueFunction, updateCallback):
        super().__init__(theme)
        # where to go back to
        self.next = backState
        # dictionary of key:displaytext pairs
        self.items = items
        self.currentValueFunction = currentValueFunction
        self.done = False
        # callback to execute on completion
        self.updateCallback = updateCallback
        # work out what size all the list items have to be before creating them
        maxitemwidth = 0
        boxheight = self.theme.menuHeight*0.01
        for label in self.items.values():
            maxitemwidth = max(maxitemwidth,self.theme.fonts.menuH1.size(label)[0])
            rowheight = self.theme.fonts.menuH1.size(label)[1] + self.theme.menuHeight*0.01
            boxheight += rowheight
        boxwidth = maxitemwidth + self.theme.menuWidth*0.2
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.surface.fill(self.theme.colours.transparent)
        self.surfacerect = self.surface.get_rect()
        # create the menu items
        self.state_dict = {}
        itemkeys = list(self.items.keys())
        if len(itemkeys)<1:
            self.state_dict[None] = ListSelectItemNone(self.theme, None, None)
        else:
            self.state_dict[None] = ListSelectItemNone(self.theme, itemkeys[-1], itemkeys[0])
        for n in range(len(itemkeys)):
            key = itemkeys[n]
            value = self.items[key]
            prevkey = itemkeys[n-1]
            nextkey = itemkeys[(n+1)%len(itemkeys)]
            self.state_dict[key] = ListSelectItem(self.theme, value, prevkey, nextkey, boxwidth)
        initialvalue = self.currentValueFunction()
        if initialvalue not in itemkeys:
            initialvalue = None
        self.state_name = initialvalue
    def cleanup(self):
        super().cleanup()
        self.surface.fill(self.theme.colours.transparent)
    def startup(self, startValue = (False,None)):
        if startValue[0]:
            initialvalue = startValue[1]
        else:
            initialvalue = self.currentValueFunction()
        if initialvalue not in self.items:
            initialvalue = None
        self.state_name = initialvalue
        self.surface.fill(self.theme.colours.backgroundSubMenu)
        self.state = self.state_dict[self.state_name]
        
        # draw all the items
        drawnext = self.theme.menuHeight*0.01
        for menuState in self.state_dict.values():
            if isinstance(menuState, ListSelectItem):
                menuState.surfacerect.top = drawnext
                menuState.surfacerect.left = 0
                drawnext = menuState.surfacerect.bottom + self.theme.menuHeight*0.01
                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
        # start the default state
        self.state.startup()
        if isinstance(self.state, ListSelectItem):
            self.surface.blit(self.state.get_surface(), self.state.surfacerect)
    def get_event(self, event):
        if(not self.state.get_event(event)):
            if(event == navEvent.BACK or event == navEvent.LEFT):
                self.done = True
                return True
            if(event == navEvent.SELECT):
#                self.currentValue = self.state_name
                if(isinstance(self.state, ListSelectItem)):
                    if(self.updateCallback is not None):
                        self.updateCallback(self.state_name)
                self.done = True
                return True
        return False

# single character selector for a larger string
class CharacterSelect(StatesSurface):
    def __init__(self, theme, left, right, currentValue, chars, directEventMapFunc, errorHighlight):
        super().__init__(theme)
        self.active = False
        self.next = None
        self.done = False
        self.right = right
        self.left = left
        self.chardict = chars
        self.charlist = list(chars.keys())
        self.directEventMapFunc = directEventMapFunc
        # what is the largest char in this font, make the box that big
        boxheight = self.theme.fonts.menuH1.size("".join(chars.values()))[1] + self.theme.menuHeight*0.01
        maxdigitwidth = 0
        for n in self.chardict:
            maxdigitwidth = max(maxdigitwidth,self.theme.fonts.menuH1.size(self.chardict[n])[0])
        boxwidth = maxdigitwidth + self.theme.menuWidth*0.02
        # actual drawing
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        if currentValue in self.chardict:
            self.textSurface = self.theme.fonts.menuH1.render(self.chardict[currentValue], True, self.theme.colours.black)
        else:
            self.textSurface = self.theme.errCharSurface.copy()
        self.surface.fill(self.theme.colours.transparent)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        self.textrect.centerx = self.surface.get_width()/2
        self.surface.blit(self.textSurface, self.textrect)
        self.surfacerect = self.surface.get_rect()
        self.currentValue = currentValue
        self.errorHighlight = errorHighlight
    def cleanup(self):
        self.surface.fill(self.theme.colours.transparent)
        self.surface.blit(self.textSurface, self.textrect)
        self.active = False
    def startup(self):
        self.surface.fill(self.theme.colours.transpBack)
        self.surface.blit(self.textSurface, self.textrect)
        self.drawDigit()
        self.active = True
    def get_event(self, event):
        if event == navEvent.UP:
            if self.currentValue == self.charlist[-1] or self.currentValue is None:
                self.currentValue = self.charlist[0]
            else:
                self.currentValue = self.charlist[self.charlist.index((self.currentValue))+1]
            return True
        elif event == navEvent.DOWN:
            if self.currentValue == self.charlist[0] or self.currentValue is None:
                self.currentValue = self.charlist[-1]
            else:
                self.currentValue = self.charlist[self.charlist.index((self.currentValue))-1]
            return True
        elif event == navEvent.LEFT:
            if(self.left != None):
                self.next=self.left
                self.done=True
                return True
        elif event == navEvent.RIGHT:
            if self.right != None:
                self.next=self.right
                self.done=True
                return True
        else:
            # handle direct char input
            canHandle, newVal = self.directEventMapFunc(event)
            if canHandle and newVal not in self.charlist:
                return True
            elif canHandle:
                self.currentValue = newVal
                self.drawDigit()
                if(self.right != None):
                    self.next=self.right
                    self.done=True
                return True
            else:
                return False
        return False
    def setValue(self, newValue):
        self.currentValue = newValue
    def setErrorHighlight(self, newValue):
        if newValue != self.errorHighlight:
            self.errorHighlight = newValue
            self.update()
            return True
        else:
            return False

    def drawDigit(self):
        textColour = self.theme.colours.black
        if self.errorHighlight:
            textColour = self.theme.colours.textError
        if self.currentValue in self.chardict:
            self.textSurface = self.theme.fonts.menuH1.render(self.chardict[self.currentValue], True, self.theme.colours.black)
        else:
            self.textSurface = self.theme.errCharSurface.copy()
        if self.active:
            self.surface.fill(self.theme.colours.transpBack)
        else:
            self.surface.fill(self.theme.colours.transparent)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        self.textrect.centerx = self.surface.get_width()/2
        self.surface.blit(self.textSurface, self.textrect)
    def update(self):
        super().update()
        self.drawDigit()

# sub menu for inputing generic character sequences and pass new value to callback when done
class CharSeqSelect(SuperStatesSurface):
    def __init__(self, theme, backState, valueConfig, updateCallback):
        super().__init__(theme)
        self.valueConfig = valueConfig
        # where to go back to
        self.suffix = ""
        self.next = backState
        self.top = 0
        self.left = 0

        self.done = False
        self.updateCallback = updateCallback
    def cleanup(self):
        super().cleanup()
        # reset back to the first digit if we close the menu
        self.state_name = '0'
        self.surface.fill(self.theme.colours.transparent)
    def startup(self):
        self.currentValue = self.valueConfig.getValue()
        self._updateValid(self.currentValue)
        # how big a box do we need
        boxwidth = int(self.theme.menuWidth*0.1)
        boxheight = self.theme.fonts.menuH1.size("".join(self.charset)+self.suffix)[1]
        # setup the state machine and create the digit states
        self.state_dict = {}
        for n in range(self.charCount):
            key = n
            prevkey = str((n-1)%self.charCount)
            nextkey = str((n+1)%self.charCount)
            self.state_dict[str(key)] = CharacterSelect(self.theme, prevkey, nextkey, self._charValueFromIndex(n), self._charmapFromIndex(n), self._mapEventToCharKey, not self.validValue)

            boxwidth += self.state_dict[str(key)].surface.get_width() + self.theme.menuWidth*0.01
        boxwidth += self.theme.fonts.menuH1.size(self.suffix)[0]
        # create and setup the surface
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.surface.fill(self.theme.colours.transparent)
        self.surfacerect = self.surface.get_rect()

        self.textSurface = self.theme.fonts.menuH1.render(self.suffix, True, self.theme.colours.black)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        self.textrect.right = self.surfacerect.right-self.theme.menuWidth*0.05
        self.surfacerect.top = self.top
        self.surfacerect.left = self.left
        # select the first character, there should always be at least one
        self.state_name = '0'
        self.surface.fill(self.theme.colours.backgroundSubMenu)
        self.surface.blit(self.textSurface, self.textrect)
        self.state = self.state_dict[self.state_name]
        # draw all the characters
        drawnext = self.theme.menuWidth*0.05
        for n in range(self.charCount):
            digitState = self.state_dict[str(n)]
            digitState.surfacerect.left = drawnext
            digitState.surfacerect.centery = self.surface.get_height()/2
            drawnext = digitState.surfacerect.right + self.theme.menuWidth*0.01
            digitState.setValue(self._charValueFromIndex(n))
            digitState.update()
            self.surface.blit(digitState.get_surface(), digitState.surfacerect)
        self.state.startup()
        self.surface.blit(self.state.get_surface(), self.state.surfacerect)
    def get_event(self, event):
        handeled = self.state.get_event(event)
        newValue = self._getValue()
        self._updateValid(newValue)
        for char in self.state_dict.values():
            if char.setErrorHighlight(not self.validValue):
                self.surface.fill(self.theme.colours.backgroundSubMenu, char.surfacerect)
                self.surface.blit(char.get_surface(), char.surfacerect)
        if not handeled:
            if event == navEvent.BACK:
                self.done = True
                return True
            if event == navEvent.SELECT :
                if self.currentValue != newValue:
                    self.currentValue = newValue
                    self.valueConfig.setValue(newValue)
                    if self.updateCallback is not None:
                        self.updateCallback()
                self.done = True
                return True
        else:
            return True
        return False

# sub menu for inputing whole numbers and pass new value to callback when done
class NumberSelect(CharSeqSelect):
    def __init__(self, theme, backState, valueConfig, updateCallback):
        super().__init__(theme, backState, valueConfig, updateCallback)
        # how many digits do we need to allow the max number to be put in
        self.charCount = len(str(max(self.valueConfig.getMaxValue(), self.valueConfig.getValue())))
        self.suffix = self.valueConfig.getUnits()
        self.charset = [str(x) for x in range(0,10)]

    def _mapEventToCharKey(self, event):
        if event.isNumeric():
            return (True, event.numericValue)
        else:
            return (False, None)

    def _getValue(self):
        newValue = 0
        for n in range(self.charCount):
            digitState = self.state_dict[str(n)]
            newValue += digitState.currentValue*pow(10,self.charCount-n-1)
        return newValue


    def _updateValid(self, newValue):
        self.validValue =  newValue >= self.valueConfig.getMinValue() and newValue <= self.valueConfig.getMaxValue()

    def _charValueFromIndex(self, n):
        # what is the current value of this digit from the whole number
        return math.floor((self.currentValue%pow(10,self.charCount-n))/pow(10, self.charCount-n-1))

    def _charmapFromIndex(self, n):
        # what is the biggest this digit could be based on its position and the max number
        maxDigit = math.floor(self.valueConfig.getMaxValue()/pow(10,self.charCount-n-1))
        if(maxDigit > 9):
            maxDigit = 9
        # name the state after its position
        chars={}
        for n in range(0, maxDigit+1):
            chars[n]=str(n)
        return chars

    def startup(self):
        # how many digits do we need to allow the max number to be put in
        self.charCount = len(str(max(self.valueConfig.getMaxValue(), self.valueConfig.getValue())))
        super().startup()

# sub menu for inputing strings and pass new value to callback when done
class StringSelect(CharSeqSelect):
    def __init__(self, theme, backState, valueConfig, updateCallback):
        super().__init__(theme, backState, valueConfig, updateCallback)
        # how many chars do we need
        self.charCount = max(self.valueConfig.getMaxLen(), len(self.valueConfig.getValue()))
        self.charset = self.valueConfig.getValidChars()

    def _mapEventToCharKey(self, event):
        return (False, None)

    def _getValue(self):
        newValue = ""
        for n in range(self.charCount):
            charState = self.state_dict[str(n)]
            if charState.currentValue is None:
                newValue += self.currentValue[n]
            else:
                newValue += charState.currentValue
        return newValue.strip()

    def _updateValid(self, newValue):
        self.validValue = len(newValue)>0 or self.valueConfig.getAllowBlank()

    def _charValueFromIndex(self, n):
        if n < len(self.currentValue):
            if self.currentValue[n] in self.charset:
                print(self.currentValue[n])
                return self.currentValue[n]
            else:
                return None
        else:
            return " "

    def _charmapFromIndex(self, n):
        return {x:x for x in self.charset}

    def startup(self):
        # how many chars do we need
        self.charCount = max(self.valueConfig.getMaxLen(), len(self.valueConfig.getValue()))
        super().startup()

# sub menu for inputing multiple whole numbers and execute a callback when done
class MultipleNumberSelect(SubMenuGeneric):
    def __init__(self, theme, backState, valueConfig, updateCallback):
        super().__init__(theme, backState, {}, '')
        self.valueConfig = valueConfig
        self.updateCallback = updateCallback
        self.typetext = self.valueConfig.getShortName()

    def cleanup(self):
        super().cleanup()
        if self.valueConfig.single:
            self.state_name = self.valueConfig[0]
        else:
            self.state_name = ("menu", self.valueConfig[0])

    def buildStates(self):
        if self.valueConfig.single:
            # load the number selector with no interim menu
            self.state_dict={self.valueConfig[0]: NumberSelect(self.theme, None, self.valueConfig[0], self.updateCallback)}
            itemleft = self.left
            self.state_name = self.valueConfig[0]
            self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
            self.surface.fill(self.theme.colours.transparent)
            self.surfacerect = self.surface.get_rect()
            self.surfacerect.top = self.top
            self.surfacerect.left = self.left
            drawnext = 0
            return (drawnext, itemleft)
        else:
            # build the menu for of values
            self.state_dict={}
            self.state_name = None
            valueCounter = 0
            prevState = None
            # setup edit buttons
            for thisVal in self.valueConfig:
                menuHeadingKey = (thisVal, 'menu')
                menuItemKey = (thisVal, 'item')
                if self.state_name is None:
                    self.state_name = menuHeadingKey
                    prevState = menuHeadingKey
                menuItem = NumberSelect(self.theme, menuHeadingKey, thisVal, self.updateCallback)
                menuHeading = SubMenuItem(self.theme, self.typetext+" "+str(valueCounter), prevState, self.state_name, menuItemKey, thisVal)
                self.state_dict[menuItemKey] = menuItem
                self.state_dict[menuHeadingKey] = menuHeading
                self.state_dict[prevState].down = menuHeadingKey
                self.state_dict[self.state_name].up = menuHeadingKey
                prevState = menuHeadingKey
                valueCounter += 1
            # setup add button
            newValuePlaceholder = self.valueConfig[0].copyConfig()
            self.state_dict[('new', 'item')] = NumberSelect(self.theme, ('new', 'menu'), newValuePlaceholder, functools.partial(self.addValue, newValuePlaceholder))
            self.state_dict[('new', 'menu')] = SubMenuItem(self.theme, "New "+self.typetext, prevState, self.state_name, ('new', 'item'), None)
            self.state_dict[prevState].down = ('new', 'menu')
            # setup delete button
            if len(self.valueConfig) > 1:
                valDict = {}
                for n in range(len(self.valueConfig)):
                    valDict[n] = self.typetext+" "+str(n)+": "+ str(self.valueConfig[n].getValue())+self.valueConfig[n].getUnits()
                self.state_dict[('del', 'item')] = ListSelect(self.theme, ('del', 'menu'), valDict, lambda:0 , self.deleteValue) 
                self.state_dict[('del', 'menu')] = SubMenuItem(self.theme, "Delete "+self.typetext, ('new', 'menu'), self.state_name, ('del', 'item'), None)
                self.state_dict[self.state_name].up = ('del', 'menu')
                self.state_dict[('new', 'menu')].down = ('del', 'menu')
            else:
                self.state_dict[self.state_name].up = ('new', 'menu')
            self.initstate = self.state_name
            return super().buildStates()

    def addValue(self, newValueConfig):
        self.valueConfig.append(newValueConfig.getValue())
        self.updateCallback()
        self.done = True

    def deleteValue(self, deleteIndex):
        del(self.valueConfig[deleteIndex])
        self.updateCallback()
        self.done = True

    def get_event(self, event):
        if self.state.get_event(event):
            # when exiting single mode also close this
            if self.state.done and self.valueConfig.single:
                self.done=True
                self.state.done=False
            return True
        else:
            if event == navEvent.BACK or event == navEvent.LEFT:
                self.done = True
                return True
            else:
                return False

# overlay a manu on the screen
class Menu(SuperStatesSurface):
    def __init__(self, theme, nextstate, stateDictGenFunc):
        super().__init__(theme)
        self.next = nextstate
        self.done = False
        self.stateDictGenFunc = stateDictGenFunc
        self.state_dict = {}
        self.cleanupFunc = None
        # import and resize the logo
        eps = Image.open(theme.logofile)
        origwidth, origheight = eps.size
        scale = theme.menuWidth/float(origwidth)*0.8
        newheight = int(round(origheight*scale))
        newwidth  = int(round(origwidth*scale))
        eps = eps.resize((newwidth,newheight), Image.ANTIALIAS)
        epsstr = eps.tobytes("raw", "RGBA")
        self.logosurface = pygame.image.fromstring(epsstr, eps.size, "RGBA")
        self.surface = None
        self.dispmanxlayer = None
        self.statesTop = 0

    def cleanup(self):
        super().cleanup()
        if self.cleanupFunc is not None:
            self.cleanupFunc()
        self.surface = None
        self.dispmanxlayer = None

    def startup(self):
        self.state_dict, initstate, self.cleanupFunc=self.stateDictGenFunc(self)
        # open and connect the display
        self.dispmanxlayer = pydispmanx.dispmanxLayer(4)
        self.surface = pygame.image.frombuffer(self.dispmanxlayer, self.dispmanxlayer.size, 'RGBA')
        boxwidth = self.theme.menuWidth
        pygame.draw.rect(self.surface, self.theme.colours.backgroundMenu, [(0,0), (boxwidth ,self.surface.get_height())])
        # draw the logo
        logosurfacerect = self.logosurface.get_rect()
        logosurfacerect.center = (boxwidth/2, (self.logosurface.get_height()/2)+(self.theme.menuHeight*0.02))
        self.surface.blit(self.logosurface, logosurfacerect)
        self.dispmanxlayer.updateLayer()
        # set the initial substate
        self.state_name = initstate
        self.statesTop = logosurfacerect.bottom + self.theme.menuHeight*0.01
        self._drawMenu_()
        self.state.startup()
        if(isinstance(self.state, MenuItem)):
            self.surface.blit(self.state.get_surface(), self.state.surfacerect)
        self.dispmanxlayer.updateLayer()

    def _drawMenu_(self):
        self.state = self.state_dict[self.state_name]
        drawnext = self.statesTop
        # draw all the states
        #TODO: auto sort so input dict isnt order sensitive
        for menuState in self.state_dict.values():
            if(isinstance(menuState, ListSelect)):
                menuState.surfacerect.top = drawnext
                menuState.surfacerect.left = self.theme.menuWidth
                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
            elif(isinstance(menuState, CharSeqSelect) or isinstance(menuState, SubMenuGeneric)):
                menuState.top = drawnext
                menuState.left = self.theme.menuWidth
                print((drawnext, self.theme.menuWidth))
#                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
            elif(isinstance(menuState, MenuItem)):
                menuState.surfacerect.top = drawnext
                menuState.surfacerect.right = self.theme.menuWidth*0.9
                drawnext = menuState.surfacerect.bottom + self.theme.menuHeight*0.01
                self.surface.blit(menuState.get_surface(), menuState.surfacerect)

    def get_event(self, event):
        # Always handle this event
        if(event == navEvent.MENU):
            self.done = True
        # check to see if anyting else handled these events already
        elif(not self.state.get_event(event)):
            if(event == navEvent.BACK):
                self.done = True

    def redrawState(self, state, rects):
        if self.surface is not None:
            for rect in rects:
                if(isinstance(state, MenuItem)):
                    self.surface.fill(self.theme.colours.backgroundSubMenu, rect)
                elif(isinstance(state, ListSelect) or isinstance(state, CharSeqSelect) or isinstance(state, SubMenuGeneric)):
                    self.surface.fill(self.theme.colours.transparent, rect)
            self.surface.blits(state.getBlitPairs())

    def refreshStates(self, passedVar):
        # shutdown current state if there is no support to maintain its internal state, should end up at a supported state
        if not (isinstance(self.state, ListSelect) or isinstance(self.state, MenuItem)):
            self.state.done = True
            self.update()
        # where to try and go back to after update
        returnToStateName = self.state_name
        returnToStateType = self.state.__class__
        returnToStateValue = None
        if isinstance(self.state, ListSelect):
            returnToStateValue = self.state.state_name
        # cleanup current state manually
        self.state.cleanup()
        if isinstance(self.state, StatesSurface):
            self.redrawState(self.state, self.state.getSurfaceRects())
        if self.cleanupFunc is not None:
            self.cleanupFunc()
        # paint out all top level menu states
        for menuState in self.state_dict.values():
            if(isinstance(menuState, MenuItem)):
                for rect in menuState.getSurfaceRects():
                    self.surface.fill(self.theme.colours.backgroundSubMenu, rect)
        # create new states
        self.state_dict, initstate, self.cleanupFunc=self.stateDictGenFunc(self)
        # try and return to previous state
        if returnToStateName in self.state_dict and isinstance(self.state_dict[returnToStateName], returnToStateType):
            self.state_name = returnToStateName
        else:
            self.state_name = initstate
        self._drawMenu_()
        # try and recover previous state value
        if isinstance(self.state, ListSelect):
            self.state.startup((True,returnToStateValue))
        else:
            self.state.startup()
        self.surface.blit(self.state.get_surface(), self.state.surfacerect)
        self.dispmanxlayer.updateLayer()

    def update(self):
        super().update()
        self.dispmanxlayer.updateLayer()
