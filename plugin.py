#!/usr/bin/python
# -*- coding: utf-8 -*-
import PluginContent as plugincontent
import Utils as utils
import urlparse
import xbmc,xbmcgui,xbmcplugin
enableProfiling = False

class Main:
    
    def __init__(self):
        
        xbmc.log('started loading pluginentry')
        
        #get params
        action = None
        params = urlparse.parse_qs(sys.argv[2][1:].decode("utf-8"))
        utils.logMsg("Parameter string: %s" % sys.argv[2])
        
        if params:        
            path=params.get("path",None)
            if path: path = path[0]
            action=params.get("action",None)
            if action: action = action[0].upper()
        
        if action:
            #get a widget listing
            refresh=params.get("reload",None)
            if refresh: refresh = refresh[0].upper()
            plugincontent.getPluginListing(action,refresh)
        else:
            #do plugin main listing...
            plugincontent.doMainListing()


if (__name__ == "__main__"):
    try:
        Main()
    except Exception as e:
        utils.logMsg("Error in plugin.py --> " + str(e),0)
        xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
utils.logMsg('finished loading pluginentry')
