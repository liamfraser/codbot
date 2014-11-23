#!/usr/bin/env python3

# Copyright (c) 2014, Liam Fraser <liam@liamfraser.co.uk>
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of  nor the names of its
#   contributors may be used to endorse or promote products derived from this
#   software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import socket
import re

class Cod4Rcon:
    """
    Based on sniffing traffic because of fuck all documentation
    """
    packet_prefix = bytearray()
    for i in range(0, 4):
        packet_prefix.append(0xff)

    map_list = ["mp_backlot","mp_bloc", "mp_bog", "mp_broadcast",
                "mp_carentan", "mp_cargoship", "mp_citystreets", "mp_convoy",
                "mp_countdown", "mp_crash", "mp_crash_snow", "mp_creek",
                "mp_crossfire", "mp_farm", "mp_killhouse", "mp_overgrown",
                "mp_pipeline", "mp_shipment","mp_showdown", "mp_strike",
                "mp_vacant"]

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server = "cod.liamfraser.co.uk"
        self.port = 28960

        with open('rconpassword', 'r') as f:
            self.rcon_password = f.read().rstrip("\n")

        self.sock.connect((self.server, self.port))
        self._data = None

    def rcon_command(self, cmd):
        out = "rcon {1} {2}".format(self.packet_prefix,
                                    self.rcon_password,
                                    cmd)
        self.sock.send(self.packet_prefix + bytes(out, 'utf-8'))
        self.recv()

    def set_map(self, m):
        if m in self.map_list:
            self.rcon_command("map {0}".format(m))
        else:
            raise Exception("{0} is not a valid map".format(m))

    def recv(self, timeout=1):
        self.sock.settimeout(timeout)
        data = bytes()

        # Recv blocks until there is no more data and we time out
        timed_out = False
        while not timed_out:
            try:
                data += self.sock.recv(4096)
            except socket.error:
                timed_out = True
        
        # Remove the first each instance of bytes of 0xff
        data = data.replace(self.packet_prefix, bytearray())
        self._data = data.decode()
        #print(self._data)

    def dvarlist(self):
        self.rcon_command("dvarlist")

    def get_hardcore(self):
        self.dvarlist()
        
        if 'scr_hardcore "1"' in self._data:
            return True
        
        return False

    def set_hardcore(self, val):
        if val:
            self.rcon_command("scr_hardcore 1")
        else:
            self.rcon_command("scr_hardcore 0")

    def status(self):
        self.rcon_command("status")
# response is:
# print
# map: mp_bloc
# num score ping guid                             name            lastmsg address               qport rate
# --- ----- ---- -------------------------------- --------------- ------- --------------------- ----- -----
#   0     0    8 0a4e05362fd573a6becfceb489228845 liamfraser^7            0 172.17.173.5:28960    -10736 25000

        cur_map = None
        players = []

        for line in self._data.split("\n"):
            line = line.rstrip("\n")

            m = re.search("\d+\s+\d+\s+(CNTCT|\d+)\s+\w+\s+(\w+)", line)
            if m:
                players.append(m.group(2))

            m = re.search("^map: (.*)", line)
            if m:
                cur_map = m.group(1) 

        return cur_map, players

class CodBot:
    def __init__(self):
        self.network = 'irc.freenode.net'
        self.port = 6667
        self.channel = "#cs-york-cod"
        self.user = "CodBot"
        self.rcon = Cod4Rcon()
        self._data = None

    def _send(self, msg):
        self.sock.send(msg.encode('utf-8'))

    def _connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.network, self.port))
        self._send("NICK {0}\r\n".format(self.user))
        self._send("USER {0} {0} {0} {0}\r\n".format(self.user))
        self._send("JOIN {0}\r\n".format(self.channel))

    def _pong(self):
        # Responds to server pings. Necessary to stay on a server
        self._send("PONG :Pong\r\n")

    def say(self, msg):
        self._send("PRIVMSG {0} :{1}\r\n".format(self.channel, msg))

    def match(self, pattern):
        match_str = self._data.rstrip("\r\n")
        m = re.search(pattern, match_str)
        return m

    def get_data(self):
        data = self.sock.recv(4096)
        self._data = data.decode('latin-1')

    def run(self):
        self._connect()

        while True:
            self.get_data()

            if self.match("PING"):
                self._pong()

            if self.match("{0}: hello".format(self.user)):
                self.say("Hello n00bs!")
            
            if self.match("hello {0}".format(self.user)):
                self.say("Hello n00bs!")

            if self.match("{0}:? help".format(self.user)):
                self.say("{0} supports the following commands".format(self.user))
                self.say("help, hello, set_map $map, list_maps, status, set_hardcore [on|off]")

            if self.match("{0}:? list_maps".format(self.user)):
                self.say(", ".join(self.rcon.map_list))
            
            m = self.match("{0}:? set_map ([^\s]+)".format(self.user))
            if m:
                new_map = m.group(1)
                try:
                    self.say("Setting map to {0}".format(new_map))
                    self.rcon.set_map(new_map)
                except Exception as e:
                    self.say("Error: {0}".format(e))
            
            if self.match("{0}:? status".format(self.user)):
                cur_map, players = self.rcon.status()
 
                out = "map: {0}, ".format(cur_map)

                out += "{0} players".format(len(players))
                if len(players) == 1:
                    out = "{0}: {1}".format(out[:-1], ", ".join(players))
                elif len(players) > 1:
                    out = "{0}: {1}".format(out, ", ".join(players))

                if self.rcon.get_hardcore():
                    out += ", game_mode: hardcore"
                else:    
                    out += ", game_mode: core"

                self.say(out)
            
            m = self.match("{0}:? set_hardcore ([^\s]+)".format(self.user))
            if m:
                bool_str = m.group(1)
            
                if bool_str == "on":
                    self.say("Setting hardcore on (starts on next map)")
                    self.rcon.set_hardcore(True)
                elif bool_str == "off":
                    self.say("Setting hardcore off (starts on next map)")
                    self.rcon.set_hardcore(False)
                else:
                    self.say("Invalid hardcore mode: {0}".format(bool_str))

if __name__ == "__main__":
    cb = CodBot()
    cb.run()
