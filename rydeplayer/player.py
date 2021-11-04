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

import pygame, vlc, select, pydispmanx, yaml, os, pkg_resources, argparse, importlib, functools, sys
import rydeplayer.sources.common
import rydeplayer.sources.longmynd
import rydeplayer.sources.combituner
from . import ir
import rydeplayer.gpio
import rydeplayer.network
import rydeplayer.common
import rydeplayer.states.gui
import rydeplayer.states.playback
import rydeplayer.osd.display
import rydeplayer.osd.modules

# container for the theme
class Theme(object):
    def __init__(self, displaySize):
        self.colours = type('colours', (object,), {
            'transparent': (0,0,0,0),
            'transpBack': (0,0,0,51),
            'black': (0,0,0,255),
            'white': (255,255,255,255),
            'red': (255,0,0,255),
            'textError': (255,0,0,255),
            'backgroundMenu': (57,169,251,255),
            'backgroundSubMenu': (57,169,251,255),
            'backgroundPlayState': (255,0,0,255),
            })
        self.displayWidth = int(displaySize[0])
        self.displayHeight = int(displaySize[1])
        self.menuWidth = int(self.displayWidth/4)
        self.menuHeight = self.displayHeight
        playStateTitleFontSize=self.fontSysSizeOptimize('Not Loaded', displaySize[0]/2, 'freesans')
        menuH1FontSize=self.fontSysSizeOptimize('BATC Ryde Project', self.menuWidth*0.85, 'freesans')
        self.fonts = type('fonts', (object,), {
            'menuH1': pygame.font.SysFont('freesans', menuH1FontSize),
            'playStateTitle' :  pygame.font.SysFont('freesans', playStateTitleFontSize),
            })
        self._circlecache = {}
        self.logofile = pkg_resources.resource_stream('rydeplayer.resources', 'logo_menu.png')
        self.muteicon = pkg_resources.resource_stream('rydeplayer.resources', 'icon_mute.png')

    # calculate the largest font size that you can render the given test in as still be less than width
    def fontSysSizeOptimize(self, text, width, fontname):
        fontsize = -1
        while True:
            fontCandidate = pygame.font.SysFont(fontname, fontsize+1)
            fontwidth = fontCandidate.size(text)[0]
            del(fontCandidate)
            if(fontwidth > width):
                break
            else:
                fontsize += 1
        return fontsize

    # calculate the largest font size that has a line height less than height
    def fontSysSizeOptimizeHeight(self, height, fontname):
        fontsize = -1
        while True:
            fontCandidate = pygame.font.SysFont(fontname, fontsize+1)
            fontheight = fontCandidate.get_linesize()
            del(fontCandidate)
            if(fontheight > height):
                break
            else:
                fontsize += 1
        return fontsize

    # size and position a pygame rectangle using screen size independent units and a datum corner
    def relativeRect(self, datum, xEdgeDistance, yEdgeDistance, width, height):
        outwidth = self.displayHeight*width
        outheight = self.displayHeight*height
        if datum is rydeplayer.common.datumCornerEnum.TR:
            outX = self.displayWidth - ((xEdgeDistance+width)*self.displayHeight)
            outY = yEdgeDistance*self.displayHeight
        elif datum is rydeplayer.common.datumCornerEnum.TC:
            outX = (self.displayWidth/2) - (((width/2)-xEdgeDistance)*self.displayHeight)
            outY = yEdgeDistance*self.displayHeight
        elif datum is rydeplayer.common.datumCornerEnum.TL:
            outX = xEdgeDistance*self.displayHeight
            outY = yEdgeDistance*self.displayHeight
        elif datum is rydeplayer.common.datumCornerEnum.CR:
            outX = self.displayWidth - ((xEdgeDistance+width)*self.displayHeight)
            outY = (self.displayHeight/2) - (((height/2)-yEdgeDistance)*self.displayHeight)
        elif datum is rydeplayer.common.datumCornerEnum.CC:
            outX = (self.displayWidth/2) - (((width/2)-xEdgeDistance)*self.displayHeight)
            outY = (self.displayHeight/2) - (((height/2)-yEdgeDistance)*self.displayHeight)
        elif datum is rydeplayer.common.datumCornerEnum.CL:
            outX = xEdgeDistance*self.displayHeight
            outY = (self.displayHeight/2) - (((height/2)-yEdgeDistance)*self.displayHeight)
        elif datum is rydeplayer.common.datumCornerEnum.BR:
            outX = self.displayWidth - ((xEdgeDistance+width)*self.displayHeight)
            outY = self.displayHeight - ((yEdgeDistance+height)*self.displayHeight)
        elif datum is rydeplayer.common.datumCornerEnum.BC:
            outX = (self.displayWidth/2) - (((width/2)-xEdgeDistance)*self.displayHeight)
            outY = self.displayHeight - ((yEdgeDistance+height)*self.displayHeight)
        elif datum is rydeplayer.common.datumCornerEnum.BL:
            outX = xEdgeDistance*self.displayHeight
            outY = self.displayHeight - ((yEdgeDistance+height)*self.displayHeight)
        return pygame.Rect((outX, outY, outwidth, outheight))

    # helper function for outline font rendering
    def _circlepoints(self,r):
        r = int(round(r))
        if r in self._circlecache:
            return self._circlecache[r]
        x, y, e = r, 0, 1 - r
        self._circlecache[r] = points = []
        while x >= y:
            points.append((x, y))
            y += 1
            if e < 0:
                e += 2 * y - 1
            else:
                x -= 1
                e += 2 * (y - x) - 1
        points += [(y, x) for x, y in points if x > y]
        points += [(-x, y) for x, y in points if x]
        points += [(x, -y) for x, y in points if y]
        points.sort()
        return points

    # render font with different coloured outline
    def outlineFontRender(self, text, font, gfcolor, ocolor, opx=2):
        textsurface = font.render(text, True, gfcolor)
        w = textsurface.get_width() + 2 * opx
        h = font.get_height()

        osurf = pygame.Surface((w, h + 2 * opx), pygame.SRCALPHA)
        osurf.fill((0, 0, 0, 0))

        surf = osurf.copy()

        osurf.blit(font.render(text, True, ocolor), (0, 0))

        for dx, dy in self._circlepoints(opx):
            surf.blit(osurf, (dx + opx, dy + opx))

        surf.blit(textsurface, (opx, opx))
        return surf



