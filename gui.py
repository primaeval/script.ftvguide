#
#      Copyright (C) 2014 Tommy Winther
#      http://tommy.winther.nu
#
#      Modified for FTV Guide (09/2014 onwards)
#      by Thomas Geppert [bluezed] - bluezed.apps@gmail.com
#
#      Modified for TV Guide Fullscren (2016)
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
import datetime
import threading
import time
import re
import os
import urllib

import xbmc
import xbmcgui
import xbmcvfs

import source as src
from notification import Notification
from strings import *
from rpc import RPC

import streaming

DEBUG = False

MODE_EPG = 'EPG'
MODE_TV = 'TV'
MODE_OSD = 'OSD'

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
ACTION_NEXT_ITEM = 14
ACTION_PREV_ITEM = 15

ACTION_MOUSE_WHEEL_UP = 104
ACTION_MOUSE_WHEEL_DOWN = 105
ACTION_MOUSE_MOVE = 107

KEY_NAV_BACK = 92
KEY_CONTEXT_MENU = 117
KEY_HOME = 159
KEY_ESC = 61467

CHANNELS_PER_PAGE = int(ADDON.getSetting('channels.per.page'))

HALF_HOUR = datetime.timedelta(minutes=30)

SKIN = ADDON.getSetting('skin')

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
    C_MAIN_IMAGE = 7023
    C_MAIN_LOGO = 7024
    C_MAIN_CHANNEL = 7025
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
    C_MAIN_MOUSE_EXIT = 4306
    C_MAIN_BACKGROUND = 4600
    C_MAIN_HEADER = 4601
    C_MAIN_FOOTER = 4602
    C_MAIN_EPG = 5000
    C_MAIN_EPG_VIEW_MARKER = 5001
    C_MAIN_OSD = 6000
    C_MAIN_OSD_TITLE = 6001
    C_MAIN_OSD_TIME = 6002
    C_MAIN_OSD_DESCRIPTION = 6003
    C_MAIN_OSD_CHANNEL_LOGO = 6004
    C_MAIN_OSD_CHANNEL_TITLE = 6005
    C_MAIN_OSD_CHANNEL_IMAGE = 6006
    C_NEXT_OSD_DESCRIPTION = 6007
    C_NEXT_OSD_TITLE = 6008
    C_NEXT_OSD_TIME = 6009
    C_MAIN_VIDEO_BACKGROUND = 5555
    C_MAIN_VIDEO_PIP = 6666

    def __new__(cls):
        return super(TVGuide, cls).__new__(cls, 'script-tvguide-main.xml', ADDON.getAddonInfo('path'), SKIN)

    def __init__(self):
        super(TVGuide, self).__init__()

        self.notification = None
        self.redrawingEPG = False
        self.isClosing = False
        self.controlAndProgramList = list()
        self.ignoreMissingControlIds = list()
        self.channelIdx = 0
        self.focusPoint = Point()
        self.epgView = EPGView()
        #self.streamingService = streaming.StreamsService(ADDON)
        self.player = xbmc.Player()
        self.database = None

        self.mode = MODE_EPG
        self.currentChannel = None

        self.category = None
        #self.categories = set()
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

        self.osdEnabled = False
        self.osdEnabled = ADDON.getSetting('enable.osd') == 'true' and ADDON.getSetting(
            'alternative.playback') != 'true'
        self.alternativePlayback = ADDON.getSetting('alternative.playback') == 'true'
        self.osdChannel = None
        self.osdProgram = None

        # find nearest half hour
        self.viewStartDate = datetime.datetime.today()
        self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                 seconds=self.viewStartDate.second)


    def getControl(self, controlId):
        try:
            return super(TVGuide, self).getControl(controlId)
        except:
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
            if self.database:
                self.database.close(super(TVGuide, self).close)
            else:
                super(TVGuide, self).close()

    def onInit(self):
        self._hideControl(self.C_MAIN_MOUSE_CONTROLS, self.C_MAIN_OSD)
        self._showControl(self.C_MAIN_EPG, self.C_MAIN_LOADING)
        self.setControlLabel(self.C_MAIN_LOADING_TIME_LEFT, strings(BACKGROUND_UPDATE_IN_PROGRESS))
        self.setFocusId(self.C_MAIN_LOADING_CANCEL)

        control = self.getControl(self.C_MAIN_EPG_VIEW_MARKER)
        if control:
            left, top = control.getPosition()
            self.focusPoint.x = left
            self.focusPoint.y = top
            self.epgView.left = left
            self.epgView.top = top
            self.epgView.right = left + control.getWidth()
            self.epgView.bottom = top + control.getHeight()
            self.epgView.width = control.getWidth()
            self.epgView.cellHeight = control.getHeight() / CHANNELS_PER_PAGE

        if self.database:
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
        else:
            try:
                self.database = src.Database()
            except src.SourceNotConfiguredException:
                self.onSourceNotConfigured()
                self.close()
                return
            self.database.initialize(self.onSourceInitialized, self.isSourceInitializationCancelled)

        self.streamingService = streaming.StreamsService(ADDON)

        self.updateTimebar()

    def onAction(self, action):
        debug('Mode is: %s' % self.mode)

        if self.mode == MODE_TV:
            self.onActionTVMode(action)
        elif self.mode == MODE_OSD:
            self.onActionOSDMode(action)
        elif self.mode == MODE_EPG:
            self.onActionEPGMode(action)

    def onActionTVMode(self, action):
        if action.getId() == ACTION_PAGE_UP:
            self._channelUp()

        elif action.getId() == ACTION_PAGE_DOWN:
            self._channelDown()

        elif not self.osdEnabled:
            pass  # skip the rest of the actions

        elif action.getId() in [ACTION_PARENT_DIR, KEY_NAV_BACK, KEY_CONTEXT_MENU, ACTION_PREVIOUS_MENU]:
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif action.getId() == ACTION_SHOW_INFO:
            self._showOsd()

    def onActionOSDMode(self, action):
        if action.getId() == ACTION_SHOW_INFO:
            self._hideOsd()

        elif action.getId() in [ACTION_PARENT_DIR, KEY_NAV_BACK, KEY_CONTEXT_MENU, ACTION_PREVIOUS_MENU]:
            self._hideOsd()
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

        elif action.getId() == ACTION_SELECT_ITEM:
            if self.playChannel(self.osdChannel, self.osdProgram):
                self._hideOsd()

        elif action.getId() == ACTION_PAGE_UP:
            self._channelUp()
            self._showOsd()

        elif action.getId() == ACTION_PAGE_DOWN:
            self._channelDown()
            self._showOsd()

        elif action.getId() == ACTION_UP:
            self.osdChannel = self.database.getPreviousChannel(self.osdChannel)
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsd()

        elif action.getId() == ACTION_DOWN:
            self.osdChannel = self.database.getNextChannel(self.osdChannel)
            self.osdProgram = self.database.getCurrentProgram(self.osdChannel)
            self._showOsd()

        elif action.getId() == ACTION_LEFT:
            previousProgram = self.database.getPreviousProgram(self.osdProgram)
            if previousProgram:
                self.osdProgram = previousProgram
                self._showOsd()

        elif action.getId() == ACTION_RIGHT:
            nextProgram = self.database.getNextProgram(self.osdProgram)
            if nextProgram:
                self.osdProgram = nextProgram
                self._showOsd()

    def onActionEPGMode(self, action):
        if action.getId() in [ACTION_PARENT_DIR, KEY_NAV_BACK]:
            self.close()
            return

        # catch the ESC key
        elif action.getId() == ACTION_PREVIOUS_MENU and action.getButtonCode() == KEY_ESC:
            self.close()
            return

        elif action.getId() == ACTION_MOUSE_MOVE:
            self._showControl(self.C_MAIN_MOUSE_CONTROLS)
            return

        elif action.getId() == KEY_CONTEXT_MENU:
            if self.player.isPlaying():
                self._hideEpg()

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
                self.setFocus(control)
                return
        if action.getId() == ACTION_LEFT:
            self._left(currentFocus)
        elif action.getId() == ACTION_RIGHT:
            self._right(currentFocus)
        elif action.getId() == ACTION_UP:
            self._up(currentFocus)
        elif action.getId() == ACTION_DOWN:
            self._down(currentFocus)
        elif action.getId() == ACTION_NEXT_ITEM:
            self._nextDay()
        elif action.getId() == ACTION_PREV_ITEM:
            self._previousDay()
        elif action.getId() == ACTION_PAGE_UP:
            self._moveUp(CHANNELS_PER_PAGE)
        elif action.getId() == ACTION_PAGE_DOWN:
            self._moveDown(CHANNELS_PER_PAGE)
        elif action.getId() == ACTION_MOUSE_WHEEL_UP:
            self._moveUp(scrollEvent=True)
        elif action.getId() == ACTION_MOUSE_WHEEL_DOWN:
            self._moveDown(scrollEvent=True)
        elif action.getId() == KEY_HOME:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30,
                                                     seconds=self.viewStartDate.second)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
        elif action.getId() in [KEY_CONTEXT_MENU, ACTION_PREVIOUS_MENU] and controlInFocus is not None:
            program = self._getProgramFromControl(controlInFocus)
            if program is not None:
                self._showContextMenu(program)
        else:
            xbmc.log('[script.tvguide.fullscreen] Unhandled ActionId: ' + str(action.getId()), xbmc.LOGDEBUG)

    def onClick(self, controlId):
        if controlId in [self.C_MAIN_LOADING_CANCEL, self.C_MAIN_MOUSE_EXIT]:
            self.close()
            return

        if self.isClosing:
            return

        if controlId == self.C_MAIN_MOUSE_HOME:
            self.viewStartDate = datetime.datetime.today()
            self.viewStartDate -= datetime.timedelta(minutes=self.viewStartDate.minute % 30, seconds=self.viewStartDate.second)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            return
        elif controlId == self.C_MAIN_MOUSE_LEFT:
            self.viewStartDate -= datetime.timedelta(hours=2)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            return
        elif controlId == self.C_MAIN_MOUSE_UP:
            self._moveUp(count=CHANNELS_PER_PAGE)
            return
        elif controlId == self.C_MAIN_MOUSE_DOWN:
            self._moveDown(count=CHANNELS_PER_PAGE)
            return
        elif controlId == self.C_MAIN_MOUSE_RIGHT:
            self.viewStartDate += datetime.timedelta(hours=2)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)
            return

        program = self._getProgramFromControl(self.getControl(controlId))
        if program is None:
            return

        if not self.playChannel(program.channel, program):
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

    def _showContextMenu(self, program):
        self._hideControl(self.C_MAIN_MOUSE_CONTROLS)
        d = PopupMenu(self.database, program, not program.notificationScheduled, self.category, self.categories)
        d.doModal()
        buttonClicked = d.buttonClicked
        self.category = d.category
        self.categories = d.categories
        del d

        if buttonClicked == PopupMenu.C_POPUP_REMIND:
            if program.notificationScheduled:
                self.notification.removeNotification(program)
            else:
                self.notification.addNotification(program)

            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

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
            if program.is_movie == "Movie":
                selection = 0
            elif program.season is not None:
                selection = 1
            else:
                selection = xbmcgui.Dialog().select("Choose media type",["Search as Movie", "Search as TV Show"])

            if selection == 0:
                xbmc.executebuiltin("RunPlugin(plugin://plugin.video.meta/movies/play_by_name/%s/%s)" % (
                    title, program.language))
            elif selection == 1:
                if program.season and program.episode:
                    xbmc.executebuiltin("RunPlugin(plugin://plugin.video.meta/tv/play_by_name/%s/%s/%s/%s)" % (
                        title, program.season, program.episode, program.language))
                else:
                    xbmc.executebuiltin("RunPlugin(plugin://plugin.video.meta/tv/play_by_name_only/%s/%s)" % (
                        title, program.language))
        elif buttonClicked == PopupMenu.C_POPUP_SUPER_FAVOURITES:
            xbmc.executebuiltin('ActivateWindow(10025,"plugin://plugin.program.super.favourites/?mode=0&keyword=%s")' % urllib.quote_plus(program.title))



    def setFocusId(self, controlId):
        control = self.getControl(controlId)
        if control:
            self.setFocus(control)

    def setFocus(self, control):
        debug('setFocus %d' % control.getId())
        if control in [elem.control for elem in self.controlAndProgramList]:
            debug('Focus before %s' % self.focusPoint)
            (left, top) = control.getPosition()
            if left > self.focusPoint.x or left + control.getWidth() < self.focusPoint.x:
                self.focusPoint.x = left
            self.focusPoint.y = top + (control.getHeight() / 2)
            debug('New focus at %s' % self.focusPoint)

        super(TVGuide, self).setFocus(control)

    def onFocus(self, controlId):
        try:
            controlInFocus = self.getControl(controlId)
        except Exception:
            return
        program = self._getProgramFromControl(controlInFocus)
        if program is None:
            return

        title = '[B]%s[/B]' % program.title
        if program.season is not None and program.episode is not None:
            title += " [B]S%sE%s[/B]" % (program.season, program.episode)
        if program.is_movie == "Movie":
            title += " [B](Movie)[/B]"
        self.setControlLabel(self.C_MAIN_TITLE, title)
        if program.startDate or program.endDate:
            self.setControlLabel(self.C_MAIN_TIME,
                                 '[B]%s - %s[/B]' % (self.formatTime(program.startDate), self.formatTime(program.endDate)))
        else:
            self.setControlLabel(self.C_MAIN_TIME, '')
        if program.description:
            description = program.description
        else:
            description = ""
        self.setControlText(self.C_MAIN_DESCRIPTION, description)

        self.setControlLabel(self.C_MAIN_CHANNEL, '[B]%s[/B]' % program.channel.title)

        if program.channel.logo is not None:
            self.setControlImage(self.C_MAIN_LOGO, program.channel.logo)
        else:
            self.setControlImage(self.C_MAIN_LOGO, '')


        if program.imageSmall is not None:
            self.setControlImage(self.C_MAIN_IMAGE, program.imageSmall)
        else:
            self.setControlImage(self.C_MAIN_IMAGE, '')
        if program.imageLarge is not None:
            self.setControlImage(self.C_MAIN_IMAGE, program.imageLarge)


        if ADDON.getSetting('program.background.enabled') == 'true' and program.imageSmall is not None:
            self.setControlImage(self.C_MAIN_BACKGROUND, program.imageSmall)
        else:
            self.setControlImage(self.C_MAIN_BACKGROUND, "grey.png")

        #if not self.osdEnabled and self.player.isPlaying():
        #    self.player.stop()

    def _left(self, currentFocus):
        control = self._findControlOnLeft(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            self.viewStartDate -= datetime.timedelta(hours=2)
            self.focusPoint.x = self.epgView.right
            self.onRedrawEPG(self.channelIdx, self.viewStartDate, focusFunction=self._findControlOnLeft)

    def _right(self, currentFocus):
        control = self._findControlOnRight(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            self.viewStartDate += datetime.timedelta(hours=2)
            self.focusPoint.x = self.epgView.left
            self.onRedrawEPG(self.channelIdx, self.viewStartDate, focusFunction=self._findControlOnRight)

    def _up(self, currentFocus):
        currentFocus.x = self.focusPoint.x
        control = self._findControlAbove(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            self.focusPoint.y = self.epgView.bottom
            self.onRedrawEPG(self.channelIdx - CHANNELS_PER_PAGE, self.viewStartDate,
                             focusFunction=self._findControlAbove)

    def _down(self, currentFocus):
        currentFocus.x = self.focusPoint.x
        control = self._findControlBelow(currentFocus)
        if control is not None:
            self.setFocus(control)
        elif control is None:
            self.focusPoint.y = self.epgView.top
            self.onRedrawEPG(self.channelIdx + CHANNELS_PER_PAGE, self.viewStartDate,
                             focusFunction=self._findControlBelow)

    def _nextDay(self):
        self.viewStartDate += datetime.timedelta(days=1)
        self.onRedrawEPG(self.channelIdx, self.viewStartDate)

    def _previousDay(self):
        self.viewStartDate -= datetime.timedelta(days=1)
        self.onRedrawEPG(self.channelIdx, self.viewStartDate)

    def _moveUp(self, count=1, scrollEvent=False):
        if scrollEvent:
            self.onRedrawEPG(self.channelIdx - count, self.viewStartDate)
        else:
            self.focusPoint.y = self.epgView.bottom
            self.onRedrawEPG(self.channelIdx - count, self.viewStartDate, focusFunction=self._findControlAbove)

    def _moveDown(self, count=1, scrollEvent=False):
        if scrollEvent:
            self.onRedrawEPG(self.channelIdx + count, self.viewStartDate)
        else:
            self.focusPoint.y = self.epgView.top
            self.onRedrawEPG(self.channelIdx + count, self.viewStartDate, focusFunction=self._findControlBelow)

    def _channelUp(self):
        channel = self.database.getNextChannel(self.currentChannel)
        program = self.database.getCurrentProgram(channel)
        self.playChannel(channel, program)

    def _channelDown(self):
        channel = self.database.getPreviousChannel(self.currentChannel)
        program = self.database.getCurrentProgram(channel)
        self.playChannel(channel, program)

    def playChannel(self, channel, program = None):
        self.currentChannel = channel
        wasPlaying = self.player.isPlaying()
        url = self.database.getStreamUrl(channel)
        if url:
            if str.startswith(url,"plugin://plugin.video.meta") and program is not None:
                import urllib
                title = urllib.quote(program.title)
                url += "/%s/%s" % (title, program.language)
            if url[0:9] == 'plugin://':
                if self.alternativePlayback:
                    xbmc.executebuiltin('XBMC.RunPlugin(%s)' % url)
                elif self.osdEnabled:
                    xbmc.executebuiltin('PlayMedia(%s,1)' % url)
                else:
                    xbmc.executebuiltin('PlayMedia(%s)' % url)
            else:
                self.player.play(item=url, windowed=self.osdEnabled)

            if not wasPlaying:
                self._hideEpg()

        threading.Timer(1, self.waitForPlayBackStopped).start()
        self.osdProgram = self.database.getCurrentProgram(self.currentChannel)

        return url is not None

    def waitForPlayBackStopped(self):
        for retry in range(0, 100):
            time.sleep(0.1)
            if self.player.isPlaying():
                break

        while self.player.isPlaying() and not xbmc.abortRequested and not self.isClosing:
            time.sleep(0.5)

        self.onPlayBackStopped()

    def _showOsd(self):
        if not self.osdEnabled:
            return

        if self.mode != MODE_OSD:
            self.osdChannel = self.currentChannel

        if self.osdProgram is not None:
            self.setControlLabel(self.C_MAIN_OSD_TITLE, '[B]%s[/B]' % self.osdProgram.title)
            if self.osdProgram.startDate or self.osdProgram.endDate:
                self.setControlLabel(self.C_MAIN_OSD_TIME, '[B]%s - %s[/B]' % (
                    self.formatTime(self.osdProgram.startDate), self.formatTime(self.osdProgram.endDate)))
            else:
                self.setControlLabel(self.C_MAIN_OSD_TIME, '')
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
                    self.setControlLabel(self.C_NEXT_OSD_TIME, '[B]%s - %s[/B]' % (
                        self.formatTime(nextOsdProgram.startDate), self.formatTime(nextOsdProgram.endDate)))
                else:
                    self.setControlLabel(self.C_NEXT_OSD_TIME, '')

        self.mode = MODE_OSD
        self._showControl(self.C_MAIN_OSD)

    def _hideOsd(self):
        self.mode = MODE_TV
        self._hideControl(self.C_MAIN_OSD)

    def _hideEpg(self):
        self._hideControl(self.C_MAIN_EPG)
        self.mode = MODE_TV
        self._clearEpg()

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

        # remove existing controls
        self._clearEpg()

        try:
            self.channelIdx, channels, programs = self.database.getEPGView(channelStart, startTime, self.onSourceProgressUpdate, clearExistingProgramList=False, category=self.category)
        except src.SourceException:
            self.onEPGLoadError()
            return

        channelsWithoutPrograms = list(channels)

        # date and time row
        self.setControlLabel(self.C_MAIN_DATE, self.viewStartDate.strftime("%A"))
        #self.setControlLabel(self.C_MAIN_DATE, self.formatDate(self.viewStartDate, False))
        self.setControlLabel(self.C_MAIN_DATE_LONG, self.formatDate(self.viewStartDate, True))
        for col in range(1, 5):
            self.setControlLabel(4000 + col, self.formatTime(startTime))
            startTime += HALF_HOUR

        if programs is None:
            self.onEPGLoadError()
            return

        # set channel logo or text
        showLogo = ADDON.getSetting('logos.enabled') == 'true'
        for idx in range(0, CHANNELS_PER_PAGE):
            if idx >= len(channels):
                self.setControlImage(4110 + idx, ' ')
                self.setControlLabel(4010 + idx, ' ')
                control = self.getControl(4210 + idx)
                control.setVisible(False)
            else:
                control = self.getControl(4210 + idx)
                control.setVisible(True)
                channel = channels[idx]
                self.setControlLabel(4010 + idx, channel.title)
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

        for program in programs:
            idx = channels.index(program.channel)
            if program.channel in channelsWithoutPrograms:
                channelsWithoutPrograms.remove(program.channel)

            startDelta = program.startDate - self.viewStartDate
            stopDelta = program.endDate - self.viewStartDate

            cellStart = self._secondsToXposition(startDelta.seconds)
            if startDelta.days < 0:
                cellStart = self.epgView.left
            cellWidth = self._secondsToXposition(stopDelta.seconds) - cellStart
            if cellStart + cellWidth > self.epgView.right:
                cellWidth = self.epgView.right - cellStart

            if cellWidth > 1:
                if program.notificationScheduled:
                    noFocusTexture = 'tvguide-program-red.png'
                    focusTexture = 'tvguide-program-red-focus.png'
                else:
                    noFocusTexture = 'black-back.png'
                    focusTexture = 'black-back.png'

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
                    focusedColor="0xFF00FFFF",
                    noFocusTexture=noFocusTexture,
                    focusTexture=focusTexture
                )

                self.controlAndProgramList.append(ControlAndProgram(control, program))

        for channel in channelsWithoutPrograms:
            idx = channels.index(channel)

            control = xbmcgui.ControlButton(
                self.epgView.left,
                self.epgView.top + self.epgView.cellHeight * idx,
                (self.epgView.right - self.epgView.left) - 2,
                self.epgView.cellHeight - 2,
                u"\u2014",
                focusedColor="0xFF00FFFF",
                noFocusTexture='black-back.png',
                focusTexture='black-back.png'
            )

            program = src.Program(channel, "", None, None, None)
            self.controlAndProgramList.append(ControlAndProgram(control, program))

        top = self.epgView.cellHeight * len(channels)
        height = 720 - top
        control = self.getControl(self.C_MAIN_FOOTER)
        if control:
            control.setPosition(0,top)
            control.setHeight(height)
            control.setImage('black-back.png')
        control = self.getControl(self.C_MAIN_TIMEBAR)
        if control:
            control.setHeight(top)


        # add program controls
        if focusFunction is None:
            focusFunction = self._findControlAt
        focusControl = focusFunction(self.focusPoint)
        controls = [elem.control for elem in self.controlAndProgramList]
        self.addControls(controls)
        if focusControl is not None:
            debug('onRedrawEPG - setFocus %d' % focusControl.getId())
            self.setFocus(focusControl)

        self.ignoreMissingControlIds.extend([elem.control.getId() for elem in self.controlAndProgramList])

        if focusControl is None and len(self.controlAndProgramList) > 0:
            self.setFocus(self.controlAndProgramList[0].control)



        self._hideControl(self.C_MAIN_LOADING)
        self.redrawingEPG = False

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
            self.notification = Notification(self.database, ADDON.getAddonInfo('path'))
            self.onRedrawEPG(0, self.viewStartDate)
            self.database.exportChannelList()

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

    def onPlayBackStopped(self):
        if not self.player.isPlaying() and not self.isClosing:
            self._hideControl(self.C_MAIN_OSD)
            self.onRedrawEPG(self.channelIdx, self.viewStartDate)

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

    def _findControlAt(self, point):
        for elem in self.controlAndProgramList:
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

    def _hideControl(self, *controlIds):
        """
        Visibility is inverted in skin
        """
        for controlId in controlIds:
            control = self.getControl(controlId)
            if control:
                control.setVisible(True)

    def _showControl(self, *controlIds):
        """
        Visibility is inverted in skin
        """
        for controlId in controlIds:
            control = self.getControl(controlId)
            if control:
                control.setVisible(False)

    def formatTime(self, timestamp):
        if timestamp:
            format = xbmc.getRegion('time').replace(':%S', '').replace('%H%H', '%H')
            return timestamp.strftime(format)
        else:
            return ''

    def formatDate(self, timestamp, longdate=False):
        if timestamp:
            if longdate == True:
                format = xbmc.getRegion('datelong')
            else:
                format = xbmc.getRegion('dateshort')
            return timestamp.strftime(format)
        else:
            return ''

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
                control.setVisible(timeDelta.days == 0)
            except:
                pass
            control.setPosition(self._secondsToXposition(timeDelta.seconds), y)

        if scheduleTimer and not xbmc.abortRequested and not self.isClosing:
            threading.Timer(1, self.updateTimebar).start()


class PopupMenu(xbmcgui.WindowXMLDialog):
    C_POPUP_LABEL = 7000
    C_POPUP_PROGRAM_LABEL = 7001
    C_POPUP_PROGRAM_IMAGE = 7002
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
    C_POPUP_CHANNEL_LOGO = 4100
    C_POPUP_CHANNEL_TITLE = 4101
    C_POPUP_PROGRAM_TITLE = 4102
    C_POPUP_LIBMOV = 80000
    C_POPUP_LIBTV = 80001
    C_POPUP_VIDEOADDONS = 80002


    def __new__(cls, database, program, showRemind, category, categories):
        return super(PopupMenu, cls).__new__(cls, 'script-tvguide-menu.xml', ADDON.getAddonInfo('path'), SKIN)

    def __init__(self, database, program, showRemind, category, categories):
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
        self.buttonClicked = None
        self.category = category
        self.categories = categories

    def onInit(self):
        labelControl = self.getControl(self.C_POPUP_LABEL)
        programLabelControl = self.getControl(self.C_POPUP_PROGRAM_LABEL)
        programImageControl = self.getControl(self.C_POPUP_PROGRAM_IMAGE)
        playControl = self.getControl(self.C_POPUP_PLAY)
        remindControl = self.getControl(self.C_POPUP_REMIND)
        channelLogoControl = self.getControl(self.C_POPUP_CHANNEL_LOGO)
        channelTitleControl = self.getControl(self.C_POPUP_CHANNEL_TITLE)
        programTitleControl = self.getControl(self.C_POPUP_PROGRAM_TITLE)
        programPlayBeginningControl = self.getControl(self.C_POPUP_PLAY_BEGINNING)
        programSuperFavourites = self.getControl(self.C_POPUP_SUPER_FAVOURITES)

        items = list()
        categories = ["Any"] + list(self.categories)
        for label in categories:
            item = xbmcgui.ListItem(label)

            items.append(item)
        listControl = self.getControl(self.C_POPUP_CATEGORY)
        listControl.addItems(items)
        if self.category:
            index = categories.index(self.category)
            if index >= 0:
                listControl.selectItem(index)

        playControl.setLabel(strings(WATCH_CHANNEL, self.program.channel.title))
        if not self.program.channel.isPlayable():
            playControl.setEnabled(False)
            self.setFocusId(self.C_POPUP_CHOOSE_STREAM)
        if self.database.getCustomStreamUrl(self.program.channel):
            chooseStrmControl = self.getControl(self.C_POPUP_CHOOSE_STREAM)
            chooseStrmControl.setLabel(strings(REMOVE_STRM_FILE))

        if self.program.channel.logo is not None:
            channelLogoControl.setImage(self.program.channel.logo)
        channelTitleControl.setLabel(self.program.channel.title)
        programTitleControl.setLabel(self.program.title)

        label = ""
        try:
            season = self.program.season
            episode = self.program.episode
            if season and episode:
                label = " - S%sE%s" % (season,episode)
        except:
            pass
        programLabelControl.setLabel(self.program.title+label)
        if self.program.imageSmall:
            programImageControl.setImage(self.program.imageSmall)
        labelControl.setLabel(self.program.description)

        if self.program.startDate:
            remindControl.setEnabled(True)
            if self.showRemind:
                remindControl.setLabel(strings(REMIND_PROGRAM))
            else:
                remindControl.setLabel(strings(DONT_REMIND_PROGRAM))
        else:
            remindControl.setEnabled(False)

    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_NAV_BACK]:
            self.close()
        elif action.getId() in [KEY_CONTEXT_MENU]:
            cList = self.getControl(self.C_POPUP_CATEGORY)
            item = cList.getSelectedItem()
            if item:
                self.category = item.getLabel()
            if self.category == "Any":
                return
            dialog = xbmcgui.Dialog()
            categories = sorted(self.categories)
            channelList = sorted([channel.title for channel in self.database.getChannelList(onlyVisible=False)])
            str = 'Select Channels for %s Categeory' % self.category
            ret = dialog.multiselect(str, channelList)
            if ret is None:
                return
            if not ret:
                ret = []
            channels = []
            for i in ret:
                channels.append(channelList[i])
            f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','rb')
            lines = f.read().splitlines()
            f.close()
            categories = {}
            categories[self.category] = []
            for line in lines:
                name,cat = line.split('=')
                if cat not in categories:
                    categories[cat] = []
                if cat != self.category:
                    categories[cat].append(name)
            for channel in channels:
                categories[self.category].append(channel)
            f = xbmcvfs.File('special://profile/addon_data/script.tvguide.fullscreen/categories.ini','wb')
            for cat in categories:
                channels = categories[cat]
                for channel in channels:
                    f.write("%s=%s\n" % (channel.encode("utf8"),cat))
            f.close()
            self.categories = [category for category in categories if category]


    def onClick(self, controlId):
        if controlId == self.C_POPUP_CHOOSE_STREAM and self.database.getCustomStreamUrl(self.program.channel):
            self.database.deleteCustomStreamUrl(self.program.channel)
            chooseStrmControl = self.getControl(self.C_POPUP_CHOOSE_STREAM)
            chooseStrmControl.setLabel(strings(CHOOSE_STRM_FILE))

            if not self.program.channel.isPlayable():
                playControl = self.getControl(self.C_POPUP_PLAY)
                playControl.setEnabled(False)
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
                categories = ["Any"] + list(self.categories)
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

    def __new__(cls, database):
        return super(ChannelsMenu, cls).__new__(cls, 'script-tvguide-channels.xml', ADDON.getAddonInfo('path'), SKIN)

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

            self.getControl(self.C_CHANNELS_SELECTION_VISIBLE).setVisible(False)
            self.setFocusId(self.C_CHANNELS_SELECTION)

        elif self.getFocusId() == self.C_CHANNELS_SELECTION and action.getId() in [ACTION_RIGHT, ACTION_SELECT_ITEM]:
            self.getControl(self.C_CHANNELS_SELECTION_VISIBLE).setVisible(True)
            xbmc.sleep(350)
            self.setFocusId(self.C_CHANNELS_LIST)

        elif self.getFocusId() == self.C_CHANNELS_SELECTION and action.getId() in [ACTION_PREVIOUS_MENU, KEY_CONTEXT_MENU]:
            listControl = self.getControl(self.C_CHANNELS_LIST)
            idx = listControl.getSelectedPosition()
            self.swapChannels(self.selectedChannel, idx)
            self.getControl(self.C_CHANNELS_SELECTION_VISIBLE).setVisible(True)
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

        elif controlId == self.C_CHANNELS_SAVE:
            self.database.saveChannelList(self.close, self.channelList)

        elif controlId == self.C_CHANNELS_CANCEL:
            self.close()

    def onFocus(self, controlId):
        pass

    def updateChannelList(self):
        listControl = self.getControl(self.C_CHANNELS_LIST)
        listControl.reset()
        for idx, channel in enumerate(self.channelList):
            if channel.visible:
                iconImage = 'tvguide-channel-visible.png'
            else:
                iconImage = 'tvguide-channel-hidden.png'

            item = xbmcgui.ListItem('%3d. %s' % (idx + 1, channel.title), iconImage=iconImage)
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
    C_STREAM_FAVOURITES = 2001
    C_STREAM_FAVOURITES_PREVIEW = 2002
    C_STREAM_FAVOURITES_OK = 2003
    C_STREAM_FAVOURITES_CANCEL = 2004
    C_STREAM_ADDONS = 3001
    C_STREAM_ADDONS_STREAMS = 3002
    C_STREAM_ADDONS_NAME = 3003
    C_STREAM_ADDONS_DESCRIPTION = 3004
    C_STREAM_ADDONS_PREVIEW = 3005
    C_STREAM_ADDONS_OK = 3006
    C_STREAM_ADDONS_CANCEL = 3007
    C_STREAM_BROWSE_ADDONS = 4001
    C_STREAM_BROWSE_STREAMS = 4002
    C_STREAM_BROWSE_NAME = 4003
    C_STREAM_BROWSE_DESCRIPTION = 4004
    C_STREAM_BROWSE_PREVIEW = 4005
    C_STREAM_BROWSE_OK = 4006
    C_STREAM_BROWSE_CANCEL = 4007
    C_STREAM_BROWSE_DIRS = 4008
    C_STREAM_BROWSE_FOLDER = 4009
    C_STREAM_CHANNEL_LOGO = 4023
    C_STREAM_CHANNEL_LABEL = 4024

    C_STREAM_VISIBILITY_MARKER = 100

    VISIBLE_STRM = 'strm'
    VISIBLE_FAVOURITES = 'favourites'
    VISIBLE_ADDONS = 'addons'
    VISIBLE_BROWSE = 'browse'

    def __new__(cls, database, channel):
        return super(StreamSetupDialog, cls).__new__(cls, 'script-tvguide-streamsetup.xml', ADDON.getAddonInfo('path'), SKIN)

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
        if self.player.isPlaying():
            self.player.stop()
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
        self.getControl(self.C_STREAM_CHANNEL_LOGO).setImage(self.channel.logo)


    def onAction(self, action):
        if action.getId() in [ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, KEY_NAV_BACK, KEY_CONTEXT_MENU]:
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

        elif controlId == self.C_STREAM_ADDONS_OK:
            listControl = self.getControl(self.C_STREAM_ADDONS_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                self.database.setCustomStreamUrl(self.channel, stream)
            self.close()
        elif controlId == self.C_STREAM_BROWSE_OK:
            listControl = self.getControl(self.C_STREAM_BROWSE_STREAMS)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                self.database.setCustomStreamUrl(self.channel, stream)
            self.close()

        elif controlId == self.C_STREAM_FAVOURITES_OK:
            listControl = self.getControl(self.C_STREAM_FAVOURITES)
            item = listControl.getSelectedItem()
            if item:
                stream = item.getProperty('stream')
                self.database.setCustomStreamUrl(self.channel, stream)
            self.close()

        elif controlId == self.C_STREAM_STRM_OK:
            self.database.setCustomStreamUrl(self.channel, self.strmFile)
            self.close()

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
            item = xbmcgui.ListItem(label)
            item.setProperty('stream', stream)
            items.append(item)
        listControl = self.getControl(StreamSetupDialog.C_STREAM_ADDONS_STREAMS)
        listControl.reset()
        listControl.addItems(items)

    def updateDirsInfo(self):
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
        dirs = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "directory"])
        items = list()
        item = xbmcgui.ListItem('[B]%s[/B]' % addon.getAddonInfo('name'))
        item.setProperty('stream', path)
        items.append(item)
        for label in sorted(dirs):
            stream = dirs[label]
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
        listControl = self.getControl(self.C_STREAM_BROWSE_DIRS)
        item = listControl.getSelectedItem()
        if item is None:
            return

        previousDirsId = self.previousDirsId

        self.previousDirsId = item.getProperty('stream')

        path = self.previousDirsId

        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
        files = response["files"]
        dirs = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "directory"])
        links = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "file"])
        thumbnails = dict([[f["label"], f["thumbnail"]] for f in files if f["filetype"] == "file"])

        items = list()
        item = xbmcgui.ListItem('[B]..[/B]')
        item.setProperty('stream', previousDirsId)
        items.append(item)

        for label in sorted(dirs):
            stream = dirs[label]
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
        items = f.read().splitlines()
        f.close()
        items.append(self.previousDirsId)
        unique = set(items)
        f = xbmcvfs.File(file_name,"w")
        lines = "\n".join(unique)
        f.write(lines)
        f.close()

        self.previousDirsId

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
            name = re.sub(r'\[.*?\]','',name)
            stream = listItem.getProperty('stream')
            if stream:
                streams[addonId][name] = stream

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
                name = re.sub(r'[:=]',' ',name)
                if not stream:
                    stream = 'nothing'
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
            #name = listItem.getLabel()
            #name = re.sub(r'\[.*?\]','',name)
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
                #name = re.sub(r'[:=]',' ',name)
                if not stream:
                    stream = 'nothing'
                write_str = "%s|%s\n" % (name,stream)
                f.write(write_str)
        f.close()



class ChooseStreamAddonDialog(xbmcgui.WindowXMLDialog):
    C_SELECTION_LIST = 1000

    def __new__(cls, addons):
        return super(ChooseStreamAddonDialog, cls).__new__(cls, 'script-tvguide-streamaddon.xml', ADDON.getAddonInfo('path'), SKIN)

    def __init__(self, addons):
        super(ChooseStreamAddonDialog, self).__init__()
        self.addons = addons
        self.stream = None

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
            self.close()

    def onFocus(self, controlId):
        pass
