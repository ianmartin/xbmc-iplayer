#/bin/python

import sys, os, os.path, re
import urllib, cgi
from string import ascii_lowercase
from socket import setdefaulttimeout
from time import time
import traceback
import md5
import logging

try:
    import xbmc, xbmcgui, xbmcplugin
except ImportError:
    pass # for PC debugging

sys.path.insert(0, os.path.join(os.getcwd(), 'lib'))

try: 
    import iplayer2 as iplayer
    import httplib2
except ImportError, error:
    print error
    print sys.path
    d = xbmcgui.Dialog()
    d.ok(str(error), 'Please check you installed this plugin correctly.')
    raise

try:
    logging.basicConfig(
        filename='iplayer2.log', 
        filemode='w',
        format='%(asctime)s %(levelname)4s %(message)s',
        level=logging.DEBUG
    )
except IOError:
    print "iplayer2 logging to stdout"
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.DEBUG,
        format='iplayer2.py: %(asctime)s %(levelname)4s %(message)s',
    )

__scriptname__  = 'IPlayer'
DIR_USERDATA = xbmc.translatePath(os.path.join( "T:"+os.sep,"plugin_data", __scriptname__ ))    
HTTP_CACHE_DIR = os.path.join(DIR_USERDATA, 'iplayer_http_cache')
CACHE_DIR = os.path.join(DIR_USERDATA, 'iplayer_cache')
MP3_CACHE = os.path.join(CACHE_DIR, 'bbc.mp3')
SUBTITLES_DIR = os.path.join(DIR_USERDATA, 'Subtitles')
THUMB_DIR = os.path.join(os.getcwd(), 'resources', 'media')

print "SUBTITLES DIR: %s" % SUBTITLES_DIR

for d in [CACHE_DIR, HTTP_CACHE_DIR, SUBTITLES_DIR]:
    if not os.path.isdir(d):
        try:
            print "%s doesn't exist, creating" % d
            os.makedirs(d)
        except IOError, e:
            print "Couldn't create %s, %s" % (d, str(e))
            raise

def get_feed_thumbnail(feed):
    thumbfn = ''
    if not feed or not feed.channel: return ''

    # support user supplied .png files
    userpng = os.path.join(iplayer.IMG_DIR, feed.channel + '.png')
    if os.path.isfile(userpng):
        return userpng

    # check for a preconfigured logo
    if iplayer.channels_logos.has_key(feed.channel):
        url = iplayer.channels_logos[feed.channel]
        return url
        
    # national TV and Radio stations have easy to find online logos
    if feed.tvradio == 'radio':
        url = "http://www.bbc.co.uk/iplayer/img/radio/%s.gif" % feed.channel
    else:
        url = "http://www.bbc.co.uk/iplayer/img/tv/%s.jpg" % feed.channel
        
    return url
    
def make_url(feed=None, listing=None, pid=None, tvradio=None, category=None, series=None, url=None, label=None):
    base = sys.argv[0]
    d = {}
    if series: d['series'] = series       
    if feed:
        if feed.channel: 
            d['feed_channel'] = feed.channel
        if feed.atoz: 
            d['feed_atoz'] = feed.atoz
    if category: d['category'] = category 
    if listing: d['listing'] = listing
    if pid: d['pid'] = pid
    if tvradio: d['tvradio'] = tvradio
    if url: d['url'] = url
    if label: d['label'] = label
    params = urllib.urlencode(d, True)
    return base + '?' + params

def read_url():
    args = cgi.parse_qs(sys.argv[2][1:])
    feed_channel = args.get('feed_channel', [None])[0]
    feed_atoz = args.get('feed_atoz', [None])[0]
    listing = args.get('listing', [None])[0]
    pid = args.get('pid', [None])[0]
    tvradio = args.get('tvradio', [None])[0]
    category = args.get('category', [None])[0]
    series = args.get('series', [None])[0]    
    url = args.get('url', [None])[0]
    label = args.get('label', [None])[0]
    
    feed = None
    if feed_channel:
        feed = iplayer.feed('auto', channel=feed_channel, atoz=feed_atoz)
    elif feed_atoz:
        feed = iplayer.feed(tvradio or 'auto', atoz=feed_atoz)
    return (feed, listing, pid, tvradio, category, series, url, label)

