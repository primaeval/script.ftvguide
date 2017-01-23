#
#      Copyright (C) 2014 Tommy Winther
#      http://tommy.winther.nu
#
#      Modified for FTV Guide (09/2014 onwards)
#      by Thomas Geppert [bluezed] - bluezed.apps@gmail.com
#
#      Modified for TV Guide Fullscreen (2016)
#      by primaeval - primaeval.dev@gmail.com
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this Program; see the file LICENSE.txt.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#
import traceback
import datetime
import thread
import threading
import time
import re
import os
import urllib
import subprocess
import xbmc
import xbmcgui
import xbmcvfs
import colors
import requests
import pickle
import json
import base64
from PIL import Image, ImageOps
import source as src
from notification import Notification
from autoplay import Autoplay
from autoplaywith import Autoplaywith
from strings import *
from rpc import RPC
import utils
import ActionEditor

import streaming

DEBUG = False

MODE_EPG = 'EPG'
MODE_QUICK_EPG = 'QUICKEPG'
MODE_TV = 'TV'
MODE_OSD = 'OSD'
MODE_OSD_BIG = 'OSD_BIG'
MODE_LASTCHANNEL = 'LASTCHANNEL'

COMMAND_ACTIONS = ActionEditor.getCommandActions()

ACTION_LEFT = 1
ACTION_RIGHT = 2
ACTION_UP = 3
ACTION_DOWN = 4
ACTION_PAGE_UP = 5
ACTION_PAGE_DOWN = 6
ACTION_SELECT_ITEM = 7
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_SHOW_INFO = 11
ACTION_STOP = 13
ACTION_NEXT_ITEM = 14
ACTION_PREV_ITEM = 15
ACTION_SHOW_CODEC = 27
ACTION_SHOW_FULLSCREEN = 36
ACTION_DELETE_ITEM = 80
ACTION_MENU = 163
ACTION_LAST_PAGE = 160
ACTION_RECORD = 170

ACTION_CREATE_BOOKMARK = 96

ACTION_PAUSE = 12
ACTION_PLAY = 68
ACTION_PLAYER_FORWARD = 77
ACTION_PLAYER_PLAY = 79
ACTION_PLAYER_PLAYPAUSE = 229
ACTION_PLAYER_REWIND = 78

ACTION_MOUSE_WHEEL_UP = 104
ACTION_MOUSE_WHEEL_DOWN = 105
ACTION_MOUSE_MOVE = 107

KEY_NAV_BACK = 92
KEY_CONTEXT_MENU = 117
KEY_HOME = 159
KEY_ESC = 61467

REMOTE_0 = 58
REMOTE_1 = 59
REMOTE_2 = 60
REMOTE_3 = 61
REMOTE_4 = 62
REMOTE_5 = 63
REMOTE_6 = 64
REMOTE_7 = 65
REMOTE_8 = 66
REMOTE_9 = 67

ACTION_JUMP_SMS2 = 142
ACTION_JUMP_SMS3 = 143
ACTION_JUMP_SMS4 = 144
ACTION_JUMP_SMS5 = 145
ACTION_JUMP_SMS6 = 146
ACTION_JUMP_SMS7 = 147
ACTION_JUMP_SMS8 = 148
ACTION_JUMP_SMS9 = 149



CHANNELS_PER_PAGE = int(ADDON.getSetting('channels.per.page'))

HALF_HOUR = datetime.timedelta(minutes=30)

if ADDON.getSetting('skin.source') == "0":
    SKIN = ADDON.getSetting('skin')
    SKIN_PATH = ADDON.getAddonInfo('path')
else:
    SKIN = ADDON.getSetting('skin.user')
    SKIN_PATH = xbmc.translatePath("special://profile/addon_data/script.tvguide.fullscreen/")

def log(what):
    xbmc.log(repr(what))

def timedelta_total_seconds(timedelta):
    return (
        timedelta.microseconds + 0.0 +
        (timedelta.seconds + timedelta.days * 24 * 3600) * 10 ** 6) / 10 ** 6

def debug(s):
    if DEBUG: xbmc.log(str(s), xbmc.LOGDEBUG)

def remove_formatting(label):
    label = re.sub(r"\[/?[BI]\]",'',label)
    label = re.sub(r"\[/?COLOR.*?\]",'',label)
    return label

class Point(object):
    def __init__(self):
        self.x = self.y = 0

    def __repr__(self):
        return 'Point(x=%d, y=%d)' % (self.x, self.y)


class EPGView(object):
    def __init__(self):
        self.top = self.left = self.right = self.bottom = self.width = self.cellHeight = 0


class ControlAndProgram(object):
    def __init__(self, control, program):
        self.control = control
        self.program = program


