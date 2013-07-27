#!/usr/bin/python

# Python program that emulates ChromeCast device

from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol
import tornado.ioloop
import tornado.web
import tornado.websocket
import threading
import string
import argparse
import signal
import logging
from textwrap import dedent
import sys

yt_status = dict(state="stopped", link="")
cc_status = dict(state="stopped", link="")
pm_status = dict(state="stopped", link="")
gm_status = dict(state="stopped", link="")
friendlyName = "Mopidy"

class SSDP(DatagramProtocol):
    SSDP_ADDR = '239.255.255.250'
    SSDP_PORT = 1900
    MS = """HTTP/1.1 200 OK\r
LOCATION: http://$ip:8008/ssdp/device-desc.xml\r
CACHE-CONTROL: max-age=1800\r
CONFIGID.UPNP.ORG: 7337\r
BOOTID.UPNP.ORG: 7337\r
USN: uuid:3e1cc7c0-f4f3-11e2-b778-0800200c9a66::urn:dial-multiscreen-org:service:dial:1\r
ST: urn:dial-multiscreen-org:service:dial:1\r
\r
"""

    def __init__(self, iface):
        self.iface = iface
        self.transport = reactor.listenMulticast(
            self.SSDP_PORT, self, listenMultiple=True)
        self.transport.setLoopbackMode(1)
        self.transport.joinGroup(self.SSDP_ADDR, interface=iface)

    def stop(self):
        self.transport.leaveGroup(self.SSDP_ADDR, interface=self.iface)
        self.transport.stopListening()

    def datagramReceived(self, datagram, address):
        if "urn:dial-multiscreen-org:service:dial:1" in datagram and "M-SEARCH" in datagram:
            data =string.Template(dedent(self.MS)).substitute(ip=self.iface)
            self.transport.write(data, address)

class LEAP(tornado.web.RequestHandler):

    service = None
    ip = None

    def prepare(self):
        self.ip = self.request.host

    def _response(self, data):
        self.set_header("Content-Type", "application/xml; charset=UTF-8")
        self.set_header("Cache-control", "no-cache, must-revalidate, no-store")
        self.set_header("Etag", "")
        self.finish(self._toXML(data))

    def post(self):
        self.set_status(201, "Created")
        self.set_header("Location", self._getLocation(self.__class__.__name__))

    def _getLocation(self, app):
        return "http://%s/apps/%s/run" % (self.ip, app )

    def _toXML(self, data):
        return string.Template(dedent(self.service)).substitute(data)

    @staticmethod
    def toInfo(service, data):
        return string.Template(dedent(service)).substitute(data)

class ChromeCast(LEAP):
    service = """<service xmlns="urn:chrome.google.com:cast">
        <name>ChromeCast</name>
        <options allowStop="true"/>
        <activity-status>
            <description>Experimental Mopidy sink</description>
            <image src="http://www.mopidy.com/media/images/penguin_speakers.jpg"/>
        </activity-status>
        <servicedata>
            <protocols>
                <protocol>video_playback</protocol>
                <protocol>audio_playback</protocol>
            </protocols>
        </servicedata>
        <state>$state</state>
        $link
    </service>
    """

    def get(self):
        global cc_status
        self._response(cc_status)

    def post(self):
        global cc_status
        super(ChromeCast, self).post()
        cc_status = dict(state="running", link="""<link rel="run" href="run"/>""")
        self._response(cc_status)

    def delete(self):
        global cc_status
        cc_status = dict(state="stopped", link="")
        self._response(cc_status)

class YouTube(LEAP):
    service = """<service xmlns="urn:dial-multiscreen-org:schemas:dial">
        <name>YouTube</name>
        <options allowStop="true"/>
        <state>$state</state>
        $link
    </service>
    """

    def get(self):
        global yt_status
        self._response(yt_status)

    def post(self):
        global yt_status
        super(YouTube, self).post()
        yt_status = dict(state="running", link="""<link rel="run" href="run"/>""")
        self._response(yt_status)

    def delete(self):
        global yt_status
        yt_status = dict(state="stopped", link="")
        self._response(yt_status)

class PlayMovies(LEAP):
    service = """<service xmlns="urn:dial-multiscreen-org:schemas:dial">
        <name>PlayMovies</name>
        <options allowStop="true"/>
        <state>$state</state>
        $link
    </service>
    """

    def get(self):
        global pm_status
        self._response(pm_status)

    def post(self):
        global pm_status
        super(PlayMovies, self).post()
        pm_status = dict(state="running", link="""<link rel="run" href="run"/>""")
        self._response(pm_status)

    def delete(self):
        global pm_status
        pm_status = dict(state="stopped", link="")
        self._response(pm_status)