def list_atoz(feed=None):
    handle = int(sys.argv[1])
    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_UNSORTED)
    
    letters = list(ascii_lowercase) + ['0']
        
    feed = feed or iplayer.tv
    feeds = [feed.get(l) for l in letters]
    for f in feeds:
        listitem = xbmcgui.ListItem(label=f.name)
        listitem.setThumbnailImage(get_feed_thumbnail(f))
        url = make_url(feed=f, listing='list')
        ok = xbmcplugin.addDirectoryItem(
            handle=handle,
            url=url,
            listitem=listitem,
            isFolder=True,
        )

    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
    
def list_feeds(feeds, tvradio='tv'):
    handle = int(sys.argv[1])
    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_TRACKNUM )   

    folders = []
    folders.append(('Categories', 'categories.png', make_url(listing='categories', tvradio=tvradio)))    
    folders.append(('Highlights', 'highlights.png', make_url(listing='highlights', tvradio=tvradio)))
    if tvradio == 'radio':
        folders.append(('Listen Live', 'listenlive.png', make_url(listing='livefeeds', tvradio=tvradio)))    
    folders.append(('Popular', 'popular.png', make_url(listing='popular', tvradio=tvradio)))
    folders.append(('Search', 'search.png', make_url(listing='search', tvradio=tvradio)))

    total = len(folders) + len(feeds) + 1

    i = 1        
    for j, (label, tn, url) in enumerate(folders):
        listitem = xbmcgui.ListItem(label=label)
        listitem.setIconImage('defaultFolder.png')
        listitem.setThumbnailImage(os.path.join(THUMB_DIR, tn))
        listitem.setProperty('tracknumber', str(i + j))            
        ok = xbmcplugin.addDirectoryItem(
            handle=handle, 
            url=url,
            listitem=listitem,
            isFolder=True,
        )

    i = len(folders) + 1
    for j, f in enumerate(feeds):
        listitem = xbmcgui.ListItem(label=f.name)
        listitem.setIconImage('defaultFolder.png')
        listitem.setThumbnailImage(get_feed_thumbnail(f))
        listitem.setProperty('tracknumber', str(i + j))
        url = make_url(feed=f, listing='list')
        ok = xbmcplugin.addDirectoryItem(
            handle=handle,
            url=url,
            listitem=listitem,
            isFolder=True,
        )
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)


def list_live_feeds(feeds, tvradio='tv'):
    #print 'list_live_feeds %s' % feeds
    handle = int(sys.argv[1])
    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_TRACKNUM)

    if tvradio == 'tv':
        return
        
    i = 0        
    for j, f in enumerate(feeds):
        if not iplayer.live_radio_stations.has_key(f.name):
            #print "no key for %s" % f.name
            continue
        listitem = xbmcgui.ListItem(label=f.name)
        listitem.setIconImage('defaultFolder.png')
        if iplayer.live_webcams.has_key(f.name):
            listitem.setThumbnailImage(iplayer.live_webcams[f.name])
        else:
            listitem.setThumbnailImage(get_feed_thumbnail(f))
        listitem.setProperty('tracknumber', str(i + j))
        
        # Real & ASX url's are just redirects that are not always well
        # handled by XBMC so if present load and process redirect
        radio_url   = iplayer.live_radio_stations[f.name]
        stream_asx  = re.compile('\.asx$', re.IGNORECASE)
        stream_mms  = re.compile('href\="(mms.*?)"', re.IGNORECASE)
        stream_real = re.compile('\.ram$', re.IGNORECASE)
               
        match_asx   = stream_mms.search(radio_url) 
        match_real  = stream_mms.search(radio_url)
        
        if match_real:
            stream_url = iplayer.httpget(radio_url)
        elif match_asx:
            txt = iplayer.httpget(radio_url)
            match_mms  = stream_mms.search(txt) 
            stream_url = matchmms.group(1)
        else:
            stream_url = radio_url
                          
        ok = xbmcplugin.addDirectoryItem(
            handle=handle,
            url=stream_url,
            listitem=listitem,
            isFolder=False,
        )
    
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)




