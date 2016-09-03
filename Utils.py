#!/usr/bin/python
# -*- coding: utf-8 -*-

import xbmcplugin, xbmcgui, xbmc, xbmcaddon, xbmcvfs
import os,sys
import urllib
from traceback import print_exc
from datetime import datetime, timedelta
import _strptime
import time
import datetime as dt
import unicodedata
import urlparse
import xml.etree.ElementTree as xmltree
from xml.dom.minidom import parse
from operator import itemgetter
try:
    from multiprocessing.pool import ThreadPool as Pool
    supportsPool = True
except: supportsPool = False

try:
    import simplejson as json
except:
    import json

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id').decode("utf-8")
ADDON_ICON = ADDON.getAddonInfo('icon').decode("utf-8")
ADDON_NAME = ADDON.getAddonInfo('name').decode("utf-8")
ADDON_PATH = ADDON.getAddonInfo('path').decode("utf-8")
ADDON_VERSION = ADDON.getAddonInfo('version').decode("utf-8")
ADDON_DATA_PATH = xbmc.translatePath("special://profile/addon_data/%s" % ADDON_ID).decode("utf-8")
KODI_VERSION  = int(xbmc.getInfoLabel( "System.BuildVersion" ).split(".")[0])
WINDOW = xbmcgui.Window(10000)
SETTING = ADDON.getSetting
KODILANGUAGE = xbmc.getLanguage(xbmc.ISO_639_1)
sys.path.append(xbmc.translatePath(os.path.join(ADDON_PATH, 'resources', 'lib')).decode('utf-8'))

def logMsg(msg, level = 1):

    if isinstance(msg, unicode):
        msg = msg.encode('utf-8')
    if "exception" in msg.lower() or "error" in msg.lower():
        xbmc.log("TV Guide --> " + msg, level=xbmc.LOGERROR)
        print_exc()
    else:
        xbmc.log("TV Guide --> " + msg, level=xbmc.LOGNOTICE)

def try_encode(text, encoding="utf-8"):
    try:
        return text.encode(encoding,"ignore")
    except:
        return text       

def try_decode(text, encoding="utf-8"):
    try:
        return text.decode(encoding,"ignore")
    except:
        return text       
 
def createListItem(item):
    liz = xbmcgui.ListItem(label=item.get("label",""),label2=item.get("label2",""))
    liz.setProperty('IsPlayable', item.get('IsPlayable','true'))
    liz.setPath(item.get('file'))
    
    nodetype = "Video"
    if item.get("type","") in ["song","album","artist"]:
        nodetype = "Music"
    
    #extra properties
    for key, value in item.get("extraproperties",{}).iteritems():
        liz.setProperty(key, value)
        
    #video infolabels
    if nodetype == "Video":
        infolabels = { 
            "title": item.get("title"),
            "size": item.get("size"),
            "genre": item.get("genre"),
            "year": item.get("year"),
            "top250": item.get("top250"),
            "tracknumber": item.get("tracknumber"),
            "rating": item.get("rating"),
            "playcount": item.get("playcount"),
            "overlay": item.get("overlay"),
            "cast": item.get("cast"),
            "castandrole": item.get("castandrole"),
            "director": item.get("director"),
            "mpaa": item.get("mpaa"),
            "plot": item.get("plot"),
            "plotoutline": item.get("plotoutline"),
            "originaltitle": item.get("originaltitle"),
            "sorttitle": item.get("sorttitle"),
            "duration": item.get("duration"),
            "studio": item.get("studio"),
            "tagline": item.get("tagline"),
            "writer": item.get("writer"),
            "tvshowtitle": item.get("tvshowtitle"),
            "premiered": item.get("premiered"),
            "status": item.get("status"),
            "code": item.get("imdbnumber"),
            "aired": item.get("aired"),
            "credits": item.get("credits"),
            "album": item.get("album"),
            "artist": item.get("artist"),
            "votes": item.get("votes"),
            "trailer": item.get("trailer"),
            "progress": item.get('progresspercentage')
        }
        if item.get("date"): infolabels["date"] = item.get("date")
        if item.get("lastplayed"): infolabels["lastplayed"] = item.get("lastplayed")
        if item.get("dateadded"): infolabels["dateadded"] = item.get("dateadded")
        if item.get("type") == "episode":
            infolabels["season"] = item.get("season")
            infolabels["episode"] = item.get("episode")

        liz.setInfo( type="Video", infoLabels=infolabels)
        #streamdetails
        if item.get("streamdetails"):
            liz.addStreamInfo("video", item["streamdetails"].get("video",{}))
            liz.addStreamInfo("audio", item["streamdetails"].get("audio",{}))
            liz.addStreamInfo("subtitle", item["streamdetails"].get("subtitle",{}))       

    #artwork
    if item.get("art"):
        liz.setArt( item.get("art"))
    if item.get("icon"):
        liz.setIconImage(item.get('icon'))
    if item.get("thumbnail"):
        liz.setThumbnailImage(item.get('thumbnail'))
    return liz