# power menu UI state machine
class SubMenuPower(rydeplayer.states.gui.ListSelect):
    def __init__(self, theme, backState, shutdownCallback):
        items = {
                    rydeplayer.common.shutdownBehavior.APPSTOP : 'App Shutdown',
                    rydeplayer.common.shutdownBehavior.APPREST : 'App Restart',
                    rydeplayer.common.shutdownBehavior.SYSSTOP : 'System Shutdown',
                    rydeplayer.common.shutdownBehavior.SYSREST : 'System Restart',
                }
        super().__init__(theme, backState, items, lambda: rydeplayer.common.shutdownBehavior.APPSTOP, shutdownCallback)
    def get_event(self, event):
        if super().get_event(event):
            return True
        else:
            if event == rydeplayer.common.navEvent.POWER:
                return super().get_event(rydeplayer.common.navEvent.SELECT)

            else:
                return False

# main UI state machine
class guiState(rydeplayer.states.gui.SuperStates):
    def __init__(self, theme, shutdownBehaviorDefault, player, osd):
        super().__init__(theme)
        self.done = False
        self.player = player
        self.osd = osd
        self.shutdownBehaviorDefault = shutdownBehaviorDefault
        self.shutdownState = rydeplayer.common.shutdownBehavior.APPSTOP

    # callback to run all the remove and cleanup callback on the active manu states
    def _cleanupMenuStates(self, activeCallbacks):
        for callback in activeCallbacks:
            callback()

    # generate the menu states based on current config capabilites
    def _genMenuStates(self, config, debugFunctions, superMenu):
        # get variables for current config
        tunerConfigVars = config.tuner.getVars()
        # generate config specific menu items
        mainMenuStates = {}
        firstkey = None
        lastkey = None
        # set of cleanup functions for the menu items
        activeCallbacks = set()
        for key in tunerConfigVars:
            validVar = False
            # create sub menu items for supported var types
            if isinstance(tunerConfigVars[key], rydeplayer.sources.common.tunerConfigIntList):
                mainMenuStates[key+'-sel'] = rydeplayer.states.gui.MultipleNumberSelect(self.theme, key, tunerConfigVars[key], config.tuner.runCallbacks)
                validVar = True

            if isinstance(tunerConfigVars[key], rydeplayer.sources.common.tunerConfigInt):
                mainMenuStates[key+'-sel'] = rydeplayer.states.gui.NumberSelect(self.theme, key, tunerConfigVars[key], config.tuner.runCallbacks)
                validVar = True

            if validVar:
                if firstkey is None:
                    firstkey = key
                if lastkey is None:
                    lastkey = key
                # create menu item
                mainMenuStates[key] = rydeplayer.states.gui.MenuItem(self.theme, tunerConfigVars[key].getLongName(), lastkey, firstkey, key+'-sel', tunerConfigVars[key])
                mainMenuStates[lastkey].down = key
                mainMenuStates[firstkey].up = key
                lastkey = key
                # callback to menu header for validity updates
                validCallFunc = functools.partial(superMenu.redrawState, mainMenuStates[key], mainMenuStates[key].getSurfaceRects())
                tunerConfigVars[key].addValidCallback(validCallFunc)
                activeCallbacks.add(functools.partial(tunerConfigVars[key].removeValidCallback,validCallFunc))
        cleanupFunc = functools.partial(self._cleanupMenuStates, activeCallbacks)

        # main menu states, order is important to get menus and sub menus to display in the right place
        if firstkey is None:
            firstkey = 'band'
        if lastkey is None:
            lastkey = 'power'
        baseMenuStates = {
            'band-sel'  : rydeplayer.states.gui.ListSelect(self.theme, 'band', config.bands, config.tuner.getBand, config.tuner.setBand),
            'band'      : rydeplayer.states.gui.MenuItem(self.theme, "Band", lastkey, "preset", "band-sel"),
            'preset-sel'  : rydeplayer.states.gui.ListSelect(self.theme, 'preset', config.presets, lambda:config.tuner, config.tuner.setConfigToMatch),
            'preset'      : rydeplayer.states.gui.MenuItem(self.theme, "Presets", "band", "power", "preset-sel"),
            'power-sel'  : SubMenuPower(self.theme, 'power', self.shutdown),
            'power'      : rydeplayer.states.gui.MenuItem(self.theme, "Power", "preset", firstkey, "power-sel"),
        }
        mainMenuStates.update(baseMenuStates)
        mainMenuStates[lastkey].down = 'band'
        mainMenuStates[firstkey].up = 'power'
        lastkey = 'power'
        
        # add debug menu if enabled in config
        if config.debug.enableMenu:
            # generate debug menu states
            debugMenuStates = {}
            debugPrevState = None
            debugFirstState = None
            for key in debugFunctions:
                menukey = key.strip().replace(" ", "").lower()
                if debugFirstState is None:
                    debugFirstState = menukey
                    debugPrevState = menukey
                debugMenuStates[menukey] = rydeplayer.states.gui.SubMenuItemFunction(self.theme, key, debugPrevState, debugFirstState, debugFunctions[key])
                debugMenuStates[debugPrevState].down = menukey
                debugMenuStates[debugFirstState].up = menukey
                debugPrevState = menukey
            mainMenuStates['debug-sel'] = rydeplayer.states.gui.SubMenuGeneric(self.theme, 'debug', debugMenuStates, debugFirstState)
            mainMenuStates['debug'] = rydeplayer.states.gui.MenuItem(self.theme, "Debug", lastkey, firstkey, "debug-sel")
            mainMenuStates[lastkey].down = 'debug'
            mainMenuStates[firstkey].up = 'debug'
            lastkey = 'debug'
        validCallFunc = superMenu.refreshStates
        config.tuner.addVarChangeCallbackFunction(validCallFunc)
        activeCallbacks.add(functools.partial(config.tuner.removeVarChangeCallbackFunction,validCallFunc))

        return (mainMenuStates, firstkey, cleanupFunc)

    def startup(self, config, debugFunctions):
        # top level state machine
        self.state_dict = {
            'menu': rydeplayer.states.gui.Menu(self.theme, 'home', functools.partial(self._genMenuStates, config, debugFunctions)),
            'home': Home(self.theme, self.osd)
        }
        self.state_name = "home"
        self.state = self.state_dict[self.state_name]
        self.state.startup()

    def shutdown(self, shutdownState):
        self.shutdownState = shutdownState
        self.state.cleanup()
        self.done = True

    def get_event(self, event):
        if not self.state.get_event(event):
            if event == rydeplayer.common.navEvent.POWER:
                self.setStateStack([self.shutdownBehaviorDefault,'power-sel','menu'])
            elif event == rydeplayer.common.navEvent.OSDON:
                self.osd.activate(1)
            elif event == rydeplayer.common.navEvent.OSDOFF:
                self.osd.deactivate(1)
            elif event == rydeplayer.common.navEvent.OSDTOG:
                self.osd.toggle(2)
            elif(event == rydeplayer.common.navEvent.MUTE):
                self.player.toggleMute()
            elif(event == rydeplayer.common.navEvent.VOLU):
                self.player.adjustVolumeByStep(True)
                self.osd.activate(3, rydeplayer.osd.display.TimerLength.USERTRIGGER)
            elif(event == rydeplayer.common.navEvent.VOLD):
                self.player.adjustVolumeByStep(False)
                self.osd.activate(3, rydeplayer.osd.display.TimerLength.USERTRIGGER)
            elif(event == rydeplayer.common.navEvent.CHANU):
                self.player.switchPresetRelative(-1)
            elif(event == rydeplayer.common.navEvent.CHAND):
                self.player.switchPresetRelative(1)


