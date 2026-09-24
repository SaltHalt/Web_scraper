import argparse
#TODO: Use GUI software
#TODO: remove twitch ttvlol thing
import asyncio
import aiohttp
import requests
from time import localtime, time, strftime
import re
from bs4 import BeautifulSoup
import json
from datetime import datetime, UTC

from tabulate import tabulate, SEPARATING_LINE
from colorama import init, Fore, Style

from os import system
from random import randint
from subprocess import Popen, DEVNULL
from threading import Thread, Event

class Scraper:
    def __init__(self):
        self._session = aiohttp.ClientSession()
        self._HEADERS = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' 
            '(KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        }
    
    async def close(self):
        await self._session.close()

    async def scrapeStreamer(self, streamer):
        url = f"https://www.twitch.tv/{streamer}"
        if DEBUG: print(f"SENT: {streamer:<20}\t{endpoint:<13}\t{time() - START_TIME:.3f}")
        self._session.get(url)
        async with self._session.get(url) as response:
            if response.status == 200:
                if DEBUG: print(f"RECV: {streamer:<22}\t{endpoint:<13}\t{time() - START_TIME:.3f}")
                return BeautifulSoup(await response.text(), 'html.parser')
            else:
                if DEBUG: print(f"RECV: {streamer:<22}\t{endpoint:<13}\t{time() - START_TIME:.3f}")
                print(f"Failed to fetch: {url}, trying again")
                return await self.scrapeStreamer(streamer)
    
    async def queryDecapi(self, endpoint, streamer):
        url = f"https://decapi.me/twitch/{endpoint}/{streamer}"
        if DEBUG: print(f"SENT: {streamer:<20}\t{endpoint:<13}\t{time() - START_TIME:.3f}")
        async with self._session.get(url) as response:
            text = await response.text()
            if DEBUG: print(f"RECV: {streamer:<22}\t{endpoint:<13}\t{time() - START_TIME:.3f}")
            return text
    
    def isOffline(self, website):
        return website.find("script", type='application/ld+json') is None

    def formatTime(self, time_str):
        start_time = datetime.fromisoformat(time_str) 
        now = datetime.now(UTC)
        diff = now - start_time
        total_seconds = diff.seconds
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:0>2} {minutes:0>2} {seconds:0>2}"

    async def getStream(self, streamer):
        website = await self.scrapeStreamer(streamer)
        if self.isOffline(website):
            return OFFLINE
        else:
            script = website.find("script", type='application/ld+json').text
            parsed_json = json.loads(script)
            js_dict2 = parsed_json['@graph']
            js_dict = js_dict2[0]
            time_str =  js_dict['publication']['startDate']
            uptime = self.formatTime(time_str)
            title = sanitiseTitle(js_dict['description'])
            [game, ccv] = await asyncio.gather(self.queryDecapi('game', streamer), self.queryDecapi('viewercount', streamer)) 
            return (streamer, ccv, uptime, game, title)

    async def getStreamGroupData(self, streamer_group):
        isOnline = lambda stream : stream != OFFLINE
        return list(filter(isOnline, await asyncio.gather(*map(self.getStream, streamer_group))))
        
parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true')
DEBUG = parser.parse_args().debug

STREAMERS = [
    [
    ],
    [
     
    ],
    [
     ],
    [
    ]
]
YOUTUBERS = {
    # user-facing name : channel id
}
QUALITY = {'l':'audio_only', 'm':'480p', 'h':'best'}
QUALITY_YOUTUBE = {'l':'worst', 'm':'480p', 'h':'720p'}


init()
COLORS = [Fore.YELLOW, Fore.GREEN, Fore.CYAN, Fore.MAGENTA]
OFFLINE = None
scraper = None

def sanitiseTitle(title):
    title = re.sub(r" !\w+", '', title) #matches commands
    title = re.sub(r"[^\x00-\x7F]", '', title) #matches unrenderable characters
    title = re.sub(r"(.)\1{3,}", r"\g<1>\g<1>\g<1>", title) #matches quadplicated chars and replaces them with triplets
    return title

def formatUptime(uptime):
    uptime_regex = re.compile(r"""
        (?:
            (?P<days>\d+)    #Capture days num
            \ days?,\ 
        )?                  #Might not have days
        (?:
            (?P<hrs>\d+)    #Capture hours num
            \ hours?,\ 
        )?                  #Might not have hours
        (?:
            (?P<mins>\d+)   #Capture minutes num
            \ minutes?,\ 
        )?                  #Might not have minutes
        (?:
            (?P<secs>\d+)   #Capture seconds num
            \ seconds?
        )?                  #Might not have seconds
    """, re.VERBOSE)
    uptime_dict = uptime_regex.match(uptime).groupdict()
    hrs = 24*int(uptime_dict['days'] or 0) + int(uptime_dict['hrs'] or 0)
    return f"{hrs:0>2} {uptime_dict['mins'] or '0':0>2} {uptime_dict['secs'] or '0':0>2}"
    
