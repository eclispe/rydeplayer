import socket, json

# Ryde network location
host = 'localhost'
port = 8765

# get bands
getBandsReq = {'request':'getBands'}
bandsSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
bandsSocket.connect((host, port))
bandsSocket.sendall(bytes(json.dumps(getBandsReq), encoding="utf-8"))
bandsResp = bandsSocket.recv(1024)
bandsSocket.close()
parsedBandsResp = json.loads(bandsResp)
        
# tune to QO-100 becon
band = parsedBandsResp['bands']['LNB Low'] # use returned band named "LNB Low"
#band = {'lofreq': 9750000, 'loside': 'LOW', 'pol': 'HORIZONTAL', 'port': 'TOP', 'gpioid': 0} # manually define a badn
setTuneReq = {'request':'setTune', 'tune':{'band':band, 'freq':10491500, 'sr':1500}}
tuneSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tuneSocket.connect((host, port))
tuneSocket.sendall(bytes(json.dumps(setTuneReq), encoding="utf-8"))
tuneResp = tuneSocket.recv(1024)
tuneSocket.close()

print(tuneResp)