# GUI state for when the menu isnt showing
class Home(rydeplayer.states.gui.States):
    def __init__(self, theme, osd):
        super().__init__(theme)
        self.next = 'menu'
        self.osd = osd
    def cleanup(self):
        None
    def startup(self):
        None
    def get_event(self, event):
        #TODO: add OSD state machine
        if(event == rydeplayer.common.navEvent.SELECT):
            self.osd.activate(3, rydeplayer.osd.display.TimerLength.USERTRIGGER)
        elif(event == rydeplayer.common.navEvent.BACK):
            self.osd.deactivate(2)
        elif(event == rydeplayer.common.navEvent.MENU):
            self.done = True

class rydeConfig(object):
    def __init__(self, theme):
        self.ir = ir.irConfig()
        self.gpio = rydeplayer.gpio.gpioConfig()
        self.tuner = rydeplayer.sources.common.tunerConfig()
        # source specific config
        self.sourceConfigs = dict()
        for thisSource in rydeplayer.sources.common.sources:
            self.sourceConfigs[thisSource]=thisSource.getSource().getConfig()()
        self.bands = {}
        defaultBand = self.tuner.getBand()
        self.bands[defaultBand] = "None"
        self.presets = {}
        self.osd = rydeplayer.osd.display.Config(theme)
        self.network = rydeplayer.network.networkConfig()
        self.shutdownBehavior = rydeplayer.common.shutdownBehavior.APPSTOP
        self.audio = type('audioConfig', (object,), {
            'muteOnStartup': False,
            'volumeOnStartup': 100,
            'volumeStep': 25,
            })
        self.debug = type('debugConfig', (object,), {
            'enableMenu': False,
            'autoplay': True,
            'disableHardwareCodec': True,
            })
        self.configRev = 3
    #setter for default values
    def setAutoplay(self, newval):
        self.debug.autoplay = newval

    # parse config dict
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            # parse config revision
            if 'configRev' in config:
                if isinstance(config['configRev'], int):
                    if config['configRev'] != self.configRev:
                        print("Unmatched config revision, config load aborted")
                        return False
                else:
                    print("Config revision not an integer, config load aborted")
                    return False
            else:
                print("WARNING: no config revision present, config load my fail")
            if 'bands' in config:
                if isinstance(config['bands'], dict):
                    newBands = {}
                    exsistingBands = list(self.bands.keys())
                    for bandName in config['bands']:
                        bandDict = config['bands'][bandName]
                        bandParseSuccess, bandObject = rydeplayer.sources.common.tunerBand.loadBand(bandDict)
                        if bandParseSuccess:
                            # dedupe band object with exsisting library
                            if bandObject in exsistingBands:
                                bandObject = exsistingBands[exsistingBands.index(bandObject)]
                            newBands[bandObject] = str(bandName)
                        else:
                            perfectConfig = False
                    if len(newBands) > 1:
                        self.bands = newBands
                    else:
                        print("No valid bands, skipping")
                        perfectConfig = False
                else:
                    print("Invalid band library")
                    perfectConfig = False
            # parse source specific configs
            if 'sources' in config:
                if isinstance(config['sources'], dict):
                    for thisSource in rydeplayer.sources.common.sources:
                        if thisSource.name.lower() in config['sources']:
                            perfectConfig = perfectConfig and self.sourceConfigs[thisSource].loadConfig(config['sources'][thisSource.name.lower()])
                        elif thisSource.name.upper() in config['sources']:
                            perfectConfig = perfectConfig and self.sourceConfigs[thisSource].loadConfig(config['sources'][thisSource.name.upper()])
                else:
                    print("Sources config not a dict")
                    perfectConfig = False
            # parse presets
            if 'presets' in config:
                if isinstance(config['presets'], dict):
                    newPresets = {}
                    exsistingPresets = list(self.presets.keys())
                    for presetName in config['presets']:
                        presetDict = config['presets'][presetName]
                        presetObject = rydeplayer.sources.common.tunerConfig()
                        if presetObject.loadConfig(presetDict, list(self.bands.keys())):
                            # dedupe preset object with exsisting library
                            if presetObject in exsistingPresets:
                                presetObject = exsistingPresets[exsistingPresets.index(presetObject)]
                            newPresets[presetObject] = str(presetName)
                        else:
                            perfectConfig = False
                    if len(newPresets) > 1:
                        self.presets = newPresets
                    else:
                        print("No valid presets, skipping")
                        perfectConfig = False
                else:
                    print("Invalid preset library")
                    perfectConfig = False
            # pass default tuner config to be parsed by longmynd module
            if 'default' in config:
                defaultPreset = rydeplayer.sources.common.tunerConfig()
