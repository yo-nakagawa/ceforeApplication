#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2018, National Institute of Information and Communications
# Technology (NICT). All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of the NICT nor the names of its contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE NICT AND CONTRIBUTORS "AS IS" AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE NICT OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.

import libcefpyco as cefpyco
import os
from sys import stderr, version_info
from contextlib import contextmanager

INTEREST_TYPE_REGULAR = 0x0000 # CefC_T_OPT_REGULAR
INTEREST_TYPE_SYMBOLIC = 0x0002 # CefC_T_LONGLIFE

class CcnPacketInfo:
    PacketTypeInterest = 0x00
    PacketTypeData = 0x01
    PacketFlagSymbolic = 0x01
    PacketFlagLonglife = 0x02
    
    def __init__(self, res):
        self.is_succeeded = (res[0] >= 0 and res[3] > 0)
        self.is_failed = not self.is_succeeded
        self.version = res[1]
        self.type = res[2]
        self.actual_data_len = res[3]
        self.name = res[4]
        self.name_len = res[5]
        self.chunk_num = res[6] if res[6] >= 0 else None
        self.end_chunk_num = res[7] if res[7] >= 0 else None
        self.flags = res[8]
        self.payload = res[9]
        self.payload_len = res[10]
    
    @property
    def is_interest(self):
        return self.is_succeeded and (self.type == self.PacketTypeInterest)
    
    @property
    def is_regular_interest(self):
        return (self.is_succeeded and 
            (self.type == self.PacketTypeInterest) and
            not self.is_symbolic)
    
    @property
    def is_symbolic_interest(self):
        return (self.is_succeeded and 
            (self.type == self.PacketTypeInterest) and
            self.is_symbolic)
    
    @property
    def is_data(self):
        return self.is_succeeded and (self.type == self.PacketTypeData)

    @property
    def is_symbolic(self):
        return (
            ((self.flags & self.PacketFlagSymbolic) != 0) and 
            ((self.flags & self.PacketFlagLonglife) != 0)
        )
    
    @property
    def packet_type(self):
        if self.is_succeeded:
            if self.is_symbolic_interest:
                return "Symbolic-interest"
            elif self.is_interest:
                return "Interest"
            elif self.is_data:
                return "Data"
        return "Unknown (id: %08x)" % self.type
    
    @property
    def payload_s(self):
        if self.payload:
            return self.payload.decode("raw_unicode_escape", errors="replace")
        else:
            return ""
    
    def __repr__(self):
        if self.is_failed:
            return "Info: Failed to receive"
        ret = (
            "Info: Succeeded in receiving {0} packet with "
            "name '{1}'"
            ).format(
                self.packet_type,
                self.name
            )
        if self.chunk_num is not None:
            ret += " (#chunk: {0})".format(self.chunk_num)
        if self.payload_len > 0:
            ret += " and payload '{0}' ({1} Bytes)".format(
                self.payload, self.payload_len)
        return ret

class CefpycoHandle(object):
    def __init__(self, enable_log=True):
        self.handler = None
        self.enable_log = enable_log
        if version_info.major == 2:
            self.sequence_of_chars_type = unicode
            self.sequence_of_bytes_type = str
        else:
            self.sequence_of_chars_type = str
            self.sequence_of_bytes_type = bytes

    def log(self, msg, force=False):
        if self.enable_log or force: stderr.write("[cefpyco] %s\n" % msg)
    
    def begin(self, ceforedir=None, portnum=9896):
        if self.handler is not None:
            raise Exception("This handler has been already used.")
        if ceforedir is None:
            self.cefdir = "%s/cefore" % (
                os.environ.get("CEFORE_DIR") or "/usr/local")
        else:
            self.cefdir = ceforedir
        self.portnum = portnum
        self.log("Configure directory is %s" % self.cefdir)
        self.handler = cefpyco.begin(
            self.portnum, self.cefdir, 1 if self.enable_log else 0)
    
    def end(self):
        if self.handler is not None:
            cefpyco.end(self.handler)
            self.handler = None
    
    def send_interest(self, name, 
        # chunk_num=-1, 
        chunk_num=0, 
        symbolic_f=INTEREST_TYPE_REGULAR,
        hop_limit=32, lifetime=4000):
        cefpyco.send_interest(self.handler, name, 
            chunk_num=chunk_num, 
            symbolic_f=symbolic_f, 
            hop_limit=hop_limit, 
            lifetime=lifetime)
    
    def send_symbolic_interest(self, name, 
        hop_limit=32, lifetime=10000):
        cefpyco.send_interest(self.handler, name, 
            chunk_num=-1, 
            symbolic_f=INTEREST_TYPE_SYMBOLIC, 
            hop_limit=hop_limit, 
            lifetime=lifetime)
    
    def _convert_to_bytes_like_object(self, payload):
        payloadtype = type(payload)
        if payloadtype is self.sequence_of_chars_type:
            return payload.encode("raw_unicode_escape")
        elif payloadtype is self.sequence_of_bytes_type:
            return payload
        else:
            return str(payload).encode("raw_unicode_escape")

    def send_data(self, name, payload, 
            chunk_num=-1, end_chunk_num=-1,
            hop_limit=32, expiry=36000000, cache_time=-1):
        payload = self._convert_to_bytes_like_object(payload)
        cefpyco.send_data(self.handler, name, 
            payload, len(payload), 
            chunk_num=chunk_num, 
            end_chunk_num=end_chunk_num, 
            hop_limit=hop_limit, 
            expiry=expiry, 
            cache_time=cache_time)
    
    def register(self, name):
        cefpyco.register(self.handler, name, is_reg=1)
        
    def deregister(self, name):
        cefpyco.register(self.handler, name, is_reg=0)
        
    def register_pit(self, name):
        cefpyco.register_for_pit(self.handler, name, is_reg=1)
        
    def deregister_pit(self, name):
        cefpyco.register_for_pit(self.handler, name, is_reg=0)
        
    def receive(self, error_on_timeout=False, timeout_ms=1000):
        i = 1 if error_on_timeout else 0
        res = cefpyco.receive(self.handler, i, timeout_ms)
        return CcnPacketInfo(res)

@contextmanager
def create_handle(ceforedir=None, portnum=9896, enable_log=True):
    h = None
    try:
        h = CefpycoHandle(enable_log)
        h.begin(ceforedir, portnum)
        yield h
    except Exception as e:
        # print(e)
        raise e
    finally:
        if h: h.end()