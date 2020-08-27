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
    def __init__(self, theme, label, up, down, select, boxwidth, validTrack = None):
        super().__init__(theme)
        self.next = None
        self.done = False
        self.label = label
        self.validTrack = validTrack
        self.up = up
        self.down = down
        # draw the surface
        boxheight = self.theme.fonts.menuH1.size(label)[1]
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.textSurface = self.drawText(label)

        self.backColour = self.theme.colours.transparent
        self.surface.fill(self.backColour)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        self.textrect.left = self.theme.menuWidth*0.1
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
    def startup(self):
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

# single digit selector for a larger number
class DigitSelect(StatesSurface):
    def __init__(self, theme, left, right, currentValue, maxValue, minValue, errorHighlight):
        super().__init__(theme)
        self.active = False
        self.next = None
        self.done = False
        self.minValue = minValue
        self.maxValue = maxValue
        self.right = right
        self.left = left
        # what is the largest digit in this font, make the box that big
        boxheight = self.theme.fonts.menuH1.size("0123456789")[1] + self.theme.menuHeight*0.01
        maxdigitwidth = 0
        for n in range(minValue, maxValue+1):
            maxdigitwidth = max(maxdigitwidth,self.theme.fonts.menuH1.size(str(n))[0])
        boxwidth = maxdigitwidth + self.theme.menuWidth*0.02
        # actual drawing
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.textSurface = self.theme.fonts.menuH1.render(str(currentValue), True, self.theme.colours.black)
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
        if( event == navEvent.UP):
            if(self.currentValue >= self.maxValue):
                self.currentValue = self.minValue
            else:
                self.currentValue += 1 
            return True
        elif( event == navEvent.DOWN):
            if(self.currentValue <= self.minValue):
                self.currentValue = self.maxValue
            else:
                self.currentValue -= 1 
            return True
        elif( event == navEvent.LEFT):
            if(self.left != None):
                self.next=self.left
                self.done=True
                return True
        elif( event == navEvent.RIGHT):
            if(self.right != None):
                self.next=self.right
                self.done=True
                return True
        elif( event.isNumeric() ):
            # handle direct digit input
            intevent = event.numericValue
            if(intevent < self.minValue or intevent > self.maxValue):
                return True
            else:
                self.currentValue = intevent
                self.drawDigit()
                if(self.right != None):
                    self.next=self.right
                    self.done=True
                return True
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
        self.textSurface = self.theme.fonts.menuH1.render(str(self.currentValue), True, textColour)
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

