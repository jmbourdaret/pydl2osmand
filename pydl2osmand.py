#!/usr/bin/env python3

import mercantile as m
import subprocess
import sqlite3
import urllib.request as req
from urllib.error import URLError, HTTPError
import argparse
import time
from progress.bar import Bar  # Not in Python default
# import a new API to create a thread pool
from concurrent.futures import ThreadPoolExecutor as PoolExecutor

TILESIZE = 0.030 # Mb
UA = "Mozilla/42.0 (Windows NT 10.0; Win64; x64) AppleWebKit/666.42 (KHTML, like Gecko) Chrome/82.0.8282.172 Safari/4222.42"
BATCHSIZE = 1000

parser = argparse.ArgumentParser(description='populate an OSMAnd sqliteDB mapfile.  Make sure your sqlitedb file is following the OsmAnd format convention, with info and url, and tiles.')
parser.add_argument('--dbfile' , required=True, help='sqlite map file')
parser.add_argument('--geoJson', required=True, help='geoJson file containing a polygon')
parser.add_argument('--maxz'   , required=True, type=int,  help='max zoom to download (from 1 to this zoom)')
parser.add_argument('--threads', required=False, type=int, help='nb of threads in parrallel, default 4', default=4)

args = parser.parse_args()
sqliteDB = args.dbfile
geolimit = args.geoJson
maxzoom  = args.maxz
minzoom  = 1
threads  = args.threads
urlTemplate = ""
timeColumn = False

def initStuff():
    global urlTemplate, timeColumn, minzoom
    conn     = sqlite3.connect(sqliteDB)
    urlTemplate = str(conn.execute('SELECT url FROM info').fetchone()[0])

    timed = str(conn.execute('SELECT timecolumn FROM info').fetchone()[0]).lower()
    if ( timed == "yes" ):
        timeColumn = True        

    minzoom = int( str(conn.execute('SELECT minzoom FROM info').fetchone()[0]) )

    conn.close()

    print("sqlite DB           : %s" % sqliteDB)
    print("time column         : %s" % timeColumn)
    print("geoJson boundaries  : %s" % geolimit)
    print("from zoom %d to zoom : %d" % (minzoom,maxzoom) )
    print("URL Template        : %s" % urlTemplate)
    print("Parrallel threads   : %d" % threads)


def displayEstimate( geolimit:str, maxzoom:int ) :
    global TILESIZE
    zoomEstimate = maxzoom-2
    if zoomEstimate < 5 :
        print("MaxZoom is really small. No estimation given. Should be small and quick.")
        return

    print("Estimation...", end="", flush=True)
    #rawOutput = subprocess.check_output(["mercantile","tiles",str(zoomEstimate),geolimit], text=True)
    rawOutput = subprocess.check_output(["more",geolimit,"|","supermercado","burn",str(zoomEstimate)], text=True, shell=True)
    rawTiles=rawOutput.splitlines()
    nbzEstimate = len(rawTiles) # zoom zoomEstimate
    totalT = nbzEstimate
    lastnbz = nbzEstimate
    for nbz in range(zoomEstimate+1, maxzoom+1):
        lastnbz = 4 * lastnbz
        totalT += lastnbz
    totalT += nbzEstimate/4 # bof

    print("%d tiles Max, %f MB (%f MB per tile)" % (totalT, totalT*TILESIZE, TILESIZE), flush=True )

def getTileNet(coords:list) -> list:
    x, y, z = coords[0], coords[1], coords[2]
    global urlTemplate, sqliteDB
    conn     = sqlite3.connect('file:'+sqliteDB+'?mode=ro', uri=True, isolation_level=None) # RO
    # Si deja, skip
    already = conn.execute("SELECT EXISTS( SELECT 1 FROM tiles WHERE x=? AND y=? AND z=? ) ",[x,y,z])
    if( already.fetchone()[0] == 1 ):
        conn.close()
        return None
    conn.close()
    
    urlTile = urlTemplate.replace("{0}",str(z)).replace("{1}",str(x)).replace("{2}",str(y))
    customReq = req.Request(urlTile)
    customReq.add_header('User-Agent', UA)
    try:
        resp = req.urlopen( customReq )
    except HTTPError as httpE:
        print("Erreur HTTP: %d (%s) on URL %s" % (httpE.code, httpE.reason, urlTile))
        raise SystemExit
    except URLError as urlE:
        print("Errrrr:",urlE)
        raise SystemExit
    else:
        image = resp.read()
        resp.close()

    timestamp = int(time.time())
    tileRow = [x,y,z, image, timestamp]
    return tileRow

def chunks(bigList:list, chunkSize:int):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(bigList), chunkSize):
        yield bigList[i : i+chunkSize]

def saveTiles(tileList:list):
    global timeColumn
    if len(tileList) == 0:
        return

    conn     = sqlite3.connect(sqliteDB, isolation_level=None)

    if ( timeColumn == True ):
        conn.executemany("REPLACE INTO tiles(x,y,z,image,time) VALUES(?,?,?,?,?)", tileList)
    else :
        for j in tileList: 
            del j[4] #time col
        conn.executemany("REPLACE INTO tiles(x,y,z,image) VALUES(?,?,?,?)", tileList)
    conn.close()

def getTileList( geolimit:str, zoom:int ) -> list:
    global TILESIZE
    print("Collecting for zoom %d ..." % zoom, end="", flush=True)
    #rawOutput = subprocess.check_output(["mercantile","tiles",str(zoom),geolimit], text=True)
    rawOutput = subprocess.check_output(["more",geolimit,"|","supermercado","burn",str(zoom)], text=True, shell=True)
    rawTiles=rawOutput.splitlines()
    nbTiles = len(rawTiles)

    tiles = []
    for rawTile in rawTiles :
        tile = eval(rawTile) # "x y z" => [x][y][z]
        #bug supermercado, 2^zoom cant be a tile, z=2 x=4 or z=4 x=16 is not possible
        boundary = 2**tile[2]
        if  tile[0] >= boundary or tile[1] >= boundary :
            continue
        else:
            tiles.append(tile)

    print(" %d tiles (%f MB) | %s" % (nbTiles, nbTiles*TILESIZE, time.asctime()), flush=True)
    return tiles

def getTiles( tiles:list ) :
    nbTiles = len(tiles)

    with Bar(message='Processing', max=nbTiles, suffix = "%(index)d/%(max)d %(elapsed_td)s" ) as bar:

        nbNewTiles = 0
        for subTiles in chunks(tiles, BATCHSIZE):
            tilesToAdd=[]
            sizeDl=0
            # create a thread pool of 4 threads
            with PoolExecutor(max_workers=threads) as executor:
                # distribute the 1000 URLs among 4 threads in the pool
                for newTile in executor.map(getTileNet, subTiles, chunksize=5):
                    if newTile :
                        tilesToAdd.append(newTile)
                        sizeDl += len(newTile[3])
                    bar.next()
                    
            # fin des threads, save
            saveTiles(tilesToAdd)
            nbNewTiles += len(tilesToAdd)

        print("   New Tiles: %d (%f MB)" % (nbNewTiles, sizeDl/(1024*1024)) )

############ MAIN
        
# check infos
initStuff()

# check total size :
displayEstimate(geolimit, maxzoom)

for zoom in range(minzoom, maxzoom+1):
    tileList = getTileList( geolimit, zoom )
    getTiles(tileList)
