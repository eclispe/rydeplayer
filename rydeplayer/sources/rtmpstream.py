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

import enum, os, copy, fcntl, collections, time, socket, threading, queue, librtmp, urllib.parse, datetime, select, string
import rydeplayer.common
import rydeplayer.sources.common

# Container for tuner status data with change callbacks
class tunerStatus(rydeplayer.sources.common.sourceStatus):
    def __init__(self):
        super().__init__()

    def setPIDs(self, audioPid, videoPid):
        audioCodecMap = {
             2:rydeplayer.sources.common.CodecEnum.MP3,
            10:rydeplayer.sources.common.CodecEnum.AAC,
            }
        videoCodecMap = {
            7:rydeplayer.sources.common.CodecEnum.H264,
            8:rydeplayer.sources.common.CodecEnum.H263,
            }
        newPIDs = {}
        if audioPid in audioCodecMap:
            newPIDs['Audio']=audioCodecMap[audioPid]
        elif audioPid is not None:
            newPIDs['Audio']=str(audioPid)+"?"

        if videoPid in videoCodecMap:
            newPIDs['Video']=videoCodecMap[videoPid]
        elif videoPid is not None:
            newPIDs['Video']=str(videoPid)+"?"

        if self.pids != newPIDs:
            self.pids = newPIDs
            self.onChangeFire()
            return True
        else:
            return False

    def setStatusToMatch(self, fromStatus):
        changed = super().setStatusToMatch(fromStatus)
        if changed:
            self.onChangeFire()

# Events from read thread
class eventsFromThread(enum.Enum):
    LOCKED   = enum.auto()
    UNLOCKED = enum.auto()
    TIMEOUT  = enum.auto()
    DATA     = enum.auto()
    ERROR    = enum.auto()

# Commands to read thread
class eventsToThread(enum.Enum):
    STOP = enum.auto()