def list_tvradio():
    """
    Lists five folders - one for TV and one for Radio, plus A-Z, highlights and popular
    """
    handle = int(sys.argv[1])
    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_TRACKNUM)
        
    folders = []
    folders.append(('TV', os.path.join(iplayer.IMG_DIR, 'tv.png'), make_url(tvradio='tv')))
    folders.append(('Radio', os.path.join(iplayer.IMG_DIR, 'radio.png'), make_url(tvradio='radio')))
    folders.append(('Settings', os.path.join(iplayer.IMG_DIR, 'settings.png'), make_url(tvradio='Settings')))
        
    for i, (label, tn, url) in enumerate(folders):
        listitem = xbmcgui.ListItem(label=label)
        listitem.setIconImage('defaultFolder.png')
        listitem.setThumbnailImage(tn)        
        ok = xbmcplugin.addDirectoryItem(
            handle=handle, 
            url=url,
            listitem=listitem,
            isFolder=True,
        )
    
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)

def get_setting_videostream(default='flashmed'):
    videostream = xbmcplugin.getSetting('video_stream')
    #Auto|Flash VP6|H.264 (800kb)|H.264 (1500kb)|H.264 (3200kb)
    if videostream:
        if videostream == 'Flash (512kb)' or videostream == '1':
            return 'flashmed'
        elif videostream == 'H.264 (800kb)' or videostream == '2':
            return 'h264 800'
        elif videostream == 'H.264 (1500kb)' or videostream == '3':
            return 'h264 1500'        
        elif videostream == 'H.264 (3200kb)' or videostream == '4':
            return 'h264 3200'        
    return default

def get_setting_audiostream(default='mp3'):
    videostream = xbmcplugin.getSetting('audio_stream')
    #Auto|MP3|Real|AAC
    if videostream:
        if videostream == 'MP3' or videostream == '1':
            return 'mp3'
        elif videostream == 'Real' or videostream == '2':
            return 'real'
        elif videostream == 'AAC' or videostream == '3':
            return 'aac'        
    return default


def get_setting_thumbnail_size():
    size = xbmcplugin.getSetting('thumbnail_size')
    #Biggest|Large|Small|Smallest|None
    if size:
        if size == 'Biggest' or size == '0':
            return 'biggest'
        elif size == 'Large' or size == '1':
            return 'large'
        elif size == 'Small' or size == '2':
            return 'small'
        elif size =='Smallest' or size == '3':
            return 'smallest'
        elif size == 'None' or size == '4':
            return 'none'
    # default
    return 'large'

def get_setting_subtitles():
    subtitles = xbmcplugin.getSetting('subtitles_control')
    #values="None|Download and Play|Download to File" default="None"
    if subtitles:
        if subtitles == 'None' or subtitles == '0':
            return None
        elif subtitles == 'Download and Play' or subtitles == '1':
            return 'autoplay'
        elif subtitles == 'Download to File' or subtitles == '2':
            return 'download'
    # default
    return None

def add_programme(programme, totalItems=None, tracknumber=None, thumbnail_size='large', tvradio='tv'):
    handle = int(sys.argv[1])

    title = programme.title
    listitem = xbmcgui.ListItem(label=title, 
                                label2=programme.summary,
                                iconImage='defaultVideo.png', 
                                thumbnailImage=programme.get_thumbnail(thumbnail_size, tvradio))

    datestr = programme.updated[:10]
    date=datestr[8:10] + '/' + datestr[5:7] + '/' +datestr[:4]#date ==dd/mm/yyyy

    if programme.categories and len(programme.categories) > 0:
        genre = programme.categories[-1]
    else: 
        genre = ''

    listitem.setInfo('video', {
        'Title': programme.title,
        'Plot': programme.summary,
        'PlotOutline': programme.summary,
        'Genre': genre,
        "Date": date,
    })
    listitem.setProperty('Title', str(title))
    if tracknumber: listitem.setProperty('tracknumber', str(tracknumber))
        
    #print "Getting URL for %s ..." % (programme.title)

    url=make_url(pid=programme.pid)
    xbmcplugin.addDirectoryItem(
        handle=handle, 
        url=url,
        listitem=listitem,
        totalItems=totalItems
    )

    return True