#                perfectConfig = perfectConfig and defaultPreset.loadConfig(config['default'], list(self.bands.keys()))
                if defaultPreset.loadConfig(config['default'], list(self.bands.keys())):
                    # dedupe preset object with exsisting library
                    exsistingPresets = list(self.presets.keys())
                    if defaultPreset in exsistingPresets:
                        defaultPreset = exsistingPresets[exsistingPresets.index(defaultPreset)]
                    self.tuner.setConfigToMatch(defaultPreset)
                else:
                    perfectConfig = False

            # pass ir config to be parsed by the ir config container
            if 'ir' in config:
                perfectConfig = perfectConfig and self.ir.loadConfig(config['ir'])
            # pass the gpio config to be parsed by the gpio config container
            if 'gpio' in config:
                perfectConfig = perfectConfig and self.gpio.loadConfig(config['gpio'])
            # pass the osd config to be parsed by the osd config container
            if 'osd' in config:
                perfectConfig = perfectConfig and self.osd.loadConfig(config['osd'])
            # pass the network config to be parsed by the network config container
            if 'network' in config:
                perfectConfig = perfectConfig and self.network.loadConfig(config['network'])
            # parse shutdown default shutdown event behavior
            if 'shutdownBehavior' in config:
                if isinstance(config['shutdownBehavior'], str):
                    validShutBehav = False
                    for shutBehavOpt in rydeplayer.common.shutdownBehavior:
                        if shutBehavOpt.name == config['shutdownBehavior'].upper():
                            self.shutdownBehavior = shutBehavOpt
                            validShutBehav = True
                            break
                    if not validShutBehav:
                        print("Shutdown behavior default invalid, skipping")
                        perfectConfig = False
                else:
                    print("Shutdown behavior default invalid, skipping")
                    perfectConfig = False
            # parse audio options
            if 'audio' in config:
                if isinstance(config['audio'], dict):
                    if 'muteOnStartup' in config['audio']:
                        if isinstance(config['audio']['muteOnStartup'], bool):
                            self.audio.muteOnStartup = config['audio']['muteOnStartup']
                        else:
                            print("Invalid mute on startup config, skipping")
                            perfectConfig = False
                    if 'volumeOnStartup' in config['audio']:
                        if isinstance(config['audio']['volumeOnStartup'], int):
                            if config['audio']['volumeOnStartup'] <= 100 and config['audio']['volumeOnStartup'] >= 0:

                                self.audio.volumeOnStartup = config['audio']['volumeOnStartup']
                            else:
                                print("Invalid startup volume config, out of range, skipping")
                                perfectConfig = False

                        else:
                            print("Invalid startup volume config, skipping")
                            perfectConfig = False
                    if 'volumeStep' in config['audio']:
                        if isinstance(config['audio']['volumeStep'], int):
                            if config['audio']['volumeStep'] <= 100 and config['audio']['volumeStep'] >= 0:

                                self.audio.volumeStep = config['audio']['volumeStep']
                            else:
                                print("Invalid volume step config, out of range, skipping")
                                perfectConfig = False

                        else:
                            print("Invalid volume step config, skipping")
                            perfectConfig = False

            # parse debug options
            if 'debug' in config:
                if isinstance(config['debug'], dict):
                    if 'enableMenu' in config['debug']:
                        if isinstance(config['debug']['enableMenu'], bool):
                            self.debug.enableMenu = config['debug']['enableMenu']
                        else:
                            print("Invalid debug menu config, skipping")
                            perfectConfig = False
                    if 'autoplay' in config['debug']:
                        if isinstance(config['debug']['autoplay'], bool):
                            self.debug.autoplay = config['debug']['autoplay']
                        else:
                            print("Invalid debug autoplay config, skipping")
                            perfectConfig = False
                    if 'disableHardwareCodec' in config['debug']:
                        if isinstance(config['debug']['disableHardwareCodec'], bool):
                            self.debug.disableHardwareCodec = config['debug']['disableHardwareCodec']
                        else:
                            print("Invalid debug hardware codec config, skipping")
                            perfectConfig = False
                else:
                    print("Invalid debug config, skipping")
                    perfectConfig = False

                    
        else:
            print("Invalid config, no fields")
            perfectConfig = False
        return perfectConfig

    # load yaml config file
    def loadFile(self, path):
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, 'r') as ymlconfigfile:
                    self.loadConfig(yaml.load(ymlconfigfile))
            except IOError as e:
                print(e)
        else:
            print("config file not found")