class rtmpStreamManager(object):
    def __init__(self, config, sourceConfig):
        self.recvSockEvent, self.sendSockEvent = socket.socketpair() # socket for notifying event queue
        self.rtmpReadEventQueue = queue.Queue() # socket for passing metadata events

        self.rtmpReadCommandQueue = queue.Queue() # socket for passing commands to rtmp read thread

        self.stdoutReadfd, self.stdoutWritefd = os.pipe() # a pipe for passing the flv stream

        self.readThread = None
        self.rtmpConnection = None
        self.statelog = [] # log of important things from rtmp stream
        self.rtmplog = [] # a complete metadata output log, for debugging
        self.threadRunning = False
        self.threadLocked = False
        self.activeConfig = config.copyConfig()
        self.lastState = { 'locked':None }
        self.changeRefState = copy.deepcopy(self.lastState)
        self.stateMonotonic = 0
        self.tunerStatus = tunerStatus()
        # state type for the core rtmp state
        self.coreStateType = collections.namedtuple('coreState', ['isRunning', 'isStarted', 'isLocked', 'monotonicState'])
        self.laststart = 0;

    def reconfig(self, config):
        """reconfigures RTMP stream"""
        if(isinstance(config, rydeplayer.sources.common.tunerConfig) and config != self.activeConfig):
            self.activeConfig = config.copyConfig()
            print(self.activeConfig)
            self.restart()
    def waitForMediaHangup(self):
        return True
    def remedia(self):
        pass
    def getMediaFd(self):
        return self.stdoutReadfd
    def getFDs(self):
        return [self.recvSockEvent]
    def getStatus(self):
        return self.tunerStatus
    def handleFD(self, fd):
        """handles a file descriptor that has data to read"""
        fdCallbacks = dict()
        fdCallbacks[self.recvSockEvent] = self.processEvents
        if(fd in fdCallbacks):
            fdCallbacks[fd]()
    def getCoreState(self):
        """gets the core system state in a single call"""
        state = self.coreStateType(self.isRunning(), self.isStarted(), self.isLocked(), self.getMonotonicState())
        return state
    def isStarted(self):
        if(self.readThread != None):
            return self.readThread.is_alive()
        else:
            return False
    def isRunning(self):
        if(self.readThread != None and self.threadRunning):
            return self.readThread.is_alive()
        else:
            return False
    def isLocked(self):
        """returns if rtmp is connected and active"""
        if(self.isRunning()):
            if(self.lastState['locked']):
                return True
            else:
                return False
        else:
            return False
    def getMonotonicState(self):
        return self.stateMonotonic

    # just restart the thread and not the connection
    def _resetThread(self):
        self.threadLocked = False
        self.stdoutReadfd, self.stdoutWritefd = os.pipe() # a pipe for passing the flv stream
        self.readThread.join()
        self.tunerStatus.setStatusToMatch(tunerStatus()) # reset status to defaults
        self.readThread = threading.Thread(target=self._readThreadLoop, args=(self.rtmpConnection, self.stdoutWritefd, self.sendSockEvent, self.rtmpReadEventQueue, self.rtmpReadCommandQueue, self.activeConfig.band.getNetworkTimeout(), self.activeConfig.band.getNetworkTimeout()))
        self.readThread.start()


    def processEvents(self):
        """track the state of the rtmp read from its events"""
        stop = False
        while not self.rtmpReadEventQueue.empty():
            self.recvSockEvent.recv(1)
            eventType, eventData = self.rtmpReadEventQueue.get()
            if eventType == eventsFromThread.LOCKED:
                self.threadLocked = True
                print("Main Locked")
            elif eventType == eventsFromThread.UNLOCKED:
                self._resetThread()
            elif eventType == eventsFromThread.TIMEOUT:
                print("Data timeout")
                self._resetThread()
            elif eventType == eventsFromThread.DATA:
                self.rtmplog.append((datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),eventData))
                packetType, packetBody = eventData
                if packetType in [librtmp.packet.PACKET_TYPE_INFO, librtmp.packet.PACKET_TYPE_INVOKE]:
                    decodedBody = librtmp.amf.decode_amf(packetBody)
                    if packetType == librtmp.packet.PACKET_TYPE_INFO and len(decodedBody)>0 and decodedBody[0] == "onMetaData":
                        audioPid = None
                        videoPid = None
                        for key in decodedBody[1]:
                            if key == "audiocodecid":
                                audioPid = decodedBody[1][key]
                            elif key == "videocodecid":
                                videoPid = decodedBody[1][key]
                        if audioPid is not None or videoPid is not None:
                            self.tunerStatus.setPIDs(audioPid, videoPid)
                    elif packetType == librtmp.packet.PACKET_TYPE_INVOKE and len(decodedBody)>0 and decodedBody[0] == 'onStatus' and decodedBody[3]['code'] == 'NetStream.Play.Start':
                        self.threadRunning = True
                elif packetType == librtmp.packet.PACKET_TYPE_CONTROL:
                    messageType = int.from_bytes(packetBody[:2], byteorder='big')
                    if messageType == 6:
                        print("RTMP - Server Ping: "+packetBody[2:].hex())
            elif eventType == eventsFromThread.ERROR:
                print("RTMPERROR - Main")
                stop = True

            self.lastState['locked'] = self.threadLocked
            if self.lastState != self.changeRefState : # if the signal parameters have changed
                self.stateMonotonic += 1
                self.changeRefState = copy.deepcopy(self.lastState)
        if stop:
            self.stop(True,True)


    def stop(self, dumpOutput = False, waitfirst=False):
        self.tunerStatus.setStatusToMatch(tunerStatus()) # reset status to defaults
        #open a clean buffer ready for the restart
        self.stdoutReadfd, self.stdoutWritefd = os.pipe() # a pipe for passing the flv stream
        if self.readThread is not None:
            if self.readThread.is_alive():
               self.rtmpReadCommandQueue.put((eventsToThread.STOP, None))
            self.readThread.join()

        self.rtmpReadCommandQueue = queue.Queue() # reset rtmp thread queue
        if self.rtmpConnection is not None:
            self.rtmpConnection.close()
        #open a clean buffer ready for the restart
        self.stdoutReadfd, self.stdoutWritefd = os.pipe() # a pipe for passing the flv stream
        self.readThread = None
        self.threadLocked = False
        self.threadRunning = False
        #TODO: parse this and display a meaningful message on screen
        if dumpOutput:
            for logline in self.rtmplog:
                print(logline)
        return None

    def cleanup(self):
        self.recvSockEvent.close()
        self.sendSockEvent.close()

    # thread loop to read RTMP data and put in the read pipe
    def _readThreadLoop(self, conn, wPipeFd, eventSock, eventQueue, commQueue, networkTimeout, networkTimeoutInit):
        if not conn.connected:
            try:
                self.rtmpConnection.connect()
            except librtmp.RTMPError:
                eventQueue.put((eventsFromThread.ERROR, None))
                eventSock.send(b'\00')
                return

        fcntl.fcntl(wPipeFd, fcntl.F_SETFL, os.O_NONBLOCK)
        wPipe = os.fdopen(wPipeFd, mode="bw")
        starttimestamp = 0;
        lastData = None
        lastPacket = time.monotonic()
        while True: # loop until break
            try:
                packet=conn.read_packet()
            except librtmp.RTMPTimeoutError: # timed out reading packet
                packet = None
                if lastData is None:
                    if time.monotonic() - lastPacket > networkTimeoutInit:
                        eventQueue.put((eventsFromThread.ERROR, None))
                        eventSock.send(b'\00')
                        break
                else:
                    if time.monotonic() - lastData > networkTimeout:
                        eventQueue.put((eventsFromThread.TIMEOUT, None))
                        eventSock.send(b'\00')
                        break
            except librtmp.RTMPError:
                packet = None
                eventQueue.put((eventsFromThread.ERROR, None))
                eventSock.send(b'\00')
                break

            if packet is not None:
                conn.handle_packet(packet) # handle packets to keep server happy
                lastPacket = time.monotonic()
                if packet.type in [librtmp.packet.PACKET_TYPE_AUDIO, librtmp.packet.PACKET_TYPE_VIDEO]:
                    # pass on media packets
                    try:
                        self._writePacketToStream(packet, wPipe)
                    except BlockingIOError:
                        packet = None
                        eventQueue.put((eventsFromThread.ERROR, None))
                        eventSock.send(b'\00')
                        break
                    lastData = time.monotonic()
                    if starttimestamp <= 0:
                        starttimestamp = packet.timestamp
                elif packet.type == librtmp.packet.PACKET_TYPE_INFO:
                    # pass on metadata packets
                    eventQueue.put((eventsFromThread.DATA, (packet.type, packet.body))) #pass metadata to source thread
                    eventSock.send(b'\00')
                    if starttimestamp <= 0:
                        starttimestamp = packet.timestamp
                elif packet.type == librtmp.packet.PACKET_TYPE_CONTROL:
                    # check for start/stop(flush) packets
                    messageType = int.from_bytes(packet.body[:2], byteorder='big')
                    eventQueue.put((eventsFromThread.DATA, (packet.type, packet.body))) #pass metadata to source thread
                    eventSock.send(b'\00')
                    if messageType == 0: #start
                        lastData = time.monotonic()
                        wPipe.write(b'FLV\x01\x05\x00\x00\x00\x09\x00\x00\x00\x00')
                        starttimestamp = 0
                        eventQueue.put((eventsFromThread.LOCKED, None))
                        eventSock.send(b'\00')
                    elif messageType == 1: #flush/stop
                        eventQueue.put((eventsFromThread.UNLOCKED, None))
                        eventSock.send(b'\00')
                        break
                else:
                    eventQueue.put((eventsFromThread.DATA, (packet.type, packet.body))) #pass metadata to source thread
                    eventSock.send(b'\00')
            commandRaw = None
            try:
                commandRaw=commQueue.get(False)
            except queue.Empty:
                commandRaw = None
            if commandRaw is not None:
                commOperator, commOperand = commandRaw
                if commOperator == eventsToThread.STOP:
                    break
        try:
            wPipe.close()
        except BlockingIOError:
            eventQueue.put((eventsFromThread.ERROR, None))
            eventSock.send(b'\00')

    # generate flv header from rtmp packet
    def _writePacketToStream(self, packet, stream):
        packetBody = packet.body
        packetOutBytes = bytes()
        packetOutBytes += packet.type.to_bytes(1, byteorder='big')
        packetOutBytes += len(packetBody).to_bytes(3, byteorder='big')
        packetOutBytes += (packet.timestamp & 0xffffff).to_bytes(3, byteorder='big')
        packetOutBytes += ((packet.timestamp & 0xff000000)>>24).to_bytes(1, byteorder='big')
        packetOutBytes += (0).to_bytes(3, byteorder='big')
        packetOutBytes += packetBody
        packetOutBytes += (len(packetBody)+11).to_bytes(4, byteorder='big')
        packetRemaining = packetOutBytes
        while len(packetRemaining) > 0:
            r, w, x = select.select([],[stream],[],1)
            if stream in w:
                try:
                    stream.write(packetRemaining)
                except BlockingIOError as ioErr:
                    packetRemaining = packetRemaining[ioErr.characters_written:]
                else:
                    break
            else:
                raise BlockingIOError()

    def start(self):
        self.laststart = time.monotonic()
        if self.activeConfig.isValid():
            if self.readThread == None :
                self.threadLocked = False
                self.statelog=[]
                self.rtmplog=[]
                self.rtmpConnection = librtmp.RTMP(urllib.parse.urlunsplit(('rtmp', self.activeConfig.band.getDomain(), '', '', '')), app=self.activeConfig.band.getApp(), playpath=self.activeConfig.streamname.getValue(), live=True, timeout=1)
                self.rtmpConnection.set_option('timeout', '1')
                self.readThread = threading.Thread(target=self._readThreadLoop, args=(self.rtmpConnection, self.stdoutWritefd, self.sendSockEvent, self.rtmpReadEventQueue, self.rtmpReadCommandQueue, self.activeConfig.band.getNetworkTimeout(), self.activeConfig.band.getNetworkTimeoutInit()))
                self.readThread.start()
                self.lastState['locked'] = self.threadLocked
                if self.lastState != self.changeRefState : # if the signal parameters have changed
                    self.stateMonotonic += 1
                    self.changeRefState = copy.deepcopy(self.lastState)
            else:
                print("RTMP connection already open")
        else:
            print("Can't start, config invalid")

    def restart(self):
        if self.readThread is not None:
            time.sleep(max(0.5-(time.monotonic()-self.laststart),0))
            self.stop(False, False)
        self.start()