def list_categories(feed=None, channels=None, progcount=True):
    handle = int(sys.argv[1])

    if not feed:
        xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_TRACKNUM)
        # top level list of channels
        for j, f in enumerate(channels):
            listitem = xbmcgui.ListItem(label=f.name)
            listitem.setIconImage('defaultFolder.png')
            listitem.setThumbnailImage(get_feed_thumbnail(f))
            listitem.setProperty('tracknumber', str(j))
            url = make_url(feed=f, listing='categories')
            ok = xbmcplugin.addDirectoryItem(
                handle=handle,
                url=url,
                listitem=listitem,
                isFolder=True,
            )
                
        xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
        return
        
    # list of categories within a channel
    xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_NONE)
    for category, count in feed.categories():
        url = make_url(feed=feed, listing='list', category=category)
        if progcount:
            label = "%s (%s)" % (category, count)
        else :
            label = category
        listitem = xbmcgui.ListItem(label=label)
        listitem.setThumbnailImage(get_feed_thumbnail(feed))
        ok = xbmcplugin.addDirectoryItem(            
            handle=handle, 
            url=url,
            listitem=listitem,
            isFolder=True,
        )
        
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
    

def list_series(feed, listing, category=None, progcount=True):
    handle = int(sys.argv[1])
    #xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_NONE)
    #xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    #xbmc.executebuiltin('XBMC.activatewindow(MyVideoLibrary,%s?feed=%s&listing=list)' % (sys.argv[0], feed.channel))

    c = 0
    name = feed.name

    d = {}
    d['list'] = feed.list
    d['popular'] = feed.popular
    d['highlights'] = feed.highlights
    programmes = d[listing]()
 
    ## filter by category
    if category:
        temp_prog = []
        # if a category filter has been specified then only parse programmes
        # in that category
        for p in programmes:
            for cat in p.categories:
                if cat == category: 
                    temp_prog.append(p)
                    continue
        programmes = temp_prog
 
    ## extract the list of series names
    series = {}
    episodes = {}
    categories = {}
    dates = {}
    seriesmatch = re.compile('^(.*?):')
    thumbnail_size = get_setting_thumbnail_size()
    for p in programmes:
        match = seriesmatch.search(p.title)
        thumb = p.get_thumbnail(thumbnail_size, feed.tvradio)

        if match:
            seriesname = match.group(1)
        else:
            # the programme title doesn't have a series delimiter
            seriesname = p.title
            
        series[seriesname] = thumb
        datestr = p.updated[:10]
        if not episodes.has_key(seriesname): 
            episodes[seriesname] = 0
            dates[seriesname] = datestr

        episodes[seriesname] += 1
        categories[seriesname] = p.categories
        
    serieslist = series.keys()
    serieslist.sort()
 
    for s in serieslist:
        url = make_url(feed=feed, listing='list', category=category, series=s )
        if progcount:
            label = "%s (%s)" % (s, episodes[s])
        else:
            label = s
        listitem = xbmcgui.ListItem(label=label, label2=label)
        listitem.setThumbnailImage(series[s])
        date=dates[s][8:10] + '/' + dates[s][5:7] + '/' +dates[s][:4] #date ==dd/mm/yyyy
        listitem.setInfo('video', {'Title': s, 'Date': date, 'Size': episodes[s], 'Genre': "/".join(categories[s])})
        ok = xbmcplugin.addDirectoryItem(            
            handle=handle, 
            url=url,
            listitem=listitem,
            isFolder=True,
        )
        c += 1        
    
    if c == 0:
        # and yes it does happen once in a while
        label = "(no programmes available - try again later)"
        listitem = xbmcgui.ListItem(label=label)
        ok = xbmcplugin.addDirectoryItem(
            url="",
            handle=handle, 
            listitem=listitem
        )        
    
    #if feed.is_tv:
    #xbmcplugin.setContent(handle=handle, content='tvshows')        
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
    
    
def search(tvradio = 'tv'):
    handle = int(sys.argv[1])
    
    kb = xbmc.Keyboard('', 'Search for')
    kb.doModal()
    if not kb.isConfirmed():
        xbmcplugin.endOfDirectory(handle=handle, succeeded=False)

    searchterm = kb.getText()
    
    feed = iplayer.feed(tvradio, searchterm=searchterm)
    list_feed_listings(feed, 'list')
    
        