class GoogleMusic(LEAP):
    service = """<service xmlns="urn:dial-multiscreen-org:schemas:dial">
        <name>GoogleMusic</name>
        <options allowStop="true"/>
        <state>$state</state>
        $link
    </service>
    """

    def get(self):
        global gm_status
        self._response(gm_status)

    def post(self):
        global gm_status
        super(GoogleMusic, self).post()
        gm_status = dict(state="running", link="""<link rel="run" href="run"/>""")
        self._response(gm_status)

    def delete(self):
        global gm_status
        gm_status = dict(state="stopped", link="")
        self._response(gm_status)

class DeviceHandler(tornado.web.RequestHandler):

    device = """<?xml version="1.0" encoding="utf-8"?>
    <root xmlns="urn:schemas-upnp-org:device-1-0" xmlns:r="urn:restful-tv-org:schemas:upnp-dd">
      <specVersion>
        <major>1</major>
        <minor>0</minor>
      </specVersion>
      <URLBase>/</URLBase>
      <device>
        <deviceType>urn:schemas-upnp-org:device:tvdevice:1</deviceType>
        <friendlyName>$friendlyName</friendlyName>
        <manufacturer>Google Inc.</manufacturer>
        <modelName>ChromeCast</modelName>
        <UDN>uuid:3e1cc7c0-f4f3-11e2-b778-0800200c9a66</UDN>
        
        <serviceList>
        <service>
          <serviceType>urn:schemas-upnp-org:service:tvcontrol:1</serviceType>
          <serviceId>urn:upnp-org:serviceId:tvcontrol1</serviceId>
          <controlURL>/upnp/control/tvcontrol1</controlURL>
          <eventSubURL>/upnp/event/tvcontrol1</eventSubURL>
          <SCPDURL>/tvcontrolSCPD.xml</SCPDURL>
        </service>
        $services
        </serviceList>
      </device>
    </root>"""

    def get(self):
        self.add_header("Application-URL","http://%s/apps" % self.request.host)
        self.set_header("Content-Type", "application/xml; charset=UTF-8")
        self.set_header("Cache-control", "no-cache")
        gservice = "\n".join( [
            LEAP.toInfo(ChromeCast.service, cc_status),
            LEAP.toInfo(YouTube.service, yt_status),
            LEAP.toInfo(PlayMovies.service, pm_status),
            LEAP.toInfo(GoogleMusic.service, gm_status),
        ])
        self.write(string.Template(dedent(self.device)).substitute(dict(services=gservice, friendlyName=friendlyName )))

class WebSocketCast(tornado.websocket.WebSocketHandler):

    def open(self):
        logging.info("WebSocket opened")

    def on_message(self, message):
        logging.info("ws: %s" % message)

    def on_close(self):
        logging.info("WebSocket opened")

class HTTPThread(threading.Thread):
   
    def run(self):

        self.application = tornado.web.Application([
            (r"/ssdp/device-desc.xml", DeviceHandler),
            (r"/apps/ChromeCast", ChromeCast),
            (r"/apps/YouTube", YouTube),
            (r"/apps/PlayMovies", PlayMovies),
            (r"/apps/GoogleMusic", GoogleMusic),
            (r"/connection", WebSocketCast),
            (r"/apps", DeviceHandler),
        ])
        self.application.listen(8008)
        tornado.ioloop.IOLoop.instance().start()
    
    def shutdown(self, ):
        logging.info('Stopping HTTP server')
        reactor.callFromThread(reactor.stop)
        logging.info('Stopping DIAL server')
        tornado.ioloop.IOLoop.instance().stop()

    def sig_handler(self, sig, frame):
        tornado.ioloop.IOLoop.instance().add_callback(self.shutdown)
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument('iface', help='Interface you want to bind to (for example 192.168.1.22)')
    parser.add_argument('--name', help='Friendly name for this device')
    args = parser.parse_args()

    if args.name:
        friendlyName = args.name
        logging.info("Service name is %s" % friendlyName)

    server = HTTPThread()
    server.start()

    signal.signal(signal.SIGTERM, server.sig_handler)
    signal.signal(signal.SIGINT, server.sig_handler)

    def LeapUPNPServer():
        logging.info("Listening on %s" % args.iface)
        sobj = SSDP(args.iface)
        reactor.addSystemEventTrigger('before', 'shutdown', sobj.stop)

    reactor.callWhenRunning(LeapUPNPServer)
    reactor.run()