def isStreamer(streamer):
    url = f"https://decapi.me/twitch/id/{streamer}"
    text = requests.get(url, timeout=30).text
    return not("User not found:" in text or "429" in text)

async def getStreamsData(streamer_groups):
    scraper = Scraper()
    streamsData = list(await asyncio.gather(*map(scraper.getStreamGroupData, streamer_groups)))
    await scraper.close()
    return streamsData

def generateTable(streamsData, colors):
    tableData = []
    for (section, color) in zip(streamsData, colors):
        addColorToField = lambda text : color + Style.BRIGHT + text + Style.NORMAL + Fore.RESET
        addColorsToRow = lambda row : tuple(map(addColorToField, row))
        tableData += list(map(addColorsToRow, section))
        tableData.append(SEPARATING_LINE)
    tableData = tableData[:-1] #remove last Separating_line
    fields = ['', "Streamer", "CCV", "Uptime", "Game", "Title"]
    if tableData == [SEPARATING_LINE]*3:
        tableData = ["n/a"]
    return tabulate(tableData, headers=fields, showindex=True, maxcolwidths=[None, 20, None, None, 18, 57], missingval="N/A")

def getStreamerList(streamsData):
    getStreamer = lambda row : row[0]
    return [getStreamer(row) for section in streamsData for row in section]

def getTime():
    return strftime("%H:%M:%S", localtime(time()))

def run(command, stream_id):
    def helper(error):
        openStreams.append(stream_id)
        # if system(twitch_command):
        if Popen(command, stdout=DEVNULL).wait():
            error.set()
        openStreams.remove(stream_id)
    isOffline = Event()
    thread = Thread(target=(helper), args=(isOffline,))
    thread.start()
    thread.join(timeout=5)
    return isOffline.is_set()

if DEBUG: 
    global START_TIME
    START_TIME = time()
last_updated = getTime()
streamsData = asyncio.run(getStreamsData(STREAMERS))
table = generateTable(streamsData, COLORS)
live = getStreamerList(streamsData)
openStreams = []
system('MODE con: cols=121 lines=35')
while True:
    message = ''
    print(f"Last updated: {last_updated}")
    print(f"Open streams: {', '.join(openStreams)}")
    print()
    print(table)
    print()
    input_regex = re.compile(r"(\d+|\w*)(\w)?")

    prompt = "Enter streamer and quality (l,m,h) [or enter 'refresh' to refresh]: "
    inp = input(prompt)
    match = input_regex.match(inp)
    streamer_i = match[1] or ''
    quality_key = match[2] or 'l'
    if (streamer_i=='refresh'):
        if DEBUG: START_TIME = time()
        last_updated = getTime()
        streamsData = asyncio.run(getStreamsData(STREAMERS))
        table = generateTable(streamsData, COLORS)
        live = getStreamerList(streamsData)
        message = 'Table refreshed.'
        system('cls')
        system('MODE con: cols=121 lines=35')
        print(message)
    else:
        if(streamer_i.isdigit() and 0 <= (i:=int(streamer_i)) < len(live) and quality_key in QUALITY):
            chosen = live[i]
            quality = QUALITY[quality_key]
        elif(isStreamer(streamer_i[:-1]) and streamer_i[-1] in QUALITY):
            chosen = streamer_i[:-1]
            quality_key = streamer_i[-1]
            quality = QUALITY[quality_key]
        else:
            message = f"ERROR: input \"{inp}\" invalid."
            system('cls')
            system('MODE con: cols=121 lines=35')
            print(message)
            continue
        
        print(f"Loading: {chosen} ({quality})")
        forceWindow = "--force-window "if quality_key == 'l' else ""
        if chosen in YOUTUBERS:
            youtube_command = f'streamlink -p=mpv -a=\"{forceWindow}--profile=twitch\" https://www.youtube.com/embed/live_stream?channel={YOUTUBERS[chosen]} {QUALITY_YOUTUBE[quality_key]}'
            print(f"Attempting to get youtube stream:\n {youtube_command}")
            stream_id = f"{chosen}_{QUALITY_YOUTUBE[quality_key]}_(youtube.com)"
            if(not run(youtube_command, stream_id)):
                system('cls')
                system('MODE con: cols=121 lines=35')
                continue
            print("Couldn't get youtube stream. Reverting to twitch stream.")
        twitch_command = f"streamlink -p=mpv -a=\"{forceWindow}--profile=twitch\" https://www.twitch.tv/{chosen} {quality}"
        stream_id = f"{chosen}_{QUALITY_YOUTUBE[quality_key]}"
        if(run(twitch_command, stream_id)): 
            message = f'ERROR: {chosen} was offline.'
        system('cls')
        system('MODE con: cols=121 lines=35')
        print(message)