def prepareListItems(items):
    listitems = []
    if supportsPool:
        pool = Pool()
        listitems = pool.map(prepareListItem, items)
        pool.close()
        pool.join()
    else:
        for item in items:
            listitems.append(prepareListItem(item))
    return listitems
    
def prepareListItem(item):
    #fix values returned from json to be used as listitem values
    properties = item.get("extraproperties",{})
    
    #set type
    for idvar in [ ('episode','DefaultTVShows.png'),('tvshow','DefaultTVShows.png'),('movie','DefaultMovies.png'),('song','DefaultAudio.png'),('musicvideo','DefaultMusicVideos.png'),('recording','DefaultTVShows.png'),('album','DefaultAudio.png') ]:
        if item.get(idvar[0] + "id"):
            properties["DBID"] = str(item.get(idvar[0] + "id"))
            if not item.get("type"): item["type"] = idvar[0]
            if not item.get("icon"): item["icon"] = idvar[1]
            break
    
    #general properties
    if item.get('genre') and isinstance(item.get('genre'), list): item["genre"] = " / ".join(item.get('genre'))
    if item.get('studio') and isinstance(item.get('studio'), list): item["studio"] = " / ".join(item.get('studio'))
    if item.get('writer') and isinstance(item.get('writer'), list): item["writer"] = " / ".join(item.get('writer'))
    if item.get('director') and isinstance(item.get('director'), list): item["director"] = " / ".join(item.get('director'))
    if not isinstance(item.get('artist'), list) and item.get('artist'): item["artist"] = [item.get('artist')]
    if not item.get('artist'): item["artist"] = []
    if item.get('type') == "album" and not item.get('album'): item['album'] = item.get('label')
    if not item.get("duration") and item.get("runtime"): item["duration"] = item.get("runtime")
    if not item.get("plot") and item.get("comment"): item["plot"] = item.get("comment")
    if not item.get("tvshowtitle") and item.get("showtitle"): item["tvshowtitle"] = item.get("showtitle")
    if not item.get("premiered") and item.get("firstaired"): item["premiered"] = item.get("firstaired")
    if not properties.get("imdbnumber") and item.get("imdbnumber"): properties["imdbnumber"] = item.get("imdbnumber")
    properties["dbtype"] = item.get("type")
    properties["type"] = item.get("type")
    properties["path"] = item.get("file")

    #cast
    listCast = []
    listCastAndRole = []
    if item.get("cast"):
        for castmember in item.get("cast"):
            if castmember:
                listCast.append( castmember["name"] )
                listCastAndRole.append( (castmember["name"], castmember["role"]) )
    item["cast"] = listCast
    item["castandrole"] = listCastAndRole
    
    if item.get("season") and item.get("episode"):
        properties["episodeno"] = "s%se%s" %(item.get("season"),item.get("episode"))
    if item.get("resume"):
        properties["resumetime"] = str(item['resume']['position'])
        properties["totaltime"] = str(item['resume']['total'])
        properties['StartOffset'] = str(item['resume']['position'])
    
    #streamdetails
    if item.get("streamdetails"):
        streamdetails = item["streamdetails"]
        audiostreams = streamdetails.get('audio',[])
        videostreams = streamdetails.get('video',[])
        subtitles = streamdetails.get('subtitle',[])
        if len(videostreams) > 0:
            stream = videostreams[0]
            height = stream.get("height","")
            width = stream.get("width","")
            if height and width:
                resolution = ""
                if width <= 720 and height <= 480: resolution = "480"
                elif width <= 768 and height <= 576: resolution = "576"
                elif width <= 960 and height <= 544: resolution = "540"
                elif width <= 1280 and height <= 720: resolution = "720"
                elif width <= 1920 and height <= 1080: resolution = "1080"
                elif width * height >= 6000000: resolution = "4K"
                properties["VideoResolution"] = resolution
            if stream.get("codec",""):   
                properties["VideoCodec"] = str(stream["codec"])
            if stream.get("aspect",""):
                properties["VideoAspect"] = str(round(stream["aspect"], 2))
            item["streamdetails"]["video"] = stream
        
        #grab details of first audio stream
        if len(audiostreams) > 0:
            stream = audiostreams[0]
            properties["AudioCodec"] = stream.get('codec','')
            properties["AudioChannels"] = str(stream.get('channels',''))
            properties["AudioLanguage"] = stream.get('language','')
            item["streamdetails"]["audio"] = stream
        
        #grab details of first subtitle
        if len(subtitles) > 0:
            properties["SubtitleLanguage"] = subtitles[0].get('language','')
            item["streamdetails"]["subtitle"] = subtitles[0]
    else:
        item["streamdetails"] = {}
        item["streamdetails"]["video"] =  {'duration': item.get('duration',0)}
    
    #additional music properties
    if item.get('album_description'):
        properties["Album_Description"] = item.get('album_description')
    
    #pvr properties
    if item.get("starttime"):
        starttime = getLocalDateTimeFromUtc(item['starttime'])
        endtime = getLocalDateTimeFromUtc(item['endtime'])
        properties["StartTime"] = starttime[1]
        properties["StartDate"] = starttime[0]
        properties["EndTime"] = endtime[1]
        properties["EndDate"] = endtime[0]
        fulldate = starttime[0] + " " + starttime[1] + "-" + endtime[1]
        properties["Date"] = fulldate
        properties["StartDateTime"] = starttime[0] + " " + starttime[1]
        item["date"] = starttime[0]
    if item.get("channellogo"): 
        properties["channellogo"] = item["channellogo"]
        properties["channelicon"] = item["channellogo"]
    if item.get("episodename"): properties["episodename"] = item.get("episodename","")
    if item.get("channel"): properties["channel"] = item.get("channel","")
    if item.get("channel"): properties["channelname"] = item.get("channel","")
    if item.get("channel"): item["label2"] = item.get("channel","")
    
    #artwork
    art = item.get("art",{})
    if item.get("type") == "episode":
        if not art.get("fanart") and art.get("tvshow.fanart"):
            art["fanart"] = art.get("tvshow.fanart")
        if not art.get("poster") and art.get("tvshow.poster"):
            art["poster"] = art.get("tvshow.poster")
        if not art.get("clearlogo") and art.get("tvshow.clearlogo"):
            art["clearlogo"] = art.get("tvshow.clearlogo")
        if not art.get("landscape") and art.get("tvshow.landscape"):
            art["landscape"] = art.get("tvshow.landscape")
    if not art.get("fanart") and item.get('fanart'): art["fanart"] = item.get('fanart')
    if not art.get("thumb") and item.get('thumbnail'): art["thumb"] = getCleanImage(item.get('thumbnail'))
    if not art.get("thumb") and art.get('poster'): art["thumb"] = getCleanImage(item.get('poster'))
    if not art.get("thumb") and item.get('icon'): art["thumb"] = getCleanImage(item.get('icon'))
    if not item.get("thumbnail") and art.get('thumb'): item["thumbnail"] = art["thumb"]
    
    #return the result
    item["extraproperties"] = properties
    return item