def list_feed_listings(feed, listing, category=None, series=None, channels=None):
    handle = int(sys.argv[1])
    if channels or listing == 'popular' or listing == 'highlights': 
        #xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_TRACKNUM)
        xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_NONE)
    else:
        xbmcplugin.addSortMethod(handle=handle, sortMethod=xbmcplugin.SORT_METHOD_LABEL)
      
    d = {}
    d['list'] = feed.list
    d['popular'] = feed.popular
    d['highlights'] = feed.highlights
    programmes = d[listing]()

    ## filter by category
    if category:
        temp_prog = []
        # if a category filter has been specified then only parse programmes
        # in that category
        for p in programmes:
            for c in p.categories:
                if c == category: 
                    temp_prog.append(p)
                    continue
        programmes = temp_prog

    ## filter by series
    if series:
        temp_prog = []
        seriesmatch = re.compile('^(.*?):')
        # if a series filter has been specified then only parse programmes
        # in that series
        i = len(series)

        for p in programmes:
            matchagainst = p.title
            match = seriesmatch.match(p.title)
            if match: matchagainst = match.group(1)
            #print "matching %s,%s" % (p.title, matchagainst)
            if series == matchagainst: 
                temp_prog.append(p)
        programmes = temp_prog
        
    # add each programme
    total = len(programmes)
    if channels: total = total + len(channels)
    count =  0
    thumbnail_size = get_setting_thumbnail_size()
    for p in programmes:
        try:
            if not add_programme(p, total, count, thumbnail_size, feed.tvradio):
                total = total - 1
        except:
            traceback.print_exc()
            total = total - 1
        count = count + 1
        
    # normally from an empty search
    if not programmes:
        label = "(no programmes available - try again later)"
        listitem = xbmcgui.ListItem(label=label)
        ok = xbmcplugin.addDirectoryItem(
            url="",
            handle=handle, 
            listitem=listitem
        )
        count= count + 1


    # add list of channels names - for top level Highlights and Popular
    if channels:  
        for j, f in enumerate(channels):
            listitem = xbmcgui.ListItem(label=f.name)
            listitem.setIconImage('defaultFolder.png')
            listitem.setThumbnailImage(get_feed_thumbnail(f))
            listitem.setProperty('tracknumber', str(count))
            count = count + 1
            url = make_url(feed=f, listing=listing, tvradio=feed.tvradio)
            ok = xbmcplugin.addDirectoryItem(
                handle=handle,
                url=url,
                listitem=listitem,
                isFolder=True,
            )

    #if feed.is_tv:
    xbmcplugin.setContent(handle=handle, content='episodes')
    #elif feed.is_radio:
    #    xbmcplugin.setContent(handle=handle, content='songs')
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)


def get_item(pid): 
    #print "Getting %s" % (pid)
    p = iplayer.programme(pid)
    #print "%s is %s" % (pid, p.title)
      
    #for i in p.items:
    #    if i.kind in ['programme', 'radioProgrammme']:
    #        return i
    return p.programme

def download_subtitles(url):
    # Download and Convert the TTAF format to srt
    # SRT:
    #1
    #00:01:22,490 --> 00:01:26,494
    #Next round!
    #
    #2
    #00:01:33,710 --> 00:01:37,714
    #Now that we've moved to paradise, there's nothing to eat.
    #
    
    # TT:
    #<p begin="0:01:12.400" end="0:01:13.880">Thinking.</p>
    
    logging.info('subtitles at =%s' % url)
    outfile = os.path.join(SUBTITLES_DIR, 'iplayer.srt')
    fw = open(outfile, 'w')
    
    if not url:
        fw.write("1\n0:00:00,001 --> 0:01:00,001\nNo subtitles available\n\n")
        fw.close() 
        return
    
    txt = iplayer.httpget(url)
        
    p= re.compile('^\s*<p.*?begin=\"(.*?)\.([0-9]+)\"\s+.*?end=\"(.*?)\.([0-9]+)\"\s*>(.*?)</p>')
    i=0
    prev = None

    # some of the subtitles are a bit rubbish in particular for live tv
    # with lots of needless repeats. The follow code will collapse sequences
    # of repeated subtitles into a single subtitles that covers the total time
    # period. The downside of this is that it would mess up in the rare case
    # where a subtitle actually needs to be repeated 
    for line in txt.split('\n'):
        entry = None
        m = p.match(line)
        if m:
            start_mil = "%s000" % m.group(2) # pad out to ensure 3 digits
            end_mil   = "%s000" % m.group(4)
            
            ma = {'start'     : m.group(1), 
                  'start_mil' : start_mil[:3], 
                  'end'       : m.group(3), 
                  'end_mil'   : start_mil[:3], 
                  'text'      : m.group(5)}
    
            ma['text'] = ma['text'].replace('&amp;', '&')
            ma['text'] = ma['text'].replace('&gt;', '>')
            ma['text'] = ma['text'].replace('&lt;', '<')
            ma['text'] = ma['text'].replace('<br />', '\n')
            ma['text'] = ma['text'].replace('<br/>', '\n')
            ma['text'] = re.sub('<.*?>', '', ma['text'])
            ma['text'] = re.sub('&#[0-9]+;', '', ma['text'])
            #ma['text'] = ma['text'].replace('<.*?>', '')
    
            if not prev:
                # first match - do nothing wait till next line
                prev = ma
                continue
            
            if prev['text'] == ma['text']:
                # current line = previous line then start a sequence to be collapsed
                prev['end'] = ma['end']
                prev['end_mil'] = ma['end_mil']
            else:
                i += 1
                entry = "%d\n%s,%s --> %s,%s\n%s\n\n" % (i, prev['start'], prev['start_mil'], prev['end'], prev['end_mil'], prev['text'])
                prev = ma
        elif prev:
            i += 1
            entry = "%d\n%s,%s --> %s,%s\n%s\n\n" % (i, prev['start'], prev['start_mil'], prev['end'], prev['end_mil'], prev['text'])
            
        if entry: fw.write(entry)
    
    fw.close()    
    return outfile

