import cgi, os, sys, urllib, re
import xml.dom.minidom as dom
import logging
import xbmcplugin, xbmcgui, xbmc
from datetime import date
from operator import itemgetter

from iplayer2 import get_provider, httpget, get_protocol, get_port, get_thumb_dir

# it would be nice to scrape what's on now - at least when the items are first created.

# note that cbbc and cbeebies use bbc three/four whilst they are offline
# channel id : order, stream id, display name, logo
# note: some channel ids used in www urls are different from the stream urls
live_tv_channels = {
    'bbc_one_london' : (1, 'bbc_one_london', 'BBC One', 'bbc_one.png'),
    'bbc_two_england': (2, 'bbc_two_england', 'BBC Two', 'bbc_two.png'),
    'bbc_three' : (3, 'bbc_three', 'BBC Three', 'bbc_three.png'),
    'bbc_four' : (4, 'bbc_four', 'BBC Four', 'bbc_four.png'),
    'cbbc' : (5, 'bbc_three', 'CBBC', 'cbbc.png'),
    'cbeebies' : (6, 'bbc_four', 'Cbeebies', 'cbeebies.png'),
    'bbc_news24' : (7, 'bbc_news24', 'BBC News', 'bbc_news24.png'),
    'bbc_parliament' : (8, 'bbc_parliament', 'BBC Parliament', 'bbc_parliament.png'),
    'bbc_alba' : (9, 'bbc_alba', 'BBC ALBA', 'bbc_alba.png'),
    #'bbc_redbutton' : (10, 'bbc_redbutton_live', 'BBC Red Button', 'bbc_one.png')
    }

def parseXML(url):
    xml = httpget(url)
    doc = dom.parseString(xml)
    root = doc.documentElement
    return root

def fetch_stream_info(channel, req_bitrate, req_provider):
    (sort, stream_id, label, thumb) = live_tv_channels[channel]

    provider = req_provider;

    if   req_bitrate <= 480: quality = 1
    elif req_bitrate == 800: quality = 2
    elif req_bitrate >= 1500: quality = 3

    if   quality == 1: quality_attr = 'pc_stream_audio_video_simulcast_uk_v_lm_p004'
    elif quality == 2: quality_attr = 'pc_stream_audio_video_simulcast_uk_v_lm_p005'
    elif quality == 3: quality_attr = 'pc_stream_audio_video_simulcast_uk_v_lm_p006'

    if channel == 'bbc_parliament' or channel == 'bbc_alba':
        quality_attr = ''
        provider = ''
        
    if channel == 'bbc_redbutton':
        provider = ''

    # if user chooses a stream type that doesn't exist for live, switch to "auto" mode
    if req_provider != 'akamai' and req_provider != 'limelight':
        provider = ''

    # bbc one seem to switch between "akamai_hd" and "akamai"
    #if ( channel == "bbc_one_london" or channel == "bbc_two_england" ) and req_provider == "akamai":
    #    req_provider = "akamai_hd"

    surl = 'http://www.bbc.co.uk/mediaselector/4/mtis/stream/%s/%s/%s' % (stream_id, quality_attr, provider)
    logging.info("getting media information from %s" % surl)
    root = parseXML(surl)
    mbitrate = 0
    url = ""
    if root.getElementsByTagName( "error" ) and root.getElementsByTagName( "error" )[0].attributes["id"].nodeValue == 'notavailable': return ""
    media = root.getElementsByTagName( "media" )[0]

    conn  = media.getElementsByTagName( "connection" )[0]

    # rtmp streams
    identifier  = conn.attributes['identifier'].nodeValue
    server      = conn.attributes['server'].nodeValue
    auth        = conn.attributes['authString'].nodeValue
    supplier    = conn.attributes['supplier'].nodeValue

    # not always listed for some reason
    try:
        application = conn.attributes['application'].nodeValue
    except:
        application = 'live'

    params = dict(protocol = get_protocol(), port = get_port(), server = server, auth = auth, ident = identifier, app = application)

    if supplier == "akamai" or supplier == "limelight":
        if supplier == "akamai":
            url = "%(protocol)s://%(server)s:%(port)s/%(app)s/?%(auth)s playpath=%(ident)s?%(auth)s" % params
        if supplier == "limelight":
            url = "%(protocol)s://%(server)s:%(port)s/ app=%(app)s?%(auth)s tcurl=%(protocol)s://%(server)s:%(port)s/%(app)s?%(auth)s playpath=%(ident)s" % params
        url += " swfurl=http://www.bbc.co.uk/emp/10player.swf swfvfy=1 live=1"
    elif supplier == "akamai_hd":
        url = conn.attributes['href'].nodeValue

    return (url)

def play_stream(channel, bitrate, showDialog):
    bitrate = int(bitrate)
    # check to see if bbcthree/cbbc or bbcfour/cbeebies is on the air?    
    if channel == 'bbc_three' or channel == 'bbc_four' or channel == 'cbeebies' or channel == 'cbbc':
        surl = 'http://www.bbc.co.uk/iplayer/tv/'+channel
        cstr = httpget(surl)
        off_air_message = re.compile('<h2 class="off-air">.+?</span>(.+?)</a></h2>').findall(cstr)
        if off_air_message:
            pDialog = xbmcgui.Dialog()
            pDialog.ok('IPlayer', 'Channel is currently Off Air')
            return

    provider = get_provider()
    
    # check for red button usage
    if channel == 'bbc_redbutton':
        pDialog = xbmcgui.Dialog()
        if not pDialog.yesno("BBC Red Button Live Stream", "This will only work when the stream is broadcasting.", "If it is not on, xbmc may retry indefinately (crash)", "Do you want to try anyway?"):
            return

    url = fetch_stream_info(channel, bitrate, provider)

    if url == "":
        pDialog = xbmcgui.Dialog()
        pDialog.ok('IPlayer', "Sorry, stream is currently unavailable")

    if showDialog:
        pDialog = xbmcgui.DialogProgress()
        pDialog.create('IPlayer', 'Loading live stream info')
        xbmc.sleep(50)

    if showDialog: pDialog.update(50, 'Starting Stream')
    # build listitem to display whilst playing
    (sort, stream_id, label, thumb) = live_tv_channels[channel]
    listitem = xbmcgui.ListItem(label = label + ' - Live')
    listitem.setIconImage('defaultVideo.png')
    listitem.setThumbnailImage(os.path.join(get_thumb_dir(), thumb))

    play = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    play.clear()
    play.add(url,listitem)
    player = xbmc.Player(xbmc.PLAYER_CORE_AUTO)
    player.play(play)
    if showDialog: pDialog.close()
    
def make_url(channel=None):
    base = sys.argv[0]
    d = {}
    if channel: d['label'] = channel
    d['pid'] = 0       
    params = urllib.urlencode(d, True)
    return base + '?' + params    

def list_channels():
    handle = int(sys.argv[1])
    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_NONE )

    channels = sorted(live_tv_channels.items(), key=itemgetter(1))
    for id, (sort, stream_id, label, thumb) in channels:
        url = make_url(channel = id)
        listitem = xbmcgui.ListItem(label=label)
        listitem.setIconImage('defaultVideo.png')
        listitem.setThumbnailImage(os.path.join(get_thumb_dir(), thumb))        
        ok = xbmcplugin.addDirectoryItem(
            handle = handle, 
            url = url,
            listitem = listitem,
            isFolder = False,
        )

    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

##############################################
if __name__ == '__main__':
    args = cgi.parse_qs(sys.argv[2][1:])
    channel = args.get('label', [None])[0]
    if channel and channel != '':
        play_stream(channel,800)
    else:
        list_channels()