def getLocalDateTimeFromUtc(timestring):
    try:
        systemtime = xbmc.getInfoLabel("System.Time")
        utc = datetime.fromtimestamp(time.mktime(time.strptime(timestring, '%Y-%m-%d %H:%M:%S')))
        epoch = time.mktime(utc.timetuple())
        offset = datetime.fromtimestamp (epoch) - datetime.utcfromtimestamp(epoch)
        correcttime = utc + offset
        if "AM" in systemtime or "PM" in systemtime:
            return (correcttime.strftime("%Y-%m-%d"),correcttime.strftime("%I:%M %p"))
        else:
            return (correcttime.strftime("%d-%m-%Y"),correcttime.strftime("%H:%M"))
    except:
        logMsg("ERROR in getLocalDateTimeFromUtc --> " + timestring, 0)
        
        return (timestring,timestring)

def double_urlencode(text):
   text = single_urlencode(text)
   text = single_urlencode(text)
   return text

def single_urlencode(text):
   blah = urllib.urlencode({'blahblahblah':try_encode(text)})
   blah = blah[13:]
   return blah

def getCleanImage(image):
    if image and "image://" in image:
        image = image.replace("image://","").replace("music@","")
        image=urllib.unquote(image.encode("utf-8"))
        if image.endswith("/"):
            image = image[:-1]
    return try_decode(image)

def normalize_string(text):
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.replace('(', "")
    text = text.replace(')', "")
    text = text.replace("\"","")
    text = text.strip()
    text = text.rstrip('.')
    text = unicodedata.normalize('NFKD', try_decode(text))
    return text
    
def recursiveDelete(path):
    success = True
    path = try_encode(path)
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        success = xbmcvfs.delete(os.path.join(path,file))
    for dir in dirs:
        success = recursiveDelete(os.path.join(path,dir))
    success = xbmcvfs.rmdir(path)
    return success 