def watch(pid):

    subtitles_file = None
    item = get_item(pid)
    logging.info('watching pid=%s' % pid)

    listitem = xbmcgui.ListItem(label=item.programme.title, label2=item.programme.summary)
    subtitles = get_setting_subtitles()

    if item.is_tv:
        # TV Stream
        pref = get_setting_videostream()
        media = item.get_media_for(pref)

        if not media and pref == 'h264 3200':
            # fallback to 'h264 1500' as 'h264 3200' is not always available
            logging.info('Steam %s not available, falling back to flash h264 1500 stream' % pref)
            pref = 'h264 1500'
            media = item.get_media_for(pref)
            
        if not media and pref == 'h264 1500':
            # fallback to 'h264 800' as 'h264 1500' is not always available
            logging.info('Steam %s not available, falling back to flash h264 800 stream' % pref)
            pref = 'h264 800'
            media = item.get_media_for(pref)
        
        if not media and pref == 'h264 800':
            # fallback to 'flash 512' as 'h264 800' is not always available
            logging.info('Steam %s not available, falling back to flash 512 stream' % pref)
            pref = 'flashmed'
            media = item.get_media_for(pref)
        
        if not media:
            d = xbmcgui.Dialog()
            d.ok('Stream Error', 'Can\'t locate tv stream for' + pref)            
            return False            
            
        url = media.url
        logging.info('watching url=%s' % url)

        if subtitles:
            subtitles_media = item.get_media_for('captions')
            if subtitles_media:
                subtitles_file = download_subtitles(subtitles_media.url)

        play=xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        
    else:
        # Radio stream
        pref = get_setting_audiostream()
        media = item.get_media_for(pref)
        if not media and pref == 'aac':
            # fallback to mp3 as aac is not always available
            logging.info('Steam %s not available, falling back to mp3 stream' % pref)
            pref = 'mp3'
            media = item.get_media_for(pref)
        if not media and pref == 'mp3':
            # fallback to real as mp3 is not always available
            logging.info('Steam %s not available, falling back to real stream' % pref)
            pref = 'real'
            media = item.get_media_for(pref)
        if not media:            
            d = xbmcgui.Dialog()
            d.ok('Stream Error', 'Error: can\'t locate radio stream')            
            return False
        if pref == 'real':
            # fetch the rtsp link from the .ram file
            url = iplayer.httpget(media.url)
        else :
            # else use the direct link
            url = media.url
            
        logging.info('Listening to url=%s' % url)
  
        play=xbmc.PlayList(xbmc.PLAYLIST_MUSIC)

    logging.info('Playing preference %s' % pref)
    listitem = xbmcgui.ListItem(label=item.programme.title)
    
    if media.connection_protocol == 'rtmp':
        if media.SWFPlayer:
            listitem.setProperty("SWFPlayer", media.SWFPlayer)
            print "SWFPlayer : " + media.SWFPlayer
        if media.PlayPath:
            listitem.setProperty("PlayPath", media.PlayPath)
            print "PlayPath  : " + media.PlayPath
        if media.PageURL:
            listitem.setProperty("PageURL", media.PageURL)
            print "PageURL  : " + media.PageURL
    
    del item
    del media
    
    play.clear()
    play.add(url,listitem)
    player = xbmc.Player(xbmc.PLAYER_CORE_AUTO)
    player.play(play)
    
    # Auto play subtitles if they have downloaded 
    print "subtitles: %s   - subtitles_file %s " % (subtitles,subtitles_file)
    if subtitles == 'autoplay' and subtitles_file: 
        player.setSubtitles(subtitles_file)