class TVGuide(xbmcgui.WindowXML):
    C_MAIN_DATE_LONG = 3999
    C_MAIN_DATE = 4000
    C_MAIN_TITLE = 7020
    C_MAIN_TIME = 7021
    C_MAIN_DESCRIPTION = 7022
    if ADDON.getSetting('program.image.scale') == 'true':
        C_MAIN_IMAGE = 7027
    else:
        C_MAIN_IMAGE = 7023
    C_MAIN_LOGO = 7024
    C_MAIN_CHANNEL = 7025
    C_MAIN_PROGRESS = 7026
    C_MAIN_CURRENT_CATEGORY = 7028
    C_MAIN_TIMEBAR = 4100
    C_MAIN_LOADING = 4200
    C_MAIN_LOADING_PROGRESS = 4201
    C_MAIN_LOADING_TIME_LEFT = 4202
    C_MAIN_LOADING_CANCEL = 4203
    C_MAIN_MOUSE_CONTROLS = 4300
    C_MAIN_MOUSE_HOME = 4301
    C_MAIN_MOUSE_LEFT = 4302
    C_MAIN_MOUSE_UP = 4303
    C_MAIN_MOUSE_DOWN = 4304
    C_MAIN_MOUSE_RIGHT = 4305
    C_MAIN_MOUSE_HOME_BIG = 44301
    C_MAIN_MOUSE_LEFT_BIG = 44302
    C_MAIN_MOUSE_UP_BIG = 44303
    C_MAIN_MOUSE_DOWN_BIG = 44304
    C_MAIN_MOUSE_RIGHT_BIG = 44305
    C_MAIN_MOUSE_EXIT = 4306
    C_MAIN_MOUSE_MENU = 4307
    C_MAIN_MOUSE_CATEGORIES = 4308
    C_MAIN_MOUSE_PIP = 4309
    C_MAIN_MOUSE_NOW = 4310
    C_MAIN_MOUSE_NEXT = 4311
    C_MAIN_MOUSE_SEARCH = 4312
    C_MAIN_MOUSE_FIRST = 4313
    C_MAIN_MOUSE_CHANNEL_NUMBER = 4314
    C_MAIN_MOUSE_STOP = 4315
    C_MAIN_MOUSE_FAVOURITES = 4316
    C_MAIN_MOUSE_MINE1 = 4317
    C_MAIN_MOUSE_NEXT_DAY = 4318
    C_MAIN_MOUSE_PREV_DAY = 4319
    C_MAIN_MOUSE_OSD_BIG = 4320
    C_MAIN_BACKGROUND = 4600
    C_MAIN_HEADER = 4601
    C_MAIN_FOOTER = 4602
    C_MAIN_EPG = 5000
    C_MAIN_EPG_VIEW_MARKER = 5001
    C_MAIN_PIP = 5002
    C_MAIN_VIDEO = 5003
    C_QUICK_EPG = 10000
    C_QUICK_EPG_VIEW_MARKER = 10001
    C_QUICK_EPG_MOUSE_CONTROLS = 10300
    C_QUICK_EPG_DATE = 14000
    C_QUICK_EPG_TITLE = 17020
    C_QUICK_EPG_TIME = 17021
    C_QUICK_EPG_DESCRIPTION = 17022
    C_QUICK_EPG_LOGO = 17024
    C_QUICK_EPG_CHANNEL = 17025
    C_QUICK_EPG_TIMEBAR = 14100
    C_QUICK_EPG_HEADER = 14601
    C_QUICK_EPG_FOOTER = 14602
    C_MAIN_OSD = 6000
    C_MAIN_OSD_BIG = 66000
    C_MAIN_OSD_BIG_CHANNEL_LOGO = 66004
    C_MAIN_OSD_BIG_CHANNEL_IMAGE = 66006
    C_MAIN_OSD_BIG_PROGRESS = 66011
    C_MAIN_OSD_TITLE = 6001
    C_MAIN_OSD_TIME = 6002
    C_MAIN_OSD_DESCRIPTION = 6003
    C_MAIN_OSD_CHANNEL_LOGO = 6004
    C_MAIN_OSD_CHANNEL_TITLE = 6005
    C_MAIN_OSD_CHANNEL_IMAGE = 6006
    C_MAIN_OSD_PROGRESS = 6011
    C_MAIN_OSD_PLAY = 6012
    C_NEXT_OSD_DESCRIPTION = 6007
    C_NEXT_OSD_TITLE = 6008
    C_NEXT_OSD_TIME = 6009
    C_NEXT_OSD_CHANNEL_IMAGE = 6010
    C_MAIN_OSD_MOUSE_CONTROLS = 6300
    C_MAIN_VIDEO_BACKGROUND = 5555
    C_MAIN_VIDEO_PIP = 6666
    C_MAIN_CAT_BACKGROUND = 7000
    C_MAIN_CAT_QUIT = 7003
    C_MAIN_CATEGORY = 7004
    C_MAIN_PROGRAM_CATEGORIES = 7005
    C_MAIN_ACTIONS = 7100
    C_MAIN_LAST_PLAYED = 8000
    C_MAIN_LAST_PLAYED_TITLE = 8001
    C_MAIN_LAST_PLAYED_TIME = 8002
    C_MAIN_LAST_PLAYED_DESCRIPTION = 8003
    C_MAIN_LAST_PLAYED_CHANNEL_LOGO = 8004
    C_MAIN_LAST_PLAYED_CHANNEL_TITLE = 8005
    C_MAIN_LAST_PLAYED_CHANNEL_IMAGE = 8006
    C_MAIN_LAST_PLAYED_PROGRESS = 8011
    C_NEXT_LAST_PLAYED_DESCRIPTION = 8007
    C_NEXT_LAST_PLAYED_TITLE = 8008
    C_NEXT_LAST_PLAYED_TIME = 8009
    C_NEXT_LAST_PLAYED_CHANNEL_IMAGE = 8010
    C_MAIN_LAST_PLAYED_MOUSE_CONTROLS = 8300
    C_UP_NEXT = 9000
    C_MAIN_UP_NEXT_TITLE = 9001
    C_MAIN_UP_NEXT_TIME = 9002
    C_MAIN_UP_NEXT_DESCRIPTION = 9003
    C_MAIN_UP_NEXT_CHANNEL_LOGO = 9004
    C_MAIN_UP_NEXT_CHANNEL_TITLE = 9005
    C_MAIN_UP_NEXT_CHANNEL_IMAGE = 9006
    C_MAIN_UP_NEXT_PROGRESS = 9011
    C_NEXT_UP_NEXT_DESCRIPTION = 9007
    C_NEXT_UP_NEXT_TITLE = 9008
    C_NEXT_UP_NEXT_TIME = 9009
    C_NEXT_UP_NEXT_CHANNEL_IMAGE = 9010
    C_MAIN_UP_NEXT_TIME_REMAINING = 9012

    def __new__(cls):
        return super(TVGuide, cls).__new__(cls, 'script-tvguide-main.xml', SKIN_PATH, SKIN)

    def __init__(self):
        super(TVGuide, self).__init__()

        #self.actions = [["Seach","Action(Number4)",r"button_search.png"]]
        #self.saveActions()
        self.loadActions()
        self.tryingToPlay = False
        self.notification = None
        self.autoplay = None
        self.autoplaywith = None
        self.redrawingEPG = False
        self.redrawingQuickEPG = False
        self.isClosing = False
        self.controlAndProgramList = list()
        self.quickControlAndProgramList = list()
        self.ignoreMissingControlIds = list()
        self.channelIdx = 0
        self.focusPoint = Point()
        self.focusPoint.x = 0
        self.focusPoint.y = 0
        self.epgView = EPGView()
        self.quickEpgView = EPGView()
        self.quickChannelIdx = 0
        self.quickFocusPoint = Point()

        self.player = xbmc.Player()
        self.database = None
        self.tvdb_urls = {}
        self.loadTVDBImages()

        self.mode = MODE_EPG
        self.channel_number_input = False
        self.channel_number = ""
        self.currentChannel = None
        s = ADDON.getSetting('last.channel')
        if s:
            (id, title, lineup, logo, streamUrl, visible, weight) = json.loads(s)
            self.lastChannel = utils.Channel(id, title, lineup, logo, streamUrl, visible, weight)
        else:
            self.lastChannel = None
        self.lastProgram = None
        self.currentProgram = None
        self.focusedProgram = None
        self.quickEpgShowInfo = False

        f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','rb')
        lines = f.read().splitlines()
        f.close()
        categories = set()
        for line in lines:
            if "=" not in line:
                continue
            name,cat = line.split('=')
            categories.add(cat)
        categories = sorted(categories)
        self.categories = categories
        if ADDON.getSetting('categories.remember') == 'false':
            self.category = ""
        else:
            self.category = ADDON.getSetting('category')
            if self.category not in self.categories:
                self.category = ""
        self.cat_index = 0
        self.action_index = 0

        self.osdEnabled = False
        self.osdBigEnabled = False
        self.osdEnabled = ADDON.getSetting('enable.osd') == 'true' and ADDON.getSetting(
            'alternative.playback') != 'true'
        self.osdBigEnabled = ADDON.getSetting('enable.osd') == 'true' and ADDON.getSetting(
            'alternative.playback') != 'true'
        self.upNextEnabled = False
        self.upNextEnabled = ADDON.getSetting('enable.nextup') == 'true'
        self.upNextTime = int(ADDON.getSetting('nextup.time'))
        self.upNextShowTimeEnabled = False
        self.upNextShowTimeEnabled = ADDON.getSetting('enable.nextup.showTime') == 'true'
        self.upNextShowTime = int(ADDON.getSetting('nextup.showTime'))
        self.alternativePlayback = ADDON.getSetting('alternative.playback') == 'true'
        self.osdChannel = None
        self.osdProgram = None
        self.lastOsdProgram = None

        # find nearest half hour
        self.viewStartDate = datetime.datetime.today()
        self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                 seconds=self.viewStartDate.second)

        self.quickViewStartDate = datetime.datetime.today()
        self.quickViewStartDate -= datetime.timedelta(minutes=self.quickViewStartDate.minute % 30,
                                                 seconds=self.quickViewStartDate.second)

    def loadTVDBImages(self):
        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/tvdb.pickle'
        if xbmcvfs.exists(file_name):
            f = open(xbmc.translatePath(file_name),'rb')
            if f:
                try:
                    self.tvdb_urls = pickle.load(f)
                    if len(self.tvdb_urls) > 1000:
                        k = self.tvdb_urls.keys()
                        k.reverse()
                        while len(self.tvdb_urls) > 1000:
                            self.tvdb_urls.pop(k.pop(),None)
                except: pass

    def getControl(self, controlId):
        if not controlId:
            return None
        try:
            return super(TVGuide, self).getControl(controlId)
        except Exception as detail:
            #log(traceback.print_stack())
            #xbmc.log("EXCEPTION: (script.tvguide.fullscreen) TVGuide.getControl %s" % detail, xbmc.LOGERROR)
            if controlId in self.ignoreMissingControlIds:
                return None
            if not self.isClosing:
                self.close()
            return None

    def close(self):
        if not self.isClosing:
            self.isClosing = True
            if self.player.isPlaying():
                if ADDON.getSetting('stop.on.exit') == "true":
                    self.player.stop()

            f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/tvdb.pickle','wb')
            try:
                pickle.dump(self.tvdb_urls,f)
            except:
                pass
            f.close()

            file_name = 'special://profile/addon_data/script.tvguide.fullscreen/custom_stream_urls_autosave.ini'
            xbmcvfs.copy(file_name,file_name+".last")
            f = xbmcvfs.File(file_name,'wb')
            if self.database:
                stream_urls = self.database.getCustomStreamUrls()
                for (name,stream) in stream_urls:
                    write_str = "%s=%s\n" % (name,stream)
                    f.write(write_str.encode("utf8"))
                f.close()

            if self.database:
                self.database.close(super(TVGuide, self).close)
            else:
                super(TVGuide, self).close()

    def onInit(self):
        self.has_cat_bar = self.getControl(self.C_MAIN_CATEGORY) != None
        self.has_action_bar = self.getControl(self.C_MAIN_ACTIONS) != None

        if self.has_action_bar:
            self.setControlVisible(self.C_MAIN_ACTIONS, ADDON.getSetting('action.bar') == 'true')

        if ADDON.getSetting('epg.video.pip') == 'true':
            self.setControlVisible(self.C_MAIN_PIP,True)
            self.setControlVisible(self.C_MAIN_VIDEO,False)
        else:
            self.setControlVisible(self.C_MAIN_PIP,False)
            self.setControlVisible(self.C_MAIN_VIDEO,True)

        self._hideControl(self.C_MAIN_OSD_MOUSE_CONTROLS)
        self._hideControl(self.C_QUICK_EPG_MOUSE_CONTROLS)
        self._hideControl(self.C_MAIN_LAST_PLAYED_MOUSE_CONTROLS)
        self._hideControl(self.C_MAIN_MOUSE_CONTROLS, self.C_MAIN_OSD)
        self._hideControl(self.C_MAIN_MOUSE_CONTROLS, self.C_MAIN_OSD_BIG)
        self._hideControl(self.C_MAIN_LAST_PLAYED)
        self._hideControl(self.C_UP_NEXT)
        self._hideControl(self.C_QUICK_EPG)
        self._showControl(self.C_MAIN_EPG, self.C_MAIN_LOADING)
        self.setControlLabel(self.C_MAIN_LOADING_TIME_LEFT, strings(BACKGROUND_UPDATE_IN_PROGRESS))
        self.setFocusId(self.C_MAIN_LOADING_CANCEL)

        control = self.getControl(self.C_MAIN_EPG_VIEW_MARKER)
        if control:
            left, top = control.getPosition()
            self.epgView.left = left
            self.epgView.top = top
            self.epgView.right = left + control.getWidth()
            self.epgView.bottom = top + control.getHeight()
            self.epgView.width = control.getWidth()
            self.epgView.cellHeight = int(control.getHeight() / float(CHANNELS_PER_PAGE))

        control = self.getControl(self.C_QUICK_EPG_VIEW_MARKER)
        if control:
            left, top = control.getPosition()
            self.quickFocusPoint.x = left
            self.quickFocusPoint.y = top
            self.quickEpgView.left = left
            self.quickEpgView.top = top
            self.quickEpgView.right = left + control.getWidth()
            self.quickEpgView.bottom = top + control.getHeight()
            self.quickEpgView.width = control.getWidth()
            self.quickEpgView.cellHeight = int(control.getHeight() / float(3))

        if self.database:
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
        else:
            try:
                self.database = src.Database()
            except src.SourceNotConfiguredException:
                self.onSourceNotConfigured()
                self.close()
                return
            self.database.setCategory(self.category)
            self.database.initialize(self.onSourceInitialized, self.isSourceInitializationCancelled)


        self.streamingService = streaming.StreamsService(ADDON)

        self.updateTimebar()

        programprogresscontrol = self.getControl(self.C_MAIN_PROGRESS)
        if programprogresscontrol:
            pos = programprogresscontrol.getPosition()
            format = xbmc.getRegion('time')
            if pos == [1130,530] and format.endswith('p'):
                programprogresscontrol.setPosition(1060,530)
                programprogresscontrol.setWidth(200)

        self.setControlVisible(self.C_MAIN_IMAGE,True)

    def playShortcut(self):
        self.channel_number_input = False
        self.viewStartDate = datetime.datetime.today()
        self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                 seconds=self.viewStartDate.second)
        if ADDON.getSetting('channel.shortcut') == '2':
            channelList = self.database.getChannelList(onlyVisible=True,all=False)
            for i in range(len(channelList)):
                if self.channel_number == channelList[i].id:
                     self.channelIdx = i
                     break
        else:
            self.channelIdx = int(self.channel_number) - 1
        self.channel_number = ""
        self.getControl(9999).setLabel(self.channel_number)

        behaviour = int(ADDON.getSetting('channel.shortcut.behaviour'))
        if (behaviour == 2) or (behaviour == 1 and self.mode != MODE_EPG):
            self._hideOsdOnly()
            self._hideQuickEpg()
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            xbmc.executebuiltin('Action(Select)')
        else:
            self._hideOsdOnly()
            self._hideQuickEpg()
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

    def onAction(self, action):
        #log((action.getId(),action.getButtonCode()))
        debug('Mode is: %s' % self.mode)

        self._hideControl(self.C_UP_NEXT)

        if action.getId() in COMMAND_ACTIONS["STOP"]:
            self.tryingToPlay = False
            self._hideOsdOnly()
            self._hideOsdBigOnly()
            self._hideQuickEpg()

            self.currentChannel = None
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                     seconds=self.viewStartDate.second)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            self.setControlVisible(self.C_MAIN_IMAGE,True)

        if (ADDON.getSetting('channel.shortcut') != '0'):
            digit = None
            if ADDON.getSetting('channel.shortcut.direct') == 'true' and not self.channel_number_input:
                code = action.getButtonCode() - 61488
                action_code = action.getId() - 58
                if (code >= 0 and code <= 9) or (action_code >= 0 and action_code <= 9):
                    digit = None
                    if (code >= 0 and code <= 9):
                        digit = code
                    else:
                        digit = action_code
                    self.channel_number_input = True
                    self.channel_number = str(digit)
                    self.getControl(9999).setLabel(self.channel_number)
            elif action.getId() in COMMAND_ACTIONS["CHANNEL_NUMBER"]:
                if not self.channel_number_input:
                    self.channel_number = "_"
                    self.getControl(9999).setLabel(self.channel_number)
                self.channel_number_input = not self.channel_number_input

            if self.channel_number_input:
                if digit == None:
                    code = action.getButtonCode() - 61488
                    action_code = action.getId() - 58
                    if (code >= 0 and code <= 9) or (action_code >= 0 and action_code <= 9):
                        digit = None
                        if (code >= 0 and code <= 9):
                            digit = code
                        else:
                            digit = action_code
                    if digit != None:
                        self.channel_number = "%s%d" % (self.channel_number.strip('_'),digit)
                    self.getControl(9999).setLabel(self.channel_number)
                    if len(self.channel_number) == int(ADDON.getSetting('channel.index.digits')):
                        self.playShortcut()
                return

        if action.getId() in COMMAND_ACTIONS["CHANNEL_DIALOG"]:
            d = xbmcgui.Dialog()
            number = d.input("Channel Shortcut Number",type=xbmcgui.INPUT_NUMERIC)
            if number:
                self.channel_number = number
                self.playShortcut()

        elif action.getId() in COMMAND_ACTIONS["NOW_LISTING"]:
            self.showNow()
        elif action.getId() in COMMAND_ACTIONS["NEXT_LISTING"]:
            self.showNext()
        elif action.getId() in COMMAND_ACTIONS["SEARCH"]:
            self.programSearchSelect()
        elif action.getId() in COMMAND_ACTIONS["REMINDERS"]:
            self.showFullReminders()
        elif action.getId() in COMMAND_ACTIONS["AUTOPLAYS"]:
            self.showFullAutoplays()
        elif action.getId() in COMMAND_ACTIONS["AUTOPLAYWITHS"]:
            self.showFullAutoplaywiths()
        elif action.getId() in COMMAND_ACTIONS["CATEGORIES"]:
            self._showCatMenu()
        elif action.getId() in COMMAND_ACTIONS["PROGRAM_SEARCH"]:
            self.programSearch()
        elif action.getId() in COMMAND_ACTIONS["DESCRIPTION_SEARCH"]:
            self.descriptionSearch()
        elif action.getId() in COMMAND_ACTIONS["CATEGORY_SEARCH"]:
            self.categorySearch()
        elif action.getId() in COMMAND_ACTIONS["CHANNEL_SEARCH"]:
            self.channelSearch()


        if self.mode == MODE_TV:
            self.onActionTVMode(action)
        elif self.mode == MODE_OSD:
            self.onActionOSDMode(action)
        elif self.mode == MODE_OSD_BIG:
            self.onActionOSDBigMode(action)
        elif self.mode == MODE_EPG:
            self.onActionEPGMode(action)
        elif self.mode == MODE_QUICK_EPG:
            self.onActionQuickEPGMode(action)
        elif self.mode == MODE_LASTCHANNEL:
            self.onActionLastPlayedMode(action)

    def onActionTVMode(self, action):
        if action.getId() in COMMAND_ACTIONS["PLAY_NEXT_CHANNEL"]:
            self._channelUp()
        elif action.getId() in COMMAND_ACTIONS["PLAY_PREV_CHANNEL"]:
            self._channelDown()

        elif not self.osdEnabled:
            pass  # skip the rest of the actions

        elif action.getId() in COMMAND_ACTIONS["CLOSE"]:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 60, seconds=self.viewStartDate.second)
            self.currentProgram = self.database.getCurrentProgram(self.currentChannel)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif action.getId() in COMMAND_ACTIONS["MENU"]:
            self.osdChannel = self.currentChannel
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsdBig()
        elif action.getId() in COMMAND_ACTIONS["OSD"] + COMMAND_ACTIONS["PLAY"]:
            self.osdChannel = self.currentChannel
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsd()
        elif action.getId() in COMMAND_ACTIONS["PLAY_LAST_CHANNEL"]:
            self._playLastChannel()
        elif action.getId() in COMMAND_ACTIONS["LAST_CHANNEL"] + COMMAND_ACTIONS["LEFT"]:
            self._showLastPlayedChannel()
        elif action.getId() in COMMAND_ACTIONS["FULLSCREEN"] + COMMAND_ACTIONS["RIGHT"]:
             xbmc.executebuiltin('Action(FullScreen)')
        elif action.getId() in COMMAND_ACTIONS["NOW_LISTING"] + COMMAND_ACTIONS["UP"]:
            self.showNow()
        elif action.getId() in COMMAND_ACTIONS["QUICK_EPG"] + COMMAND_ACTIONS["DOWN"]:
            self.quickViewStartDate = datetime.datetime.today()
            self.quickViewStartDate -= datetime.timedelta(minutes=self.quickViewStartDate.minute % 60, seconds=self.quickViewStartDate.second)
            self.currentProgram = self.database.getCurrentProgram(self.currentChannel)
            self.onRedrawQuickEPG(self.quickChannelIdx, self.quickViewStartDate)
        elif action.getId() in COMMAND_ACTIONS["CHANNEL_LISTING"]:
            self.showListing(self.currentChannel)


    def onActionOSDMode(self, action):
        if action.getId() == ACTION_MOUSE_MOVE:
            if ADDON.getSetting('mouse.controls') == "true":
                self._showControl(self.C_MAIN_OSD_MOUSE_CONTROLS)
            return

        if action.getId() in COMMAND_ACTIONS["OSD"]:
            self._hideOsd()

        elif action.getId() in COMMAND_ACTIONS["CLOSE"]:
            self._hideOsd()
            self._hideOsdBig()

        elif action.getId() in COMMAND_ACTIONS["PLAY"]:
            self._hideOsd()
            self.playOrChoose(self.osdProgram)

        elif action.getId() in COMMAND_ACTIONS["MENU"]:
            self.osdChannel = self.currentChannel
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsdBig()

        elif action.getId() in COMMAND_ACTIONS["PLAY_NEXT_CHANNEL"]:
            self._channelUp()
            self._hideOsd()

        elif action.getId() in COMMAND_ACTIONS["PLAY_PREV_CHANNEL"]:
            self._channelDown()
            self._hideOsd()

        elif action.getId() in COMMAND_ACTIONS["UP"]:
            self.osdChannel = self.database.getPreviousChannel(self.osdChannel)
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsd()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["DOWN"]:
            self.osdChannel = self.database.getNextChannel(self.osdChannel)
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsd()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["LEFT"]:
            previousProgram = self.database.getPreviousProgram(self.osdProgram)
            if previousProgram:
                self.osdProgram = previousProgram
                self._showOsd()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["RIGHT"]:
            nextProgram = self.database.getNextProgram(self.osdProgram)
            if nextProgram:
                self.osdProgram = nextProgram
                self._showOsd()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["CHANNEL_LISTING"]:
            self.showListing(self.osdChannel)

    def onActionOSDBigMode(self, action):
        if action.getId() == ACTION_MOUSE_MOVE:
            if ADDON.getSetting('mouse.controls') == "true":
                self._showControl(self.C_MAIN_OSD_MOUSE_CONTROLS)
            return

        if action.getId() in COMMAND_ACTIONS["OSD"]:
            self._hideOsdBig()

        elif action.getId() in COMMAND_ACTIONS["CLOSE"]:
            self._hideOsdBig()
            self._hideOsd()

        elif action.getId() in COMMAND_ACTIONS["PLAY"]:
            self._hideOsdBig()
            self.playOrChoose(self.osdProgram)   

        elif action.getId() in COMMAND_ACTIONS["MENU"]:
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            if self.osdProgram is not None:
                self._showContextMenu(self.osdProgram)

        elif action.getId() in COMMAND_ACTIONS["PLAY_NEXT_CHANNEL"]:
            self._channelUp()
            self._hideOsdBig()

        elif action.getId() in COMMAND_ACTIONS["PLAY_PREV_CHANNEL"]:
            self._channelDown()
            self._hideOsdBig()

        elif action.getId() in COMMAND_ACTIONS["UP"]:
            self.osdChannel = self.database.getPreviousChannel(self.osdChannel)
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsdBig()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["DOWN"]:
            self.osdChannel = self.database.getNextChannel(self.osdChannel)
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsdBig()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["LEFT"]:
            previousProgram = self.database.getPreviousProgram(self.osdProgram)
            if previousProgram:
                self.osdProgram = previousProgram
                self._showOsdBig()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["RIGHT"]:
            nextProgram = self.database.getNextProgram(self.osdProgram)
            if nextProgram:
                self.osdProgram = nextProgram
                self._showOsdBig()
            self.osdActive = True

        elif action.getId() in COMMAND_ACTIONS["CHANNEL_LISTING"]:
            self.showListing(self.osdChannel)

    def onActionLastPlayedMode(self, action):
        if action.getId() == ACTION_MOUSE_MOVE:
            if ADDON.getSetting('mouse.controls') == "true":
                self._showControl(self.C_MAIN_LAST_PLAYED_MOUSE_CONTROLS)
            return
        if action.getId() in COMMAND_ACTIONS["LAST_CHANNEL"]:
            self._hideLastPlayed()

        elif action.getId() in COMMAND_ACTIONS["CLOSE"]:
            self._hideLastPlayed()
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 60, seconds=self.viewStartDate.second)
            self.currentProgram = self.database.getCurrentProgram(self.currentChannel)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif action.getId() in COMMAND_ACTIONS["MENU"]:
            self.currentProgram = self.database.getCurrentProgram(self.currentChannel)
            if self.currentProgram is not None:
                self._showContextMenu(self.currentProgram)

        elif action.getId() in COMMAND_ACTIONS["PLAY"]:
            self._hideLastPlayed()
            self.playOrChoose(self.lastProgram)

        elif action.getId() in COMMAND_ACTIONS["LEFT"]:
            self._hideLastPlayed()

        elif action.getId() in COMMAND_ACTIONS["RIGHT"]:
            self._hideLastPlayed()


    # epg mode
    def onActionEPGMode(self, action):
        if action.getId() in [ACTION_PARENT_DIR]:
            self.close()
            return

        # catch the ESC key
        elif action.getId() == ACTION_PREVIOUS_MENU and action.getButtonCode() == KEY_ESC:
            self.close()
            return

        if action.getId() == ACTION_MOUSE_MOVE:
            if ADDON.getSetting('mouse.controls') == "true":
                self._showControl(self.C_MAIN_MOUSE_CONTROLS)
            return

        elif action.getId() in COMMAND_ACTIONS["CLOSE"]:
            if self.player.isPlaying():
                if (ADDON.getSetting("exit.on.back") == "true") and (ADDON.getSetting("play.minimized") == "false"):
                    self.close()
                    return
                else:
                    self._hideEpg()
            else:
                self.close()
                return

        elif action.getId() in COMMAND_ACTIONS["CATEGORIES_BAR"] and self.getControl(self.C_MAIN_CATEGORY):
            self.setFocusId(self.C_MAIN_CATEGORY)
            return


        controlInFocus = None
        currentFocus = self.focusPoint
        try:
            controlInFocus = self.getFocus()
            if controlInFocus in [elem.control for elem in self.controlAndProgramList]:
                (left, top) = controlInFocus.getPosition()
                currentFocus = Point()
                currentFocus.x = left + (controlInFocus.getWidth() / 2)
                currentFocus.y = top + (controlInFocus.getHeight() / 2)
        except Exception:
            control = self._findControlAt(self.focusPoint)
            if control is None and len(self.controlAndProgramList) > 0:
                control = self.controlAndProgramList[0].control
            if control is not None:
                #self.setFocus(control)
                return

        if action.getId() in COMMAND_ACTIONS["NEXT_DAY"]:
            self._nextDay()
        elif action.getId() in COMMAND_ACTIONS["PREV_DAY"]:
            self._previousDay()
        elif action.getId() in COMMAND_ACTIONS["PAGE_UP"]:
            self._moveUp(CHANNELS_PER_PAGE)
        elif action.getId() in COMMAND_ACTIONS["PAGE_DOWN"]:
            self._moveDown(CHANNELS_PER_PAGE)
        elif self.getFocusId() not in [self.C_MAIN_CATEGORY, self.C_MAIN_ACTIONS] and action.getId() == ACTION_MOUSE_WHEEL_UP:
            self._moveUp(scrollEvent=True)
        elif self.getFocusId() not in [self.C_MAIN_CATEGORY, self.C_MAIN_ACTIONS] and action.getId() == ACTION_MOUSE_WHEEL_DOWN:
            self._moveDown(scrollEvent=True)
        elif action.getId() in COMMAND_ACTIONS["GO_TO_NOW"]:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                     seconds=self.viewStartDate.second)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
        elif action.getId() in COMMAND_ACTIONS["GO_TO_FIRST_CHANNEL"]:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                     seconds=self.viewStartDate.second)
            self.onRedrawEPG(0, self.viewStartDate)

        elif action.getId() in COMMAND_ACTIONS["CHANNEL_LISTING"]:
            program = self._getProgramFromControl(controlInFocus)
            if program is not None:
                self.showListing(program.channel)
        elif action.getId() in COMMAND_ACTIONS["STOP_AUTOPLAYWITH"]:
            self.stopWith()
        elif action.getId() in COMMAND_ACTIONS["PLAY_AUTOPLAYWITH"]:
            program = self._getProgramFromControl(controlInFocus)
            if program:
                self.playWithChannel(program.channel)
        elif action.getId() in COMMAND_ACTIONS["DELETE_PROGRAM_IMAGE"]:
            program = self._getProgramFromControl(controlInFocus)
            if program:
                self.tvdb_urls[program.title] = ''
                self.setControlImage(self.C_MAIN_IMAGE, self.tvdb_urls[program.title])
        elif action.getId() in COMMAND_ACTIONS["SCHEDULERS_MENU"]:
            program = self._getProgramFromControl(controlInFocus)
            d = xbmcgui.Dialog()

            if not program.notificationScheduled:
                remind = "Remind"
            else:
                remind = "Don't Remind"
            if not program.autoplayScheduled:
                autoplay = "AutoPlay"
            else:
                autoplay = "Don't AutoPlay"
            if not program.autoplaywithScheduled:
                autoplaywith = "AutoPlayWith"
            else:
                autoplaywith = "Don't AutoPlayWith"
            schedulers = [remind,autoplay,autoplaywith]
            what = d.select("Schedule", schedulers)
            if what > -1:
                if what == 0:
                    if program.notificationScheduled:
                        self.notification.removeNotification(program)
                    else:
                        times = ["once","always"]
                        when = d.select("%s When" % schedulers[what], times)
                        if when > -1:
                            self.notification.addNotification(program, when)
                elif what == 1:
                    if program.autoplayScheduled:
                        self.autoplay.removeAutoplay(program)
                    else:
                        times = ["once","always"]
                        when = d.select("%s When" % schedulers[what], times)
                        if when > -1:
                            self.autoplay.addAutoplay(program, when)
                elif what == 2:
                    if program.autoplaywithScheduled:
                        self.autoplaywith.removeAutoplaywith(program)
                    else:
                        times = ["once","always"]
                        when = d.select("%s When" % schedulers[what], times)
                        if when > -1:
                            self.autoplaywith.addAutoplaywith(program, when)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
        elif action.getId() in COMMAND_ACTIONS["PLAY_CHOOSE"]:
            program = self._getProgramFromControl(controlInFocus)
            if program:
                result = self.streamingService.detectStream(program.channel)
                if not result:
                    # could not detect stream, show stream setup
                    d = StreamSetupDialog(self.database, program.channel)
                    d.doModal()
                    del d
                    self.streamingService = streaming.StreamsService(ADDON)
                    self.onRedrawEPG(self.channelIdx, self.viewStartDate)
                elif type(result) == str:
                    # one single stream detected, save it and start streaming
                    self.database.setCustomStreamUrl(program.channel, result)
                    self.playChannel(program.channel, program)
                else:
                    # multiple matches, let user decide
                    d = ChooseStreamAddonDialog(result)
                    d.doModal()
                    if d.stream is not None:
                        self.database.setCustomStreamUrl(program.channel, d.stream)
                        self.playChannel(program.channel, program)
        elif action.getId() in COMMAND_ACTIONS["EXTENDED_INFO"]:
            program = self._getProgramFromControl(controlInFocus)
            title = program.title
            match = re.search('(.*?)\([0-9]{4}\)$',title)
            if match:
                title = match.group(1).strip()
                program.is_movie = "Movie"
            if program.is_movie == "Movie":
                selection = 0
            elif program.season:
                selection = 1
            else:
                selection = xbmcgui.Dialog().select("Choose media type",["Search as Movie", "Search as TV Show", "Search as Either"])
            where = ["movie","tv","multi"]
            url = base64.b64decode("aHR0cHM6Ly9hcGkudGhlbW92aWVkYi5vcmcvMy9zZWFyY2gvJXM/cXVlcnk9JXMmYXBpX2tleT1kNjk5OTJlYzgxMGQwZjQxNGQzZGU0YTIyOTRiODcwMCZpbmNsdWRlX2FkdWx0PWZhbHNlJnBhZ2U9MQ==") % (where[selection],title)
            r = requests.get(url)
            data = json.loads(r.content)
            results = data.get('results')
            id = ''
            if results:
                if len(results) > 1:
                    names = ["%s (%s)" % (x.get('name') or x.get('title'),x.get('first_air_date') or x.get('release_date')) for x in results]
                    what = xbmcgui.Dialog().select(title,names)
                    if what > -1:
                        id = results[what].get('id')
                        result_type = results[what].get('media_result_type')
                        if result_type not in ["movie","tv"]:
                            if selection == 0:
                                result_type = "movie"
                            else:
                                result_type = "tv"
                        if result_type == 'movie':
                            xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedinfo,name=%s,id=%s)' % (title,id))
                        elif result_type == 'tv':
                            xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedtvinfo,name=%s,id=%s)' % (program.title,id))
                    else:
                        xbmcgui.Dialog().notification("TV Guide Fullscreen", "Couldn't find: %s" % title)
                else:
                    if selection == 0:
                        xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedinfo,name=%s)' % (title))
                    elif selection == 1:
                        xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedtvinfo,name=%s)' % (program.title))
            else:
                xbmcgui.Dialog().notification("TV Guide Fullscreen", "Couldn't find: %s" % title)
        elif action.getId() in COMMAND_ACTIONS["UP"]:
            self._up(currentFocus)
        elif action.getId() in COMMAND_ACTIONS["DOWN"]:
            self._down(currentFocus)

        elif action.getId() in COMMAND_ACTIONS["MENU"] and self.getFocusId() in [self.C_MAIN_CATEGORY]:
            kodi = float(xbmc.getInfoLabel("System.BuildVersion")[:4])
            dialog = xbmcgui.Dialog()
            if kodi < 16:
                dialog.ok('TV Guide Fullscreen', 'Editing categories in Kodi %s is currently not supported.' % kodi)
            else:
                cList = self.getControl(self.C_MAIN_CATEGORY)
                item = cList.getSelectedItem()
                if item:
                    self.selected_category = item.getLabel()
                if self.selected_category == "All Channels":
                    selection = ["Add Category"]
                else:
                    selection = ["Add Category","Add Channels","Remove Channels","Clear Channels"]
                dialog = xbmcgui.Dialog()
                ret = dialog.select("%s" % self.selected_category, selection)
                if ret < 0:
                    return

                f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','rb')
                lines = f.read().splitlines()
                f.close()
                categories = {}
                if self.selected_category not in ["Any", "All Channels"]:
                    categories[self.selected_category] = []
                for line in lines:
                    if '=' in line:
                        name,cat = line.strip().split('=')
                        if cat not in categories:
                            categories[cat] = []
                        categories[cat].append(name)

                if ret == 1:
                    channelList = sorted([channel.title for channel in self.database.getChannelList(onlyVisible=True,all=True)])
                    channelList = [c for c in channelList if c not in categories[self.selected_category]]
                    sstr = 'Add Channels To %s' % self.selected_category
                    ret = dialog.multiselect(sstr, channelList)
                    if ret is None:
                        return
                    if not ret:
                        ret = []
                    channels = []
                    for i in ret:
                        channels.append(channelList[i])

                    for channel in channels:
                        if channel not in categories[self.selected_category]:
                            categories[self.selected_category].append(channel)

                elif ret == 2:
                    channelList = sorted(categories[self.selected_category])
                    sstr = 'Remove Channels From %s' % self.selected_category
                    ret = dialog.multiselect(sstr, channelList)
                    if ret is None:
                        return
                    if not ret:
                        ret = []
                    channels = []
                    for i in ret:
                        channelList[i] = ""
                    categories[self.selected_category] = []
                    for name in channelList:
                        if name:
                            categories[self.selected_category].append(name)

                elif ret == 3:
                    categories[self.selected_category] = []

                elif ret == 0:
                    dialog = xbmcgui.Dialog()
                    cat = dialog.input('Add Category', type=xbmcgui.INPUT_ALPHANUM)
                    if cat:
                        if cat not in categories:
                            categories[cat] = []
                        items = list()
                        new_categories = ["All Channels"] + sorted(categories.keys(), key=lambda x: x.lower())
                        for label in new_categories:
                            item = xbmcgui.ListItem(label)
                            items.append(item)
                        listControl = self.getControl(self.C_MAIN_CATEGORY)
                        listControl.reset()
                        listControl.addItems(items)

                f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','wb')
                for cat in categories:
                    channels = categories[cat]
                    for channel in channels:
                        f.write("%s=%s\n" % (channel.encode("utf8"),cat))
                f.close()
                self.categories = [category for category in categories if category]

        elif action.getId() in COMMAND_ACTIONS["MENU"] and controlInFocus is not None:
            program = self._getProgramFromControl(controlInFocus)
            if program is not None:
                self._showContextMenu(program)
        elif action.getId() in COMMAND_ACTIONS["LEFT"] and self.getFocusId() not in [self.C_MAIN_ACTIONS,self.C_MAIN_CATEGORY,self.C_MAIN_PROGRAM_CATEGORIES]:
            self._left(currentFocus)
        elif action.getId() in COMMAND_ACTIONS["RIGHT"] and self.getFocusId() not in [self.C_MAIN_ACTIONS,self.C_MAIN_CATEGORY,self.C_MAIN_PROGRAM_CATEGORIES]:
            self._right(currentFocus)

        else:
            xbmc.log('[script.tvguide.fullscreen] Unhandled ActionId: ' + str(action.getId()), xbmc.LOGDEBUG)



    def onActionQuickEPGMode(self, action):
        if action.getId() == ACTION_MOUSE_MOVE:
        #elif action.getId() in COMMAND_ACTIONS["EPG_MODE_SHOW_TOUCH_CONTROLS"]:
            if ADDON.getSetting('mouse.controls') == "true":
                self._showControl(self.C_QUICK_EPG_MOUSE_CONTROLS)
            return
        #if action.getId() in [ACTION_PARENT_DIR, KEY_NAV_BACK]:
        if action.getId() in COMMAND_ACTIONS["CLOSE"]:
            self._hideQuickEpg()

        # catch the ESC key
        #elif action.getId() == ACTION_PREVIOUS_MENU and action.getButtonCode() == KEY_ESC:
        #elif action.getId() in COMMAND_ACTIONS["QUICK_EPG_MODE_EXIT"] and action.getButtonCode() == KEY_ESC:
        #    self._hideQuickEpg()

        elif action.getId() in COMMAND_ACTIONS["INFO"]:
            self.quickEpgShowInfo = not self.quickEpgShowInfo
            self.setControlVisible(self.C_QUICK_EPG_DESCRIPTION,self.quickEpgShowInfo)

        controlInFocus = None
        currentFocus = self.quickFocusPoint
        try:
            controlInFocus = self.getFocus()
            if controlInFocus in [elem.control for elem in self.quickControlAndProgramList]:
                (left, top) = controlInFocus.getPosition()
                currentFocus = Point()
                currentFocus.x = left + (controlInFocus.getWidth() / 2)
                currentFocus.y = top + (controlInFocus.getHeight() / 2)
        except Exception:
            control = self._findQuickControlAt(self.quickFocusPoint)
            if control is None and len(self.quickControlAndProgramList) > 0:
                control = self.quickControlAndProgramList[0].control
            if control is not None:
                self.setQuickFocus(control)
                xbmc.log("exception in onActionQuickEPGMode", xbmc.LOGERROR)
                return
        if action.getId() in COMMAND_ACTIONS["LEFT"]:
            self._quickLeft(currentFocus)
        elif action.getId() in COMMAND_ACTIONS["RIGHT"]:
            self._quickRight(currentFocus)
        elif action.getId() in COMMAND_ACTIONS["UP"]:
            self._quickUp(currentFocus)
        elif action.getId() in COMMAND_ACTIONS["DOWN"]:
            self._quickDown(currentFocus)
        elif action.getId() in COMMAND_ACTIONS["NEXT_DAY"]:
            self._quickNextDay()
        elif action.getId() in COMMAND_ACTIONS["PREV_DAY"]:
            self._quickPreviousDay()
        elif action.getId() in COMMAND_ACTIONS["PAGE_UP"]:
            self._quickMoveUp(3)
        elif action.getId() in COMMAND_ACTIONS["PAGE_DOWN"]:
            self._quickMoveDown(3)
        elif action.getId() == ACTION_MOUSE_WHEEL_UP:
            self._quickMoveUp(1)
        elif action.getId() == ACTION_MOUSE_WHEEL_DOWN:
            self._quickMoveDown(1)
        elif action.getId() in COMMAND_ACTIONS["PLAY"]:
            self._hideQuickEpg()
            self.playOrChoose(self.osdProgram)
        elif action.getId() in COMMAND_ACTIONS["CHANNEL_LISTING"]:
            program = self._getQuickProgramFromControl(controlInFocus)
            if program is not None:
                self.showListing(program.channel)
        elif action.getId() in COMMAND_ACTIONS["MENU"]  and controlInFocus is not None:
            program = self._getQuickProgramFromControl(controlInFocus)
            if program is not None:
                self._showContextMenu(program)
        else:
            xbmc.log('[script.tvguide.fullscreen] quick epg Unhandled ActionId: ' + str(action.getId()), xbmc.LOGDEBUG)

    def pip_toggle(self):
        if ADDON.getSetting('epg.video.pip') == 'false':
            ADDON.setSetting('epg.video.pip', 'true')
        elif ADDON.getSetting('epg.video.pip') == 'true':
            ADDON.setSetting('epg.video.pip', 'false')
        self.reopen()

    def reopen(self):
        import gui
        xbmc.executebuiltin('XBMC.ActivateWindow(home)')
        xbmc.sleep(350)
        w = gui.TVGuide()
        w.doModal()
        xbmc.sleep(350)
        del w

    def onClick(self, controlId):
        if controlId in [self.C_MAIN_LOADING_CANCEL, self.C_MAIN_MOUSE_EXIT]:
            self.close()
            return

        if self.isClosing:
            return
        if controlId == self.C_MAIN_ACTIONS:
            cList = self.getControl(self.C_MAIN_ACTIONS)
            pos = cList.getSelectedPosition()
            self.action_index = pos
            xbmc.executebuiltin(self.actions[pos][1])
        if controlId == self.C_MAIN_CATEGORY:
            cList = self.getControl(self.C_MAIN_CATEGORY)
            item = cList.getSelectedItem()
            if item:
                self.selected_category = item.getLabel()
                self.category = self.selected_category
        if controlId in [self.C_MAIN_MOUSE_FIRST]:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                     seconds=self.viewStartDate.second)
            self.onRedrawEPG(0, self.viewStartDate)
            return
        elif controlId in [self.C_MAIN_MOUSE_CHANNEL_NUMBER]:
            d = xbmcgui.Dialog()
            number = d.input("Channel Shortcut Number",type=xbmcgui.INPUT_NUMERIC)
            if number:
                self.channel_number = number
                self.playShortcut()
            return
        elif controlId in [self.C_MAIN_MOUSE_STOP]:
            self.player.stop()
            self.tryingToPlay = False
            self._hideOsdOnly()
            self._hideOsdBigOnly()
            self._hideQuickEpg()

            self.currentChannel = None
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                     seconds=self.viewStartDate.second)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            self.setControlVisible(self.C_MAIN_IMAGE,True)
            return
        elif controlId in [self.C_MAIN_MOUSE_FAVOURITES]:
            favourites = ADDON.getSetting('favourites')
            if favourites == 'Simple Favourites':
                xbmc.executebuiltin("ActivateWindow(10001,plugin://plugin.program.simple.favourites,return)")
            elif favourites == 'Video Favourites':
                xbmc.executebuiltin("ActivateWindow(10025,plugin://plugin.video.favourites,return)")
            elif favourites == 'Super Favourites':
                xbmc.executebuiltin("ActivateWindow(10001,plugin://plugin.program.super.favourites,return)")
            elif favourites == 'Favourites':
                xbmc.executebuiltin("ActivateWindow(10134)")
            return
        elif controlId in [self.C_MAIN_MOUSE_MINE1]:
            command = ADDON.getSetting('mine1')
            xbmc.executebuiltin(command)
            return
        elif controlId in [self.C_MAIN_MOUSE_HOME, self.C_MAIN_MOUSE_HOME_BIG]:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30, seconds=self.viewStartDate.second)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            return
        elif controlId in [self.C_MAIN_MOUSE_LEFT, self.C_MAIN_MOUSE_LEFT_BIG]:
            self.viewStartDate -= datetime.timedelta(hours=2)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            return
        elif controlId in [self.C_MAIN_MOUSE_UP, self.C_MAIN_MOUSE_UP_BIG]:
            self._moveUp(count=CHANNELS_PER_PAGE)
            return
        elif controlId in [self.C_MAIN_MOUSE_DOWN, self.C_MAIN_MOUSE_DOWN_BIG]:
            self._moveDown(count=CHANNELS_PER_PAGE)
            return
        elif controlId in [self.C_MAIN_MOUSE_RIGHT, self.C_MAIN_MOUSE_RIGHT_BIG]:
            self.viewStartDate += datetime.timedelta(hours=2)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            return
        elif controlId in [self.C_MAIN_MOUSE_NEXT_DAY]:
            self._nextDay()
            return
        elif controlId in [self.C_MAIN_MOUSE_PREV_DAY]:
            self._previousDay()
            return
        elif controlId == self.C_MAIN_MOUSE_MENU:
            program = utils.Program(channel='', title='', sub_title='', startDate=None, endDate=None, description='', categories='')
            program.autoplayScheduled = False
            program.autoplaywithScheduled = False
            self._showContextMenu(program)
            return
        elif controlId == self.C_MAIN_MOUSE_CATEGORIES:
            self._showCatMenu()
            return
        elif controlId == self.C_MAIN_MOUSE_PIP:
            self.pip_toggle()
            return
        elif controlId == self.C_MAIN_MOUSE_NOW:
            self.showNow()
            return
        elif controlId == self.C_MAIN_MOUSE_NEXT:
            self.showNext()
            return
        elif controlId == self.C_MAIN_MOUSE_SEARCH:
            self.programSearchSelect()
            return
        elif controlId == self.C_MAIN_MOUSE_OSD_BIG:
            self._showOsdBig()
            self._hideOsdOnly()
        elif controlId == self.C_MAIN_PROGRAM_CATEGORIES:
            self.categorySearch()
            return
        elif controlId == self.C_MAIN_CATEGORY:
            cList = self.getControl(self.C_MAIN_CATEGORY)
            item = cList.getSelectedItem()
            if item:
                self.category = item.getLabel()
                ADDON.setSetting('category',self.category)
                self.database.setCategory(self.category)
                self.onRedrawEPG(self.channelIdx, self.viewStartDate)
                return

        program = self._getProgramFromControl(self.getControl(controlId))
        if self.mode == MODE_QUICK_EPG :
            program = self._getQuickProgramFromControl(self.getControl(controlId))
        elif self.mode == MODE_OSD:
            program = self.osdProgram
        elif self.mode == MODE_LASTCHANNEL:
            self._hideLastPlayed()
            program = self.lastProgram
        if program is None:
            return
        if ADDON.getSetting('play.menu') == 'true':
            self._showContextMenu(program)
        else:
            self.playOrChoose(program)


    def playOrChoose(self,program):
        if self.player.isPlaying() and self.currentChannel and (program.channel.id == self.currentChannel.id) and (ADDON.getSetting('play.alt.choose') == 'false'):
                self._hideEpg()
                self._hideQuickEpg()
                return

        if not self.playChannel(program.channel, program):
            result = self.streamingService.detectStream(program.channel)
            if not result:
                # could not detect stream, show stream setup
                d = StreamSetupDialog(self.database, program.channel)
                d.doModal()
                del d
                self.streamingService = streaming.StreamsService(ADDON)
                self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            elif type(result) == str:
                # one single stream detected, save it and start streaming
                self.database.setCustomStreamUrl(program.channel, result)
                self.playChannel(program.channel, program)
            else:
                # multiple matches, let user decide
                d = ChooseStreamAddonDialog(result)
                d.doModal()
                if d.stream is not None:
                    self.database.setCustomStreamUrl(program.channel, d.stream)
                    self.playChannel(program.channel, program)

    def showListing(self, channel):
        programList = self.database.getChannelListing(channel)
        title = channel.title
        d = ProgramListDialog(title,programList)
        d.doModal()
        index = d.index
        if index > -1:
            self._showContextMenu(programList[index])


    def showNow(self):
        programList = self.database.getNowList()
        title = "Now"
        d = ProgramListDialog(title,programList)
        d.doModal()
        index = d.index
        action = d.action
        if action == ACTION_RIGHT:
            self.showNext()
        elif action == ACTION_LEFT:
            self.showListing(programList[index].channel)
        elif action == KEY_CONTEXT_MENU:
            if index > -1:
                self._showContextMenu(programList[index])
        else:
            if index > -1:
                self.playOrChoose(programList[index])

    def showNext(self):
        programList = self.database.getNextList()
        title = "Next"
        d = ProgramListDialog(title,programList)
        d.doModal()
        index = d.index
        action = d.action
        if action == ACTION_LEFT:
            self.showNow()
        elif action == ACTION_RIGHT:
            self.showListing(programList[index].channel)
        elif action == KEY_CONTEXT_MENU:
            if index > -1:
                self._showContextMenu(programList[index])
        else:
            if index > -1:
                self.playOrChoose(programList[index])


    def programSearchSelect(self):
        d = xbmcgui.Dialog()
        what = d.select("Search",["Title","Synopsis","Category","Channel"])
        if what == -1:
            return
        if what == 0:
            self.programSearch()
        elif what == 1:
            self.descriptionSearch()
        elif what == 2:
            self.categorySearch()
        elif what == 3:
            self.channelSearch()


    def programSearch(self):
        d = xbmcgui.Dialog()
        title = ''
        try:
            controlInFocus = self.getFocus()
            if controlInFocus:
                program = self._getProgramFromControl(controlInFocus)
                if program:
                    title = program.title
        except:
            if self.currentProgram:
                title = self.currentProgram.title
        file_name = "special://profile/addon_data/script.tvguide.fullscreen/title_search.list"
        f = xbmcvfs.File(file_name,"rb")
        searches = sorted(f.read().splitlines())
        f.close()
        actions = ["New Search", "Remove Search"] + searches
        action = d.select("Program Search: %s" % title, actions)
        if action == -1:
            return
        elif action == 0:
            pass
        elif action == 1:
            which = d.select("Remove Search",searches)
            if which == -1:
                return
            else:
                del searches[which]
                f = xbmcvfs.File(file_name,"wb")
                f.write('\n'.join(searches))
                f.close()
                return
        else:
            title = searches[action-2]
        search = d.input("Program Search",title)
        if not search:
            return
        searches = list(set([search] + searches))
        f = xbmcvfs.File(file_name,"wb")
        f.write('\n'.join(searches))
        f.close()
        programList = self.database.programSearch(search)
        title = "Program Search"
        d = ProgramListDialog(title, programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        action = d.action
        if action == ACTION_RIGHT:
            self.showNext()
        elif action == ACTION_LEFT:
            self.showListing(programList[index].channel)
        elif action == KEY_CONTEXT_MENU:
            if index > -1:
                self._showContextMenu(programList[index])
        else:
            if index > -1:
                self.playOrChoose(programList[index])


    def descriptionSearch(self):
        d = xbmcgui.Dialog()
        title = ''
        file_name = "special://profile/addon_data/script.tvguide.fullscreen/synopsis_search.list"
        f = xbmcvfs.File(file_name,"rb")
        searches = sorted(f.read().splitlines())
        f.close()
        actions = ["New Search", "Remove Search"] + searches
        action = d.select("Synopsis Search:", actions)
        if action == -1:
            return
        elif action == 0:
            pass
        elif action == 1:
            which = d.select("Remove Search",searches)
            if which == -1:
                return
            else:
                del searches[which]
                f = xbmcvfs.File(file_name,"wb")
                f.write('\n'.join(searches))
                f.close()
                return
        else:
            title = searches[action-2]
        search = d.input("Synopsis Search",title)
        if not search:
            return
        searches = list(set([search] + searches))
        f = xbmcvfs.File(file_name,"wb")
        f.write('\n'.join(searches))
        f.close()
        programList = self.database.descriptionSearch(search)
        title = "Program Search"
        d = ProgramListDialog(title, programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        action = d.action
        if action == ACTION_RIGHT:
            self.showNext()
        elif action == ACTION_LEFT:
            self.showListing(programList[index].channel)
        elif action == KEY_CONTEXT_MENU:
            if index > -1:
                self._showContextMenu(programList[index])
        else:
            if index > -1:
                self.playOrChoose(programList[index])

    def categorySearch(self):
        d = xbmcgui.Dialog()
        f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/category_count.ini',"rb")
        category_count = [x.split("=",1) for x in f.read().splitlines()]
        f.close()
        categories = []
        for (c,v) in category_count:
            if not self.category or self.category == "All Channels":
                s = "%s (%s)" % (c,v)
            else:
                s = c
            categories.append(s)
        which = d.select("Program Category Search",categories)
        if which == -1:
            return
        category = category_count[which][0]
        programList = self.database.programCategorySearch(category)
        title = "%s" % category
        d = ProgramListDialog(title, programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        action = d.action
        if action == ACTION_RIGHT:
            self.showNext()
        elif action == ACTION_LEFT:
            self.showListing(programList[index].channel)
        elif action == KEY_CONTEXT_MENU:
            if index > -1:
                self._showContextMenu(programList[index])
        else:
            if index > -1:
                self.playOrChoose(programList[index])

    def channelSearch(self):
        d = xbmcgui.Dialog()
        search = d.input("Channel Search")
        if not search:
            return
        programList = self.database.channelSearch(search)
        title = "Channel Search"
        d = ProgramListDialog(title, programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        action = d.action
        if action == ACTION_RIGHT:
            self.showNext()
        elif action == ACTION_LEFT:
            self.showListing(programList[index].channel)
        elif action == KEY_CONTEXT_MENU:
            if index > -1:
                self._showContextMenu(programList[index])
        else:
            if index > -1:
                self.playOrChoose(programList[index])

    def showReminders(self):
        programList = self.database.getNotifications()
        title = "Reminders"
        d = ProgramListDialog(title,programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        if index > -1:
            self._showContextMenu(programList[index])

    def showFullReminders(self):
        programList = self.database.getFullNotifications()
        title = "Reminders"
        d = ProgramListDialog(title,programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        if index > -1:
            self._showContextMenu(programList[index])

    def showAutoplays(self):
        programList = self.database.getAutoplays()
        labels = []
        for channelTitle, programTitle, start, end in programList:
            day = self.formatDateTodayTomorrow(start)
            start = start.strftime("%H:%M")
            start = "%s %s" % (day,start)
            label = "%s - %s - %s" % (channelTitle.encode("utf8"),start,programTitle.encode("utf8"))
            labels.append(label)
        title = "AutoPlays"
        d = xbmcgui.Dialog()
        index = d.select(title,labels)
        if index > -1:
            program = programList[index]
            self._showContextMenu(program)

    def showFullAutoplays(self):
        programList = self.database.getFullAutoplays()
        title = "AutoPlays"
        d = ProgramListDialog(title, programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        if index > -1:
            self._showContextMenu(programList[index])

    def showAutoplaywiths(self):
        programList = self.database.getAutoplaywiths()
        labels = []
        for channelTitle, programTitle, start, end in programList:
            day = self.formatDateTodayTomorrow(start)
            start = start.strftime("%H:%M")
            start = "%s %s" % (day,start)
            label = "%s - %s - %s" % (channelTitle.encode("utf8"),start,programTitle.encode("utf8"))
            labels.append(label)
        title = "AutoPlayWiths"
        d = xbmcgui.Dialog()
        index = d.select(title,labels)
        if index > -1:
            program = programList[index]
            self._showContextMenu(program)

    def showFullAutoplaywiths(self):
        programList = self.database.getFullAutoplaywiths()
        title = "AutoPlayWiths"
        d = ProgramListDialog(title, programList, ADDON.getSetting('listing.sort.time') == 'true')
        d.doModal()
        index = d.index
        if index > -1:
            self._showContextMenu(programList[index])

    def _showContextMenu(self, program):
        self._hideControl(self.C_MAIN_MOUSE_CONTROLS)
        self._hideControl(self.C_MAIN_OSD_MOUSE_CONTROLS)
        self._hideControl(self.C_QUICK_EPG_MOUSE_CONTROLS)
        self._hideControl(self.C_MAIN_LAST_PLAYED_MOUSE_CONTROLS)
        if not program.imageSmall and (program.title in self.tvdb_urls):
            program.imageSmall = self.tvdb_urls[program.title]
        d = PopupMenu(self.database, program, not program.notificationScheduled, not program.autoplayScheduled, not program.autoplaywithScheduled, self.category, self.categories)
        d.doModal()
        buttonClicked = d.buttonClicked
        self.category = d.category
        ADDON.setSetting('category',self.category)
        self.database.setCategory(self.category)
        self.categories = d.categories
        del d

        if buttonClicked == PopupMenu.C_POPUP_REMIND:
            if program.notificationScheduled:
                self.notification.removeNotification(program)
            else:
                d = xbmcgui.Dialog()
                play_type = d.select("Notification play_type", ["once","always"]) #TODO ,"same time","same day"
                if play_type > -1:
                    self.notification.addNotification(program, play_type)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif buttonClicked == PopupMenu.C_POPUP_AUTOPLAY:
            if program.autoplayScheduled:
                self.autoplay.removeAutoplay(program)
            else:
                d = xbmcgui.Dialog()
                play_type = d.select("AutoPlay play_type", ["once","always"]) #TODO ,"same time","same day"
                if play_type > -1:
                    self.autoplay.addAutoplay(program, play_type)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif buttonClicked == PopupMenu.C_POPUP_AUTOPLAYWITH:
            if program.autoplaywithScheduled:
                self.autoplaywith.removeAutoplaywith(program)
            else:
                d = xbmcgui.Dialog()
                play_type = d.select("AutoPlayWith play_type", ["once","always"]) #TODO ,"same time","same day"
                if play_type > -1:
                    self.autoplaywith.addAutoplaywith(program, play_type)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif buttonClicked == PopupMenu.C_POPUP_LISTS:
            d = xbmcgui.Dialog()
            list = d.select("Lists", ["Channel Listing","On Now", "On Next", "Search", "Reminders", "AutoPlays", "AutoPlayWiths"])
            if list < 0:
                self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            if list == 0:
                self.showListing(program.channel)
            elif list == 1:
                self.showNow()
            elif list == 2:
                self.showNext()
            elif list == 3:
                self.programSearchSelect()
            elif list == 4:
                self.showFullReminders()
            elif list == 5:
                self.showFullAutoplays()
            elif list == 6:
                self.showFullAutoplaywiths()

        elif buttonClicked == PopupMenu.C_POPUP_CATEGORY:
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif buttonClicked == PopupMenu.C_POPUP_CHOOSE_STREAM:
            result = self.streamingService.detectStream(program.channel)
            if not result:
                # could not detect stream, show context menu
                self._showContextMenu(program)
            elif type(result) == str:
                # one single stream detected, save it and start streaming
                self.database.setCustomStreamUrl(program.channel, result)
                self.playChannel(program.channel, program)

            else:
                # multiple matches, let user decide

                d = ChooseStreamAddonDialog(result)
                d.doModal()
                if d.stream is not None:
                    self.database.setCustomStreamUrl(program.channel, d.stream)
                    self.playChannel(program.channel, program)

        elif buttonClicked == PopupMenu.C_POPUP_CHOOSE_ALT:
            result = self.streamingService.detectStream(program.channel,False)
            if not result:
                # could not detect stream, show context menu
                d = StreamSetupDialog(self.database, program.channel)
                d.doModal()
                del d
                self.streamingService = streaming.StreamsService(ADDON)
                self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            elif type(result) == str:
                # one single stream detected, save it and start streaming
                self.database.setCustomStreamUrl(program.channel, result)
            else:
                # multiple matches, let user decide
                d = ChooseStreamAddonDialog(result)
                d.doModal()
                if d.stream is not None:
                    self.database.setAltCustomStreamUrl(program.channel, d.title, d.stream)

        elif buttonClicked == PopupMenu.C_POPUP_STREAM_SETUP:
            d = StreamSetupDialog(self.database, program.channel)
            d.doModal()
            del d
            self.streamingService = streaming.StreamsService(ADDON)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif buttonClicked == PopupMenu.C_POPUP_PLAY:
            self.playChannel(program.channel, program)

        elif buttonClicked == PopupMenu.C_POPUP_CHANNELS:
            d = ChannelsMenu(self.database)
            d.doModal()
            del d
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif buttonClicked == PopupMenu.C_POPUP_QUIT:
            self.close()

        elif buttonClicked == PopupMenu.C_POPUP_LIBMOV:
            xbmc.executebuiltin('ActivateWindow(Videos,videodb://movies/titles/)')

        elif buttonClicked == PopupMenu.C_POPUP_LIBTV:
            xbmc.executebuiltin('ActivateWindow(Videos,videodb://tvshows/titles/)')

        elif buttonClicked == PopupMenu.C_POPUP_VIDEOADDONS:
            xbmc.executebuiltin('ActivateWindow(Videos,addons://sources/video/)')

        elif buttonClicked == PopupMenu.C_POPUP_PLAY_BEGINNING:
            title = program.title.replace(" ", "%20").replace(",", "").replace(u"\u2013", "-")
            title = unicode.encode(title, "ascii", "ignore")
            match = re.search('(.*?)\([0-9]{4}\)$',title)
            if match:
                title = match.group(1).strip()
                program.is_movie = "Movie"
            if program.is_movie == "Movie":
                selection = 0
            elif program.season:
                selection = 1
            else:
                selection = xbmcgui.Dialog().select("Choose media type",["Search as Movie", "Search as TV Show"])

            if not program.language:
                program.language = "en"

            catchup = ADDON.getSetting('catchup').lower()
            if selection == 0:
                xbmc.executebuiltin("RunPlugin(plugin://plugin.video.%s/movies/play_by_name/%s/%s)" % (
                    catchup, title, program.language))
            elif selection == 1:
                if program.season and program.episode:
                    xbmc.executebuiltin("RunPlugin(plugin://plugin.video.%s/tv/play_by_name/%s/%s/%s/%s)" % (
                        catchup, title, program.season, program.episode, program.language))
                else:
                    xbmc.executebuiltin("RunPlugin(plugin://plugin.video.%s/tv/play_by_name_only/%s/%s)" % (
                        catchup, title, program.language))
        elif buttonClicked == PopupMenu.C_POPUP_SUPER_FAVOURITES:
            if ADDON.getSetting('search.type') == 'MySearch':
                script = "special://home/addons/script.tvguide.fullscreen/search.py"
                if xbmcvfs.exists(script):
                    if program.season:
                        xbmc.executebuiltin('RunScript(%s,%s,%s,%s)' % (script, program.title, program.season, program.episode))
                    else:
                        xbmc.executebuiltin('RunScript(%s,%s)' % (script, program.title))
            else:
                xbmc.executebuiltin('ActivateWindow(10025,"plugin://plugin.program.super.favourites/?mode=0&keyword=%s",return)' % urllib.quote_plus(program.title))
        elif buttonClicked == PopupMenu.C_POPUP_FAVOURITES:
            favourites = ADDON.getSetting('favourites')
            if favourites == 'Simple Favourites':
                xbmc.executebuiltin("ActivateWindow(10001,plugin://plugin.program.simple.favourites,return)")
            elif favourites == 'Video Favourites':
                xbmc.executebuiltin("ActivateWindow(10025,plugin://plugin.video.favourites,return)")
            elif favourites == 'Super Favourites':
                xbmc.executebuiltin("ActivateWindow(10001,plugin://plugin.program.super.favourites,return)")
            elif favourites == 'Favourites':
                xbmc.executebuiltin("ActivateWindow(10134)")
        elif buttonClicked == PopupMenu.C_POPUP_EXTENDED:
            title = program.title
            match = re.search('(.*?)\([0-9]{4}\)$',title)
            if match:
                title = match.group(1).strip()
                program.is_movie = "Movie"
            if program.is_movie == "Movie":
                selection = 0
            elif program.season:
                selection = 1
            else:
                selection = xbmcgui.Dialog().select("Choose media type",["Search as Movie", "Search as TV Show", "Search as Either"])
            where = ["movie","tv","multi"]
            url = "https://api.themoviedb.org/3/search/%s?query=%s&api_key=d69992ec810d0f414d3de4a2294b8700&include_adult=false&page=1" % (where[selection],title)
            r = requests.get(url)
            data = json.loads(r.content)
            results = data.get('results')
            id = ''
            if results:
                if len(results) > 1:
                    names = ["%s (%s)" % (x.get('name') or x.get('title'),x.get('first_air_date') or x.get('release_date')) for x in results]
                    what = xbmcgui.Dialog().select(title,names)
                    if what > -1:
                        id = results[what].get('id')
                        ttype = results[what].get('media_ttype')
                        if ttype not in ["movie","tv"]:
                            if selection == 0:
                                ttype = "movie"
                            else:
                                ttype = "tv"
                        if ttype == 'movie':
                            xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedinfo,name=%s,id=%s)' % (title,id))
                        elif ttype == 'tv':
                            xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedtvinfo,name=%s,id=%s)' % (program.title,id))
                    else:
                        xbmcgui.Dialog().notification("TV Guide Fullscreen", "Couldn't find: %s" % title)
                else:
                    if selection == 0:
                        xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedinfo,name=%s)' % (title))
                    elif selection == 1:
                        xbmc.executebuiltin('RunScript(script.extendedinfo,info=extendedtvinfo,name=%s)' % (program.title))
            else:
                xbmcgui.Dialog().notification("TV Guide Fullscreen", "Couldn't find: %s" % title)

    def _showCatMenu(self):
        #self._hideControl(self.C_MAIN_MOUSE_CONTROLS)
        d = CatMenu(self.database, self.category, self.categories)
        d.doModal()
        buttonClicked = d.buttonClicked
        self.category = d.category
        ADDON.setSetting('category',self.category)
        #self.setControlLabel(self.C_MAIN_CAT_LABEL, '[B]%s[/B]' % self.category)
        self.database.setCategory(self.category)
        self.categories = d.categories
        del d

        if buttonClicked == CatMenu.C_CAT_CATEGORY:
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)


    def setFocusId(self, controlId):
        control = self.getControl(controlId)
        if control:
            self.setFocus(control)

    def setQuickFocusId(self, controlId):
        control = self.getControl(controlId)
        if control:
            self.setQuickFocus(control)

    def setFocus(self, control):
        if not control:
            return
        debug('setFocus %d' % control.getId())
        if control in [elem.control for elem in self.controlAndProgramList]:
            debug('Focus before %s' % self.focusPoint)
            (left, top) = control.getPosition()
            if left > self.focusPoint.x or left + control.getWidth() < self.focusPoint.x:
                self.focusPoint.x = left
            self.focusPoint.y = top + (control.getHeight() / 2)
            debug('New focus at %s' % self.focusPoint)

        super(TVGuide, self).setFocus(control)

    def setQuickFocus(self, control):
        if control in [elem.control for elem in self.quickControlAndProgramList]:
            (left, top) = control.getPosition()
            if left > self.quickFocusPoint.x or left + control.getWidth() < self.quickFocusPoint.x:
                self.quickFocusPoint.x = left
            self.quickFocusPoint.y = top + (control.getHeight() / 2)

        super(TVGuide, self).setFocus(control)

    def onFocus(self, controlId):
        if self.has_cat_bar and self.mode == MODE_EPG and controlId != self.C_MAIN_CATEGORY:
            listControl = self.getControl(self.C_MAIN_CATEGORY)
            if listControl:
                listControl.selectItem(self.cat_index)

        try:
            controlInFocus = self.getControl(controlId)
        except Exception:
            return
        program = self._getProgramFromControl(controlInFocus)
        self.focusedProgram = program
        if self.mode == MODE_QUICK_EPG:
            program = self._getQuickProgramFromControl(controlInFocus)

        if program is None:
            return

        if program.sub_title:
            title = '[B]%s - %s[/B]' % (program.title, program.sub_title)
        else:
            title = '[B]%s[/B]' % program.title
        if program.season and program.episode:
            title += " S%sE%s" % (program.season, program.episode)
        #if program.is_movie == "Movie":
        #    title += " [B](Movie)[/B]"

        if self.mode == MODE_QUICK_EPG:
            self.setControlLabel(self.C_QUICK_EPG_TITLE, title)
            if program.startDate or program.endDate:
                self.setControlLabel(self.C_QUICK_EPG_TIME,
                                 '[B]%s - %s[/B]' % (self.formatTime(program.startDate), self.formatTime(program.endDate)))
            else:
                self.setControlLabel(self.C_QUICK_EPG_TIME, '')
            if program.description:
                description = program.description
            else:
                description = ""
            self.setControlText(self.C_QUICK_EPG_DESCRIPTION, description)
            self.setControlLabel(self.C_QUICK_EPG_CHANNEL, '[B]%s[/B]' % program.channel.title)
            if program.channel.logo is not None:
                self.setControlImage(self.C_QUICK_EPG_LOGO, program.channel.logo)
            else:
                self.setControlImage(self.C_QUICK_EPG_LOGO, '')

        else:
            self.setControlLabel(self.C_MAIN_TITLE, title)
            if program.startDate or program.endDate:
                self.setControlLabel(self.C_MAIN_TIME,
                                     '[B]%s - %s[/B]' % (self.formatTime(program.startDate), self.formatTime(program.endDate)))
            else:
                self.setControlLabel(self.C_MAIN_TIME, '')
            if program.startDate and program.endDate:
                programprogresscontrol = self.getControl(self.C_MAIN_PROGRESS)
                if programprogresscontrol:
                    percent = self.percent(program.startDate,program.endDate)
                    programprogresscontrol.setPercent(percent)
            if program.description:
                description = program.description
            else:
                description = ""
            self.setControlText(self.C_MAIN_DESCRIPTION, description)

            self.setControlLabel(self.C_MAIN_CHANNEL, '[B]%s[/B]' % program.channel.title)

            if self.category in ["Any","All Channels"]:
                label = ''
            else:
                label = self.category
            self.setControlLabel(self.C_MAIN_CURRENT_CATEGORY, '[B]%s[/B]' % label)

            if program.channel.logo is not None:
                self.setControlImage(self.C_MAIN_LOGO, program.channel.logo)
            else:
                self.setControlImage(self.C_MAIN_LOGO, '')
            if ADDON.getSetting('channel.logo') == "true":
                self.setControlVisible(self.C_MAIN_LOGO,True)
            else:
                self.setControlVisible(self.C_MAIN_LOGO,False)

            program_image = ''
            if ADDON.getSetting('program.image') == 'true':
                if program.imageSmall:
                    program_image = program.imageSmall
                else:
                    program_image = ''
                if program.imageLarge:
                    program_image = program.imageLarge

            if not program_image and ADDON.getSetting('find.program.images') == 'true': #TODO
                if program.title in self.tvdb_urls:
                    program_image = self.tvdb_urls[program.title]
                else:
                    title = program.title
                    year = ''
                    season = program.season
                    episode = program.episode
                    movie = program.is_movie
                    match = re.search('(.*?) \(([0-9]{4})\)',program.title)
                    if match:
                        title = match.group(1)
                        year = match.group(2)
                    threading.Thread(target=self.getImage,args=(program.title,title,year,season,episode,movie,True)).start()

            for control in [self._findControlBelow(self.focusPoint), self._findControlOnRight(self.focusPoint),
            self._findControlAbove(self.focusPoint),self._findControlOnRight(self.focusPoint)]:
                prog = self._getProgramFromControl(control)
                if prog:
                    if prog.title not in self.tvdb_urls:
                        title = prog.title
                        year = ''
                        season = prog.season
                        episode = prog.episode
                        movie = prog.is_movie
                        match = re.search('(.*?) \(([0-9]{4})\)',prog.title)
                        if match:
                            title = match.group(1)
                            year = match.group(2)
                        threading.Thread(target=self.getImage,args=(prog.title,title,year,season,episode,movie,False)).start()


            if not program_image and (ADDON.getSetting('program.channel.logo') == "true"):
                program_image = program.channel.logo
            if not program_image:
                program_image = "tvg-tv.png"
            self.setControlImage(self.C_MAIN_IMAGE, program_image)

            color = colors.color_name["white"]
            if ADDON.getSetting('program.background.enabled') == 'true' and program.imageSmall:
                program_image = re.sub(' ','+',program.imageSmall)
                self.setControlImage(self.C_MAIN_BACKGROUND, program_image)
            else:
                image = ''
                source = ADDON.getSetting('program.background.image.source')
                if source == "1":
                    image = ADDON.getSetting('program.background.image')
                elif source == "2":
                    image = ADDON.getSetting('program.background.image.url')
                if image:
                    self.setControlImage(self.C_MAIN_BACKGROUND, image)
                else:
                    if ADDON.getSetting("program.background.flat") == 'true':
                        self.setControlImage(self.C_MAIN_BACKGROUND, "white.png")
                    else:
                        self.setControlImage(self.C_MAIN_BACKGROUND, ADDON.getSetting("program.background.texture.url"))
                    name = remove_formatting(ADDON.getSetting('program.background.color'))
                    color = colors.color_name[name]

            control = self.getControl(self.C_MAIN_BACKGROUND)
            control.setColorDiffuse(color)

            #if not self.osdEnabled and self.player.isPlaying():
            #    self.player.stop()

    def getImage(self,program_title,title,year,season,episode,movie,load):
        img = ''
        imdbID = ''
        plot = ''
        unique = False
        if ADDON.getSetting('omdb') == 'true':
            if year:
                url = 'http://www.omdbapi.com/?t=%s&y=%s&plot=short&r=json&type=movie' % (urllib.quote_plus(title.encode("utf8"),year))
            elif movie:
                url = 'http://www.omdbapi.com/?t=%s&y=&plot=short&r=json&type=movie' % (urllib.quote_plus(title.encode("utf8")))
            elif season and episode:
                unique = True
                url = 'http://www.omdbapi.com/?t=%s&y=&plot=short&r=json&type=episode&Season=%s&Episode=%s' % (urllib.quote_plus(title.encode("utf8"),season,episode))
            else:
                url = 'http://www.omdbapi.com/?t=%s&y=&plot=short&r=json' % urllib.quote_plus(title.encode("utf8"))
            try: data = requests.get(url).content
            except: data = ''

            if data:
                try:
                    j = json.loads(data)
                    if j['Response'] != 'False':
                        img = j.get('Poster','')
                        plot = j.get('Plot','')
                        imdbID = j.get('imdbID','')
                        if plot == 'N/A':
                            plot = ''
                        if img == 'N/A':
                            img = ''
                        if imdbID == 'N/A':
                            imdbID = ''
                except:
                    pass


            if not img and imdbID and (ADDON.getSetting('tvdb.imdb') == 'true'):
                url = 'http://www.imdb.com/title/%s/' % imdbID
                headers = {'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'}
                try:html = requests.get(url,headers=headers).content
                except: html = ''
                match = re.search('Poster".*?src="(.*?)"',html,flags=(re.DOTALL | re.MULTILINE))
                if match:
                    img = match.group(1)
                    if ADDON.getSetting('imdb.big') == 'true':
                        img = re.sub(r'S[XY].*_.jpg','SY240_.jpg',img)

                if not movie:
                    tvdb_url = "http://thetvdb.com/api/GetSeriesByRemoteID.php?imdbid=%s" % imdbID
                    try:
                        r = requests.get(tvdb_url)
                        tvdb_html = r.text
                    except:
                        return
                    tvdb_match = re.search(re.compile(r'<seriesid>(.*?)</seriesid>', flags=(re.DOTALL | re.MULTILINE)), tvdb_html)
                    if tvdb_match:
                        tvdb_id = tvdb_match.group(1)
                        url = 'http://thetvdb.com/?tab=series&id=%s' % tvdb_id
                        html = requests.get(url).content
                        match = re.search('<img src="(/banners/_cache/fanart/original/.*?\.jpg)"',html)
                        if match:
                            img = "http://thetvdb.com%s" % re.sub('amp;','',match.group(1))

            if img:
                if not unique:
                    self.tvdb_urls[program_title] = img
                #log(("omdb",program_title,img))

        if not img and (ADDON.getSetting('tvdb.imdb') == 'true'):
            if not (year or movie):
                self.getTVDBImage(program_title, season, episode, load)
            else:
                self.getIMDBImage(title, year, load)
            return


        if load and self.focusedProgram and (self.focusedProgram.title.encode("utf8") == program_title):
            if img:
                self.setControlImage(self.C_MAIN_IMAGE, img)
            if plot and not self.focusedProgram.description:
                self.setControlText(self.C_MAIN_DESCRIPTION, plot)


    def getOMDbInfo(self,program_title,title,year,season,episode):
        if year:
            url = 'http://www.omdbapi.com/?t=%s&y=%s&plot=short&r=json&type=movie' % (urllib.quote_plus(title),year)
        elif season and episode:
            url = 'http://www.omdbapi.com/?t=%s&y=&plot=short&r=json&type=episode&Season=%s&Episode=%s' % (urllib.quote_plus(title),season,episode)
        else:
            url = 'http://www.omdbapi.com/?t=%s&y=&plot=short&r=json' % urllib.quote_plus(title)
        try: data = requests.get(url).content
        except: return
        try:
            j = json.loads(data)
        except:
            return
        if j['Response'] == 'False':
            return
        img = j.get('Poster','')
        plot = j.get('Plot','')
        if plot == 'N/A':
            plot = ''
        if img == 'N/A':
            img = ''

        if self.focusedProgram and (self.focusedProgram.title.encode("utf8") == program_title):
            if img:
                #log(("omdb",title,img))
                self.setControlImage(self.C_MAIN_IMAGE, img)
            if plot and not self.focusedProgram.description:
                self.setControlText(self.C_MAIN_DESCRIPTION, plot)
        if img:
            return img


    def getTVDBImage(self, title, season, episode, load=True):
        orig_title = title
        try: title = title.encode("utf8")
        except: title = unicode(title)
        url = "http://thetvdb.com/?string=%s&searchseriesid=&tab=listseries&function=Search" % urllib.quote_plus(title)
        try:
            html = requests.get(url).content
        except:
            return
        match = re.search('<a href="(/\?tab=series&amp;id=.*?)">(.*?)</a>',html)
        tvdb_url = ''
        if match:
            url = "http://thetvdb.com%s" % re.sub('amp;','',match.group(1))
            name = match.group(2).strip()
            found = False
            tvdb_match = ADDON.getSetting('tvdb.match')
            if not title:
                found = False
            elif tvdb_match == "0":
                if title.lower().strip() ==  name.lower().strip():
                    found = True
            elif tvdb_match == "1":
                title_search = re.escape(title.lower().strip())
                name_search = name.lower().strip()
                if re.search(title_search,name_search):
                    found = True
                else:
                    title_search = title.lower().strip()
                    name_search = re.escape(name.lower().strip())
                    if ' ' in title and re.search(name_search,title_search):
                        found = True
            elif tvdb_match == "2":
                found = True
            if found:
                try:
                    html = requests.get(url).content
                except:
                    return
                for type in ["fanart/original","posters","graphical"]:
                    match = re.search('<img src="(/banners/_cache/%s/.*?\.jpg)"' % type,html)
                    if match:
                        tvdb_url = "http://thetvdb.com%s" % re.sub('amp;','',match.group(1))
                        break


        if title not in self.tvdb_urls:
            self.tvdb_urls[title] = tvdb_url
            #log(("tvdb",title,tvdb_url))
        if load and tvdb_url and self.focusedProgram and (self.focusedProgram.title.encode("utf8") == title):
            self.setControlImage(self.C_MAIN_IMAGE, tvdb_url)

    def getIMDBImage(self, title, year, load=True):
        orig_title = "%s (%s)" % (title,year)
        try: utf_title = orig_title.encode("utf8")
        except: utf_title = unicode(utf_title)
        headers = {'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'}
        url = "http://www.bing.com/search?q=site%%3Aimdb.com+%s" % urllib.quote_plus(utf_title)
        try: html = requests.get(url).content
        except: return

        match = re.search('href="(http://www.imdb.com/title/tt.*?/)".*?<strong>(.*?)</strong>',html)
        tvdb_url = ''
        if match:
            url = match.group(1)
            name = match.group(2)
            name = re.sub('\([0-9]*$','',name)
            name = name.strip()
            found = False
            imdb_match = ADDON.getSetting('imdb.match')
            if not title:
                found = False
            elif imdb_match == "0":
                if title.lower().strip() ==  name.lower().strip():
                    found = True
            elif imdb_match == "1":
                title_search = re.escape(title.lower().strip())
                name_search = name.lower().strip()
                if re.search(title_search,name_search):
                    found = True
                else:
                    title_search = title.lower().strip()
                    name_search = re.escape(name.lower().strip())
                    if re.search(name_search,title_search):
                        found = True
            elif imdb_match == "2":
                found = True
            if found:
                try: html = requests.get(url,headers=headers).content
                except: return
                match = re.search('Poster".*?src="(.*?)"',html,flags=(re.DOTALL | re.MULTILINE))
                if match:
                    tvdb_url = match.group(1)
                    if ADDON.getSetting('imdb.big') == 'true':
                        tvdb_url = re.sub(r'S[XY].*_.jpg','SY240_.jpg',tvdb_url)

        if orig_title not in self.tvdb_urls:
            self.tvdb_urls[orig_title] = tvdb_url
        if load and tvdb_url and self.focusedProgram and (self.focusedProgram.title.encode("utf8") == utf_title):
            self.setControlImage(self.C_MAIN_IMAGE, tvdb_url)


    def _left(self, currentFocus):
        control = self._findControlOnLeft(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            self.viewStartDate -= datetime.timedelta(hours=2)
            self.focusPoint.x = self.epgView.right
            self.onRedrawEPG(self.channelIdx, self.viewStartDate, focusFunction=self._findControlOnLeft)

    def _quickLeft(self, currentFocus):
        control = self._findQuickControlOnLeft(currentFocus)
        if control is not None:
            self.setQuickFocus(control)
        elif control is None:
            self.quickViewStartDate -= datetime.timedelta(hours=2)
            self.quickFocusPoint.x = self.quickEpgView.right
            self.onRedrawQuickEPG(self.quickChannelIdx, self.quickViewStartDate, focusFunction=self._findQuickControlOnLeft)

    def _right(self, currentFocus):
        control = self._findControlOnRight(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            self.viewStartDate += datetime.timedelta(hours=2)
            self.focusPoint.x = self.epgView.left
            self.onRedrawEPG(self.channelIdx, self.viewStartDate, focusFunction=self._findControlOnRight)

    def _quickRight(self, currentFocus):
        control = self._findQuickControlOnRight(currentFocus)
        if control is not None:
            self.setQuickFocus(control)
        elif control is None:
            self.quickViewStartDate += datetime.timedelta(hours=2)
            self.quickFocusPoint.x = self.quickEpgView.left
            self.onRedrawQuickEPG(self.quickChannelIdx, self.quickViewStartDate, focusFunction=self._findQuickControlOnRight)

    def _up(self, currentFocus):
        if self.getFocusId() in [self.C_MAIN_ACTIONS]:
            currentFocus.y = 1280
        currentFocus.x = self.focusPoint.x
        control = self._findControlAbove(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            if self.getControl(self.C_MAIN_CATEGORY) and ADDON.getSetting('up.cat.mode') == 'Always':
                self.setFocusId(self.C_MAIN_CATEGORY)
                return
            first_channel = self.channelIdx - CHANNELS_PER_PAGE
            if first_channel < 0:
                if self.getControl(self.C_MAIN_CATEGORY) and ADDON.getSetting('up.cat.mode') == 'First Channel':
                    self.setFocusId(self.C_MAIN_CATEGORY)
                    return
                len_channels = self.database.getNumberOfChannels()
                last_page = len_channels % CHANNELS_PER_PAGE
                first_channel = len_channels - last_page
            self.focusPoint.y = self.epgView.bottom
            self.onRedrawEPG(first_channel, self.viewStartDate,
                             focusFunction=self._findControlAbove)

    def _quickUp(self, currentFocus):
        currentFocus.x = self.quickFocusPoint.x
        control = self._findQuickControlAbove(currentFocus)
        if control is not None:
            self.setQuickFocus(control)
        elif control is None:
            first_channel = self.quickChannelIdx - 3
            if first_channel < 0:
                len_channels = self.database.getNumberOfChannels()
                last_page = len_channels % 3
                first_channel = len_channels - last_page
            self.quickFocusPoint.y = self.quickEpgView.bottom
            self.onRedrawQuickEPG(first_channel, self.quickViewStartDate,
                             focusFunction=self._findQuickControlAbove)

    def _down(self, currentFocus):
        if self.getFocusId() in [self.C_MAIN_CATEGORY, self.C_MAIN_PROGRAM_CATEGORIES]:
            currentFocus.y = 0
        currentFocus.x = self.focusPoint.x
        control = self._findControlBelow(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            if self.getControl(self.C_MAIN_ACTIONS) and ADDON.getSetting('action.bar') == 'true' and ADDON.getSetting('down.action') == 'true':
                self.setFocusId(self.C_MAIN_ACTIONS)
                return
            self.focusPoint.y = self.epgView.top
            self.onRedrawEPG(self.channelIdx + CHANNELS_PER_PAGE, self.viewStartDate,
                             focusFunction=self._findControlBelow)

    def _quickDown(self, currentFocus):
        currentFocus.x = self.quickFocusPoint.x
        control = self._findQuickControlBelow(currentFocus)
        if control is not None:
            self.setQuickFocus(control)
        elif control is None:
            self.quickFocusPoint.y = self.quickEpgView.top
            self.onRedrawQuickEPG(self.quickChannelIdx + 3, self.quickViewStartDate,
                             focusFunction=self._findQuickControlBelow)

    def _nextDay(self):
        self.viewStartDate += datetime.timedelta(days=1)
        self.onRedrawEPG(self.channelIdx, self.viewStartDate)

    def _quickNextDay(self):
        self.quickViewStartDate += datetime.timedelta(days=1)
        self.onRedrawQuickEPG(self.quickChannelIdx, self.quickViewStartDate)

    def _previousDay(self):
        self.viewStartDate -= datetime.timedelta(days=1)
        self.onRedrawEPG(self.channelIdx, self.viewStartDate)

    def _quickPreviousDay(self):
        self.quickViewStartDate -= datetime.timedelta(days=1)
        self.onRedrawQuickEPG(self.quickChannelIdx, self.quickViewStartDate)

    def _moveUp(self, count=1, scrollEvent=False):
        first_channel = self.channelIdx - count
        if first_channel < 0:
            len_channels = self.database.getNumberOfChannels()
            last_page = len_channels % CHANNELS_PER_PAGE
            first_channel = len_channels - last_page
        if scrollEvent:
            self.onRedrawEPG(first_channel, self.viewStartDate)
        else:
            self.focusPoint.y = self.epgView.bottom
            self.onRedrawEPG(first_channel, self.viewStartDate, focusFunction=self._findControlAbove)

    def _quickMoveUp(self, count=1, scrollEvent=False):
        first_channel = self.quickChannelIdx - count
        if first_channel < 0:
            len_channels = self.database.getNumberOfChannels()
            last_page = len_channels % 3
            first_channel = len_channels - last_page
        if scrollEvent:
            self.onRedrawQuickEPG(first_channel, self.quickViewStartDate)
        else:
            self.quickFocusPoint.y = self.quickEpgView.bottom
            self.onRedrawQuickEPG(first_channel, self.quickViewStartDate, focusFunction=self._findQuickControlAbove)

    def _moveDown(self, count=1, scrollEvent=False):
        if scrollEvent:
            self.onRedrawEPG(self.channelIdx + count, self.viewStartDate)
        else:
            self.focusPoint.y = self.epgView.top
            self.onRedrawEPG(self.channelIdx + count, self.viewStartDate, focusFunction=self._findControlBelow)

    def _quickMoveDown(self, count=1, scrollEvent=False):
        if scrollEvent:
            self.onRedrawQuickEPG(self.quickChannelIdx + count, self.quickViewStartDate)
        else:
            self.quickFocusPoint.y = self.quickEpgView.top
            self.onRedrawQuickEPG(self.quickChannelIdx + count, self.quickViewStartDate, focusFunction=self._findQuickControlBelow)

    def _channelUp(self):
        channel = self.database.getNextChannel(self.currentChannel)
        program = self.database.getCurrentProgram(channel)
        self.playOrChoose(program)

    def _channelDown(self):
        channel = self.database.getPreviousChannel(self.currentChannel)
        program = self.database.getCurrentProgram(channel)
        self.playOrChoose(program)

    def playChannel(self, channel, program = None):
        if ADDON.getSetting('epg.video.pip') == 'true':
            self.setControlVisible(self.C_MAIN_IMAGE,True)
        url = self.database.getStreamUrl(channel)
        alt_url = self.database.getAltStreamUrl(channel)
        self.alt_urls = []
        if url and alt_url:
            d = xbmcgui.Dialog()
            alt_urls = [url] + [x[0] for x in alt_url]
            self.alt_urls = alt_urls
            names = []
            alt_url = [(url,channel.title)] + alt_url
            for u in alt_url:
                match = re.match('plugin://(.*?)/',u[0])
                if match:
                    plugin = match.group(1)
                    plugin = xbmcaddon.Addon(plugin).getAddonInfo('name')
                else:
                    plugin = "Favourite"
                names.append("%s - %s" % (plugin,u[1]))
            names[0] = "%s" % names[0]
            result = d.select("%s" % channel.title, names)
            if result > -1:
                url = alt_urls[result]
                self.alt_urls.remove(url)
            else:
                return True
        if self.currentChannel:
            self.lastChannel = self.currentChannel
            s = json.dumps([self.lastChannel.id, self.lastChannel.title, self.lastChannel.lineup, self.lastChannel.logo, self.lastChannel.streamUrl, self.lastChannel.visible, self.lastChannel.weight])
            ADDON.setSetting('last.channel',s)
        self.currentChannel = channel
        self.currentProgram = self.database.getCurrentProgram(self.currentChannel)
        wasPlaying = self.player.isPlaying()
        if url:
            self.player.stop()
            if url.startswith("plugin://plugin.video.meta/movies/play_by_name") and program is not None:
                import urllib
                title = urllib.quote(program.title)
                url += "/%s/%s" % (title, program.language)
            if url.startswith("plugin://plugin.video.meta/tv/play_by_name") and program is not None:
                import urllib
                title = urllib.quote(program.title)
                url += "%s/%s/%s/%s" % (title, program.season, program.episode, program.language)
            if url.startswith('@'):
                xbmc.executebuiltin('XBMC.RunPlugin(%s)' % url[1:])
            elif url[0:14] == "ActivateWindow":
                xbmc.executebuiltin(url)
            elif url[0:9] == 'plugin://':
                if self.alternativePlayback:
                    xbmc.executebuiltin('XBMC.RunPlugin(%s)' % url)
                else:
                    self.player.play(item=url, windowed=self.osdEnabled)
            else:
                self.player.play(item=url, windowed=self.osdEnabled)

            self.tryingToPlay = True
            if ADDON.getSetting('play.minimized') == 'false':
                self._hideEpg()
                self._hideQuickEpg()
                threading.Timer(1, self.waitForPlayBackStopped, [channel.title]).start()
            self.osdProgram = self.database.getCurrentProgram(self.currentChannel)

        return url is not None

    def playWithChannel(self, channel, program = None):
        if ADDON.getSetting('epg.video.pip') == 'true':
            self.setControlVisible(self.C_MAIN_IMAGE,False)
        if self.currentChannel:
            self.lastChannel = self.currentChannel
        self.currentChannel = channel
        self.currentProgram = self.database.getCurrentProgram(self.currentChannel)
        if not self.currentProgram:
            return
        wasPlaying = self.player.isPlaying()
        url = self.database.getStreamUrl(channel)
        if url:
            now = datetime.datetime.now()
            timestamp = time.mktime(self.currentProgram.startDate.timetuple())
            script = "special://profile/addon_data/script.tvguide.fullscreen/playwithchannel.py"
            if xbmcvfs.exists(script):
                xbmc.executebuiltin('RunScript(%s,%s,%s)' % (script,channel.id,timestamp))
            core = ADDON.getSetting('autoplaywith.player')
            if core:
                xbmc.executebuiltin('PlayWith(%s)' % core)
                xbmc.executebuiltin('PlayMedia(%s)' % url)


    def stopWith(self):
        script = "special://profile/addon_data/script.tvguide.fullscreen/stopwithchannel.py"
        if xbmcvfs.exists(script):
            xbmc.executebuiltin('RunScript(%s)' % (script))
        xbmc.Player().stop()


    def waitForPlayBackStopped(self,title):
        time.sleep(0.5)
        self._showOsd()
        self.osdActive = False
        time.sleep(int(ADDON.getSetting('playback.osd.timeout')))

        countdown = int(ADDON.getSetting('playback.timeout'))
        while countdown:
            time.sleep(1)
            countdown = countdown - 1
            if self.player.isPlaying():
                if self.mode == MODE_OSD and not self.osdActive:
                    self._hideOsd()
                return
            if self.tryingToPlay == False:
                return
        dialog = xbmcgui.Dialog()
        dialog.notification('Stream Failed', title, xbmcgui.NOTIFICATION_ERROR, 5000, sound=True)

        finish = False
        if ADDON.getSetting('play.alt.continue') == 'true':
            if self.alt_urls:
                url = self.alt_urls.pop(0)
                #TODO meta
                if url.startswith('@'):
                    xbmc.executebuiltin('XBMC.RunPlugin(%s)' % url[1:])
                elif url[0:14] == "ActivateWindow":
                    xbmc.executebuiltin(url)
                elif url[0:9] == 'plugin://':
                    if self.alternativePlayback:
                        xbmc.executebuiltin('XBMC.RunPlugin(%s)' % url)
                    else:
                        self.player.play(item=url, windowed=self.osdEnabled)
                else:
                    self.player.play(item=url, windowed=self.osdEnabled)
                self.tryingToPlay = True
                if ADDON.getSetting('play.minimized') == 'false':
                    self._hideEpg()
                    self._hideQuickEpg()
                threading.Timer(1, self.waitForPlayBackStopped, [title]).start()
            else:
                finish = True
        else:
            finish = True

        if finish:
            if not self.osdActive:
                self._hideOsd()
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)


    def _updateNextUpInfo(self,firstTime):
        if self.currentProgram and self.lastOsdProgram and self.currentProgram != self.lastOsdProgram:
            # a change so update last
            self.lastOsdProgram = self.currentProgram
        elif self.currentProgram and not self.lastOsdProgram:
            # no last so set it
            self.lastOsdProgram = self.currentProgram

        self._populateNextUpInfo(firstTime)

    def _populateNextUpInfo(self,firstTime):
        if self.currentProgram is not None and firstTime:
            self.setControlLabel(self.C_MAIN_UP_NEXT_TITLE, '[B]%s[/B]' % self.currentProgram.title)
            if self.currentProgram.startDate or self.currentProgram.endDate:
                self.setControlLabel(self.C_MAIN_UP_NEXT_TIME, '[B]%s - %s[/B]' % (
                    self.formatTime(self.currentProgram.startDate), self.formatTime(self.currentProgram.endDate)))
            else:
                self.setControlLabel(self.C_MAIN_UP_NEXT_TIME, '')
            if self.currentProgram.startDate and self.currentProgram.endDate:
                osdprogramprogresscontrol = self.getControl(self.C_MAIN_OSD_PROGRESS)
                if osdprogramprogresscontrol:
                    osdprogramprogresscontrol.setPercent(self.percent(self.currentProgram.startDate,self.currentProgram.endDate))
                remainingseconds = int(timedelta_total_seconds((self.currentProgram.endDate - datetime.datetime.now())))
                self.setControlLabel(self.C_MAIN_UP_NEXT_TIME_REMAINING, '%s' % remainingseconds)

            self.setControlText(self.C_MAIN_UP_NEXT_DESCRIPTION, self.currentProgram.description)
            self.setControlLabel(self.C_MAIN_UP_NEXT_CHANNEL_TITLE, self.currentChannel.title)
            if self.currentProgram.channel.logo is not None:
                self.setControlImage(self.C_MAIN_UP_NEXT_CHANNEL_LOGO, self.currentProgram.channel.logo)
            else:
                self.setControlImage(self.C_MAIN_UP_NEXT_CHANNEL_LOGO, '')
            if self.currentProgram.imageSmall is not None:
                self.setControlImage(self.C_MAIN_UP_NEXT_CHANNEL_IMAGE, self.currentProgram.imageSmall)
            else:
                self.setControlImage(self.C_MAIN_UP_NEXT_CHANNEL_IMAGE, '')

            try: nextOsdProgram = self.database.getNextProgram(self.currentProgram)
            except: return
            if nextOsdProgram:
                self.setControlText(self.C_NEXT_UP_NEXT_DESCRIPTION, nextOsdProgram.description)
                self.setControlLabel(self.C_NEXT_UP_NEXT_TITLE, nextOsdProgram.title)
                if nextOsdProgram.startDate or nextOsdProgram.endDate:
                    self.setControlLabel(self.C_NEXT_UP_NEXT_TIME, '%s - %s' % (
                        self.formatTime(nextOsdProgram.startDate), self.formatTime(nextOsdProgram.endDate)))
                else:
                    self.setControlLabel(self.C_NEXT_UP_NEXT_TIME, '')
                try:
                    nextOsdControl = self.getControl(self.C_NEXT_UP_NEXT_CHANNEL_IMAGE)
                    if nextOsdControl != None and nextOsdProgram.imageSmall is not None:
                        nextOsdControl.setImage(nextOsdProgram.imageSmall)
                    elif nextOsdControl != None:
                        nextOsdControl.setImage('')
                except:
                    pass
        elif self.currentProgram is not None and not firstTime:
            if self.currentProgram.startDate and self.currentProgram.endDate:
                remainingseconds = int(timedelta_total_seconds((self.currentProgram.endDate - datetime.datetime.now())))
                self.setControlLabel(self.C_MAIN_UP_NEXT_TIME_REMAINING, '%s' % remainingseconds)
    def _showOsd(self):
        if not self.osdEnabled:
            return

        if self.mode != MODE_OSD:
            self.osdChannel = self.currentChannel

        if not self.osdChannel:
            self.osdChannel = self.currentChannel
        if not self.osdChannel:
            return #TODO this should not happen
        if self.osdProgram is not None:
            self.setControlLabel(self.C_MAIN_OSD_TITLE, '[B]%s[/B]' % self.osdProgram.title)
            if self.osdProgram.startDate or self.osdProgram.endDate:
                self.setControlLabel(self.C_MAIN_OSD_TIME, '[B]%s - %s[/B]' % (
                    self.formatTime(self.osdProgram.startDate), self.formatTime(self.osdProgram.endDate)))
            else:
                self.setControlLabel(self.C_MAIN_OSD_TIME, '')
            if self.osdProgram.startDate and self.osdProgram.endDate:
                osdprogramprogresscontrol = self.getControl(self.C_MAIN_OSD_PROGRESS)
                if osdprogramprogresscontrol:
                    osdprogramprogresscontrol.setPercent(self.percent(self.osdProgram.startDate,self.osdProgram.endDate))
            self.setControlText(self.C_MAIN_OSD_DESCRIPTION, self.osdProgram.description)
            self.setControlLabel(self.C_MAIN_OSD_CHANNEL_TITLE, self.osdChannel.title)
            if self.osdProgram.channel.logo is not None:
                self.setControlImage(self.C_MAIN_OSD_CHANNEL_LOGO, self.osdProgram.channel.logo)
            else:
                self.setControlImage(self.C_MAIN_OSD_CHANNEL_LOGO, '')
            if self.osdProgram.imageSmall is not None:
                self.setControlImage(self.C_MAIN_OSD_CHANNEL_IMAGE, self.osdProgram.imageSmall)
            else:
                self.setControlImage(self.C_MAIN_OSD_CHANNEL_IMAGE, '')

            nextOsdProgram = self.database.getNextProgram(self.osdProgram)
            if nextOsdProgram:
                self.setControlText(self.C_NEXT_OSD_DESCRIPTION, nextOsdProgram.description)
                self.setControlLabel(self.C_NEXT_OSD_TITLE, nextOsdProgram.title)
                if nextOsdProgram.startDate or nextOsdProgram.endDate:
                    self.setControlLabel(self.C_NEXT_OSD_TIME, '%s - %s' % (
                        self.formatTime(nextOsdProgram.startDate), self.formatTime(nextOsdProgram.endDate)))
                else:
                    self.setControlLabel(self.C_NEXT_OSD_TIME, '')
                try:
                    nextOsdControl = self.getControl(self.C_NEXT_OSD_CHANNEL_IMAGE)
                    if nextOsdControl != None and nextOsdProgram.imageSmall is not None:
                        nextOsdControl.setImage(nextOsdProgram.imageSmall)
                    elif nextOsdControl != None:
                        nextOsdControl.setImage('')
                except:
                    pass

        self.mode = MODE_OSD
        self._showControl(self.C_MAIN_OSD)

    def _showOsdBig(self):
        if not self.osdEnabled:
            return

        if self.mode != MODE_OSD_BIG:
            self.osdChannel = self.currentChannel

        if not self.osdChannel:
            self.osdChannel = self.currentChannel
        if not self.osdChannel:
            return #TODO this should not happen
        if self.osdProgram is not None:
            self.setControlLabel(self.C_MAIN_OSD_TITLE, '[B]%s[/B]' % self.osdProgram.title)
            if self.osdProgram.startDate or self.osdProgram.endDate:
                self.setControlLabel(self.C_MAIN_OSD_TIME, '[B]%s - %s[/B]' % (
                    self.formatTime(self.osdProgram.startDate), self.formatTime(self.osdProgram.endDate)))
            else:
                self.setControlLabel(self.C_MAIN_OSD_TIME, '')
            if self.osdProgram.startDate and self.osdProgram.endDate:
                osdprogramprogresscontrol = self.getControl(self.C_MAIN_OSD_BIG_PROGRESS)
                if osdprogramprogresscontrol:
                    osdprogramprogresscontrol.setPercent(self.percent(self.osdProgram.startDate,self.osdProgram.endDate))
            self.setControlText(self.C_MAIN_OSD_DESCRIPTION, self.osdProgram.description)
            self.setControlLabel(self.C_MAIN_OSD_CHANNEL_TITLE, self.osdChannel.title)
            if self.osdProgram.channel.logo is not None:
                self.setControlImage(self.C_MAIN_OSD_BIG_CHANNEL_LOGO, self.osdProgram.channel.logo)
            else:
                self.setControlImage(self.C_MAIN_OSD_BIG_CHANNEL_LOGO, '')
            if self.osdProgram.imageSmall is not None:
                self.setControlImage(self.C_MAIN_OSD_BIG_CHANNEL_IMAGE, self.osdProgram.imageSmall)
            else:
                self.setControlImage(self.C_MAIN_OSD_BIG_CHANNEL_IMAGE, '')

            nextOsdProgram = self.database.getNextProgram(self.osdProgram)
            if nextOsdProgram:
                self.setControlText(self.C_NEXT_OSD_DESCRIPTION, nextOsdProgram.description)
                self.setControlLabel(self.C_NEXT_OSD_TITLE, nextOsdProgram.title)
                if nextOsdProgram.startDate or nextOsdProgram.endDate:
                    self.setControlLabel(self.C_NEXT_OSD_TIME, '%s - %s' % (
                        self.formatTime(nextOsdProgram.startDate), self.formatTime(nextOsdProgram.endDate)))
                else:
                    self.setControlLabel(self.C_NEXT_OSD_TIME, '')
                try:
                    nextOsdControl = self.getControl(self.C_NEXT_OSD_CHANNEL_IMAGE)
                    if nextOsdControl != None and nextOsdProgram.imageSmall is not None:
                        nextOsdControl.setImage(nextOsdProgram.imageSmall)
                    elif nextOsdControl != None:
                        nextOsdControl.setImage('')
                except:
                    pass

        self.mode = MODE_OSD_BIG
        self._showControl(self.C_MAIN_OSD_BIG)

    def _showLastPlayedChannel(self):
        if not self.lastChannel:
            return

        self.lastProgram = self.database.getCurrentProgram(self.lastChannel)

        if self.lastProgram is not None:
            self.setControlLabel(self.C_MAIN_LAST_PLAYED_TITLE, '[B]%s[/B]' % self.lastProgram.title)
            if self.lastProgram.startDate or self.lastProgram.endDate:
                self.setControlLabel(self.C_MAIN_LAST_PLAYED_TIME, '[B]%s - %s[/B]' % (
                    self.formatTime(self.lastProgram.startDate), self.formatTime(self.lastProgram.endDate)))
            else:
                self.setControlLabel(self.C_MAIN_LAST_PLAYED_TIME, '')
            if self.lastProgram.startDate and self.lastProgram.endDate:
                osdprogramprogresscontrol = self.getControl(self.C_MAIN_LAST_PLAYED_PROGRESS)
                if osdprogramprogresscontrol:
                    osdprogramprogresscontrol.setPercent(self.percent(self.lastProgram.startDate,self.lastProgram.endDate))
            self.setControlText(self.C_MAIN_LAST_PLAYED_DESCRIPTION, self.lastProgram.description)
            self.setControlLabel(self.C_MAIN_LAST_PLAYED_CHANNEL_TITLE, self.lastChannel.title)
            if self.lastProgram.channel.logo is not None:
                self.setControlImage(self.C_MAIN_LAST_PLAYED_CHANNEL_LOGO, self.lastProgram.channel.logo)
            else:
                self.setControlImage(self.C_MAIN_LAST_PLAYED_CHANNEL_LOGO, '')
            if self.lastProgram.imageSmall is not None:
                self.setControlImage(self.C_MAIN_LAST_PLAYED_CHANNEL_IMAGE, self.lastProgram.imageSmall)
            else:
                self.setControlImage(self.C_MAIN_LAST_PLAYED_CHANNEL_IMAGE, '')

            nextLastPlayedProgram = self.database.getNextProgram(self.lastProgram)
            if nextLastPlayedProgram:
                self.setControlText(self.C_NEXT_LAST_PLAYED_DESCRIPTION, nextLastPlayedProgram.description)
                self.setControlLabel(self.C_NEXT_LAST_PLAYED_TITLE, nextLastPlayedProgram.title)
                if nextLastPlayedProgram.startDate or nextLastPlayedProgram.endDate:
                    self.setControlLabel(self.C_NEXT_LAST_PLAYED_TIME, '%s - %s' % (
                        self.formatTime(nextLastPlayedProgram.startDate), self.formatTime(nextLastPlayedProgram.endDate)))
                else:
                    self.setControlLabel(self.C_NEXT_LAST_PLAYED_TIME, '')
                try:
                    nextOsdControl = self.getControl(self.C_NEXT_LAST_PLAYED_CHANNEL_IMAGE)
                    if nextOsdControl != None and nextLastPlayedProgram.imageSmall is not None:
                        nextOsdControl.setImage(nextLastPlayedProgram.imageSmall)
                    elif nextOsdControl != None:
                        nextOsdControl.setImage('')
                except:
                    pass

        self.mode = MODE_LASTCHANNEL
        self._showControl(self.C_MAIN_LAST_PLAYED)

    def _playLastChannel(self):
        if not self.lastChannel:
            return
        else:
            channel = self.lastChannel
            program = self.database.getCurrentProgram(channel)
            self.lastChannel = self.currentChannel
            self.playOrChoose(program)

    def _hideOsdOnly(self):
        self._hideControl(self.C_MAIN_OSD)

    def _hideOsd(self):
        self.mode = MODE_TV
        self._hideControl(self.C_MAIN_OSD)

    def _hideOsdBigOnly(self):
        self._hideControl(self.C_MAIN_OSD_BIG)

    def _hideOsdBig(self):
        self.mode = MODE_TV
        self._hideControl(self.C_MAIN_OSD_BIG)

    def _hideLastPlayed(self):
        self.mode = MODE_TV
        self._hideControl(self.C_MAIN_LAST_PLAYED)

    def _hideEpg(self):
        self._hideControl(self.C_MAIN_EPG)
        self.mode = MODE_TV
        self._clearEpg()

    def _hideQuickEpg(self):
        self._hideControl(self.C_QUICK_EPG)
        self.mode = MODE_TV
        self._clearQuickEpg()

    def onRedrawEPG(self, channelStart, startTime, focusFunction=None):
        if self.redrawingEPG or (self.database is not None and self.database.updateInProgress) or self.isClosing:
            debug('onRedrawEPG - already redrawing')
            return  # ignore redraw request while redrawing
        debug('onRedrawEPG')

        self.redrawingEPG = True
        self.mode = MODE_EPG
        self._showControl(self.C_MAIN_EPG)
        self.updateTimebar(scheduleTimer=False)

        # show Loading screen
        self.setControlLabel(self.C_MAIN_LOADING_TIME_LEFT, strings(CALCULATING_REMAINING_TIME))
        self._showControl(self.C_MAIN_LOADING)
        self.setFocusId(self.C_MAIN_LOADING_CANCEL)

        if self.has_cat_bar:
            items = []
            categories = ["All Channels"] + sorted(self.categories, key=lambda x: x.lower())
            for label in categories:
                item = xbmcgui.ListItem(label)
                items.append(item)
            listControl = self.getControl(self.C_MAIN_CATEGORY)
            if listControl:
                listControl.reset()
                if len(items) > 1:
                    listControl.addItems(items)
                    if self.category:
                        index = categories.index(self.category)
                        self.cat_index = index
                        listControl.selectItem(index)
                name = remove_formatting(ADDON.getSetting('categories.background.color'))
                color = colors.color_name[name]
                control = self.getControl(self.C_MAIN_BACKGROUND)
                control.setColorDiffuse(color)

        if self.has_action_bar:
            listControl = self.getControl(self.C_MAIN_ACTIONS)
            if listControl:
                items = []
                for label,action,iconImage in self.actions:
                    item = xbmcgui.ListItem(label,iconImage=iconImage)
                    items.append(item)
                listControl.reset()
                listControl.addItems(items)
                listControl.selectItem(self.action_index)

        # remove existing controls
        self._clearEpg()

        if ADDON.getSetting('epg.video.pip') == 'true' and self.player.isPlaying():
            self.setControlVisible(self.C_MAIN_IMAGE,False)

        try:
            self.channelIdx, channels, programs = self.database.getEPGView(channelStart, startTime, self.onSourceProgressUpdate, clearExistingProgramList=False, category=self.category)
        except src.SourceException:
            self.onEPGLoadError()
            return

        channelsWithoutPrograms = list(channels)

        # date and time row
        self.setControlLabel(self.C_MAIN_DATE, self.formatDateTodayTomorrow(self.viewStartDate))
        if ADDON.getSetting('date.long') == 'true':
            self.setControlLabel(self.C_MAIN_DATE_LONG, self.formatDate(self.viewStartDate, True))
        else:
            self.setControlLabel(self.C_MAIN_DATE_LONG, self.formatDate(self.viewStartDate, False))
        #self.setControlLabel(self.C_MAIN_DATE_LONG, '{dt:%A} {dt.day} {dt:%B}'.format(dt=self.viewStartDate))
        for col in range(1, 5):
            self.setControlLabel(4000 + col, self.formatTime(startTime))
            startTime += HALF_HOUR

        if programs is None:
            self.onEPGLoadError()
            return

        # set channel logo or text
        showLogo = ADDON.getSetting('logos.enabled') == 'true'
        channel_index_format = "%%0%sd" % ADDON.getSetting('channel.index.digits')
        for idx in range(0, CHANNELS_PER_PAGE):
            if idx >= len(channels):
                self.setControlImage(4110 + idx, ' ')
                self.setControlLabel(4010 + idx, ' ')
                self.setControlLabel(4410 + idx, ' ')
                self.setControlVisible(4210 + idx,False)
            else:
                self.setControlVisible(4210 + idx,True)
                channel = channels[idx]
                self.setControlLabel(4010 + idx, channel.title)
                if ADDON.getSetting('channel.shortcut') == '1':
                    self.setControlLabel(4410 + idx, channel_index_format % (self.channelIdx + idx + 1))
                elif ADDON.getSetting('channel.shortcut') == '2':
                    self.setControlLabel(4410 + idx, channel.id)
                else:
                    self.setControlLabel(4410 + idx, ' ')
                if (channel.logo is not None and showLogo == True):
                    self.setControlImage(4110 + idx, channel.logo)
                else:
                    self.setControlImage(4110 + idx, ' ')
            control = self.getControl(4010 + idx)
            height = self.epgView.cellHeight
            top = self.epgView.cellHeight * idx
            control = self.getControl(4210 + idx)
            if control:
                control.setHeight(self.epgView.cellHeight-2)
                control.setWidth(176)
                control.setPosition(2,top)
                try:
                    if self.player.isPlaying() and (self.currentChannel == channels[idx]):
                        control.setImage("tvg-playing-nofocus.png")
                    else:
                        control.setImage("tvg-program-nofocus.png")
                except:
                    control.setImage("tvg-program-nofocus.png")
            control = self.getControl(4010 + idx)
            if control:
                control.setHeight(self.epgView.cellHeight-2)
                control.setWidth(176)
                control.setPosition(2,top)
            control = self.getControl(4110 + idx)
            if control:
                control.setWidth(176)
                control.setHeight(self.epgView.cellHeight-2)
                control.setPosition(2,top)
            control = self.getControl(4410 + idx)
            if control:
                control.setWidth(176)
                control.setHeight(self.epgView.cellHeight-2)
                control.setPosition(2,top)

        name = remove_formatting(ADDON.getSetting('epg.nofocus.color'))
        color = colors.color_name[name]
        noFocusColor = color
        name = remove_formatting(ADDON.getSetting('epg.focus.color'))
        color = colors.color_name[name]
        focusColor = color

        font = ADDON.getSetting('epg.font')
        isPlaying = self.player.isPlaying()
        for program in programs:
            idx = channels.index(program.channel)
            if program.channel in channelsWithoutPrograms:
                channelsWithoutPrograms.remove(program.channel)

            if isPlaying and self.currentChannel and (self.currentChannel == channels[idx]):
                channel_playing = True
            else:
                channel_playing = False

            startDelta = program.startDate - self.viewStartDate
            stopDelta = program.endDate - self.viewStartDate

            cellStart = self._secondsToXposition(startDelta.seconds)
            if startDelta.days < 0:
                cellStart = self.epgView.left
            cellWidth = self._secondsToXposition(stopDelta.seconds) - cellStart
            if cellStart + cellWidth > self.epgView.right:
                cellWidth = self.epgView.right - cellStart

            if cellWidth > 1:
                #if self.isProgramPlaying(program):
                if channel_playing and not (program.autoplaywithScheduled or program.autoplayScheduled or program.notificationScheduled):
                    noFocusTexture = 'tvg-playing-nofocus.png'
                    focusTexture = 'tvg-playing-focus.png'
                elif program.autoplaywithScheduled:
                    noFocusTexture = 'tvg-autoplaywith-nofocus.png'
                    focusTexture = 'tvg-autoplaywith-focus.png'
                elif program.autoplayScheduled:
                    noFocusTexture = 'tvg-autoplay-nofocus.png'
                    focusTexture = 'tvg-autoplay-focus.png'
                elif program.notificationScheduled:
                    noFocusTexture = 'tvg-remind-nofocus.png'
                    focusTexture = 'tvg-remind-focus.png'
                else:
                    noFocusTexture = 'tvg-program-nofocus.png'
                    focusTexture = 'tvg-program-focus.png'

                if cellWidth < 25:
                    title = ''  # Text will overflow outside the button if it is too narrow
                else:
                    title = program.title

                control = xbmcgui.ControlButton(
                    cellStart,
                    self.epgView.top + self.epgView.cellHeight * idx,
                    cellWidth - 2,
                    self.epgView.cellHeight - 2,
                    title,
                    focusedColor=focusColor,
                    textColor=noFocusColor,
                    noFocusTexture=noFocusTexture,
                    focusTexture=focusTexture,
                    font=font
                )

                self.controlAndProgramList.append(ControlAndProgram(control, program))

        for channel in channelsWithoutPrograms:
            idx = channels.index(channel)
            noFocusTexture = 'tvg-program-nofocus.png'
            focusTexture = 'tvg-program-focus.png'
            control = xbmcgui.ControlButton(
                self.epgView.left,
                self.epgView.top + self.epgView.cellHeight * idx,
                (self.epgView.right - self.epgView.left) - 2,
                self.epgView.cellHeight - 2,
                '-',
                focusedColor=focusColor,
                textColor=noFocusColor,
                noFocusTexture=noFocusTexture,
                focusTexture=focusTexture,
                font=font
            )

            program = src.Program(channel, "", '', None, None, None, '')
            self.controlAndProgramList.append(ControlAndProgram(control, program))

        top = self.epgView.top + self.epgView.cellHeight * len(channels)
        height = 720 - top
        control = self.getControl(self.C_MAIN_FOOTER)
        if control:
            control.setPosition(0,top)
            control.setHeight(height)

        control = self.getControl(self.C_MAIN_TIMEBAR)
        if control:
            control.setHeight(top - self.epgView.top - 2)
            color = colors.color_name[remove_formatting(ADDON.getSetting('timebar.color'))]
            control.setColorDiffuse(color)
        self.getControl(self.C_QUICK_EPG_TIMEBAR).setColorDiffuse(colors.color_name[remove_formatting(ADDON.getSetting('timebar.color'))])
        #self.getControl(self.C_MAIN_BACKGROUND).setHeight(top+2)

        # add program controls
        if focusFunction is None:
            focusFunction = self._findControlAt

        controls = [elem.control for elem in self.controlAndProgramList]
        try:
            self.addControls(controls)
        except:
            pass
        focusControl = focusFunction(self.focusPoint)
        if focusControl is not None:
            debug('onRedrawEPG - setFocus %d' % focusControl.getId())
            self.setFocus(focusControl)

        self.ignoreMissingControlIds.extend([elem.control.getId() for elem in self.controlAndProgramList])

        if focusControl is None and len(self.controlAndProgramList) > 0:
            control = self.getControl(self.C_MAIN_EPG_VIEW_MARKER)
            if control:
                left, top = control.getPosition()
                self.focusPoint.x = left
                self.focusPoint.y = top
                focusControl = focusFunction(self.focusPoint)
                self.setFocus(focusControl)

        self._hideControl(self.C_MAIN_LOADING)
        self.redrawingEPG = False

    def onRedrawQuickEPG(self, channelStart, startTime, focusFunction=None):
        if self.redrawingQuickEPG or (self.database is not None and self.database.updateInProgress) or self.isClosing:
            debug('onRedrawQuickEPG - already redrawing')
            return  # ignore redraw request while redrawing
        debug('onRedrawQuickEPG')

        self.redrawingQuickEPG = True
        self.mode = MODE_QUICK_EPG
        self._showControl(self.C_QUICK_EPG)
        self.updateQuickTimebar(scheduleTimer=False)

        # remove existing controls
        self._clearQuickEpg()

        self.setControlVisible(self.C_QUICK_EPG_DESCRIPTION,self.quickEpgShowInfo)

        try:
            self.quickChannelIdx, channels, programs = self.database.getQuickEPGView(channelStart, startTime, self.onSourceProgressUpdate, clearExistingProgramList=False, category=self.category)
        except src.SourceException:
            self.onEPGLoadError()
            return

        channelsWithoutPrograms = list(channels)

        # date and time row
        self.setControlLabel(self.C_QUICK_EPG_DATE, self.formatDateTodayTomorrow(self.quickViewStartDate))
        for col in range(1, 5):
            self.setControlLabel(14000 + col, self.formatTime(startTime))
            startTime += HALF_HOUR

        if programs is None:
            self.onEPGLoadError()
            return

        # set channel logo or text
        showLogo = ADDON.getSetting('logos.enabled') == 'true'
        for idx in range(0, 3):
            if idx >= len(channels):
                self.setControlImage(14110 + idx, ' ')
                self.setControlLabel(14010 + idx, ' ')
                self.setControlVisible(14210 + idx,False)
            else:
                self.setControlVisible(14210 + idx,True)
                channel = channels[idx]
                self.setControlLabel(14010 + idx, channel.title)
                if (channel.logo is not None and showLogo == True):
                    self.setControlImage(14110 + idx, channel.logo)
                else:
                    self.setControlImage(14110 + idx, ' ')
            control = self.getControl(14010 + idx)
            height = self.quickEpgView.cellHeight
            top = self.quickEpgView.cellHeight * idx
            control = self.getControl(14210 + idx)
            if control:
                control.setHeight(self.quickEpgView.cellHeight-2)
                control.setWidth(176)
                control.setPosition(2,top)
                try:
                    if self.currentChannel == channels[idx]:
                        control.setImage("tvg-playing-nofocus.png")
                    else:
                        control.setImage("tvg-program-nofocus.png")
                except:
                    control.setImage("tvg-program-nofocus.png")
            control = self.getControl(14010 + idx)
            if control:
                control.setHeight(self.quickEpgView.cellHeight-2)
                control.setWidth(176)
                control.setPosition(2,top)
            control = self.getControl(14110 + idx)
            if control:
                control.setWidth(176)
                control.setHeight(self.quickEpgView.cellHeight-2)
                control.setPosition(2,top)

        name = remove_formatting(ADDON.getSetting('epg.nofocus.color'))
        color = colors.color_name[name]
        noFocusColor = color
        name = remove_formatting(ADDON.getSetting('epg.focus.color'))
        color = colors.color_name[name]
        focusColor = color

        isPlaying = self.player.isPlaying()
        for program in programs:
            idx = channels.index(program.channel)
            if program.channel in channelsWithoutPrograms:
                channelsWithoutPrograms.remove(program.channel)

            if isPlaying and (self.currentChannel == channels[idx]):
                channel_playing = True
            else:
                channel_playing = False

            startDelta = program.startDate - self.quickViewStartDate
            stopDelta = program.endDate - self.quickViewStartDate

            cellStart = self._secondsToXposition(startDelta.seconds)
            if startDelta.days < 0:
                cellStart = self.quickEpgView.left
            cellWidth = self._secondsToXposition(stopDelta.seconds) - cellStart
            if cellStart + cellWidth > self.quickEpgView.right:
                cellWidth = self.quickEpgView.right - cellStart

            if cellWidth > 1:
                #if self.isProgramPlaying(program):
                if channel_playing and not (program.autoplaywithScheduled or program.autoplayScheduled or program.notificationScheduled):
                    noFocusTexture = 'tvg-playing-nofocus.png'
                    focusTexture = 'tvg-playing-focus.png'
                elif program.autoplaywithScheduled:
                    noFocusTexture = 'tvg-autoplaywith-nofocus.png'
                    focusTexture = 'tvg-autoplaywith-focus.png'
                elif program.autoplayScheduled:
                    noFocusTexture = 'tvg-autoplay-nofocus.png'
                    focusTexture = 'tvg-autoplay-focus.png'
                elif program.notificationScheduled:
                    noFocusTexture = 'tvg-remind-nofocus.png'
                    focusTexture = 'tvg-remind-focus.png'
                else:
                    noFocusTexture = 'tvg-program-nofocus.png'
                    focusTexture = 'tvg-program-focus.png'

                if cellWidth < 25:
                    title = ''  # Text will overflow outside the button if it is too narrow
                else:
                    title = program.title

                control = xbmcgui.ControlButton(
                    cellStart,
                    self.quickEpgView.top + self.quickEpgView.cellHeight * idx,
                    cellWidth - 2,
                    self.quickEpgView.cellHeight - 2,
                    title,
                    focusedColor=focusColor,
                    textColor=noFocusColor,
                    noFocusTexture=noFocusTexture,
                    focusTexture=focusTexture
                )

                self.quickControlAndProgramList.append(ControlAndProgram(control, program))

        for channel in channelsWithoutPrograms:
            idx = channels.index(channel)
            noFocusTexture = 'tvg-program-nofocus.png'
            focusTexture = 'tvg-program-focus.png'
            control = xbmcgui.ControlButton(
                self.quickEpgView.left,
                self.quickEpgView.top + self.quickEpgView.cellHeight * idx,
                (self.quickEpgView.right - self.quickEpgView.left) - 2,
                self.quickEpgView.cellHeight - 2,
                '-',
                focusedColor=focusColor,
                textColor=noFocusColor,
                noFocusTexture=noFocusTexture,
                focusTexture=focusTexture
            )

            program = src.Program(channel, "", '', None, None, None, '')
            self.quickControlAndProgramList.append(ControlAndProgram(control, program))

        top = self.quickEpgView.cellHeight * len(channels)
        height = 720 - top
        control = self.getControl(self.C_QUICK_EPG_FOOTER)
        if control:
            control.setPosition(0,top)
            control.setHeight(height)
        control = self.getControl(self.C_QUICK_EPG_TIMEBAR)
        if control:
            control.setHeight(top-2)

        # add program controls
        if focusFunction is None:
            focusFunction = self._findQuickControlAt
        focusControl = focusFunction(self.quickFocusPoint)
        controls = [elem.control for elem in self.quickControlAndProgramList]
        try:
            self.addControls(controls)
        except:
            pass
        if focusControl is not None:
            debug('onRedrawEPG - setFocus %d' % focusControl.getId())
            self.setQuickFocus(focusControl)

        self.ignoreMissingControlIds.extend([elem.control.getId() for elem in self.quickControlAndProgramList])

        if focusControl is None and len(self.quickControlAndProgramList) > 0:
            self.setQuickFocus(self.quickControlAndProgramList[0].control)

        self.redrawingQuickEPG = False

    def _clearEpg(self):
        controls = [elem.control for elem in self.controlAndProgramList]
        try:
            self.removeControls(controls)
        except RuntimeError:
            for elem in self.controlAndProgramList:
                try:
                    self.removeControl(elem.control)
                except RuntimeError:
                    pass  # happens if we try to remove a control that doesn't exist
        del self.controlAndProgramList[:]

    def _clearQuickEpg(self):
        controls = [elem.control for elem in self.quickControlAndProgramList]
        try:
            self.removeControls(controls)
        except RuntimeError:
            for elem in self.quickControlAndProgramList:
                try:
                    self.removeControl(elem.control)
                except RuntimeError:
                    pass  # happens if we try to remove a control that doesn't exist
        del self.quickControlAndProgramList[:]

    def onEPGLoadError(self):
        self.redrawingEPG = False
        self._hideControl(self.C_MAIN_LOADING)
        xbmcgui.Dialog().ok(strings(LOAD_ERROR_TITLE), strings(LOAD_ERROR_LINE1), strings(LOAD_ERROR_LINE2))
        self.close()

    def onSourceNotConfigured(self):
        self.redrawingEPG = False
        self._hideControl(self.C_MAIN_LOADING)
        xbmcgui.Dialog().ok(strings(LOAD_ERROR_TITLE), strings(LOAD_ERROR_LINE1), strings(CONFIGURATION_ERROR_LINE2))
        self.close()

    def isSourceInitializationCancelled(self):
        return xbmc.abortRequested or self.isClosing

    def onSourceInitialized(self, success):
        if success:
            #TODO test if schedules should go here
            self.notification = Notification(self.database, ADDON.getAddonInfo('path'))
            self.autoplay = Autoplay(self.database, ADDON.getAddonInfo('path'))
            self.autoplaywith = Autoplaywith(self.database, ADDON.getAddonInfo('path'))
            self.onRedrawEPG(0, self.viewStartDate)
            self.database.exportChannelList()
            self.database.exportChannelIdList()
            self.notification.scheduleNotifications()
            self.autoplay.scheduleAutoplays()
            self.autoplaywith.scheduleAutoplaywiths()
            self.loadChannelMappings()

    def saveActions(self):
        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/actions.json'
        f = xbmcvfs.File(file_name,"wb")
        data = json.dumps(self.actions,indent=2)
        f.write(data)
        f.close()

    def loadActions(self):
        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/actions.json'
        f = xbmcvfs.File(file_name,"rb")
        data = f.read()
        f.close()
        if data:
            self.actions = json.loads(data)
        else:
            self.actions = []


    def loadChannelMappings(self):
        if ADDON.getSetting('mapping.ini.enabled') == 'true':
            if ADDON.getSetting('mapping.ini.type') == '0':
                customFile = ADDON.getSetting('mapping.ini.file')
            else:
                customFile = ADDON.getSetting('mapping.ini.url')
            basename = os.path.basename(customFile)
            file_name = 'special://profile/addon_data/script.tvguide.fullscreen/%s' % basename
            f = open(xbmc.translatePath(file_name),"rb")
            lines = f.read()
            f.close()
            lines = lines.splitlines()
            stream_urls = [line.split("=",1) for line in lines]
            f.close()
            if stream_urls:
                self.database.setCustomStreamUrls(stream_urls)

        if ADDON.getSetting('mapping.m3u.enabled') == 'true':
            if ADDON.getSetting('mapping.m3u.type') == '0':
                customFile = ADDON.getSetting('mapping.m3u.file')
            else:
                customFile = ADDON.getSetting('mapping.m3u.url')
            basename = os.path.basename(customFile)
            file_name = 'special://profile/addon_data/script.tvguide.fullscreen/%s' % basename
            f = open(xbmc.translatePath(file_name),"rb")
            data = f.read()
            f.close()
            matches = re.findall(r'#EXTINF:.*?,(.*?)\n(.*?)\n',data,flags=(re.DOTALL | re.MULTILINE))
            stream_urls = []
            for name,url in matches:
                if name and url:
                    stream_urls.append((name.decode("utf8"),url))
            f.close()
            if stream_urls:
                self.database.setCustomStreamUrls(stream_urls)

    def onSourceProgressUpdate(self, percentageComplete):
        control = self.getControl(self.C_MAIN_LOADING_PROGRESS)
        if percentageComplete < 1:
            if control:
                control.setPercent(1)
            self.progressStartTime = datetime.datetime.now()
            self.progressPreviousPercentage = percentageComplete
        elif percentageComplete != self.progressPreviousPercentage:
            if control:
                control.setPercent(percentageComplete)
            self.progressPreviousPercentage = percentageComplete
            delta = datetime.datetime.now() - self.progressStartTime

            if percentageComplete < 20:
                self.setControlLabel(self.C_MAIN_LOADING_TIME_LEFT, strings(CALCULATING_REMAINING_TIME))
            else:
                secondsLeft = int(delta.seconds) / float(percentageComplete) * (100.0 - percentageComplete)
                if secondsLeft > 30:
                    secondsLeft -= secondsLeft % 10
                self.setControlLabel(self.C_MAIN_LOADING_TIME_LEFT, strings(TIME_LEFT) % secondsLeft)

        return not xbmc.abortRequested and not self.isClosing



    def _secondsToXposition(self, seconds):
        return self.epgView.left + (seconds * self.epgView.width / 7200)

    def _findControlOnRight(self, point):
        distanceToNearest = 10000
        nearestControl = None

        for elem in self.controlAndProgramList:
            control = elem.control
            (left, top) = control.getPosition()
            x = left + (control.getWidth() / 2)
            y = top + (control.getHeight() / 2)

            if point.x < x and point.y == y:
                distance = abs(point.x - x)
                if distance < distanceToNearest:
                    distanceToNearest = distance
                    nearestControl = control

        return nearestControl

    def _findQuickControlOnRight(self, point):
        distanceToNearest = 10000
        nearestControl = None

        for elem in self.quickControlAndProgramList:
            control = elem.control
            (left, top) = control.getPosition()
            x = left + (control.getWidth() / 2)
            y = top + (control.getHeight() / 2)

            if point.x < x and point.y == y:
                distance = abs(point.x - x)
                if distance < distanceToNearest:
                    distanceToNearest = distance
                    nearestControl = control

        return nearestControl

    def _findControlOnLeft(self, point):
        distanceToNearest = 10000
        nearestControl = None

        for elem in self.controlAndProgramList:
            control = elem.control
            (left, top) = control.getPosition()
            x = left + (control.getWidth() / 2)
            y = top + (control.getHeight() / 2)

            if point.x > x and point.y == y:
                distance = abs(point.x - x)
                if distance < distanceToNearest:
                    distanceToNearest = distance
                    nearestControl = control

        return nearestControl

    def _findQuickControlOnLeft(self, point):
        distanceToNearest = 10000
        nearestControl = None

        for elem in self.quickControlAndProgramList:
            control = elem.control
            (left, top) = control.getPosition()
            x = left + (control.getWidth() / 2)
            y = top + (control.getHeight() / 2)

            if point.x > x and point.y == y:
                distance = abs(point.x - x)
                if distance < distanceToNearest:
                    distanceToNearest = distance
                    nearestControl = control

        return nearestControl

    def _findControlBelow(self, point):
        nearestControl = None

        for elem in self.controlAndProgramList:
            control = elem.control
            (leftEdge, top) = control.getPosition()
            y = top + (control.getHeight() / 2)

            if point.y < y:
                rightEdge = leftEdge + control.getWidth()
                if leftEdge <= point.x < rightEdge and (nearestControl is None or nearestControl.getPosition()[1] > top):
                    nearestControl = control

        return nearestControl

    def _findQuickControlBelow(self, point):
        nearestControl = None

        for elem in self.quickControlAndProgramList:
            control = elem.control
            (leftEdge, top) = control.getPosition()
            y = top + (control.getHeight() / 2)

            if point.y < y:
                rightEdge = leftEdge + control.getWidth()
                if leftEdge <= point.x < rightEdge and (nearestControl is None or nearestControl.getPosition()[1] > top):
                    nearestControl = control

        return nearestControl

    def _findControlAbove(self, point):
        nearestControl = None
        for elem in self.controlAndProgramList:
            control = elem.control
            (leftEdge, top) = control.getPosition()
            y = top + (control.getHeight() / 2)

            if point.y > y:
                rightEdge = leftEdge + control.getWidth()
                if leftEdge <= point.x < rightEdge and (nearestControl is None or nearestControl.getPosition()[1] < top):
                    nearestControl = control

        return nearestControl

    def _findQuickControlAbove(self, point):
        nearestControl = None
        for elem in self.quickControlAndProgramList:
            control = elem.control
            (leftEdge, top) = control.getPosition()
            y = top + (control.getHeight() / 2)

            if point.y > y:
                rightEdge = leftEdge + control.getWidth()
                if leftEdge <= point.x < rightEdge and (nearestControl is None or nearestControl.getPosition()[1] < top):
                    nearestControl = control

        return nearestControl

    def _findControlAt(self, point):
        for elem in self.controlAndProgramList:
            control = elem.control
            (left, top) = control.getPosition()
            bottom = top + control.getHeight()
            right = left + control.getWidth()

            if left <= point.x <= right and top <= point.y <= bottom:
                return control

        return None

    def _findQuickControlAt(self, point):
        for elem in self.quickControlAndProgramList:
            control = elem.control
            (left, top) = control.getPosition()
            bottom = top + control.getHeight()
            right = left + control.getWidth()

            if left <= point.x <= right and top <= point.y <= bottom:
                return control

        return None

    def _getProgramFromControl(self, control):
        for elem in self.controlAndProgramList:
            if elem.control == control:
                return elem.program
        return None

    def _getQuickProgramFromControl(self, control):
        for elem in self.quickControlAndProgramList:
            if elem.control == control:
                return elem.program
        return None

    def _hideControl(self, *controlIds):
        """
        Visibility is inverted in skin
        """
        for controlId in controlIds:
            self.setControlVisible(controlId,True)

    def _showControl(self, *controlIds):
        """
        Visibility is inverted in skin
        """
        for controlId in controlIds:
            self.setControlVisible(controlId,False)

    def formatTime(self, timestamp):
        if timestamp:
            format = xbmc.getRegion('time').replace(':%S', '').replace('%H%H', '%H')
            return timestamp.strftime(format)
        else:
            return ''
    def t(self,dt):
        return time.mktime(dt.timetuple())

    def percent(self,start_time, end_time):
        total = self.t(end_time) - self.t(start_time)
        current_time = datetime.datetime.now()
        current = self.t(current_time) - self.t(start_time)
        percentagefloat = (100.0 * current) / total
        return int(round(percentagefloat))

    def formatDate(self, timestamp, longdate=False):
        if timestamp:
            if longdate == True:
                format = xbmc.getRegion('datelong')
            else:
                format = xbmc.getRegion('dateshort')
            return timestamp.strftime(format)
        else:
            return ''

    def formatDateTodayTomorrow(self, timestamp):
        if timestamp:
            today = datetime.datetime.today()
            tomorrow = today + datetime.timedelta(days=1)
            yesterday = today - datetime.timedelta(days=1)
            if today.date() == timestamp.date():
                return 'Today'
            elif tomorrow.date() == timestamp.date():
                return 'Tomorrow'
            elif yesterday.date() == timestamp.date():
                return 'Yesterday'
            else:
                return timestamp.strftime("%A")

    def isProgramPlaying(self, program):
        if not self.player.isPlaying():
            return False
        if self.currentChannel and self.currentProgram:
            currentTitle = self.currentProgram.title
            currentStartDate = self.currentProgram.startDate
            currentEndDate = self.currentProgram.endDate
            programTitle = program.title
            programStartDate = program.startDate
            programEndDate = program.endDate
            if currentTitle == programTitle and currentStartDate == programStartDate and currentEndDate == programEndDate and self.currentChannel.title == program.channel.title:
              return True

        return False

    def setControlVisible(self, controlId, visible):
        if not controlId:
            return
        control = self.getControl(controlId)
        if control:
            control.setVisible(visible)

    def setControlEnabled(self, controlId, enable):
        if not controlId:
            return
        control = self.getControl(controlId)
        if control:
            control.setEnabled(enable)

    def getControl(self, controlId):
        if not controlId:
            return None
        try:
            return super(TVGuide, self).getControl(controlId)
        except Exception as detail:
            #if not self.isClosing:
            #    self.close()
            return None

    def setControlImage(self, controlId, image):
        control = self.getControl(controlId)
        if control:
            control.setImage(image.encode('utf-8'))

    def setControlLabel(self, controlId, label):
        control = self.getControl(controlId)
        if control and label:
            control.setLabel(label)

    def setControlText(self, controlId, text):
        control = self.getControl(controlId)
        if control:
            control.setText(text)

    def updateTimebar(self, scheduleTimer=True):
        # move timebar to current time
        timeDelta = datetime.datetime.today() - self.viewStartDate
        control = self.getControl(self.C_MAIN_TIMEBAR)
        if control:
            (x, y) = control.getPosition()
            try:
                # Sometimes raises:
                # exceptions.RuntimeError: Unknown exception thrown from the call "setVisible"
                self.setControlVisible(self.C_MAIN_TIMEBAR,timeDelta.days == 0)
                control.setPosition(self._secondsToXposition(timeDelta.seconds), y)
            except:
                pass

        if scheduleTimer and not xbmc.abortRequested and not self.isClosing:
            threading.Timer(1, self.updateTimebar).start()

    def updateQuickTimebar(self, scheduleTimer=True):
        # move timebar to current time
        timeDelta = datetime.datetime.today() - self.quickViewStartDate
        control = self.getControl(self.C_QUICK_EPG_TIMEBAR)
        if control:
            (x, y) = control.getPosition()
            try:
                # Sometimes raises:
                # exceptions.RuntimeError: Unknown exception thrown from the call "setVisible"
                self.setControlVisible(self.C_QUICK_EPG_TIMEBAR,timeDelta.days == 0)
            except:
                pass
            control.setPosition(self._secondsToXposition(timeDelta.seconds), y)

        if scheduleTimer and not xbmc.abortRequested and not self.isClosing:
            threading.Timer(1, self.updateQuickTimebar).start()


class PopupMenu(xbmcgui.WindowXMLDialog):
    C_POPUP_LABEL = 7000
    C_POPUP_PROGRAM_LABEL = 7001
    C_POPUP_PROGRAM_IMAGE = 7002
    C_POPUP_PROGRAM_DATE = 7003
    C_POPUP_CATEGORY = 7004
    C_POPUP_SET_CATEGORY = 7005
    C_POPUP_PLAY = 4000
    C_POPUP_CHOOSE_STREAM = 4001
    C_POPUP_REMIND = 4002
    C_POPUP_CHANNELS = 4003
    C_POPUP_QUIT = 4004
    C_POPUP_PLAY_BEGINNING = 4005
    C_POPUP_SUPER_FAVOURITES = 4006
    C_POPUP_STREAM_SETUP = 4007
    C_POPUP_AUTOPLAY = 4008
    C_POPUP_AUTOPLAYWITH = 4009
    C_POPUP_LISTS = 4011
    C_POPUP_FAVOURITES = 4012
    C_POPUP_EXTENDED = 4013
    C_POPUP_CHOOSE_ALT = 4014
    C_POPUP_CHOOSE_CLOSE = 4015
    C_POPUP_CHANNEL_LOGO = 4100
    C_POPUP_CHANNEL_TITLE = 4101
    C_POPUP_PROGRAM_TITLE = 4102
    C_POPUP_LIBMOV = 80000
    C_POPUP_LIBTV = 80001
    C_POPUP_VIDEOADDONS = 80002


    def __new__(cls, database, program, showRemind, showAutoplay, showAutoplaywith, category, categories):
        return super(PopupMenu, cls).__new__(cls, 'script-tvguide-menu.xml', SKIN_PATH, SKIN)

    def __init__(self, database, program, showRemind, showAutoplay, showAutoplaywith, category, categories):
        """

        @type database: source.Database
        @param program:
        @type program: source.Program
        @param showRemind:
        """
        super(PopupMenu, self).__init__()
        self.database = database
        self.program = program
        self.showRemind = showRemind
        self.showAutoplay = showAutoplay
        self.showAutoplaywith = showAutoplaywith
        self.buttonClicked = None
        self.category = category
        self.categories = categories

    def onInit(self):
        labelControl = self.getControl(self.C_POPUP_LABEL)
        programLabelControl = self.getControl(self.C_POPUP_PROGRAM_LABEL)
        programDateControl = self.getControl(self.C_POPUP_PROGRAM_DATE)
        programImageControl = self.getControl(self.C_POPUP_PROGRAM_IMAGE)
        playControl = self.getControl(self.C_POPUP_PLAY)
        remindControl = self.getControl(self.C_POPUP_REMIND)
        autoplayControl = self.getControl(self.C_POPUP_AUTOPLAY)
        autoplaywithControl = self.getControl(self.C_POPUP_AUTOPLAYWITH)
        channelLogoControl = self.getControl(self.C_POPUP_CHANNEL_LOGO)
        channelTitleControl = self.getControl(self.C_POPUP_CHANNEL_TITLE)
        programTitleControl = self.getControl(self.C_POPUP_PROGRAM_TITLE)
        programPlayBeginningControl = self.getControl(self.C_POPUP_PLAY_BEGINNING)
        programSuperFavourites = self.getControl(self.C_POPUP_SUPER_FAVOURITES)

        items = list()
        categories = ["All Channels"] + sorted(list(self.categories), key=lambda x: x.lower())
        for label in categories:
            item = xbmcgui.ListItem(label)

            items.append(item)
        listControl = self.getControl(self.C_POPUP_CATEGORY)
        listControl.addItems(items)
        if self.category and self.category in categories:
            index = categories.index(self.category)
            if index >= 0:
                listControl.selectItem(index)

        #playControl.setLabel(strings(WATCH_CHANNEL, self.program.channel.title))
        playControl.setLabel("Watch Channel")
        if self.program.channel and not self.program.channel.isPlayable():
            #playControl.setEnabled(False)
            self.setFocusId(self.C_POPUP_CHOOSE_STREAM)
        if self.database.getCustomStreamUrl(self.program.channel):
            chooseStrmControl = self.getControl(self.C_POPUP_CHOOSE_STREAM)
            chooseStrmControl.setLabel(strings(REMOVE_STRM_FILE))

        if self.program.channel and self.program.channel.logo is not None:
            channelLogoControl.setImage(self.program.channel.logo)

        if self.program.channel:
            channelTitleControl.setLabel(self.program.channel.title)
        programTitleControl.setLabel(self.program.title)

        label = ""
        try:
            season = self.program.season
            episode = self.program.episode
            if season and episode:
                label = " S%sE%s" % (season,episode)
        except:
            pass
        programLabelControl.setLabel(self.program.title+label)
        start = self.program.startDate
        if start:
            day = self.formatDateTodayTomorrow(start)
            start = start.strftime("%H:%M")
            start = "%s %s" % (day,start)
            programDateControl.setLabel(start)
        if self.program.imageSmall:
            programImageControl.setImage(self.program.imageSmall)
        if self.program.imageLarge:
            programImageControl.setImage(self.program.imageLarge)
        labelControl.setLabel(self.program.description)

        if self.program.startDate:
            remindControl.setEnabled(True)
            autoplayControl.setEnabled(True)
            autoplaywithControl.setEnabled(True)
            if self.showRemind:
                remindControl.setLabel("Remind")
            else:
                remindControl.setLabel("Don't Remind")
            if self.showAutoplay:
                autoplayControl.setLabel("AutoPlay")
            else:
                autoplayControl.setLabel("Don't AutoPlay")
            if self.showAutoplaywith:
                autoplaywithControl.setLabel("AutoPlayWith")
            else:
                autoplaywithControl.setLabel("Don't AutoPlayWith")

        if not self.program.title:
            labelControl.setEnabled(False)
            programLabelControl.setEnabled(False)
            programDateControl.setEnabled(False)
            programImageControl.setEnabled(False)
            remindControl.setEnabled(False)
            autoplayControl.setEnabled(False)
            autoplaywithControl.setEnabled(False)
            channelLogoControl.setEnabled(False)
            channelTitleControl.setEnabled(False)
            programTitleControl.setEnabled(False)
            programPlayBeginningControl.setEnabled(False)
            programSuperFavourites.setEnabled(False)
            self.getControl(self.C_POPUP_EXTENDED).setEnabled(False)
        if not self.program.channel:
            playControl.setEnabled(False)
            self.getControl(self.C_POPUP_CHOOSE_STREAM).setEnabled(False)
            self.getControl(self.C_POPUP_STREAM_SETUP).setEnabled(False)
            self.getControl(self.C_POPUP_CHOOSE_ALT).setEnabled(False)

    def formatDateTodayTomorrow(self, timestamp):
        if timestamp:
            today = datetime.datetime.today()
            tomorrow = today + datetime.timedelta(days=1)
            yesterday = today - datetime.timedelta(days=1)
            if today.date() == timestamp.date():
                return 'Today'
            elif tomorrow.date() == timestamp.date():
                return 'Tomorrow'
            elif yesterday.date() == timestamp.date():
                return 'Yesterday'
            else:
                return timestamp.strftime("%A")

    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_NAV_BACK]:
            self.close()
        elif action.getId() in [KEY_CONTEXT_MENU]:
            cList = self.getControl(self.C_POPUP_CATEGORY)
            item = cList.getSelectedItem()
            if item:
                self.category = item.getLabel()
            if self.category == "All Channels":
                return
            dialog = xbmcgui.Dialog()
            ret = dialog.select("%s" % self.category, ["Add Channels","Remove Channels","Clear Channels"])
            if ret < 0:
                return

            f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','rb')
            lines = f.read().splitlines()
            f.close()
            categories = {}
            categories[self.category] = []
            for line in lines:
                name,cat = line.split('=')
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(name)

            if ret == 0:
                channelList = sorted([channel.title for channel in self.database.getChannelList(onlyVisible=True,all=True)])
                channelList = [c for c in channelList if c not in categories[self.category]]
                str = 'Add Channels To %s' % self.category
                ret = dialog.multiselect(str, channelList)
                if ret is None:
                    return
                if not ret:
                    ret = []
                channels = []
                for i in ret:
                    channels.append(channelList[i])

                for channel in channels:
                    if channel not in categories[self.category]:
                        categories[self.category].append(channel)

            elif ret == 1:
                channelList = sorted(categories[self.category])
                str = 'Remove Channels From %s' % self.category
                ret = dialog.multiselect(str, channelList)
                if ret is None:
                    return
                if not ret:
                    ret = []
                channels = []
                for i in ret:
                    channelList[i] = ""
                categories[self.category] = []
                for name in channelList:
                    if name:
                        categories[self.category].append(name)

            elif ret == 2:
                categories[self.category] = []

            f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','wb')
            for cat in categories:
                channels = categories[cat]
                for channel in channels:
                    s = "%s=%s\n" % (channel.encode("utf8"),cat)
                    f.write(s)
            f.close()
            self.categories = [category for category in categories if category]

    def onClick(self, controlId):
        if controlId == self.C_POPUP_CHOOSE_STREAM and self.database.getCustomStreamUrl(self.program.channel):
            self.database.deleteCustomStreamUrl(self.program.channel)
            chooseStrmControl = self.getControl(self.C_POPUP_CHOOSE_STREAM)
            chooseStrmControl.setLabel(strings(CHOOSE_STRM_FILE))

            if not self.program.channel.isPlayable():
                playControl = self.getControl(self.C_POPUP_PLAY)
                #playControl.setEnabled(False)
        elif controlId == self.C_POPUP_CATEGORY:
            cList = self.getControl(self.C_POPUP_CATEGORY)
            item = cList.getSelectedItem()
            if item:
                self.category = item.getLabel()
            self.buttonClicked = controlId
            self.close()
        elif controlId == 80003:
            dialog = xbmcgui.Dialog()
            cat = dialog.input('Add Category', type=xbmcgui.INPUT_ALPHANUM)
            if cat:
                categories = set(self.categories)
                categories.add(cat)
                self.categories = list(set(categories))
                items = list()
                categories = ["All Channels"] + sorted(list(self.categories), key=lambda x: x.lower())
                for label in categories:
                    item = xbmcgui.ListItem(label)
                    items.append(item)
                listControl = self.getControl(self.C_POPUP_CATEGORY)
                listControl.reset()
                listControl.addItems(items)
        else:
            self.buttonClicked = controlId
            self.close()

    def onFocus(self, controlId):
        pass


class ChannelsMenu(xbmcgui.WindowXMLDialog):
    C_CHANNELS_LIST = 6000
    C_CHANNELS_SELECTION_VISIBLE = 6001
    C_CHANNELS_SELECTION = 6002
    C_CHANNELS_SAVE = 6003
    C_CHANNELS_CANCEL = 6004
    C_CHANNELS_LOGO = 6005
    C_CHANNELS_LOGOS = 6006

    def __new__(cls, database):
        return super(ChannelsMenu, cls).__new__(cls, 'script-tvguide-channels.xml', SKIN_PATH, SKIN)

    def __init__(self, database):
        """

        @type database: source.Database
        """
        super(ChannelsMenu, self).__init__()
        self.database = database
        self.channelList = database.getChannelList(onlyVisible=False)
        self.swapInProgress = False

        self.selectedChannel = 0

    def onInit(self):
        self.updateChannelList()
        self.setFocusId(self.C_CHANNELS_LIST)

    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, KEY_NAV_BACK]:
            self.close()
            return

        if self.getFocusId() == self.C_CHANNELS_LIST and action.getId() in [ACTION_PREVIOUS_MENU, KEY_CONTEXT_MENU, ACTION_LEFT]:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            idx = listControl.getSelectedPosition()
            self.selectedChannel = idx
            buttonControl = self.getControl(self.C_CHANNELS_SELECTION)
            buttonControl.setLabel('[B]%s[/B]' % self.channelList[idx].title)

            self.setControlVisible(self.C_CHANNELS_SELECTION_VISIBLE,False)
            self.setFocusId(self.C_CHANNELS_SELECTION)

        elif self.getFocusId() == self.C_CHANNELS_SELECTION and action.getId() in [ACTION_RIGHT, ACTION_SELECT_ITEM]:
            self.setControlVisible(self.C_CHANNELS_SELECTION_VISIBLE,True)
            xbmc.sleep(350)
            self.setFocusId(self.C_CHANNELS_LIST)

        elif self.getFocusId() == self.C_CHANNELS_SELECTION and action.getId() in [ACTION_PREVIOUS_MENU, KEY_CONTEXT_MENU]:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            idx = listControl.getSelectedPosition()
            self.swapChannels(self.selectedChannel, idx)
            self.setControlVisible(self.C_CHANNELS_SELECTION_VISIBLE,True)
            xbmc.sleep(350)
            self.setFocusId(self.C_CHANNELS_LIST)

        elif self.getFocusId() == self.C_CHANNELS_SELECTION and action.getId() == ACTION_UP:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            idx = listControl.getSelectedPosition()
            if idx > 0:
                self.swapChannels(idx, idx - 1)

        elif self.getFocusId() == self.C_CHANNELS_SELECTION and action.getId() == ACTION_DOWN:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            idx = listControl.getSelectedPosition()
            if idx < listControl.size() - 1:
                self.swapChannels(idx, idx + 1)


    def onClick(self, controlId):
        if controlId == self.C_CHANNELS_LIST:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            item = listControl.getSelectedItem()
            channel = self.channelList[int(item.getProperty('idx'))]
            channel.visible = not channel.visible

            if channel.visible:
                iconImage = 'tvguide-channel-visible.png'
            else:
                iconImage = 'tvguide-channel-hidden.png'
            item.setIconImage(iconImage)
            item.setArt({ 'banner': channel.logo })
        elif controlId == self.C_CHANNELS_SAVE:
            self.database.saveChannelList(self.close, self.channelList)
        elif controlId == self.C_CHANNELS_LOGO:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            item = listControl.getSelectedItem()
            channel = self.channelList[int(item.getProperty('idx'))]
            d = xbmcgui.Dialog()
            logo_source = ["TheLogoDB","None","Folder","URL"]
            selected = d.select("Logo Source: %s" % channel.title,logo_source)
            if selected > -1:
                logo = channel.logo
                if selected == 0:
                    title = d.input("TheLogoDB: %s" % channel.title,channel.title)
                    if title:
                        logo = utils.getLogo(title,True)
                elif selected == 1:
                    logo = ""
                elif selected == 2:
                    image = d.browse(2, "Logo Source: %s" % channel.title, 'files')
                    if image:
                        logo = image
                elif selected == 3:
                    url = d.input('Logo URL for %s' % channel.title)
                    if url:
                        logo = url

                item.setArt({ 'banner': logo })
                self.channelList[int(item.getProperty('idx'))].logo = logo
                self.database.saveChannelList(None, self.channelList)
        elif controlId == self.C_CHANNELS_LOGOS:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            item = listControl.getSelectedItem()
            channel = self.channelList[int(item.getProperty('idx'))]
            d = xbmcgui.Dialog()
            selected = d.select("Logos",["Clear All","Find Missing","Find All"])
            if selected > -1:
                if selected == 0:
                    for idx, channel in enumerate(self.channelList):
                        self.channelList[idx].logo = ""
                        item = listControl.getListItem(idx)
                        item.setArt({ 'banner': '' })
                    self.database.saveChannelList(None, self.channelList)
                elif selected == 1:
                    logo_source = ["TheLogoDB","Folder","URL"]
                    selected = d.select("Logo Source:",logo_source)
                    if selected > -1:
                        logo = channel.logo
                        if selected == 0:
                            for idx, channel in enumerate(self.channelList):
                                if channel.logo:
                                    continue
                                title = d.input("TheLogoDB: %s" % channel.title,channel.title)
                                if title:
                                    logo = utils.getLogo(title,True)
                                    if logo:
                                        self.channelList[idx].logo = logo
                                        item = listControl.getListItem(idx)
                                        item.setArt({ 'banner': self.channelList[idx].logo })
                        elif selected == 1:
                            folder = d.browse(0, "Logo Folder:", 'files')
                            if folder:
                                dirs, files = xbmcvfs.listdir(folder)
                                files = dict([(f.lower(),f) for f in files])
                                for idx, channel in enumerate(self.channelList):
                                    if channel.logo:
                                        continue
                                    title_lower = "%s.png" % channel.title.lower()
                                    if title_lower in files:
                                        logo_file = "%s%s" % (folder,files[title_lower])
                                        self.channelList[idx].logo = logo_file
                                        item = listControl.getListItem(idx)
                                        item.setArt({ 'banner': self.channelList[idx].logo })
                        elif selected == 2:
                            url = d.input('Base URL for Logos')
                            if url:
                                for idx, channel in enumerate(self.channelList):
                                    if channel.logo:
                                        continue
                                    self.channelList[idx].logo = "%s/%s.png" % (url,channel.title)
                                    item = listControl.getListItem(idx)
                                    item.setArt({ 'banner': self.channelList[idx].logo })
                        self.database.saveChannelList(None, self.channelList)
                elif selected == 2:
                    logo_source = ["TheLogoDB","Folder","URL"]
                    selected = d.select("Logo Source:",logo_source)
                    if selected > -1:
                        logo = channel.logo
                        if selected == 0:
                            for idx, channel in enumerate(self.channelList):
                                title = channel.title
                                if title:
                                    logo = utils.getLogo(title,False)
                                    if logo:
                                        self.channelList[idx].logo = logo
                                        item = listControl.getListItem(idx)
                                        item.setArt({ 'banner': self.channelList[idx].logo })
                        elif selected == 1:
                            folder = d.browse(0, "Logo Folder:", 'files')
                            if folder:
                                dirs, files = xbmcvfs.listdir(folder)
                                files = dict([(f.lower(),f) for f in files])
                                for idx, channel in enumerate(self.channelList):
                                    title_lower = "%s.png" % channel.title.lower()
                                    if title_lower in files:
                                        logo_file = "%s%s" % (folder,files[title_lower])
                                        self.channelList[idx].logo = logo_file
                                        item = listControl.getListItem(idx)
                                        item.setArt({ 'banner': self.channelList[idx].logo })
                        elif selected == 2:
                            url = d.input('Base URL for Logos')
                            if url:
                                for idx, channel in enumerate(self.channelList):
                                    self.channelList[idx].logo = "%s/%s.png" % (url,channel.title)
                                    item = listControl.getListItem(idx)
                                    item.setArt({ 'banner': self.channelList[idx].logo })
                        self.database.saveChannelList(None, self.channelList)
        elif controlId == self.C_CHANNELS_CANCEL:
            self.close()

    def onFocus(self, controlId):
        pass

    def setControlVisible(self, controlId, visible):
        if not controlId:
            return
        control = self.getControl(controlId)
        if control:
            control.setVisible(visible)

    def updateChannelList(self):
        listControl = self.getControl(self.C_CHANNELS_LIST)
        listControl.reset()
        for idx, channel in enumerate(self.channelList):
            if channel.visible:
                iconImage = 'tvguide-channel-visible.png'
            else:
                iconImage = 'tvguide-channel-hidden.png'
            item = xbmcgui.ListItem('%3d. %s' % (idx + 1, channel.title), iconImage=iconImage)
            item.setArt({ 'banner': channel.logo })
            item.setProperty('idx', str(idx))
            listControl.addItem(item)

    def updateListItem(self, idx, item):
        channel = self.channelList[idx]
        item.setLabel('%3d. %s' % (idx + 1, channel.title))

        if channel.visible:
            iconImage = 'tvguide-channel-visible.png'
        else:
            iconImage = 'tvguide-channel-hidden.png'
        item.setIconImage(iconImage)
        item.setArt({ 'banner': channel.logo })
        item.setProperty('idx', str(idx))

    def swapChannels(self, fromIdx, toIdx):
        if self.swapInProgress:
            return
        self.swapInProgress = True

        c = self.channelList[fromIdx]
        self.channelList[fromIdx] = self.channelList[toIdx]
        self.channelList[toIdx] = c

        # recalculate weight
        for idx, channel in enumerate(self.channelList):
            channel.weight = idx

        listControl = self.getControl(self.C_CHANNELS_LIST)
        self.updateListItem(fromIdx, listControl.getListItem(fromIdx))
        self.updateListItem(toIdx, listControl.getListItem(toIdx))

        listControl.selectItem(toIdx)
        xbmc.sleep(50)
        self.swapInProgress = False

class StreamSetupDialog(xbmcgui.WindowXMLDialog):
    C_STREAM_STRM_TAB = 101
    C_STREAM_FAVOURITES_TAB = 102
    C_STREAM_ADDONS_TAB = 103
    C_STREAM_BROWSE_TAB = 104
    C_STREAM_STRM_BROWSE = 1001
    C_STREAM_STRM_FILE_LABEL = 1005
    C_STREAM_STRM_PREVIEW = 1002
    C_STREAM_STRM_OK = 1003
    C_STREAM_STRM_CANCEL = 1004
    C_STREAM_STRM_IMPORT = 1006
    C_STREAM_STRM_PVR = 1007
    C_STREAM_STRM_CLEAR_ALT = 1009
    C_STREAM_FAVOURITES = 2001
    C_STREAM_FAVOURITES_PREVIEW = 2002
    C_STREAM_FAVOURITES_OK = 2003
    C_STREAM_FAVOURITES_CANCEL = 2004
    C_STREAM_FAVOURITES_ALT = 2005
    C_STREAM_ADDONS = 3001
    C_STREAM_ADDONS_STREAMS = 3002
    C_STREAM_ADDONS_NAME = 3003
    C_STREAM_ADDONS_DESCRIPTION = 3004
    C_STREAM_ADDONS_PREVIEW = 3005
    C_STREAM_ADDONS_OK = 3006
    C_STREAM_ADDONS_CANCEL = 3007
    C_STREAM_ADDONS_ALT = 3009
    C_STREAM_BROWSE_ADDONS = 4001
    C_STREAM_BROWSE_STREAMS = 4002
    C_STREAM_BROWSE_NAME = 4003
    C_STREAM_BROWSE_DESCRIPTION = 4004
    C_STREAM_BROWSE_PREVIEW = 4005
    C_STREAM_BROWSE_OK = 4006
    C_STREAM_BROWSE_CANCEL = 4007
    C_STREAM_BROWSE_DIRS = 4008
    C_STREAM_BROWSE_FOLDER = 4009
    C_STREAM_BROWSE_ALT = 4010
    C_STREAM_CHANNEL_LOGO = 4023
    C_STREAM_CHANNEL_LABEL = 4024
    C_STREAM_ADDON_LOGO = 4025
    C_STREAM_ADDON_LABEL = 4026

    C_STREAM_VISIBILITY_MARKER = 100

    VISIBLE_STRM = 'strm'
    VISIBLE_FAVOURITES = 'favourites'
    VISIBLE_ADDONS = 'addons'
    VISIBLE_BROWSE = 'browse'

    def __new__(cls, database, channel):
        return super(StreamSetupDialog, cls).__new__(cls, 'script-tvguide-streamsetup.xml', SKIN_PATH, SKIN)

    def __init__(self, database, channel):
        """
        @type database: source.Database
        @type channel:source.Channel
        """
        super(StreamSetupDialog, self).__init__()
        self.database = database
        self.channel = channel

        self.player = xbmc.Player()
        self.previousAddonId = None
        self.previousDirsId = None
        self.previousBrowseId = None
        self.strmFile = None
        self.streamingService = streaming.StreamsService(ADDON)

    def close(self):
        #if self.player.isPlaying():
        #    self.player.stop()
        super(StreamSetupDialog, self).close()

    def onInit(self):
        self.getControl(self.C_STREAM_VISIBILITY_MARKER).setLabel(self.VISIBLE_STRM)

        favourites = self.streamingService.loadFavourites()
        items = list()
        for label, value in favourites:
            item = xbmcgui.ListItem(label)
            item.setProperty('stream', value)
            items.append(item)

        listControl = self.getControl(StreamSetupDialog.C_STREAM_FAVOURITES)
        listControl.addItems(items)

        items = list()
        for id in self.streamingService.getAddons():
            try:
                addon = xbmcaddon.Addon(id) # raises Exception if addon is not installed
                item = xbmcgui.ListItem(addon.getAddonInfo('name'), iconImage=addon.getAddonInfo('icon'))
                item.setProperty('addon_id', id)
                items.append(item)
            except Exception:
                pass
        listControl = self.getControl(StreamSetupDialog.C_STREAM_ADDONS)
        listControl.addItems(items)
        self.updateAddonInfo()

        all_addons = []
        for type in ["xbmc.addon.video", "xbmc.addon.audio"]:
            response = RPC.addons.get_addons(type=type,properties=["name", "thumbnail"])
            if "addons" in response:
                found_addons = response["addons"]
                all_addons = all_addons + found_addons

        seen = set()
        addons = []
        for addon in all_addons:
            if addon['addonid'] not in seen:
                addons.append(addon)
            seen.add(addon['addonid'])

        items = list()
        addons = sorted(addons, key=lambda addon: remove_formatting(addon['name']).lower())
        for addon in addons:
            item = xbmcgui.ListItem(addon['name'], iconImage=addon['thumbnail'])
            item.setProperty('addon_id', addon['addonid'])
            items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_ADDONS)
        listControl.addItems(items)

        self.getControl(self.C_STREAM_CHANNEL_LABEL).setLabel(self.channel.title)
        if self.channel.logo:
            try:
                control = self.getControl(self.C_STREAM_CHANNEL_LOGO)
                if control:
                    control.setImage(self.channel.logo)
            except:
                pass

        url = self.database.getStreamUrl(self.channel)
        if url:
            if url.startswith('plugin://'):
                match = re.search('plugin://(.*?)/.*',url)
                if match:
                    id = match.group(1)
                    addon = xbmcaddon.Addon(id)
                    name = addon.getAddonInfo('name')
                    icon = addon.getAddonInfo('icon')
            else:
                name = "Playlist"
                icon = xbmcaddon.Addon('script.tvguide.fullscreen').getAddonInfo('icon')
            if name:
                try:
                    control = self.getControl(self.C_STREAM_ADDON_LABEL)
                    if control:
                        control.setLabel(name)
                except:
                    pass
            if icon:
                try:
                    control = self.getControl(self.C_STREAM_ADDON_LOGO)
                    if control:
                        control.setImage(icon)
                except:
                    pass

    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_NAV_BACK]:
            self.close()
            return
        elif self.getFocusId() == self.C_STREAM_ADDONS:
            self.updateAddonInfo()


    def onClick(self, controlId):
        if controlId == self.C_STREAM_BROWSE_ADDONS:
            self.updateDirsInfo()
        elif controlId == self.C_STREAM_BROWSE_DIRS:
            self.updateBrowseInfo()
        elif controlId == self.C_STREAM_BROWSE_FOLDER:
            self.addBrowseFolder()

        elif controlId == self.C_STREAM_STRM_BROWSE:
            dialog = xbmcgui.Dialog()
            stream = dialog.browse(1, ADDON.getLocalizedString(30304), 'video', '.strm|.m3u|.m3u8')
            if stream:
                stream_name = stream
                f = xbmcvfs.File(stream,"rb")
                data = f.read()
                lines = data.splitlines()
                if len(lines) > 1:
                    matches = re.findall(r'#EXTINF:.*?,(.*?)\n(.*?)\n',data,flags=(re.DOTALL | re.MULTILINE))
                    names = []
                    urls =[]
                    for name,url in matches:
                        names.append(name.strip())
                        urls.append(url.strip())
                    if names:
                        index = dialog.select("Choose stream",names)
                        if index != -1:
                            stream = urls[index]
                            stream_name = names[index]

            if stream:
                self.database.setCustomStreamUrl(self.channel, stream)
                self.getControl(self.C_STREAM_STRM_FILE_LABEL).setText(stream_name)
                self.strmFile = stream

        elif controlId == self.C_STREAM_STRM_IMPORT:
            dialog = xbmcgui.Dialog()
            stream = dialog.browseSingle(1, ADDON.getLocalizedString(30304), 'files', '.strm|.m3u|.m3u8')
            if stream:
                stream_name = stream
                f = xbmcvfs.File(stream,"rb")
                data = f.read()
                lines = data.splitlines()
                if len(lines) > 1:
                    matches = re.findall(r'#EXTINF:.*?,(.*?)\n(.*?)\n',data,flags=(re.DOTALL | re.MULTILINE))
                    playlist_streams = {}
                    for name,url in matches:
                        name = remove_formatting(name.strip())
                        name = re.sub(r'[,:=]',' ',name)
                        playlist_streams[name] = url.strip()

                    #TODO make this a function
                    file_name = 'special://profile/addon_data/script.tvguide.fullscreen/addons.ini'
                    f = xbmcvfs.File(file_name)
                    items = f.read().splitlines()
                    f.close()
                    streams = {}
                    addonId = 'nothing'
                    for item in items:
                        if item.startswith('['):
                            addonId = item.strip('[] \t')
                            streams[addonId] = {}
                        elif item.startswith('#'):
                            pass
                        else:
                            name_url = item.split('=',1)
                            if len(name_url) == 2:
                                name = name_url[0]
                                url = name_url[1]
                                if url:
                                    streams[addonId][name] = url

                    addonId = "script.tvguide.fullscreen"
                    if addonId not in streams:
                        streams[addonId] = {}
                    for name in playlist_streams:
                        streams[addonId][name] = playlist_streams[name]

                    f = xbmcvfs.File(file_name,'w')
                    write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next folder add.\n\n"
                    f.write(write_str.encode("utf8"))
                    for addonId in sorted(streams):
                        write_str = "[%s]\n" % (addonId)
                        f.write(write_str)
                        addonStreams = streams[addonId]
                        for name in sorted(addonStreams):
                            stream = addonStreams[name]
                            if name.startswith(' '):
                                continue
                            name = re.sub(r'[,:=]',' ',name)
                            if not stream:
                                stream = 'nothing'
                            write_str = "%s=%s\n" % (name,stream)
                            f.write(write_str)
                    f.close()

        elif controlId == self.C_STREAM_STRM_PVR:
            index = 0
            urls = []
            channels = {}
            for group in ["radio","tv"]:
                urls = urls + xbmcvfs.listdir("pvr://channels/%s/All channels/" % group)[1]
            for group in ["radio","tv"]:
                groupid = "all%s" % group
                json_query = RPC.PVR.get_channels(channelgroupid=groupid, properties=[ "thumbnail", "channeltype", "hidden", "locked", "channel", "lastplayed", "broadcastnow" ] )
                if "channels" in json_query:
                    for channel in json_query["channels"]:
                        channelname = channel["label"]
                        streamUrl = urls[index]
                        index = index + 1
                        url = "pvr://channels/%s/All channels/%s" % (group,streamUrl)
                        channels[url] = channelname
            #TODO make this a function
            file_name = 'special://profile/addon_data/script.tvguide.fullscreen/addons.ini'
            f = xbmcvfs.File(file_name)
            items = f.read().splitlines()
            f.close()
            streams = {}
            addonId = 'nothing'
            for item in items:
                if item.startswith('['):
                    addonId = item.strip('[] \t')
                    streams[addonId] = {}
                elif item.startswith('#'):
                    pass
                else:
                    name_url = item.split('=',1)
                    if len(name_url) == 2:
                        name = name_url[0]
                        url = name_url[1]
                        if url:
                            streams[addonId][name] = url

            addonId = "script.tvguide.fullscreen"
            if addonId not in streams:
                streams[addonId] = {}
            for url in channels:
                name = channels[url]
                streams[addonId][name] = url

            f = xbmcvfs.File(file_name,'w')
            write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next folder add.\n\n"
            f.write(write_str.encode("utf8"))
            for addonId in sorted(streams):
                write_str = "[%s]\n" % (addonId)
                f.write(write_str)
                addonStreams = streams[addonId]
                for name in sorted(addonStreams):
                    stream = addonStreams[name]
                    if name.startswith(' '):
                        continue
                    name = re.sub(r'[,:=]',' ',name)
                    if not stream:
                        stream = 'nothing'
                    write_str = "%s=%s\n" % (name,stream)
                    try:
                        f.write(write_str.encode("utf8"))
                    except:
                        f.write(write_str)
            f.close()

        elif controlId == self.C_STREAM_ADDONS_STREAMS:
            listControl = self.getControl(self.C_STREAM_ADDONS)
            item = listControl.getSelectedItem()
            addon = item.getProperty('addon_id')
            listControl = self.getControl(self.C_STREAM_ADDONS_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                if stream.startswith("@"):
                    stream = stream[1:]
                    item.setProperty('stream',stream)
                    label = remove_formatting(item.getLabel())
                    item.setLabel(label)
                else:
                    stream = "@%s" % stream
                    item.setProperty('stream',stream)
                    label = item.getLabel()
                    label = "[COLOR green]%s[/COLOR]" % label
                    item.setLabel(label)
                name = remove_formatting(item.getLabel())
                self.streamingService.setAddonStream(addon, name, stream)

        elif controlId == self.C_STREAM_ADDONS_OK:
            listControl = self.getControl(self.C_STREAM_ADDONS_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                self.database.setCustomStreamUrl(self.channel, stream)
            self.close()
        elif controlId == self.C_STREAM_ADDONS_ALT:
            listControl = self.getControl(self.C_STREAM_ADDONS_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                title = item.getLabel()
                self.database.setAltCustomStreamUrl(self.channel, title, stream)
                d = xbmcgui.Dialog()
                d.notification("TV Guide Fullscreen", title, sound=False, time=500)

        elif controlId == self.C_STREAM_BROWSE_OK:
            listControl = self.getControl(self.C_STREAM_BROWSE_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                self.database.setCustomStreamUrl(self.channel, stream)
            self.close()
        elif controlId == self.C_STREAM_BROWSE_ALT:
            listControl = self.getControl(self.C_STREAM_BROWSE_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                title = item.getLabel()
                self.database.setAltCustomStreamUrl(self.channel, title, stream)
                d = xbmcgui.Dialog()
                d.notification("TV Guide Fullscreen", title, sound=False, time=500)


        elif controlId == self.C_STREAM_FAVOURITES_OK:
            listControl = self.getControl(self.C_STREAM_FAVOURITES)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                self.database.setCustomStreamUrl(self.channel, stream)
            self.close()
        elif controlId == self.C_STREAM_FAVOURITES_ALT:
            listControl = self.getControl(self.C_STREAM_FAVOURITES)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                title = item.getLabel()
                self.database.setAltCustomStreamUrl(self.channel, title, stream)
                d = xbmcgui.Dialog()
                d.notification("TV Guide Fullscreen", title, sound=False, time=500)

        elif controlId == self.C_STREAM_STRM_OK:
            self.database.setCustomStreamUrl(self.channel, self.strmFile)
            self.close()

        elif controlId == self.C_STREAM_STRM_CLEAR_ALT:
            alt_url = self.database.getAltStreamUrl(self.channel)
            if alt_url:
                d = xbmcgui.Dialog()
                names = []
                for u in alt_url:
                    match = re.match('plugin://(.*?)/',u[0])
                    if match:
                        plugin = match.group(1)
                        plugin = xbmcaddon.Addon(plugin).getAddonInfo('name')
                    else:
                        plugin = "Favourite"
                    names.append("%s - %s" % (plugin,u[1]))
                result = d.select("%s" % self.channel.title, names)
                if result > - 1:
                    url = alt_url[result][0]
                    self.database.deleteAltCustomStreamUrl(url)

        elif controlId in [self.C_STREAM_ADDONS_CANCEL, self.C_STREAM_BROWSE_CANCEL, self.C_STREAM_FAVOURITES_CANCEL, self.C_STREAM_STRM_CANCEL]:
            self.close()

        elif controlId in [self.C_STREAM_ADDONS_PREVIEW, self.C_STREAM_BROWSE_PREVIEW, self.C_STREAM_FAVOURITES_PREVIEW, self.C_STREAM_STRM_PREVIEW]:
            if self.player.isPlaying():
                self.player.stop()
                self.getControl(self.C_STREAM_ADDONS_PREVIEW).setLabel(strings(PREVIEW_STREAM))
                self.getControl(self.C_STREAM_BROWSE_PREVIEW).setLabel(strings(PREVIEW_STREAM))
                self.getControl(self.C_STREAM_FAVOURITES_PREVIEW).setLabel(strings(PREVIEW_STREAM))
                self.getControl(self.C_STREAM_STRM_PREVIEW).setLabel(strings(PREVIEW_STREAM))
                return

            stream = None
            visible = self.getControl(self.C_STREAM_VISIBILITY_MARKER).getLabel()
            if visible == self.VISIBLE_ADDONS:
                listControl = self.getControl(self.C_STREAM_ADDONS_STREAMS)
                item = listControl.getSelectedItem()
                if item:
                    stream = item.getProperty('stream')
            elif visible == self.VISIBLE_BROWSE:
                listControl = self.getControl(self.C_STREAM_BROWSE_STREAMS)
                item = listControl.getSelectedItem()
                if item:
                    stream = item.getProperty('stream')
            elif visible == self.VISIBLE_FAVOURITES:
                listControl = self.getControl(self.C_STREAM_FAVOURITES)
                item = listControl.getSelectedItem()
                if item:
                    stream = item.getProperty('stream')
            elif visible == self.VISIBLE_STRM:
                stream = self.strmFile

            if stream is not None:
                self.player.play(item=stream, windowed=True)
                if self.player.isPlaying():
                    self.getControl(self.C_STREAM_ADDONS_PREVIEW).setLabel(strings(STOP_PREVIEW))
                    self.getControl(self.C_STREAM_BROWSE_PREVIEW).setLabel(strings(STOP_PREVIEW))
                    self.getControl(self.C_STREAM_FAVOURITES_PREVIEW).setLabel(strings(STOP_PREVIEW))
                    self.getControl(self.C_STREAM_STRM_PREVIEW).setLabel(strings(STOP_PREVIEW))

    def onFocus(self, controlId):
        if controlId == self.C_STREAM_STRM_TAB:
            self.getControl(self.C_STREAM_VISIBILITY_MARKER).setLabel(self.VISIBLE_STRM)
        elif controlId == self.C_STREAM_FAVOURITES_TAB:
            self.getControl(self.C_STREAM_VISIBILITY_MARKER).setLabel(self.VISIBLE_FAVOURITES)
        elif controlId == self.C_STREAM_ADDONS_TAB:
            self.getControl(self.C_STREAM_VISIBILITY_MARKER).setLabel(self.VISIBLE_ADDONS)
        elif controlId == self.C_STREAM_BROWSE_TAB:
            self.getControl(self.C_STREAM_VISIBILITY_MARKER).setLabel(self.VISIBLE_BROWSE)

    def updateAddonInfo(self):
        listControl = self.getControl(self.C_STREAM_ADDONS)
        item = listControl.getSelectedItem()
        if item is None:
            return

        if item.getProperty('addon_id') == self.previousAddonId:
            return

        self.previousAddonId = item.getProperty('addon_id')
        addon = xbmcaddon.Addon(id=item.getProperty('addon_id'))
        self.getControl(self.C_STREAM_ADDONS_NAME).setLabel('[B]%s[/B]' % addon.getAddonInfo('name'))
        self.getControl(self.C_STREAM_ADDONS_DESCRIPTION).setText(addon.getAddonInfo('description'))

        streams = self.streamingService.getAddonStreams(item.getProperty('addon_id'))
        items = list()
        for (label, stream) in streams:
            if item.getProperty('addon_id') == "plugin.video.meta":
                label = self.channel.title
                stream = stream.replace("<channel>", self.channel.title.replace(" ","%20"))
            if stream.startswith('@'):
                label = "[COLOR green]%s[/COLOR]" % label
            item = xbmcgui.ListItem(label)
            if type(stream) is list:
                stream = stream[0]
            item.setProperty('stream', stream)
            items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_ADDONS_STREAMS)
        listControl.reset()
        listControl.addItems(items)

    def updateDirsInfo(self):
        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/folders.list'
        f = xbmcvfs.File(file_name)
        lines = f.read().splitlines()
        folders = []
        for folder in lines:
            if folder.startswith('@'):
                folders.append(folder[1:])
            else:
                folders.append(folder)
        f.close()
        listControl = self.getControl(self.C_STREAM_BROWSE_ADDONS)
        item = listControl.getSelectedItem()
        if item is None:
            return

        self.previousBrowseId = item.getProperty('addon_id')

        try:
            addon = xbmcaddon.Addon(id=item.getProperty('addon_id'))
        except:
            return
        self.getControl(self.C_STREAM_BROWSE_NAME).setLabel('[B]%s[/B]' % addon.getAddonInfo('name'))
        self.getControl(self.C_STREAM_BROWSE_DESCRIPTION).setText(addon.getAddonInfo('description'))

        id = addon.getAddonInfo('id')
        if id == xbmcaddon.Addon().getAddonInfo('id'):
            return
        path = "plugin://%s" % id
        self.previousDirsId = path
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
        files = response["files"]
        dirs = dict([[f["file"],f["label"]] for f in files if f["filetype"] == "directory"])
        items = list()
        item = xbmcgui.ListItem('[B]%s[/B]' % addon.getAddonInfo('name'))
        item.setProperty('stream', path)
        items.append(item)
        for stream in sorted(dirs, key=lambda x: dirs[x]):
            label = remove_formatting(dirs[stream])
            if stream in folders:
                label = '[COLOR fuchsia]%s[/COLOR]' % label
            if item.getProperty('addon_id') == "plugin.video.meta":
                label = self.channel.title
                stream = stream.replace("<channel>", self.channel.title.replace(" ","%20"))
            item = xbmcgui.ListItem(label)
            item.setProperty('stream', stream)
            items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_DIRS)
        listControl.reset()
        listControl.addItems(items)

        items = list()
        item = xbmcgui.ListItem('[B][/B]') #NOTE focus placeholder
        item.setProperty('stream', '')
        items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_STREAMS)
        listControl.reset()
        listControl.addItems(items)


    def updateBrowseInfo(self):
        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/folders.list'
        f = xbmcvfs.File(file_name)
        lines = f.read().splitlines()
        folders = []
        for folder in lines:
            if folder.startswith('@'):
                folders.append(folder[1:])
            else:
                folders.append(folder)
        listControl = self.getControl(self.C_STREAM_BROWSE_DIRS)
        item = listControl.getSelectedItem()
        if item is None:
            return

        previousDirsId = self.previousDirsId

        self.previousDirsId = item.getProperty('stream')
        self.folder = item.getLabel()

        path = self.previousDirsId
        if path in folders:
            self.getControl(self.C_STREAM_BROWSE_FOLDER).setLabel('Remove Folder')
        else:
            self.getControl(self.C_STREAM_BROWSE_FOLDER).setLabel('Add Folder')
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
        files = response["files"]
        dirs = dict([[f["file"],f["label"]] for f in files if f["filetype"] == "directory"])
        links = {}
        thumbnails = {}
        for f in files:
            if f["filetype"] == "file":
                label = f["label"]
                label = re.sub(r'\[[BI]\]','',label)
                label = re.sub(r'\[/?COLOR.*?\]','',label)
                file = f["file"]
                while (label in links):
                    label = "%s." % label
                links[label] = file
                thumbnails[label] = f["thumbnail"]

        items = list()
        item = xbmcgui.ListItem('[B]..[/B]')
        item.setProperty('stream', previousDirsId)
        items.append(item)

        for stream in sorted(dirs, key=lambda x: dirs[x]):
            label = remove_formatting(dirs[stream])
            if stream in folders:
                label = '[COLOR fuchsia]%s[/COLOR]' % label
            item = xbmcgui.ListItem(label)
            item.setProperty('stream', stream)
            items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_DIRS)
        listControl.reset()
        listControl.addItems(items)

        items = list()

        for label in sorted(links):
            stream = links[label]
            item = xbmcgui.ListItem(label)
            item.setProperty('stream', stream)
            item.setProperty('icon', thumbnails[label])
            items.append(item)
        item = xbmcgui.ListItem('[B][/B]') #NOTE focus placeholder
        item.setProperty('stream', '')
        items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_STREAMS)
        listControl.reset()
        listControl.addItems(items)


    def addBrowseFolder(self):
        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/folders.list'
        f = xbmcvfs.File(file_name)
        lines = f.read().splitlines()
        folders = {}
        for folder in lines:
            if folder.startswith('@'):
                path = folder[1:]
                folders[path] = folder
            else:
                folders[folder] = folder
        f.close()
        if self.previousDirsId in folders:
            del folders[self.previousDirsId]
            add = False
            self.getControl(self.C_STREAM_BROWSE_FOLDER).setLabel('Add Folder')
        else:
            self.getControl(self.C_STREAM_BROWSE_FOLDER).setLabel('Remove Folder')
            add = True
            method = xbmcgui.Dialog().select("Play Method",["Default","Alternative Streaming Method"])
            if method == -1:
                return
            if method == 0:
                folders[self.previousDirsId] = self.previousDirsId
            else:
                folders[self.previousDirsId] = "@"+self.previousDirsId
        f = xbmcvfs.File(file_name,"w")
        lines = "\n".join(folders.values())
        f.write(lines)
        f.close()

        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/addons.ini'
        f = xbmcvfs.File(file_name)
        items = f.read().splitlines()
        f.close()
        streams = {}
        addonId = 'nothing'
        for item in items:
            if item.startswith('['):
                addonId = item.strip('[] \t')
                streams[addonId] = {}
            elif item.startswith('#'):
                pass
            else:
                name_url = item.split('=',1)
                if len(name_url) == 2:
                    name = name_url[0]
                    url = name_url[1]
                    if url:
                        streams[addonId][name] = url

        addonId = self.previousBrowseId
        if addonId not in streams:
            streams[addonId] = {}

        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_STREAMS)
        for i in range(0,listControl.size()):
            listItem = listControl.getListItem(i)
            name = listItem.getLabel()
            stream = listItem.getProperty('stream')
            if stream:
                if add:
                    if ADDON.getSetting('append.folder') == 'true':
                        name = "%s (%s)" % (name,self.folder)
                    if (method == 1):
                        stream = "@%s" % stream
                    streams[addonId][name] = stream
                else:
                    for k,v in streams[addonId].items():
                        if v == stream or v == "@"+stream:
                           del streams[addonId][k]

        for addon in streams.keys():
            if len(streams[addon]) == 0:
                del streams[addon]

        f = xbmcvfs.File(file_name,'w')
        write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next folder add.\n\n"
        f.write(write_str.encode("utf8"))
        for addonId in sorted(streams):
            write_str = "[%s]\n" % (addonId)
            f.write(write_str)
            addonStreams = streams[addonId]
            for name in sorted(addonStreams):
                stream = addonStreams[name]
                #if name.startswith(' '):
                #    continue
                name = name.lstrip()
                name = re.sub(r'[,:=]',' ',name)
                if not stream:
                    stream = 'nothing'
                stream = re.sub('plugin ://','plugin://',stream)
                write_str = "%s=%s\n" % (name,stream)
                f.write(write_str)
        f.close()

        file_name = 'special://profile/addon_data/script.tvguide.fullscreen/icons.ini'

        f = xbmcvfs.File(file_name)
        items = f.read().splitlines()
        f.close()
        streams = {}
        addonId = 'nothing'
        for item in items:
            if item.startswith('['):
                addonId = item.strip('[] \t')
                streams[addonId] = {}
            elif item.startswith('#'):
                pass
            else:
                name_url = item.rsplit('|',1)
                if len(name_url) == 2:
                    name = name_url[0]
                    url = name_url[1]
                    if url:
                        streams[addonId][name] = url

        addonId = self.previousBrowseId
        if addonId not in streams:
            streams[addonId] = {}

        listControl = self.getControl(StreamSetupDialog.C_STREAM_BROWSE_STREAMS)
        for i in range(0,listControl.size()):
            listItem = listControl.getListItem(i)
            stream = listItem.getProperty('stream')
            icon = listItem.getProperty('icon')
            if stream:
                streams[addonId][stream] = icon

        f = xbmcvfs.File(file_name,'w')
        write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next folder add.\n\n"
        f.write(write_str.encode("utf8"))
        for addonId in sorted(streams):
            write_str = "[%s]\n" % (addonId)
            f.write(write_str)
            addonStreams = streams[addonId]
            for name in sorted(addonStreams):
                stream = addonStreams[name]
                if name.startswith(' '):
                    continue
                if not stream:
                    stream = 'nothing'
                write_str = "%s|%s\n" % (name,stream)
                f.write(write_str)
        f.close()

        d = xbmcgui.Dialog()
        if add:
            title = "Added Folder"
        else:
            title = "Removed Folder"
        d.notification("TV Guide Fullscreen", title, sound=False, time=500)


class ChooseStreamAddonDialog(xbmcgui.WindowXMLDialog):
    C_SELECTION_LIST = 1000

    def __new__(cls, addons):
        return super(ChooseStreamAddonDialog, cls).__new__(cls, 'script-tvguide-streamaddon.xml', SKIN_PATH, SKIN)

    def __init__(self, addons):
        super(ChooseStreamAddonDialog, self).__init__()
        self.addons = addons
        self.stream = None
        self.title = None

    def onInit(self):
        items = list()
        for id, label, url in self.addons:
            addon = xbmcaddon.Addon(id)

            item = xbmcgui.ListItem(label, addon.getAddonInfo('name'), addon.getAddonInfo('icon'))
            item.setProperty('stream', url)
            items.append(item)

        listControl = self.getControl(ChooseStreamAddonDialog.C_SELECTION_LIST)
        listControl.addItems(items)

        self.setFocus(listControl)

    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_NAV_BACK]:
            self.close()

    def onClick(self, controlId):
        if controlId == ChooseStreamAddonDialog.C_SELECTION_LIST:
            listControl = self.getControl(ChooseStreamAddonDialog.C_SELECTION_LIST)
            self.stream = listControl.getSelectedItem().getProperty('stream')
            self.title = listControl.getSelectedItem().getLabel()
            self.close()

    def onFocus(self, controlId):
        pass

