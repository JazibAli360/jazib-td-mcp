# Jazib MCP for TouchDesigner -- WebSocket DAT callbacks (Text DAT /jazib_mcp/callbacks).
# Everything is forwarded to the handlers module (td/handlers.py). Keep this file tiny; ASCII only.
# Edits here need the install line rerun in TD (handlers.py edits only need the `reload` command).


def _h():
    return op('handlers').module


def onConnect(dat):
    _h().on_connect(dat)
    return


def onDisconnect(dat):
    _h().on_disconnect(dat)
    return


def onReceiveText(dat, rowIndex, message):
    _h().on_text(dat, message)
    return


def onReceiveBinary(dat, contents):
    _h().on_binary(dat, contents)
    return


def onReceivePing(dat, contents):
    _h().on_ping(dat, contents)
    return


def onReceivePong(dat, contents):
    _h().on_pong(dat, contents)
    return


def onMonitorMessage(dat, message):
    return