def watch_live(label='', url=None):
    
    if not url:
        return
    
    logging.info('watching live station=%s url=%s' % (label,url))

    txt = iplayer.httpget(url)
    
    # some of the the urls passed in are .asx. These are text files with multiple mss stream hrefs
    stream = re.compile('href\="(mms.*?)"', re.IGNORECASE)
    match  = stream.search(txt) 
    stream_url = None
    if match:
        stream_url = match.group(1)
    else:
        # pass it to xbmc and see if it is directly supported 
        stream_url = url
        
    listitem = xbmcgui.ListItem(label=label, label2='Live %s' % label)
    
    play=xbmc.PlayList(xbmc.PLAYLIST_MUSIC)

    play.clear()
    play.add(stream_url,listitem)
        
    environment = os.environ.get( "OS", "xbox" )
    if environment in ['Linux', 'xbox']:
        # mms decoding can be done by mplayer
        player = xbmc.Player(xbmc.PLAYER_CORE_MPLAYER)
    else: 
        # but mplayer isn't available on all platforms
        player = xbmc.Player(xbmc.PLAYER_CORE_AUTO)

    player.play(play)


    
if __name__ == "__main__":
    #print sys.argv
    
    #print "Settings:"
    #for s in ['video_stream', 'thumbnails', 'thumbnail_life', 'socket_timeout']:
    #    print "    %s: %s" % (s, xbmcplugin.getSetting(s))
   
    # setup and check script environment 
    cache = httplib2.FileCache(HTTP_CACHE_DIR, safe=lambda x: md5.new(x).hexdigest())
    iplayer.set_http_cache(cache)

    environment = os.environ.get( "OS", "xbox" )
    try:
        timeout = int(xbmcplugin.getSetting('socket_timeout'))
    except:
        timeout = 5
    if environment in ['Linux', 'xbox'] and timeout > 0:
        setdefaulttimeout(timeout)

    progcount = True
    if xbmcplugin.getSetting('progcount') == 'false':  progcount = False
  
    # get current state parameters
    (feed, listing, pid, tvradio, category, series, url, label) = read_url()
    print (feed, listing, pid, tvradio, category, series, url, label)
    #if feed:
    #    print feed.name
    #else:
    #    print "no feed"

    # state engine
    if pid:
        watch(pid)
    elif url:
        watch_live(label, url)
    elif not (feed or listing):
        if not tvradio:
            list_tvradio()
        elif tvradio == 'Settings':
            xbmcplugin.openSettings(sys.argv[ 0 ])  
        elif tvradio:
            feed = iplayer.feed(tvradio).channels_feed()
            list_feeds(feed, tvradio)
    elif listing == 'categories':
        channels = None
        if not feed: channels = iplayer.feed(tvradio or 'tv').channels_feed()
        list_categories(feed, channels, progcount=progcount)
    elif listing == 'search':
        search(tvradio)
    elif listing == 'atoz':
        list_atoz(feed)
    elif listing == 'livefeeds':
        channels = iplayer.feed(tvradio or 'tv').channels_feed()
        list_live_feeds(channels, tvradio)
    elif listing == 'list' and not series:
        feed = feed or iplayer.feed(tvradio or 'tv')
        list_series(feed, listing, category=category, progcount=progcount)
    elif listing:
        channels=None
        if not feed:
            feed = feed or iplayer.feed(tvradio or 'tv')
            channels=feed.channels_feed()
        list_feed_listings(feed, listing, category=category, series=series, channels=channels)
    

