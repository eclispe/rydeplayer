#    Ryde Player provides a on screen interface and video player for Longmynd compatible tuners.
#    Copyright © 2022 Tim Clark
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

import threading, time, socket

class sourceWatchdogConfig(object):
    def __init__(self):
        self.minRestartTime = 0.1
        self.maxRestartTime = 300
        self.backoffRate = 2

    # parse a dict containing the source watchdog config
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            if 'minRestartTime' in config:
                if isinstance(config['minRestartTime'], int):
                    self.minRestartTime = float(config['minRestartTime'])
                elif isinstance(config['minRestartTime'], float):
                    self.minRestartTime = config['minRestartTime']
                else:
                    print("Invalid minimum restart time, skipping")
                    perfectConfig = False
            else:
                print("No minimum restart time, skipping")
                perfectConfig = False

            if 'maxRestartTime' in config:
                if isinstance(config['minRestartTime'], int):
                    if self.minRestartTime <= float(config['maxRestartTime']):
                        self.maxRestartTime = float(config['maxRestartTime'])
                    else:
                        print("Maximum restart time is smaller than minimum restart time, skipping")
                        perfectConfig = False
                elif isinstance(config['minRestartTime'], float):
                    if self.minRestartTime <= config['maxRestartTime']:
                        self.maxRestartTime = config['maxRestartTime']
                    else:
                        print("Maximum restart time is smaller than minimum restart time, skipping")
                        perfectConfig = False
                else:
                    print("Invalid maximum restart time, skipping")
                    perfectConfig = False
            else:
                print("No maximum restart time, skipping")
                perfectConfig = False

            if 'backoffRate' in config:
                if isinstance(config['backoffRate'], int):
                    if float(config['backoffRate']) >= 1:
                        self.backoffRate = float(config['backoffRate'])
                    else:
                        print("Invalid backoff rate, must be at least 1, ignoring")
                        perfectConfig = False
                elif isinstance(config['backoffRate'], float):
                    if config['backoffRate'] >= 1:
                        self.backoffRate = config['backoffRate']
                    else:
                        print("Invalid backoff rate, must be at least 1, ignoring")
                        perfectConfig = False
                else:
                    print("Invalid backoff rate, skipping")
                    perfectConfig = False
            else:
                print("No backoff rate, skipping")
                perfectConfig = False

        else:
            print("Source watchdog config invalid, ignoring")
            perfectConfig = False
        return perfectConfig

class sourceWatchdog(object):
    def __init__(self, config, action = None):
        self.config = config
        self.lastAutostart = None
        self.lastLoaded = None
        self.delay = None
        self.timer = None
        self.recvSock, self.sendSock = socket.socketpair()
        self.action = action

    def getFDs(self):
        return [self.recvSock]

    def handleFD(self,fd):
        if fd == self.recvSock:
            self._timerExpire()

    def _timerExpire(self):
        self.recvSock.recv(1)
        self.timer = None
        self.lastAutostart = time.monotonic()
        if self.action is not None:
            print("Watchdog Fired")
            self.action()

    def _timerExpireThread(self):
        self.sendSock.send(b'\00')

    def reset(self, newConfig):
        self.lastAutostart = None
        self.lastLoaded = None
        self.delay = None
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer = None

    def service(self):
        self.cancel() # if you are servicing it you shouldn't still be timing
        if self.lastAutostart is not None and ( self.lastLoaded is None or self.lastLoaded < self.lastAutostart):
            self.lastLoaded = time.monotonic()

    def fault(self):
        if self.timer is None: # Watchdog not already waiting
            if self.lastAutostart is None or self.delay is None or (self.lastLoaded is not None and self.lastLoaded > self.lastAutostart and (time.monotonic() - self.lastLoaded) > self.delay):
                self.delay = self.config.minRestartTime
            else:
                self.delay = min(self.delay*self.config.backoffRate, self.config.maxRestartTime)
            self.timer = threading.Timer(self.delay, self._timerExpireThread)
            print("Watchdog Starting: "+str(self.delay))
            self.timer.start()