class ProgramListDialog(xbmcgui.WindowXMLDialog):
    C_PROGRAM_LIST = 1000
    C_PROGRAM_LIST_TITLE = 1001

    def __new__(cls,title,programs,sort_time=False):
        return super(ProgramListDialog, cls).__new__(cls, 'script-tvguide-programlist.xml', SKIN_PATH, SKIN)

    def __init__(self,title,programs,sort_time=False):
        super(ProgramListDialog, self).__init__()
        self.title = title
        self.programs = programs
        self.index = -1
        self.action = None
        self.sort_time = sort_time

    def onInit(self):
        control = self.getControl(ProgramListDialog.C_PROGRAM_LIST_TITLE)
        control.setLabel(self.title)

        items = list()
        index = 0

        for program in self.programs:

            label = program.title
            se_label = ""
            try:
                season = program.season
                episode = program.episode
                if season and episode:
                    se_label = " S%sE%s" % (season,episode)
            except:
                pass
            label = label + se_label
            name = ""
            icon = program.channel.logo
            item = xbmcgui.ListItem(label, name, icon)

            item.setProperty('index', str(index))
            index = index + 1

            item.setProperty('ChannelName', program.channel.title)
            item.setProperty('Plot', program.description)
            item.setProperty('startDate', str(time.mktime(program.startDate.timetuple())))

            start = program.startDate
            end = program.endDate
            duration = end - start
            now = datetime.datetime.now()

            if now > start:
                when = datetime.timedelta(-1)
                elapsed = now - start
            else:
                when = start - now
                elapsed = datetime.timedelta(0)

            day = self.formatDateTodayTomorrow(start)
            start_str = start.strftime("%H:%M")
            start_str = "%s %s" % (start_str,day)
            item.setProperty('StartTime', start_str)

            duration_str = "%d mins" % (duration.seconds / 60)
            item.setProperty('Duration', duration_str)

            days = when.days
            hours, remainder = divmod(when.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if days > 1:
                when_str = "in %d days" % (days)
                item.setProperty('When', when_str)
            elif days > 0:
                when_str = "in %d day" % (days)
                item.setProperty('When', when_str)
            elif hours > 1:
                when_str = "in %d hours" % (hours)
                item.setProperty('When', when_str)
            elif seconds > 0:
                when_str = "in %d mins" % (when.seconds / 60)
                item.setProperty('When', when_str)

            if elapsed.seconds > 0:
                progress = 100.0 * float(timedelta_total_seconds(elapsed)) / float(duration.seconds+0.001)
                progress = str(int(progress))
            else:
                #TODO hack for progress bar with 0 time
                progress = "0"

            if progress and (int(progress) < 100):
                item.setProperty('Completed', progress)

            program_image = program.imageSmall if program.imageSmall else program.imageLarge
            item.setProperty('ProgramImage', program_image)
            items.append(item)

        if self.sort_time == True:
            items = sorted(items, key=lambda x: x.getProperty('startDate'))

        listControl = self.getControl(ProgramListDialog.C_PROGRAM_LIST)
        listControl.addItems(items)

        self.setFocus(listControl)


    def onAction(self, action):
        listControl = self.getControl(self.C_PROGRAM_LIST)
        self.id = self.getFocusId(self.C_PROGRAM_LIST)
        item = listControl.getSelectedItem()
        if item:
            self.index = int(item.getProperty('index'))
        else:
            self.index = -1
        #if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_NAV_BACK]:
        if action.getId() in COMMAND_ACTIONS["CLOSE"]:
            self.index = -1
            self.close()
        #elif action.getId() in [KEY_CONTEXT_MENU]:
        elif action.getId() in COMMAND_ACTIONS["MENU"]:
            self.action = KEY_CONTEXT_MENU
            self.close()
        elif action.getId() == ACTION_LEFT:
            self.action = ACTION_LEFT
            self.close()
        elif action.getId() == ACTION_RIGHT:
            self.action = ACTION_RIGHT
            self.close()

    def onClick(self, controlId):
        if controlId == self.C_PROGRAM_LIST:
            listControl = self.getControl(self.C_PROGRAM_LIST)
            self.id = self.getFocusId(self.C_PROGRAM_LIST)
            item = listControl.getSelectedItem()
            if item:
                self.index = int(item.getProperty('index'))
            else:
                self.index = -1
            self.close()

    def onFocus(self, controlId):
        pass

    #TODO make global function
    def formatDateTodayTomorrow(self, timestamp):
        if timestamp:
            today = datetime.datetime.today()
            tomorrow = today + datetime.timedelta(days=1)
            yesterday = today - datetime.timedelta(days=1)
            if today.date() == timestamp.date():
                return 'Today'
            elif tomorrow.date() == timestamp.date():
                return 'Tomorrow'
            elif yesterday.date() == timestamp.date():
                return 'Yesterday'
            else:
                return timestamp.strftime("%A")

    def close(self):
        super(ProgramListDialog, self).close()

class CatMenu(xbmcgui.WindowXMLDialog):
    C_CAT_BACKGROUND = 7000
    C_CAT_QUIT = 7003
    C_CAT_CATEGORY = 7004
    C_CAT_SET_CATEGORY = 7005

    def __new__(
        cls,
        database,
        category,
        categories,
        ):

        # Skin in resources
        # return super(CatMenu, cls).__new__(cls, 'script-tvguide-categories.xml', ADDON.getAddonInfo('path'), SKIN)
        # Skin in user settings

        return super(CatMenu, cls).__new__(cls, 'script-tvguide-categories.xml', SKIN_PATH, SKIN)

    def __init__(
        self,
        database,
        category,
        categories,
        ):
        """

........@type database: source.Database
........"""

        super(CatMenu, self).__init__()
        self.database = database
        self.buttonClicked = None
        self.category = category
        self.selected_category = category
        self.categories = categories

    def onInit(self):
        items = list()
        categories = ["All Channels"] + sorted(self.categories, key=lambda x: x.lower())
        for label in categories:
            item = xbmcgui.ListItem(label)
            items.append(item)
        listControl = self.getControl(self.C_CAT_CATEGORY)
        listControl.addItems(items)
        if self.selected_category and self.selected_category in categories:
            index = categories.index(self.selected_category)
            listControl.selectItem(index)
        self.setFocus(listControl)
        name = remove_formatting(ADDON.getSetting('categories.background.color'))
        color = colors.color_name[name]
        control = self.getControl(self.C_CAT_BACKGROUND)
        control.setColorDiffuse(color)

    def onAction(self, action):
        #if action.getId() in [KEY_CONTEXT_MENU]:
        if action.getId() in COMMAND_ACTIONS["MENU"]:
            kodi = float(xbmc.getInfoLabel("System.BuildVersion")[:4])
            dialog = xbmcgui.Dialog()
            if kodi < 16:
                dialog.ok('TV Guide Fullscreen', 'Editing categories in Kodi %s is currently not supported.' % kodi)
            else:
                cList = self.getControl(self.C_CAT_CATEGORY)
                item = cList.getSelectedItem()
                if item:
                    self.selected_category = item.getLabel()
                if self.selected_category == "All Channels":
                    selection = ["Add Category"]
                else:
                    selection = ["Add Category","Add Channels","Remove Channels","Clear Channels"]
                dialog = xbmcgui.Dialog()
                ret = dialog.select("%s" % self.selected_category, selection)
                if ret < 0:
                    return

                f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','rb')
                lines = f.read().splitlines()
                f.close()
                categories = {}
                if self.selected_category not in ["Any", "All Channels"]:
                    categories[self.selected_category] = []
                for line in lines:
                    if '=' in line:
                        name,cat = line.strip().split('=')
                        if cat not in categories:
                            categories[cat] = []
                        categories[cat].append(name)

                if ret == 1:
                    channelList = sorted([channel.title for channel in self.database.getChannelList(onlyVisible=True,all=True)])
                    channelList = [c for c in channelList if c not in categories[self.selected_category]]
                    str = 'Add Channels To %s' % self.selected_category
                    ret = dialog.multiselect(str, channelList)
                    if ret is None:
                        return
                    if not ret:
                        ret = []
                    channels = []
                    for i in ret:
                        channels.append(channelList[i])

                    for channel in channels:
                        if channel not in categories[self.selected_category]:
                            categories[self.selected_category].append(channel)

                elif ret == 2:
                    channelList = sorted(categories[self.selected_category])
                    str = 'Remove Channels From %s' % self.selected_category
                    ret = dialog.multiselect(str, channelList)
                    if ret is None:
                        return
                    if not ret:
                        ret = []
                    channels = []
                    for i in ret:
                        channelList[i] = ""
                    categories[self.selected_category] = []
                    for name in channelList:
                        if name:
                            categories[self.selected_category].append(name)

                elif ret == 3:
                    categories[self.selected_category] = []

                elif ret == 0:
                    dialog = xbmcgui.Dialog()
                    cat = dialog.input('Add Category', type=xbmcgui.INPUT_ALPHANUM)
                    if cat:
                        if cat not in categories:
                            categories[cat] = []
                        items = list()
                        new_categories = ["All Channels"] + sorted(categories.keys(), key=lambda x: x.lower())
                        for label in new_categories:
                            item = xbmcgui.ListItem(label)
                            items.append(item)
                        listControl = self.getControl(self.C_CAT_CATEGORY)
                        listControl.reset()
                        listControl.addItems(items)

                f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','wb')
                for cat in categories:
                    channels = categories[cat]
                    for channel in channels:
                        f.write("%s=%s\n" % (channel.encode("utf8"),cat))
                f.close()
                self.categories = [category for category in categories if category]
        #elif action.getId() in [ACTION_MENU, ACTION_PARENT_DIR, KEY_NAV_BACK, KEY_ESC]:
        elif action.getId() in COMMAND_ACTIONS["CLOSE"] + COMMAND_ACTIONS["CATEGORIES"] :
            self.close()
            return

    def onClick(self, controlId):
        if controlId == self.C_CAT_CATEGORY:
            cList = self.getControl(self.C_CAT_CATEGORY)
            item = cList.getSelectedItem()
            if item:
                self.selected_category = item.getLabel()
                self.category = self.selected_category
            self.buttonClicked = controlId
            self.close()
        elif controlId == 80005:
            kodi = float(xbmc.getInfoLabel("System.BuildVersion")[:4])
            dialog = xbmcgui.Dialog()
            if kodi < 16:
                dialog.ok('TV Guide Fullscreen', 'Editing categories in Kodi %s is currently not supported.' % kodi)
            else:
                cat = dialog.input('Add Category', type=xbmcgui.INPUT_ALPHANUM)
                if cat:
                    categories = set(self.categories)
                    categories.add(cat)
                    self.categories = list(set(categories))
                    items = list()
                    categories = ["All Channels"] + list(self.categories)
                    for label in categories:
                        item = xbmcgui.ListItem(label)
                        items.append(item)
                    listControl = self.getControl(self.C_CAT_CATEGORY)
                    listControl.reset()
                    listControl.addItems(items)
        else:
            self.buttonClicked = controlId
            self.close()

    def onFocus(self, controlId):
        pass