# sub menu for inputing whole numbers and pass new value to callback when done
class NumberSelect(SuperStatesSurface):
    def __init__(self, theme, backState, unittext, valueConfig, updateCallback):
        super().__init__(theme)
        # where to go back to
        self.next = backState
        self.valueConfig = valueConfig
        # how many digits do we need to allow the max number to be put in
        self.digitCount = len(str(max(self.valueConfig.getMaxValue(), self.valueConfig.getValue())))
        self.top = 0
        self.left = 0

        self.done = False
        self.updateCallback = updateCallback
        self.unittext = unittext
    def cleanup(self):
        super().cleanup()
        # reset back to the first digit if we close the menu
        self.state_name = '0'
        self.surface.fill(self.theme.colours.transparent)
    def startup(self):
        # how many digits do we need to allow the max number to be put in
        self.digitCount = len(str(max(self.valueConfig.getMaxValue(), self.valueConfig.getValue())))
        self.currentValue = self.valueConfig.getValue()
        self.maxValue = self.valueConfig.getMaxValue()
        self.minValue = self.valueConfig.getMinValue()
        self.inRange =  self.currentValue >= self.minValue and self.currentValue <= self.maxValue
        # how big a box do we need
        boxwidth = int(self.theme.menuWidth*0.1)
        boxheight = self.theme.fonts.menuH1.size("0123456789"+self.unittext)[1]
        # setup the state machine and create the digit states
        self.state_dict = {}
        for n in range(self.digitCount):
            key = n
            prevkey = str((n-1)%self.digitCount)
            nextkey = str((n+1)%self.digitCount)
            # what is the current value of this digit from the whole number
            currentDigit = math.floor((self.currentValue%pow(10,self.digitCount-n))/pow(10, self.digitCount-n-1))
            # what is the biggest this digit could be based on its position and the max number
            maxDigit = math.floor(self.maxValue/pow(10,self.digitCount-n-1))
            if(maxDigit > 9):
                maxDigit = 9
            # name the state after its position
            self.state_dict[str(key)] = DigitSelect(self.theme, prevkey, nextkey, currentDigit, maxDigit, 0, not self.inRange)
            boxwidth += self.state_dict[str(key)].surface.get_width() + self.theme.menuWidth*0.01
        boxwidth += self.theme.fonts.menuH1.size(self.unittext)[0]
        # create and setup the surface
        self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
        self.surface.fill(self.theme.colours.transparent)
        self.surfacerect = self.surface.get_rect()

        self.textSurface = self.theme.fonts.menuH1.render(self.unittext, True, self.theme.colours.black)
        self.textrect = self.textSurface.get_rect()
        self.textrect.centery = self.surface.get_height()/2
        self.textrect.right = self.surfacerect.right-self.theme.menuWidth*0.05
        self.surfacerect.top = self.top
        self.surfacerect.left = self.left
        # select the first digit, there should always be at least one
        self.state_name = '0'
        self.surface.fill(self.theme.colours.backgroundSubMenu)
        self.surface.blit(self.textSurface, self.textrect)
        self.state = self.state_dict[self.state_name]
        # draw all the digits
        drawnext = self.theme.menuWidth*0.05
        for n in range(self.digitCount):
            digitState = self.state_dict[str(n)]
            digitState.surfacerect.left = drawnext
            digitState.surfacerect.centery = self.surface.get_height()/2
            drawnext = digitState.surfacerect.right + self.theme.menuWidth*0.01
            currentDigit = math.floor((self.currentValue%pow(10,self.digitCount-n))/pow(10, self.digitCount-n-1))
            digitState.setValue(currentDigit)
            digitState.update()
            self.surface.blit(digitState.get_surface(), digitState.surfacerect)
        self.state.startup()
        self.surface.blit(self.state.get_surface(), self.state.surfacerect)
    def get_event(self, event):
        handeled = self.state.get_event(event)
        newValue = 0
        for n in range(self.digitCount):
            digitState = self.state_dict[str(n)]
            newValue += digitState.currentValue*pow(10,self.digitCount-n-1)
        self.inRange =  newValue >= self.minValue and newValue <= self.maxValue
        for digit in self.state_dict.values():
            if digit.setErrorHighlight(not self.inRange):
                self.surface.fill(self.theme.colours.backgroundSubMenu, digit.surfacerect)
                self.surface.blit(digit.get_surface(), digit.surfacerect)
        if not handeled:
            if event == navEvent.BACK:
                self.done = True
                return True
            if event == navEvent.SELECT :
                self.currentValue = newValue
                self.valueConfig.setValue(newValue)
                if self.updateCallback is not None:
                    self.updateCallback()
                self.done = True
                return True
        else:
            return True
        return False

