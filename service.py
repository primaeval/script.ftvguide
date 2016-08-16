# -*- coding: utf-8 -*-
#
#      Copyright (C) 2012 Tommy Winther
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
import xbmcaddon
import notification
import xbmc
import source


class Service(object):
    def __init__(self):
        self.database = source.Database()
        self.database.initialize(self.onInit)

    def onInit(self, success):
        if success:
            self.database.updateChannelAndProgramListCaches(self.onCachesUpdated)
        else:
            self.database.close()

    def onCachesUpdated(self):

        if ADDON.getSetting('notifications.enabled') == 'true':
            n = notification.Notification(self.database, ADDON.getAddonInfo('path'))
            n.scheduleNotifications()

        self.database.close(None)


if __name__ == '__main__':
    try:
        ADDON = xbmcaddon.Addon('script.tvguide.fullscreen')
        if ADDON.getSetting('autostart') == "true":
            xbmc.executebuiltin("RunAddon(script.tvguide.fullscreen)")

        if ADDON.getSetting('background.service') == 'true':
            monitor = xbmc.Monitor()
            xbmc.log("[script.tvguide.fullscreen] Background service started...", xbmc.LOGDEBUG)
            Service()
            if ADDON.getSetting('service.addon.folders') == "true":
                xbmc.executebuiltin('RunScript(special://home/addons/script.tvguide.fullscreen/ReloadAddonFolders.py)')
            interval = int(ADDON.getSetting('service.interval'))
            waitTime = 21600  # Default 6hrs
            if interval == 0:
                waitTime = 7200   # 2hrs
            elif interval == 1:
                waitTime = 21600  # 6hrs
            elif interval == 2:
                waitTime = 43200  # 12hrs
            elif interval == 3:
                waitTime = 86400  # 24hrs
            while not monitor.abortRequested():
                # Sleep/wait for specified time
                xbmc.log("[script.tvguide.fullscreen] Service waiting for interval %s" % waitTime, xbmc.LOGDEBUG)
                if monitor.waitForAbort(waitTime):
                    # Abort was requested while waiting. We should exit
                    break
                xbmc.log("[script.tvguide.fullscreen] Service now triggered...", xbmc.LOGDEBUG)
                Service()
                if ADDON.getSetting('service.addon.folders') == "true":
                    xbmc.executebuiltin('RunScript(special://home/addons/script.tvguide.fullscreen/ReloadAddonFolders.py)')

    except source.SourceNotConfiguredException:
        pass  # ignore
    except Exception, ex:
        xbmc.log('[script.tvguide.fullscreen] Uncaught exception in service.py: %s' % str(ex), xbmc.LOGDEBUG)