def addToZip(src, zf, abs_src):
    dirs, files = xbmcvfs.listdir(src)
    for file in files:
        file = file.decode("utf-8")
        logMsg("zipping " + file)
        file = xbmc.translatePath( os.path.join(src, file) ).decode("utf-8")
        absname = os.path.abspath(file)
        arcname = absname[len(abs_src) + 1:]
        try:
            #newer python can use unicode for the files in the zip
            zf.write(absname, arcname)
        except:
            #older python version uses utf-8 for filenames in the zip
            zf.write(absname.encode("utf-8"), arcname.encode("utf-8"))
    for dir in dirs:
        addToZip(os.path.join(src,dir),zf,abs_src)
    return zf
        
def zip(src, dst):
    import zipfile
    src = try_decode(src)
    dst = try_decode(dst)
    zf = zipfile.ZipFile("%s.zip" % (dst), "w", zipfile.ZIP_DEFLATED)
    abs_src = os.path.abspath(xbmc.translatePath(src).decode("utf-8"))
    zf = addToZip(src,zf,abs_src)
    zf.close()
    
def unzip(zip_file,path):
    import shutil
    import zipfile
    zip_file = try_decode(zip_file)
    path = try_decode(path)
    logMsg("START UNZIP of file %s  to path %s " %(zipfile,path))
    f = zipfile.ZipFile(zip_file, 'r')
    for fileinfo in f.infolist():
        filename = fileinfo.filename
        filename = try_decode(filename)
        logMsg("unzipping " + filename)
        if "\\" in filename: xbmcvfs.mkdirs(os.path.join(path,filename.rsplit("\\", 1)[0]))
        elif "/" in filename: xbmcvfs.mkdirs(os.path.join(path,filename.rsplit("/", 1)[0]))
        filename = os.path.join(path,filename)
        logMsg("unzipping " + filename)
        try:
            #newer python uses unicode
            outputfile = open(filename, "wb")
        except:
            #older python uses utf-8
            outputfile = open(filename.encode("utf-8"), "wb")
        #use shutil to support non-ascii formatted files in the zip
        shutil.copyfileobj(f.open(fileinfo.filename), outputfile)
        outputfile.close()
    f.close()
    logMsg("UNZIP DONE of file %s  to path %s " %(zipfile,path))
     
def listFilesInPath(path, allFilesList=None):
    #used for easy matching of studio logos
    if not allFilesList: 
        allFilesList = {}
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        file = file.decode("utf-8")
        name = file.split(".png")[0].lower()
        if not allFilesList.has_key(name):
            allFilesList[name] = path + file
    for dir in dirs:
        dirs2, files2 = xbmcvfs.listdir(os.path.join(path,dir)+os.sep)
        for file in files2:
            file = file.decode("utf-8")
            dir = dir.decode("utf-8")
            name = dir + "/" + file.split(".png")[0].lower()
            if not allFilesList.has_key(name):
                if "/" in path:
                    sep = "/"
                else:
                    sep = "\\"
                allFilesList[name] = path + dir + sep + file
    
    #return the list
    return allFilesList
   
def getDataFromCacheFile(file):
    data = {}
    try:
        if xbmcvfs.exists(file):
            f = xbmcvfs.File(file, 'r')
            text =  f.read().decode("utf-8")
            f.close()
            if text: data = eval(text)   
    except Exception as e:
        logMsg("ERROR in getDataFromCacheFile for file %s --> %s" %(file,str(e)), 0)
    return data
      
def saveDataToCacheFile(file,data):
    #safety check: does the config directory exist?
    if not xbmcvfs.exists(ADDON_DATA_PATH + os.sep):
        xbmcvfs.mkdirs(ADDON_DATA_PATH)
    try:            
        str_data = repr(data).encode("utf-8")
        f = xbmcvfs.File(file, 'w')
        f.write(str_data)
        f.close()
    except Exception as e:
        logMsg("ERROR in saveDataToCacheFile for file %s --> %s" %(file,str(e)), 0)

def getCompareString(string,optionalreplacestring=""):
    #strip all kinds of chars from a string to be used in compare actions
    string = try_encode(string)
    string = string.lower().replace(".","").replace(" ","").replace("-","").replace("_","").replace("'","").replace("`","").replace("’","").replace("_new","").replace("new_","")
    if optionalreplacestring: string = string.replace(optionalreplacestring.lower(),"")
    string = try_decode(string)
    string = normalize_string(string)
    return string
    
def intWithCommas(x):
    try:
        x = int(x)
        if x < 0:
            return '-' + intWithCommas(-x)
        result = ''
        while x >= 1000:
            x, r = divmod(x, 1000)
            result = ",%03d%s" % (r, result)
        return "%d%s" % (x, result)
    except: return ""
    