class config(object):

    def loadConfig(self, config):
        perfectConfig = True
        if config is not None:
            print("Invalid RTMP Stream config")
            perfectConfig = False
        return perfectConfig

class band(rydeplayer.sources.common.tunerBand):
    def __init__(self):
        self.source = rydeplayer.sources.common.sources.RTMPSTREAM
        self.domain = None
        self.app = None
        self.networkTimeout = 5
        self.networkTimeoutInit = 25
        super().__init__()
        self.source = rydeplayer.sources.common.sources.RTMPSTREAM


    def dumpBand(self):
        super().dumpBand()
        self.dumpCache['domain'] = self.domain
        self.dumpCache['rtmpapp'] = self.app
        self.dumpCache['networkTimeout'] = self.networkTimeout
        self.dumpCache['networkTimeoutInit'] = self.networkTimeoutInit
        return self.dumpCache

    @classmethod
    def loadBand(cls, config):
        perfectConfig = True
        subClassSuccess, self = super(band, cls).loadBand(config)
        perfectConfig = perfectConfig and subClassSuccess
        if 'domain' in config:
            if isinstance(config['domain'], str):
                self.domain = config['domain']
            else:
                print("RTMP domain invalid, skipping")
                perfectConfig = False
        else:
            print("RTMP domain missing, skipping")
            perfectConfig = False
        if 'rtmpapp' in config:
            if isinstance(config['rtmpapp'], str):
                self.app = config['rtmpapp']
            else:
                print("RTMP app invalid, skipping")
                perfectConfig = False
        else:
            print("RTMP app missing, skipping")
            perfectConfig = False
        if 'networkTimeout' in config:
            if isinstance(config['networkTimeout'], int):
                self.networkTimeout = config['networkTimeout']
            else:
                print("Network timeout invalid, skipping")
                perfectConfig = False
        if 'networkTimeoutInit' in config:
            if isinstance(config['networkTimeoutInit'], int):
                self.networkTimeoutInit = config['networkTimeoutInit']
            else:
                print("Network initialisation timeout invalid, skipping")
                perfectConfig = False
        return (perfectConfig, self)

    def getDomain(self):
        return self.domain

    def getApp(self):
        return self.app

    def getNetworkTimeout(self):
        return self.networkTimeout

    def getNetworkTimeoutInit(self):
        return self.networkTimeoutInit

    # takes a current set of vars and adjusts them to be compatible with this sub band
    def syncVars(self, oldVars):
        # remove keys this class handles and pass all others to the superclass to process
        updated, newVars = super().syncVars({key:oldVars[key] for key in oldVars if key!='streamname'})
        # keep old url if it exsisted or create a new one
        if 'streamname' in oldVars and isinstance(oldVars['streamname'], rydeplayer.sources.common.tunerConfigStr):
            newVars['streamname'] = oldVars['streamname']
            # remove prerequisites from to deleted vars
            removedVars = set(oldVars.keys())-set(newVars.keys())
            if len(removedVars) > 0:
                newVars['streamname'].removePrereqs(removedVars)
                varsUpdated = True
        else:
            validChars = list(string.ascii_lowercase)+list(string.digits)+list("-_ ")
            newVars['streamname'] = rydeplayer.sources.common.tunerConfigStr('', 15, False, validChars, 'Stream Name')
            updated = True
        return (updated, newVars)

    def __eq__(self, other):
        # compare 2 rtmp bands
        if not isinstance(other, self.__class__):
            return False
        else:
            comp = super().__eq__(other) and self.domain == other.domain and self.app == other.app and self.networkTimeout == other.networkTimeout and self.networkTimeoutInit == other.networkTimeoutInit
            return comp

    def __hash__(self):
        return hash((super().__hash__(), self.domain, self.app, self.networkTimeout, self.networkTimeoutInit))

class source(rydeplayer.sources.common.source):
    @classmethod
    def getConfig(cls):
        return config

    @classmethod
    def getBand(cls):
        return band

    @classmethod
    def getNewStatus(cls):
        return tunerStatus

    @classmethod
    def getManager(cls):
        return rtmpStreamManager

    @classmethod
    def getSource(cls, enum):
        if enum == rydeplayer.sources.common.sources.RTMPSTREAM:
            return cls
        else:
            return False
