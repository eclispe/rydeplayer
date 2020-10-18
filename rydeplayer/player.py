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

import pygame, vlc, select, pydispmanx, yaml, os, pkg_resources, argparse, importlib, functools, sys
from . import longmynd
from . import ir
import rydeplayer.gpio
import rydeplayer.common
import rydeplayer.states.gui
import rydeplayer.states.playback

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
        self.menuWidth = int(displaySize[0]/4)
        self.menuHeight = int(displaySize[1])
        playStateTitleFontSize=self.fontSysSizeOptimize('Not Loaded', displaySize[0]/2, 'freesans')
        menuH1FontSize=self.fontSysSizeOptimize('BATC Ryde Project', self.menuWidth*0.85, 'freesans')
        self.fonts = type('fonts', (object,), {
            'menuH1': pygame.font.SysFont('freesans', menuH1FontSize),
            'playStateTitle' :  pygame.font.SysFont('freesans', playStateTitleFontSize),
            })
        self.logofile = pkg_resources.resource_stream('rydeplayer.resources', 'logo_menu.png')

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
    def __init__(self, theme, shutdownBehaviorDefault, player):
        super().__init__(theme)
        self.done = False
        self.player = player
        self.shutdownBehaviorDefault = shutdownBehaviorDefault
        self.shutdownState = rydeplayer.common.shutdownBehavior.APPSTOP
    def startup(self, config, debugFunctions):
        # main menu states, order is important to get menus and sub menus to display in the right place
        mainMenuStates = {
            'freq-sel' : rydeplayer.states.gui.MultipleNumberSelect(self.theme, 'freq', 'kHz', 'Freq', config.tuner.freq, config.tuner.runCallbacks),
            'freq'     : rydeplayer.states.gui.MenuItem(self.theme, "Frequency", "power", "sr", "freq-sel", config.tuner.freq),
            'sr-sel'   : rydeplayer.states.gui.MultipleNumberSelect(self.theme, 'sr', 'kS', 'SR', config.tuner.sr, config.tuner.runCallbacks),
            'sr'       : rydeplayer.states.gui.MenuItem(self.theme, "Symbol Rate", "freq", "band", "sr-sel", config.tuner.sr),
            'band-sel'  : rydeplayer.states.gui.ListSelect(self.theme, 'band', config.bands, config.tuner.getBand, config.tuner.setBand),
            'band'      : rydeplayer.states.gui.MenuItem(self.theme, "Band", "sr", "preset", "band-sel"),
            'preset-sel'  : rydeplayer.states.gui.ListSelect(self.theme, 'preset', config.presets, lambda:config.tuner, config.tuner.setConfigToMatch),
            'preset'      : rydeplayer.states.gui.MenuItem(self.theme, "Presets", "band", "power", "preset-sel"),
            'power-sel'  : SubMenuPower(self.theme, 'power', self.shutdown),
            'power'      : rydeplayer.states.gui.MenuItem(self.theme, "Power", "preset", "freq", "power-sel"),
        }

        firstkey = 'freq'
        lastkey = 'power'
        
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

        self.state_dict = {
            'menu': rydeplayer.states.gui.Menu(self.theme, 'home', mainMenuStates, "freq"),
            'home': Home(self.theme, self.player)
        }
        # add callback to rederaw menu item if tuner data is updated
        config.tuner.freq.addValidCallback(functools.partial(self.state_dict['menu'].redrawState, mainMenuStates['freq'], mainMenuStates['freq'].getSurfaceRects()))
        config.tuner.sr.addValidCallback(functools.partial(self.state_dict['menu'].redrawState, mainMenuStates['sr'], mainMenuStates['sr'].getSurfaceRects()))
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

# GUI state for when the menu isnt showing
class Home(rydeplayer.states.gui.States):
    def __init__(self, theme, player):
        super().__init__(theme)
        self.next = 'menu'
        self.player = player
    def cleanup(self):
        None
    def startup(self):
        None
    def get_event(self, event):
        #TODO: add OSD state machine
        if(event == rydeplayer.common.navEvent.SELECT):
            self.osd.activate(3)
        elif(event == rydeplayer.common.navEvent.BACK):
            self.osd.deactivate(3)
        elif(event == rydeplayer.common.navEvent.MUTE):
            self.player.toggleMute()
        elif(event == rydeplayer.common.navEvent.MENU):
            self.done = True

