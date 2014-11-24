#!/usr/bin/env python3

# Copyright (c) 2014, Liam Fraser <liam@liamfraser.co.uk>
# All rights reserved.
#
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

import sys
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

    def __init__(self, dev):
        self.dev = dev
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
        
        # Remove each instance of 4 bytes of 0xff which occur at the start
        # of each rcon packet
        data = data.replace(self.packet_prefix, bytearray())
        self._data = data.decode()
        if self.dev:
            print(self._data)

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
    def __init__(self, mode, name):
        self.dev = False
        if mode == "dev":
            self.dev = True

        self.network = 'irc.freenode.net'
        self.port = 6667
        self.channel = "#cs-york-cod"
        self.user = name
        self.rcon = Cod4Rcon(self.dev)
        self._data = None
        # list of users on the channel
        self._users = []

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

    def run(self):
        self._connect()

        while True:
            data = self.sock.recv(4096)
            # Process data line by line
            for line in data.decode('latin-1').split("\r\n"):
                if self.dev:
                    print(line)

                self._data = line
                self.dispatch()

    def dispatch(self):
        if self.match("PING"):
             self._pong()

        if self.match("PRIVMSG {0} :".format(self.user)):
            # Ignore pms
            return

        if self.match("{0}:? help".format(self.user)):
            self.say("{0} supports the following commands".format(self.user))
            self.say("help, hello, set_map $map, list_maps, status, set_hardcore [on|off], next_map, summon")

        if self.match("{0}:? next_map".format(self.user)):
            self.say("Loading next map")
            self.rcon.rcon_command("map_rotate")

        if self.match("{0}: hello".format(self.user)):
            self.say("Hello n00bs!")
        
        if self.match("hello {0}".format(self.user)):
            self.say("Hello n00bs!")

        if self.match("{0}:? list_maps".format(self.user)):
            self.say(", ".join(self.rcon.map_list))
        
        if self.match("{0}:? summon".format(self.user)):
            self.say("{0} plz".format(", ".join(self._users)))
        
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

        # This is a list of users on the channel
        m = self.match("353 {0} = {1} :{0} (.*)$".format(self.user,
                                                         self.channel))
        if m:
            self._users = []
            user_list = m.group(1).replace("@", "").split()
            for u in user_list:
                # Don't add ourselves to the list. That would be silly
                if u != self.user:
                    self._users.append(u)

            if self.dev:
                print("User list: {0}".format(self._users))

        # Keep track of users leaving and joining
        m = self.match("^\:(.*?)![^\s]+ (PART|JOIN|QUIT)")
        if m:
            user = m.group(1)
            action = m.group(2)

            # Dont track our own user
            if user == self.user:
                return

            if action == "JOIN":
                self._users.append(user)
                self.say("Hi {0}".format(user))
            else:
                # Must be part or quit because of regex
                if user in self._users:
                    self._users.remove(user)
                
            if self.dev:
                print("User list: {0}".format(self._users))
        
        # Keep track of nick changes
        m = self.match("^\:(.*?)![^\s]+ NICK :(.*)$")
        if m:
            old = m.group(1)
            new = m.group(2)

            # Must be part or quit because of regex
            if old in self._users:
                self._users.remove(old)
            self._users.append(new)
                
            if self.dev:
                print("{0} became {1}".format(old, new))
                print("User list: {0}".format(self._users))
        
        # Keep track of kicks
        m = self.match("^\:(.*?)![^\s]+ KICK {0} ([^\s]+)".format(self.channel))
        if m:
            kicker = m.group(1)
            kickee = m.group(2)

            # Must be part or quit because of regex
            if kickee in self._users:
                self._users.remove(kickee)

            self.say("{0} just rekt {1}".format(kicker, kickee))

            if self.dev:
                print("{0} got kicked".format(kickee))

if __name__ == "__main__":
    usage = "Usage: {0} dev|prod".format(sys.argv[0])
    if len(sys.argv) != 2:
        sys.exit(usage)

    mode = sys.argv[1]
    name = ""

    if mode == "dev":
        name = "CodbotDev"
    elif mode == "prod":
        name = "CaptainHaddocko"
    else:
        sys.exit(usage)

    cb = CodBot(mode, name)
    cb.run()
