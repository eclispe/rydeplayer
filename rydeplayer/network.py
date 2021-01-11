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

import socket, json
import rydeplayer.longmynd

class networkConfig(object):
    def __init__(self):
        self.enabled = False
        self.bindaddr = 'localhost'
        self.port = 8765

    # parse a dict containing the network config
    def loadConfig(self, config):
        perfectConfig = True
        if isinstance(config, dict):
            if 'bindaddr' in config:
                if isinstance(config['bindaddr'], str):
                    self.bindaddr = config['bindaddr']
                else:
                    print("Invalid bind ip address, skipping")
                    perfectConfig = False
            else:
                print("No bind ip address, skipping")
                perfectConfig = False
            if 'port' in config:
                if isinstance(config['port'], int):
                    if config['port'] <= 65535 and config['port']>0: # max TCP port, (2^16)-1
                        self.port = config['port']
                    else:
                        print("Invalid port number, out of range, skipping")
                        perfectConfig = False
                else:
                    print("Invalid port number, not an int, skipping")
                    perfectConfig = False
        else:
            print("Network config invalid, ignoring")
        if perfectConfig:
            self.enabled = True
        return perfectConfig


class networkManager(object):
    def __init__(self, config):
        self.config = config
        self.activeConnections = dict()
        if self.config.network.enabled:
            self.mainSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.mainSock.setblocking(0)
            self.mainSock.bind((self.config.network.bindaddr, self.config.network.port))
            self.mainSock.listen(5)
            self.commands = {"getBands":self.getBands, "setTune":self.setTune}

    def getFDs(self):
        if self.config.network.enabled:
            return [self.mainSock] + list(self.activeConnections.keys())
        else:
            return []

    def handleFD(self, fd):
        if fd is self.mainSock:
            connection, addr = fd.accept()
            connection.setblocking(0)
            self.activeConnections[connection] = bytes()
        elif fd in self.activeConnections:
            dataStr = fd.recv(1024)
            if dataStr:
                self.activeConnections[fd]+=dataStr
                if len(self.activeConnections[fd]) > (100*1024): # 100kB command limit
                    del self.activeConnections[fd]
                    fd.close()
                    print("Network command too long, chopping")
                try:
                    data = json.loads(self.activeConnections[fd])
                except json.JSONDecodeError:
                    return
                result = self.processCommand(data)
                fd.send(bytes(json.dumps(result),encoding="utf-8"))
            else:
                del self.activeConnections[fd]
                fd.close()

    def processCommand(self, command):
        result = {'success': True}
        print(command)
        print(type(command))
        if not isinstance(command,dict):
            result['success'] = False
            result['error'] = "JSON is not an object"
            return result
        if 'request' not in command:
            result['success'] = False
            result['error'] = "Request type missing"
            return result
        if command['request'] not in self.commands.keys():
            result['success'] = False
            result['error'] = "Invalid request type"
            return result
        if self.commands[command['request']] is not None:
            commandResult = self.commands[command['request']](command)
            return {**result, **commandResult}
        return result

    def getBands(self, command):
        result = {'success':True, 'bands': {}}
        for band, bandName in self.config.bands.items():
            result['bands'][bandName]=band.dumpBand()
        return result

    def setTune(self, command):
        result = {'success':True}
        if 'tune' not in command:
            result['success'] = False
            result['error'] = "No tune details"
            return result
        newconfig = rydeplayer.longmynd.tunerConfig()
        if not newconfig.loadConfig(command['tune'],list(self.config.bands.keys())):
            result['success'] = False
            result['error'] = "Parse Failure, see Ryde log for details"
            return result
        self.config.tuner.setConfigToMatch(newconfig)
        return result
