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

import threading, time, socket, os

class sourceWatchdogConfig(object):
    def __init__(self):
        self.minRestartTime = 0.1
        self.maxRestartTime = 300
        self.backoffRate = 2
        self.enabled = True

    # parse a dict containing the source watchdog config
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            self.enabled = True
            minCandidate = self.minRestartTime
            maxCandidate = self.maxRestartTime
            if 'minRestartTime' in config:
                if isinstance(config['minRestartTime'], int):
                    if float(config['minRestartTime']) > 0:
                        minCandidate = float(config['minRestartTime'])
                    else:
                        print("Minimum restart time must be greater than 0, skipping")
                        perfectConfig = False
                elif isinstance(config['minRestartTime'], float):
                    if config['minRestartTime'] > 0:
                        minCandidate = config['minRestartTime']
                    else:
                        print("Minimum restart time must be greater than 0, skipping")
                        perfectConfig = False
                else:
                    print("Invalid minimum restart time, skipping")
                    perfectConfig = False
            else:
                print("No minimum restart time, skipping")
                perfectConfig = False

            if 'maxRestartTime' in config:
                if isinstance(config['minRestartTime'], int):
                    maxCandidate = float(config['maxRestartTime'])
                elif isinstance(config['minRestartTime'], float):
                    maxCandidate = config['maxRestartTime']
                else:
                    print("Invalid maximum restart time, skipping")
                    perfectConfig = False
            else:
                print("No maximum restart time, skipping")
                perfectConfig = False

            if minCandidate <= maxCandidate:
                self.minRestartTime = minCandidate
                self.maxRestartTime = maxCandidate
            else:
                print("Maximum restart time must be at least the minimum restart time, ignoring")
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
        elif config is None:
            self.enabled = False
        else:
            print("Source watchdog config invalid, ignoring")
            perfectConfig = False
        return perfectConfig

class watchdogServiceConfig(object):
    def __init__(self):
        self.serivceInterval = 1
        self.pidPath = "/tmp/rydePlayer.pid"
        self.enabled = True

    # parse a dict containing the watchdog servicing config
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            self.enabled = True
            if 'serviceInterval' in config:
                if isinstance(config['serviceInterval'], int):
                    if float(config['serviceInterval']) > 0:
                        self.serviceInterval = float(config['serviceInterval'])
                    else:
                        print("Watchdog service interval must be greater than 0, skipping")
                        perfectConfig = False
                elif isinstance(config['serviceInterval'], float):
                    if config['serviceInterval'] > 0:
                        self.serviceInterval = config['serviceInterval']
                    else:
                        print("Watchdog service interval must be greater than 0, skipping")
                        perfectConfig = False
                else:
                    print("Invalid watchdog service interval, skipping")
                    perfectConfig = False
            else:
                print("No watchdog service interval, skipping")
                perfectConfig = False
            if 'pidPath' in config:
                if isinstance(config['pidPath'], str):
                    pidDir, pidFile = os.path.split(config['pidPath'])
                    if os.path.isdir(pidDir):
                        if os.access(pidDir, os.W_OK):
                            if pidFile == "":
                                pidFile = "rydePlayer.pid"
                                print("Watchdog PID path is a directory, using rydePlayer.pid as filename")
                            pidPath = os.path.join(pidDir, pidFile)
                            if os.path.exists(pidPath):
                                if os.access(pidPath, os.W_OK):
                                    print("Warning: Watchdog file already exists, file will be reused")
                                    self.pidPath = pidPath;
                                else:
                                    print("Watchdog file directory already exists but is not writable, skipping")
                                    perfectConfig = False
                            else:
                                self.pidPath = pidPath;
                        else:
                            print("Watchdog file directory is not writable, skipping")
                            perfectConfig = False
                    else:
                        print("Watchdog file directory does not exist, skipping")
                        perfectConfig = False
                else:
                    print("Invalid watchdog PID path, skipping")
                    perfectConfig = False
            else:
                print("No watchdog PID path, skipping")
                perfectConfig = False
        elif config is None:
            self.enabled = False
        else:
            print("Service interval config invalid, ignoring")
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
        if self.timer is None and self.config.enabled: # Watchdog not already waiting
            if self.lastAutostart is None or self.delay is None or (self.lastLoaded is not None and self.lastLoaded > self.lastAutostart and (time.monotonic() - self.lastLoaded) > self.delay):
                self.delay = self.config.minRestartTime
            else:
                self.delay = min(self.delay*self.config.backoffRate, self.config.maxRestartTime)
            self.timer = threading.Timer(self.delay, self._timerExpireThread)
            print("Watchdog Starting: "+str(self.delay))
            self.timer.start()

class watchdogService(object):
    def __init__(self, config, pid = None):
        self.config = config
        if config.enabled:
            try:
                with open(config.pidPath, 'w') as pidFile:
                    pidFile.write(str(pid))
            except IOError as e:
                print(e)
            print(config.pidPath)
            self.recvSock, self.sendSock = socket.socketpair()
            self.timer = None
            self.lastService = None
            self.service()

    def getFDs(self):
        if self.config.enabled:
            return [self.recvSock]
        else:
            return []

    def service(self):
        if self.config.enabled:
            if self.lastService is None or(time.monotonic() - self.lastService) > (self.config.serviceInterval*0.75):
                self.lastService = time.monotonic()
                try:
                    os.utime(self.config.pidPath)
                except IOError as e:
                    print(e)
                if self.timer is not None:
                    self.timer.cancel()
                self.timer = threading.Timer(self.config.serviceInterval, self._timerExpireThread)
                self.timer.start()

    def handleFD(self,fd):
        if fd == self.recvSock:
            self.recvSock.recv(1)
            if self.config.enabled:
                self.service()
            else:
                self.timer = None

    def _timerExpireThread(self):
        self.sendSock.send(b'\00')

    def stop(self):
        if self.config.enabled:
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None
            try:
                os.remove(self.config.pidPath)
            except IOError as e:
                print(e)