class player(object):

    def __init__(self, configFile = None):
        # setup ui core
        pygame.init()
        self.theme = Theme(pydispmanx.getDisplaySize())
        self.playbackState = rydeplayer.states.playback.StateDisplay(self.theme)
        print(pygame.font.get_fonts())

        # load config
        self.config = rydeConfig(self.theme)
        if configFile != None:
            self.config.loadFile(configFile)
        print(self.config.tuner)

        # mute
        self.mute = self.config.audio.muteOnStartup
        self.muteCallbacks = []

        # volume
        self.volume = self.config.audio.volumeOnStartup
        self.volumeCallbacks = []

        # setup source 
        self.sourceMan = rydeplayer.sources.common.sourceManagerThread(self.config.tuner, self.config.sourceConfigs)
        self.config.tuner.addCallbackFunction(self.sourceMan.reconfig)

        self.vlcStartup()

        # setup on screen display
        self.osd = rydeplayer.osd.display.Controller(self.theme, self.config.osd, self.sourceMan.getStatus(), self, self.config.tuner)

        debugFunctions = {'Restart Source':self.sourceMan.restart, 'Force VLC':self.vlcStop, 'Abort VLC': self.vlcAbort}

        # start ui
        self.app = guiState(self.theme, self.config.shutdownBehavior, self, self.osd)
        self.app.startup(self.config, debugFunctions)

        # start network
        self.netMan = rydeplayer.network.networkManager(self.config, self.stepSM, self.setMute, debugFunctions)

        # setup ir
        self.irMan = ir.irManager(self.stepSM, self.config.ir)

        # setup gpio
        self.gpioMan = rydeplayer.gpio.gpioManager(self.stepSM, self.config.gpio, self.config.tuner)
        self.config.tuner.addCallbackFunction(self.gpioMan.setBandOutFromPreset)

        # start source
        self.sourceMan.start()
        print("Ready")
        self.monotonicState = 0;

    def start(self):
        quit = False
        # main event loop
        while not quit:
            # need to regen every loop, lm stdout handler changes on lm restart
            fds = self.irMan.getFDs() + self.sourceMan.getFDs() + self.gpioMan.getFDs() + self.osd.getFDs() + self.netMan.getFDs()
            r, w, x = select.select(fds, [], [])
            for fd in r:
                quit = self.handleEvent(fd)
                self.updateState()
                if quit:
                    break
        self.shutdown(self.app.shutdownState)

    def addMuteCallback(self, callback):
        self.muteCallbacks.append(callback)

    def removeMuteCallback(self, callback):
        self.muteCallbacks.remove(callback)

    def setMute(self,newMute):
        if self.mute != newMute:
            self.mute = newMute
            self.vlcPlayer.audio_set_mute(newMute)
            for callback in self.muteCallbacks:
                callback(newMute)

    def getMute(self):
        return self.mute

    def toggleMute(self):
        self.setMute(not self.mute)

    def addVolumeCallback(self, callback):
        self.volumeCallbacks.append(callback)

    def removeVolumeCallback(self, callback):
        self.volumeCallbacks.remove(callback)

    def setVolume(self,newVolume):
        if newVolume > 100:
            newVolume = 100
        elif newVolume < 0:
            newVolume = 0
        if self.volume != newVolume:
            self.volume = newVolume
            self.vlcPlayer.audio_set_volume(newVolume)
            for callback in self.volumeCallbacks:
                callback(newVolume)

    def getVolume(self):
        return self.volume

    def adjustVolume(self, volumeAdjustment):
        self.setVolume(self.volume + volumeAdjustment)

    def adjustVolumeByStep(self, up):
        if up:
            self.adjustVolume(self.config.audio.volumeStep)
        else:
            self.adjustVolume(-self.config.audio.volumeStep)

    def getPresetName(self, preset):
        if preset in self.config.presets:
            return str(self.config.presets[preset])
        else:
            return ""

    def switchPresetRelative(self, offset):
        presetkeys = list(self.config.presets.keys())
        if len(presetkeys) > 0:
            newindex = None
            if self.config.tuner in presetkeys:
                newindex = (presetkeys.index(self.config.tuner) + offset)%len(presetkeys)
            else:
                if offset > 0:
                    newindex = 0
                elif offset < 0:
                    newindex = len(presetkeys)-1
            if newindex is not None:
                self.config.tuner.setConfigToMatch(presetkeys[newindex])
                self.osd.activate(3, rydeplayer.osd.display.TimerLength.USERTRIGGER)

    def shutdown(self, behaviour):
        del(self.osd)
        del(self.playbackState)
        self.sourceMan.shutdown()
        if behaviour is rydeplayer.common.shutdownBehavior.APPREST:
            os.execv(sys.executable, ['python3', '-m', 'rydeplayer'] + sys.argv[1:])
        elif behaviour is rydeplayer.common.shutdownBehavior.SYSSTOP:
            os.system("sudo shutdown -h now")
        elif behaviour is rydeplayer.common.shutdownBehavior.SYSREST:
            os.system("sudo shutdown -r now")

    def handleEvent(self, fd):
        quit = False
        # handle ready file descriptors
        if(fd in self.irMan.getFDs()):
            quit = self.irMan.handleFD(fd)
        elif(fd in self.sourceMan.getFDs()):
            self.sourceMan.handleFD(fd)
        elif(fd in self.gpioMan.getFDs()):
            quit = self.gpioMan.handleFD(fd)
        elif(fd in self.osd.getFDs()):
            quit = self.osd.handleFD(fd)
        elif(fd in self.netMan.getFDs()):
            quit = self.netMan.handleFD(fd)
        return quit

    def updateState(self):
        # update playback state
        state = self.sourceMan.getCoreState()
        if(state.isRunning):
            if(state.isLocked):
                self.playbackState.setState(rydeplayer.states.playback.States.LOCKED)
                newMonoState = state.monotonicState

                if self.monotonicState != newMonoState:
                    self.monotonicState = newMonoState
                    self.vlcStop()
                    print("Param Restart")
                if self.vlcPlayer.get_state() not in [vlc.State.Playing, vlc.State.Opening] and self.config.debug.autoplay:
                    self.vlcPlay()
                    self.osd.activate(4, rydeplayer.osd.display.TimerLength.PROGRAMTRIGGER)
                self.gpioMan.setRXgood(True)
            else:
                self.playbackState.setState(rydeplayer.states.playback.States.NOLOCK)
                if self.config.debug.autoplay:
                    self.vlcStop()
                self.gpioMan.setRXgood(False)
        else:
            if state.isStarted:
                self.playbackState.setState(rydeplayer.states.playback.States.SOURCELOAD)
            else:
                self.playbackState.setState(rydeplayer.states.playback.States.NOSOURCE)
            if self.config.debug.autoplay:
                self.vlcStop()