# sub menu for inputing multiple whole numbers and execute a callback when done
class MultipleNumberSelect(SuperStatesSurface):
    def __init__(self, theme, backState, unittext, typetext, valueConfig, updateCallback):
        super().__init__(theme)
        # where to go back to
        self.next = backState
        self.valueConfig = valueConfig
        self.top = 0
        self.left = 0
        self.done = False
        self.updateCallback = updateCallback
        self.unittext = unittext
        self.typetext = typetext

    def cleanup(self):
        super().cleanup()
        if self.valueConfig.single:
            self.state_name = self.valueConfig[0]
        else:
            self.state_name = ("menu", self.valueConfig[0])

        self.surface.fill(self.theme.colours.transparent)
    def startup(self):
        if self.valueConfig.single:
            # load the number selector with no interim menu
            self.state_dict={self.valueConfig[0]: NumberSelect(self.theme, None, self.unittext, self.valueConfig[0], self.updateCallback)}
            itemleft = self.left
            self.state_name = self.valueConfig[0]
            self.surface = pygame.Surface((0, 0), pygame.SRCALPHA)
            self.surface.fill(self.theme.colours.transparent)
            self.surfacerect = self.surface.get_rect()
            self.surfacerect.top = self.top
            self.surfacerect.left = self.left
            drawnext = 0
        else:
            # work out what size all the list items have to be before creating them
            maxitemwidth = 0
            boxheight = self.theme.menuHeight*0.01
            menuLabels = []
            for n in range(len(self.valueConfig)):
                menuLabels.append(self.typetext+" "+str(n))
            menuLabels.append("New "+self.typetext)
            if len(self.valueConfig) > 1:
                menuLabels.append("Delete "+self.typetext)
            for label in menuLabels:
                maxitemwidth = max(maxitemwidth,self.theme.fonts.menuH1.size(label)[0])
                rowheight = self.theme.fonts.menuH1.size(label)[1] + self.theme.menuHeight*0.01
                boxheight += rowheight
            boxwidth = maxitemwidth + self.theme.menuWidth*0.2
            itemleft = self.left + boxwidth
            self.surface = pygame.Surface((boxwidth, boxheight), pygame.SRCALPHA)
            self.surface.fill(self.theme.colours.backgroundMenu)
            self.surfacerect = self.surface.get_rect()
            self.surfacerect.top = self.top
            self.surfacerect.left = self.left

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
                menuItem = NumberSelect(self.theme, menuHeadingKey, self.unittext, thisVal, self.updateCallback)
                menuHeading = SubMenuItem(self.theme, self.typetext+" "+str(valueCounter), prevState, self.state_name, menuItemKey, boxwidth, thisVal)
                self.state_dict[menuItemKey] = menuItem
                self.state_dict[menuHeadingKey] = menuHeading
                self.state_dict[prevState].down = menuHeadingKey
                self.state_dict[self.state_name].up = menuHeadingKey
                prevState = menuHeadingKey
                valueCounter += 1
            # setup add button
            newValuePlaceholder = self.valueConfig[0].copyConfig()
            self.state_dict[('new', 'item')] = NumberSelect(self.theme, ('new', 'menu'), self.unittext, newValuePlaceholder, functools.partial(self.addValue, newValuePlaceholder))
            self.state_dict[('new', 'menu')] = SubMenuItem(self.theme, "New "+self.typetext, prevState, self.state_name, ('new', 'item'), boxwidth, None)
            self.state_dict[prevState].down = ('new', 'menu')
            # setup delete button
            if len(self.valueConfig) > 1:
                valDict = {}
                for n in range(len(self.valueConfig)):
                    valDict[n] = self.typetext+" "+str(n)+": "+ str(self.valueConfig[n].getValue())+self.unittext
                self.state_dict[('del', 'item')] = ListSelect(self.theme, ('del', 'menu'), valDict, lambda:0 , self.deleteValue) 
                self.state_dict[('del', 'menu')] = SubMenuItem(self.theme, "Delete "+self.typetext, ('new', 'menu'), self.state_name, ('del', 'item'), boxwidth, None)
                self.state_dict[self.state_name].up = ('del', 'menu')
                self.state_dict[('new', 'menu')].down = ('del', 'menu')
            else:
                self.state_dict[self.state_name].up = ('new', 'menu')

            drawnext = self.theme.menuHeight*0.01

        # align the menu items and sub items
        self.state = self.state_dict[self.state_name]
        for menuState in self.state_dict.values():
            if(isinstance(menuState, NumberSelect)):
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

    def addValue(self, newValueConfig):
        self.valueConfig.append(newValueConfig.getValue())
        self.updateCallback()
        self.done = True

    def deleteValue(self, deleteIndex):
        del(self.valueConfig[deleteIndex])
        self.updateCallback()
        self.done = True

    def getSurfaceRects(self):
        # if its a sub menu return the rectangles for it to the parent for painting
        if(isinstance(self.state, ListSelect) or isinstance(self.state, NumberSelect) or isinstance(self.state, MultipleNumberSelect)):
            rectlist = [self.surfacerect]
            rectlist.extend(self.state.getSurfaceRects())
            return rectlist
        else:
            return [self.surfacerect]

    def getBlitPairs(self):
        # if its a sub menu return the surfaces directly to the parent for bliting
        if(isinstance(self.state, ListSelect) or isinstance(self.state, NumberSelect) or isinstance(self.state, MultipleNumberSelect)):
            pairlist = [(self.surface, self.surfacerect)]
            pairlist.extend(self.state.getBlitPairs())
            return pairlist
        else:
            return [(self.surface, self.surfacerect)]

    def redrawState(self, state, rects):
        # if its not a sub menu draw it onto the local surface
        if not (isinstance(self.state, ListSelect) or isinstance(self.state, NumberSelect) or isinstance(self.state, MultipleNumberSelect)):
            super().redrawState(state, rects)

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
    def __init__(self, theme, nextstate, state_dict, initstate):
        super().__init__(theme)
        self.next = nextstate
        self.done = False
        self.state_dict = state_dict
        self.initstate = initstate
        # import and resize the logo
        eps = Image.open(theme.logofile)
        origwidth, origheight = eps.size
        scale = theme.menuWidth/float(origwidth)*0.8
        newheight = int(round(origheight*scale))
        newwidth  = int(round(origwidth*scale))
        eps = eps.resize((newwidth,newheight), Image.ANTIALIAS)
        epsstr = eps.tobytes("raw", "RGBA")
        self.logosurface = pygame.image.fromstring(epsstr, eps.size, "RGBA")

    def cleanup(self):
        super().cleanup()
        del(self.surface)
        del(self.dispmanxlayer)

    def startup(self):
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
        self.state_name = self.initstate
        self.state = self.state_dict[self.state_name]
        drawnext = logosurfacerect.bottom + self.theme.menuHeight*0.01
        # draw all the states
        #TODO: auto sort so input dict isnt order sensitive
        for menuState in self.state_dict.values():
            if(isinstance(menuState, ListSelect)):
                menuState.surfacerect.top = drawnext
                menuState.surfacerect.left = self.theme.menuWidth
                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
            elif(isinstance(menuState, NumberSelect) or isinstance(menuState, MultipleNumberSelect)):
                menuState.top = drawnext
                menuState.left = self.theme.menuWidth
                print((drawnext, self.theme.menuWidth))
