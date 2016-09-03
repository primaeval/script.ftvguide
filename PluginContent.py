#!/usr/bin/python
# -*- coding: utf-8 -*-

from xml.dom.minidom import parse
from operator import itemgetter
from Utils import *
import random
import source as src
import sys

def getPluginListing(action,refresh=None):
    #general method to get a widget/plugin listing and check cache etc.
    count = 0
    allItems = []
    limit = None
    cachePath = os.path.join(ADDON_DATA_PATH,"widgetcache-%s.json" %action)
    #get params for each action
    if "PVR" in action:
        type = "episodes"
        refresh = WINDOW.getProperty("widgetreload2")

    cacheStr = "tvguide-%s-%s" %(action,refresh)
    
    #set widget content type
    xbmcplugin.setContent(int(sys.argv[1]), type)
    
    #try to get from cache first...
    cache = WINDOW.getProperty(cacheStr).decode("utf-8")
    if cache:
        allItems = eval(cache)
            
    #Call the correct method to get the content from json when no cache
    if not allItems:

        allItems = eval(action)(limit)
        allItems = prepareListItems(allItems)
        #save the cache
        WINDOW.setProperty(cacheStr, repr(allItems).encode("utf-8"))
    
    #fill that listing...
    for item in allItems:
        if item.get("file"):
            liz = createListItem(item)
            isFolder = item.get("isFolder",False)
            xbmcplugin.addDirectoryItem(int(sys.argv[1]), item['file'], liz, isFolder)
            count += 1
            if count == limit:
                break
    
    #end directory listing
    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))
    
def addDirectoryItem(label, path, folder=True):
    li = xbmcgui.ListItem(label, path=path)
    li.setThumbnailImage("special://home/addons/script.tvguide.fullscreen2/icon.png")
    li.setArt({"fanart":"special://home/addons/script.tvguide.fullscreen2/fanart.jpg"})
    li.setArt({"landscape":"special://home/addons/script.tvguide.fullscreen2/fanart.jpg"})
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[0]), url=path, listitem=li, isFolder=folder)

def doMainListing(mode=""):
    xbmcplugin.setContent(int(sys.argv[0]), 'files')

    #pvr nodes

    addDirectoryItem("Channels Now", "plugin://script.skin.tvguide.fullscreen2/?action=pvrchannels")

    xbmcplugin.endOfDirectory(int(sys.argv[0]))
    
def PVRCHANNELS(limit):
    count = 0
    allItems = []
    database = None
    try:
        database = src.Database()
        database.initialize(None, None)

    except src.SourceNotConfiguredException:
        return
    if database:
        # get now channels
        programList = database.getNowList()

        for program in programList:
            item = []
            channelname = program.channel.title
            channellogo = program.channel.logo

            url = database.getStreamUrl(program.channel)

            item["title"] = program.title
            item["file"] = url
            item["channellogo"] = channellogo
            item["icon"] = channellogo
            item["channel"] = channelname
            item["label2"] = channelname
            item["cast"] = None
            item["starttime"] = program.startDate
            item["endtime"] = program.endDate
            item["fanart"] = program.imageLarge
            item["thumbnail"] = program.imageSmall
            allItems.append(item)
        
    #return result
    return allItems