#               print("parsed:"+str(vlcMedia.is_parsed()))
            self.gpioMan.setRXgood(False)
        self.vlcPlayer.audio_set_mute(self.mute)
        self.vlcPlayer.audio_set_volume(self.volume)
        print(self.vlcPlayer.get_state())

    # Step the state machine with a navEvent
    def stepSM(self, code):
        self.app.get_event(code)
        if(self.app.done):
            self.app.cleanup()
            return True
        self.app.update()
        return False

    # retrigger vlc to play, mostly exsists as its needed as a callback
    def vlcPlay(self):
        self.vlcPlayer.set_media(self.vlcMedia)
        self.vlcPlayer.play()
    def vlcStop(self):
        self.vlcPlayer.stop()
    def vlcAbort(self):
        del(self.vlcMedia)
        del(self.vlcPlayer)
        del(self.vlcInstance)
        importlib.reload(vlc)
        self.sourceMan.remedia()
#        self.sourceMan.restart()
        self.vlcStartup()

    def vlcStartup(self):
        vlcArgs = ''
        displaySize = pydispmanx.getDisplaySize()
        vlcArgs += '--width '+str(displaySize[0])+' --height '+str(displaySize[1])+' '
        displayPAR = pydispmanx.getPixelAspectRatio()
        vlcArgs += '--monitor-par '+str(displayPAR[0])+':'+str(displayPAR[1])+' '
        if self.config.debug.disableHardwareCodec:
            vlcArgs += '--codec ffmpeg '
#        vlcArgs += '--gain 4 --alsa-audio-device hw:CARD=Headphones,DEV=0 '
        print(vlcArgs)
        self.vlcInstance = vlc.Instance(vlcArgs)

        self.vlcPlayer = self.vlcInstance.media_player_new()
        self.vlcMedia = self.vlcInstance.media_new_fd(self.sourceMan.getMediaFd().fileno())

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument(metavar="config filename", dest='conffile', help="YAML config file to try and load. Default: config.yaml", nargs='?', default='config.yaml')
    args = parser.parse_args()
    print(args)
    newplayer = player(args.conffile)
    newplayer.start()

if __name__ == '__main__':
    run()