#                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
            elif(isinstance(menuState, MenuItem)):
                menuState.surfacerect.top = drawnext
                menuState.surfacerect.right = self.theme.menuWidth*0.9
                drawnext = menuState.surfacerect.bottom + self.theme.menuHeight*0.01
                self.surface.blit(menuState.get_surface(), menuState.surfacerect)
        self.state.startup()
        if(isinstance(self.state, MenuItem)):
            self.surface.blit(self.state.get_surface(), self.state.surfacerect)
        self.dispmanxlayer.updateLayer()

    def get_event(self, event):
        # Always handle this event
        if(event == navEvent.MENU):
            self.done = True
        # check to see if anyting else handled these events already
        elif(not self.state.get_event(event)):
            if(event == navEvent.BACK):
                self.done = True

    def redrawState(self, state, rects):
        for rect in rects:
            if(isinstance(state, MenuItem)):
                self.surface.fill(self.theme.colours.backgroundSubMenu, rect)
            elif(isinstance(state, ListSelect) or isinstance(state, NumberSelect) or isinstance(state, MultipleNumberSelect)):
                self.surface.fill(self.theme.colours.transparent, rect)
        self.surface.blits(state.getBlitPairs())

    def update(self):
        super().update()
        self.dispmanxlayer.updateLayer()
