import os
import re
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
from rpc import RPC

ADDON = xbmcaddon.Addon(id='script.tvguide.fullscreen')

file_name = 'special://profile/addon_data/script.tvguide.fullscreen/folders.list'
f = xbmcvfs.File(file_name)
items = f.read().splitlines()
f.close()
unique = set(items)

file_name = 'special://profile/addon_data/script.tvguide.fullscreen/addons.ini'
if int(ADDON.getSetting('addons.ini.type')) == 1:
    customFile = str(ADDON.getSetting('addons.ini.file'))
    if os.path.exists(customFile) and os.access(customFile,os.W_OK):
        file_name = customFile

plugins = {}
logos = {}
for path in unique:
    try:
        response = RPC.files.get_directory(media="files", directory=path, properties=["thumbnail"])
    except:
        continue
    files = response["files"]
    dirs = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "directory"])
    links = dict([[f["label"], f["file"]] for f in files if f["filetype"] == "file"])
    thumbnails = dict([[f["file"], f["thumbnail"]] for f in files if f["filetype"] == "file"])
    match = re.match(r"plugin://(.*?)/",path)
    if match:
        plugin = match.group(1)
    else:
        continue
    if plugin not in plugins:
        plugins[plugin] = {}
    if plugin not in logos:
        logos[plugin] = {}

    streams = plugins[plugin]
    for label in links:
        file = links[label]
        streams[label] = file
    thumbs = logos[plugin]
    for file in thumbnails:
        thumb = thumbnails[file]
        thumbs[file] = thumb

f = xbmcvfs.File(file_name,'wb')
write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next folder add.\n\n"
f.write(write_str.encode("utf8"))

for addonId in sorted(plugins):
    write_str = "[%s]\n" % (addonId)
    f.write(write_str)
    addonStreams = plugins[addonId]
    for name in sorted(addonStreams):
        stream = addonStreams[name]
        if name.startswith(' '):
            continue
        name = re.sub(r'[:=]',' ',name)
        name = re.sub(r'\[.*?\]','',name)
        if not name: #TODO names in brackets
            continue
        if name.startswith(' '):
            continue
        if not stream:
            stream = 'nothing'
        write_str = "%s=%s\n" % (name,stream)
        f.write(write_str.encode("utf8"))
f.close()

file_name = 'special://profile/addon_data/script.tvguide.fullscreen/icons.ini'
f = xbmcvfs.File(file_name,'wb')
write_str = "# WARNING Make a copy of this file.\n# It will be overwritten on the next folder add.\n\n"
f.write(write_str.encode("utf8"))

for addonId in sorted(logos):
    write_str = "[%s]\n" % (addonId)
    f.write(write_str)
    addonLogos = logos[addonId]
    for file in sorted(addonLogos):
        logo = addonLogos[file]
        if logo:
            write_str = "%s|%s\n" % (file,logo)
            f.write(write_str.encode("utf8"))
f.close()

dialog = xbmcgui.Dialog()
dialog.notification("TV Guide Fullscreen","Done: Reload Addon Folders",sound=False)