class rydeConfig(object):
    def __init__(self, theme):
        self.ir = ir.irConfig()
        self.gpio = rydeplayer.gpio.gpioConfig()
        self.tuner = longmynd.tunerConfig()
        #important longmynd path defaults
        self.longmynd = type('lmConfig', (object,), {
            'binpath': '/home/pi/longmynd/longmynd',
            'mediapath': '/home/pi/lmmedia',
            'statuspath': '/home/pi/lmstatus',
            'tstimeout': 5000,
            })
        self.bands = {}
        defaultBand = longmynd.tunerBand()
        self.bands[defaultBand] = "None"
        self.presets = {}
        self.shutdownBehavior = rydeplayer.common.shutdownBehavior.APPSTOP
        self.debug = type('debugConfig', (object,), {
            'enableMenu': False,
            'autoplay': True,
            'disableHardwareCodec': True,
            })
        self.configRev = 2
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
                        bandObject = longmynd.tunerBand()
                        if bandObject.loadBand(bandDict):
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
            # parse critical longmynd paths
            if 'longmynd' in config:
                if isinstance(config['longmynd'], dict):
                    if 'binpath' in config['longmynd']:
                        if isinstance(config['longmynd']['binpath'], str):
                            self.longmynd.binpath = config['longmynd']['binpath']
                            # TODO: check this path is valid
                        else:
                            print("Invalid longymnd binary path")
                            perfectConfig = False
                    if 'mediapath' in config['longmynd']:
                        if isinstance(config['longmynd']['mediapath'], str):
                            self.longmynd.mediapath = config['longmynd']['mediapath']
                        else:
                            print("Invalid longymnd media FIFO path")
                            perfectConfig = False
                    if 'statuspath' in config['longmynd']:
                        if isinstance(config['longmynd']['statuspath'], str):
                            self.longmynd.statuspath = config['longmynd']['statuspath']
                        else:
                            print("Invalid longymnd status FIFO path")
                            perfectConfig = False
                    if 'tstimeout' in config['longmynd']:
                        if isinstance(config['longmynd']['tstimeout'], int):
                            self.longmynd.tstimeout = config['longmynd']['tstimeout']
                        else:
                            print("Invalid longmynd TS timeout")
                            perfectConfig = False
                else:
                    print("Invalid longmynd config")
                    perfectConfig = False
            # parse presets
            if 'presets' in config:
                if isinstance(config['presets'], dict):
                    newPresets = {}
                    exsistingPresets = list(self.presets.keys())
                    for presetName in config['presets']:
                        presetDict = config['presets'][presetName]
                        presetObject = longmynd.tunerConfig()
                        if presetObject.loadConfig(presetDict):
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
                defaultPreset = longmynd.tunerConfig()
                if defaultPreset.loadConfig(config['default']):
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
                with open("config.yaml", 'r') as ymlconfigfile:
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
        self.mute = False
        self.muteCallbacks = []

        # setup longmynd
        self.lmMan = longmynd.lmManager(self.config.tuner, self.config.longmynd.binpath, self.config.longmynd.mediapath, self.config.longmynd.statuspath, self.config.longmynd.tstimeout)
        self.config.tuner.addCallbackFunction(self.lmMan.reconfig)

        self.vlcStartup()

        # start ui
        self.app = guiState(self.theme, self.config.shutdownBehavior, self)
        self.app.startup(self.config, {'Restart LongMynd':self.lmMan.restart, 'Force VLC':self.vlcStop, 'Abort VLC': self.vlcAbort})

        # setup ir
        self.irMan = ir.irManager(self.stepSM, self.config.ir)

        # setup gpio
        self.gpioMan = rydeplayer.gpio.gpioManager(self.stepSM, self.config.gpio)

        # start longmynd
        self.lmMan.start()
        print("Ready")
        self.monotonicState = 0;

    def start(self):
        quit = False
        # main event loop
        while not quit:
            # need to regen every loop, lm stdout handler changes on lm restart
            fds = self.irMan.getFDs() + self.lmMan.getFDs() + self.gpioMan.getFDs()
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

    def toggleMute(self):
        self.setMute(not self.mute)

    def shutdown(self, behaviour):
        del(self.playbackState)
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
        elif(fd in self.lmMan.getFDs()):
            self.lmMan.handleFD(fd)
        elif(fd in self.gpioMan.getFDs()):
            quit = self.gpioMan.handleFD(fd)
        return quit

    def updateState(self):
        # update playback state
        if(self.lmMan.isRunning()):
            if(self.lmMan.isLocked()):
                self.playbackState.setState(rydeplayer.states.playback.States.LOCKED)
                newMonoState = self.lmMan.getMonotonicState()

                if self.monotonicState != newMonoState:
                    self.monotonicState = newMonoState
                    self.vlcStop()
                    print("Param Restart")
                if self.vlcPlayer.get_state() not in [vlc.State.Playing, vlc.State.Opening] and self.config.debug.autoplay:
                    self.vlcPlay()
                self.gpioMan.setRXgood(True)
            else:
                self.playbackState.setState(rydeplayer.states.playback.States.NOLOCK)
                if self.config.debug.autoplay:
                    self.vlcStop()
                self.gpioMan.setRXgood(False)
        else:
            self.playbackState.setState(rydeplayer.states.playback.States.NOLONGMYND)
            if self.config.debug.autoplay:
                self.vlcStop()
#               print("parsed:"+str(vlcMedia.is_parsed()))
            self.gpioMan.setRXgood(False)
        self.vlcPlayer.audio_set_mute(self.mute)
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
        self.lmMan.remedia()
#        self.lmMan.restart()
        self.vlcStartup()

    def vlcStartup(self):
        vlcArgs = ''
        displaySize = pydispmanx.getDisplaySize()
        vlcArgs += '--width '+str(displaySize[0])+' --height '+str(displaySize[1])+' '
        if self.config.debug.disableHardwareCodec:
            vlcArgs += '--codec ffmpeg '
#        vlcArgs += '--gain 4 --alsa-audio-device hw:CARD=Headphones,DEV=0 '
        print(vlcArgs)
        self.vlcInstance = vlc.Instance(vlcArgs)

        self.vlcPlayer = self.vlcInstance.media_player_new()
        self.vlcMedia = self.vlcInstance.media_new_fd(self.lmMan.getMediaFd().fileno())

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("Config File", help="YAML config file to try and load. Default: config.yaml", nargs='?', default='config.yaml')
    args = parser.parse_args()
    print(args)
    newplayer = player('config.yaml')
    newplayer.start()

if __name__ == '__main__':
    run()
