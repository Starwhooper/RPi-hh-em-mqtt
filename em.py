#!/usr/bin/python3
# Creator: Thiemo Schuff
# Source: https://github.com/Starwhooper/RPi-hh-em-mqtt

#######################################################
#
# prepare
#
#######################################################

#Logging Levels https://rollbar.com/blog/logging-in-python/#
#    DEBUG - Detailed information, typically of interest when diagnosing problems.
#    INFO - Confirmation of things working as expected.
#    WARNING - Indication of something unexpected or a problem in the near future e.g. 'disk space low'.
#    ERROR - A more serious problem due to which the program was unable to perform a function.
#    CRITICAL - A serious error, indicating that the program itself may not be able to continue executing.

##### check if all required packages are aviable
import sys
try:
 from luma.core.render import canvas
 from PIL import ImageFont, Image, ImageDraw
 from urllib.parse import quote
 from datetime import datetime, timedelta  
 import RPi.GPIO as GPIO
 import json
 import logging
 import os
 import psutil
 import requests
 import re
 import time
 import paho.mqtt.client as paho
 from paho import mqtt 
 
 from functions import pomessage
 from functions import is_json
 from functions import colorbar
 
except:
 sys.exit("\033[91m {}\033[00m" .format('any needed package is not aviable. Please check README.md to check which components should be installed via pip3".'))

logging.getLogger("urllib3")
logging.basicConfig(
 filename='/var/log/hh-em.log', 
 level=logging.INFO, encoding='utf-8', 
# level=logging.WARNING, encoding='utf-8', 
 format='%(asctime)s:%(levelname)s:%(message)s'
)

#set const
globals()['scriptroot'] = os.path.dirname(__file__)

##### import config.json
try:
 with open(scriptroot + '/config.json','r') as file:
  cf = json.loads(file.read())
except:
 logging.critical('The configuration file ' + scriptroot + '/config.json does not exist or has incorrect content. Please rename the file config.json.example to config.json and change the content as required ')
 sys.exit("\033[91m {}\033[00m" .format('exit: The configuration file ' + scriptroot + '/config.json does not exist or has incorrect content. Please rename the file config.json.example to config.json and change the content as required '))

globals()['pages'] = cf['pages']#['detail','pretty','blank']
 
##### import module demo_opts
try:
 sys.path.append(cf['luma']['demo_opts.py']['folder'])
 from demo_opts import get_device
except:
 logging.critical('file ' + cf['luma']['demo_opts.py']['folder'] + '/demo_opts.py not found. Please check config.json or do sudo git clone https://github.com/rm-hull/luma.examples /opt/luma.examples')
 sys.exit("\033[91m {}\033[00m" .format('file ' + cf['luma']['demo_opts.py']['folder'] + '/demo_opts.py not found. Please check config.json or do sudo git clone https://github.com/rm-hull/luma.examples /opt/luma.examples'))

KEY_UP_PIN     = 19 #6 
KEY_DOWN_PIN   = 6 #19
KEY_LEFT_PIN   = 26 #5
KEY_RIGHT_PIN  = 5 #26
KEY_PRESS_PIN  = 13
KEY1_PIN       = 16 #21
KEY2_PIN       = 20
KEY3_PIN       = 21 #16

GPIO.setmode(GPIO.BCM) 
#GPIO.cleanup()
GPIO.setup(KEY_UP_PIN,      GPIO.IN, pull_up_down=GPIO.PUD_UP)    # Input with pull-up
GPIO.setup(KEY_DOWN_PIN,    GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Input with pull-up
GPIO.setup(KEY_LEFT_PIN,    GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Input with pull-up
GPIO.setup(KEY_RIGHT_PIN,   GPIO.IN, pull_up_down=GPIO.PUD_UP) # Input with pull-up
GPIO.setup(KEY_PRESS_PIN,   GPIO.IN, pull_up_down=GPIO.PUD_UP) # Input with pull-up
GPIO.setup(KEY1_PIN,        GPIO.IN, pull_up_down=GPIO.PUD_UP)      # Input with pull-up
GPIO.setup(KEY2_PIN,        GPIO.IN, pull_up_down=GPIO.PUD_UP)      # Input with pull-up
GPIO.setup(KEY3_PIN,        GPIO.IN, pull_up_down=GPIO.PUD_UP)      # Input with pull-up

electricitymeter_now = 0
electricitymeter_total_in = 0
electricitymeter_total_out = 0
plug = [0,0,0,0]


def inverterurl():
 url = 'http://' + cf['inverter']['user'] + ':' + quote(cf['inverter']['pw']) + '@' + cf['inverter']['address'] + '/' + cf['inverter']['site']
 logging.debug('provide url: ' + url)
 return(url)


def prepare():
 #####global vars with const value
 ## font
 if cf['font']['ttf'] == True:
  try:
   font = ImageFont.truetype(cf['font']['ttffile'], cf['font']['ttfsize'])
  except:
   font = ImageFont.load_default()
   logging.error('font ' + cf['font']['ttffile'] + ' could not used. Use instead default font')
 else:
  font = ImageFont.load_default()
 globals()['font'] = font

 
def imagepath(page = ''):
 import tempfile
 folder = tempfile.gettempdir()
 filename = 'RPi-hh-em-mqtt'
 fileext = '.gif'

 if page == '': path = str(folder) + '/' + str(filename) + str(fileext)
 else: path = str(folder) + '/' + str(filename) + '_' + str(page) + str(fileext)
 
 logging.debug('file exportpath: ' + str(path))
 return(path)

def on_mqtt_message(client, userdata, msg):
 if is_json(msg.payload) == True: payload = json.loads(str(msg.payload.decode("utf-8")))
 else: payload = msg.payload.decode("utf-8")
 
 logging.info('mqtt topic: ' + msg.topic)
 
 if msg.topic == cf['mqtt']['em']['subscribe']:
  global electricitymeter_total_in
  global electricitymeter_total_out
  global electricitymeter_now
  electricitymeter_total_in = payload['Power']['Total_in']
  electricitymeter_total_out = payload['Power']['Total_out']
  electricitymeter_now = payload['Power']['Power_curr']

 else:
  for i in cf['mqtt']['plug']:
   if msg.topic == cf['mqtt']['plug'][i]['subscribe']:
    global plug
    plug[int(i)] = payload['ENERGY']['Power']
    break
 
#######################################################
#
# read and calculate
#
#######################################################

#####read inverter
def readinverter():
 #inverterurl = str(inverterurl()) 
 total = -1
 now = 0
 inverterread = False
 global inverterofflinecount
 
 try: inverterofflinecount
 except: inverterofflinecount = 0
 
 try:
  for i in range(5):
   inverter = requests.get(inverterurl(), timeout=1)
   if inverter.status_code == 200: 
    inverterread = True
    break
   time.sleep(1)
 except:
  inverterofflinecount += 1
  if inverterofflinecount >= 100:
   logging.warning('could not open/read from inverter ' + inverterurl() + ' ' + str(inverterofflinecount) + ' times')
   inverterofflinecount = 0
 

 if inverterread == True:
  if inverterofflinecount >= 1: 
   logging.warning('could not open/read from inverter ' + inverterurl() + ' ' + str(inverterofflinecount) + ' times, but now its back')
   inverterofflinecount = 0
  try:
   total = float(re.search(r'var\s+webdata_total_e\s*=\s*"([^"]+)"', inverter.text).group(1))
   now = int(re.search(r'var\s+webdata_now_p\s*=\s*"([^"]+)"', inverter.text).group(1))
   logging.debug('could read values from inverter ' + inverterurl())
  except:
   logging.warning('could not find searched values from inverter frontend' + inverterurl())

 return(total,now)
    
##### calculate values
def calculate():

#calculate plugs
 global lastcalculate
 try: lastcalculate
 except: lastcalculate = datetime(1970, 1, 1)

 if lastcalculate >= (datetime.now() - timedelta(seconds=cf['calculationrefresh'])):
  logging.debug('skip calculation')
  return
 logging.debug('start calculation')
 
 if lastcalculate == datetime(1970,1,1):
  if cf['pushover']['messages'] == True: pomessage(msg='in reason of none previous calculation, the system seams to be restarted', prio=1, attachment='', apikey=cf["pushover"]["apikey"], userkey = cf["pushover"]["userkey"], logging = logging)
  else: logger.warning('send message is not enabled in config.json')

 global lastnegativepowerusagemessage
 try: lastnegativepowerusagemessage
 except: lastnegativepowerusagemessage = datetime(1970, 1, 1)
 
#calculate inverter  
 global inverter_now
 try: inverter_now
 except: inverter_now = 0
 
 global inverter_time
 try: inverter_time
 except: 
  inverter_time = datetime(1970, 1, 1)
  logging.debug('set last inverter read time to 1. Jan 1970')
 
 global inverter_total
 global inverter_adj
 
 if (inverter_time <= datetime.now() - timedelta(minutes=1)) or inverter_now == 0:
  inv_t, inverter_now = readinverter()
  
  if inv_t >= 1: 
   inverter_total = inv_t
   inverter_time = datetime.now()
  else:
   inverter_total = 0
  
  inverter_adj = inverter_total + cf['inverter']['offset']  

 global electricitymeter_now
 if electricitymeter_now < -50 and (lastnegativepowerusagemessage <= datetime.now() - timedelta(minutes=15)):
  saveimage(exportpathfile = imagepath(page = 'detail'), force = True)  
  if cf['pushover']['messages'] == True: pomessage(msg='electricitymeter now: ' + str(electricitymeter_now), attachment=imagepath(page = 'detail'), apikey=cf["pushover"]["apikey"], userkey = cf["pushover"]["userkey"], logging = logging)
  else: logger.warning('send message is not enabled in config.json')
  lastnegativepowerusagemessage = datetime.now()

 try:
  global electricitymeter_agg_per_day
  electricitymeter_agg_per_day = round(electricitymeter_total_in / (( datetime.utcnow().timestamp() - cf['electricitymeter']['since']) / 60 / 60 / 24),1)
 except:
  logging.warning('could not calculate electricitymeter_agg_per_day')

 try:
  global powersource
  if electricitymeter_now <= 0: powersource = 'sun'
  else: powersource = 'net'
 except:
  logging.warning('could not define powersource')


#calculate others 
 global consumption
 consumption = electricitymeter_now + inverter_now
 global selfusedsunenergy
 try: selfusedsunenergy = inverter_adj - electricitymeter_total_out
 except: 
  selfusedsunenergy = 0
  logging.warning('could not calculate selfusedsunenergy')

 
 #########compare current consumption and current provided over inverter to know how much of current consumption cames from sun
 global rateconsumptionfromsun
 try:
  rateconsumptionfromsun = int(100 / consumption * inverter_now)
 except:
  rateconsumptionfromsun = 0
  logging.warning('could not calculate rateconsumptionfromsun')

 
 #########compare current provided over inverter and current consumption to know how much of current solar power are used from my household
 global ratesolarpowerforhousehold
 try:
  ratesolarpowerforhousehold = int(100 / inverter_now * consumption)
  if ratesolarpowerforhousehold > 100: ratesolarpowerforhousehold = 100
 except:
  ratesolarpowerforhousehold = 0
  logging.warning('could not calculate ratesolarpowerforhousehold')


 #########compare complete provided from interver exclude the adjustemt with the complete provided over electricitymeter out to net to know how much of collected sun energy i use myself
 global rateinverteradjvselectricimetertotalout
 try:
  rateinverteradjvselectricimetertotalout = int(100 / inverter_adj * (selfusedsunenergy))
 except:
  rateinverteradjvselectricimetertotalout = 0
  logging.warning('could not calculate rateinverteradjvselectricimetertotalout')
 lastcalculate = datetime.now()

#######################################################
#
# create output image
#
#######################################################


def pagetoshow(operation = ""):
 #pages = ['detail','pretty'] #,'blank']
 global pagecounter
 try: pagecounter
 except: pagecounter = 0
 
 global lastpagechange
 try: lastpagechange
 except: lastpagechange = datetime.now()
 
 if lastpagechange < (datetime.now() - timedelta(seconds=1)) or lastpagechange > datetime.now():
  if operation == "next":
   lastpagechange = datetime.now()
   pagecounter += 1
   logging.debug(str(lastpagechange) + 'next')
  elif operation == "previous":
   lastpagechange = datetime.now()
   pagecounter -= 1
   logging.debug(str(lastpagechange) + 'prev')
  elif operation == "stay30":
   lastpagechange = datetime.now() + timedelta(seconds=30)
   print(str(lastpagechange) + 'stay30')
  elif lastpagechange < (datetime.now() - timedelta(seconds=cf['pagerotation'])):
   lastpagechange = datetime.now()
   pagecounter += 1
   logging.debug(str(lastpagechange) + 'rotate')
 else:
  logging.debug(str(lastpagechange) + 'ignored')
 
 pageid = pagecounter % len(pages)
 return(pages[pageid])
  
def createimage(imagewidth,imageheight):
 global outputimage
 global sunbeam
 try: sunbeam
 except: sunbeam = 0
 global sunkwh
 try: sunkwh
 except: sunkwh = 'tot'
 global imagestyle
 
 global plug
 
 if GPIO.input(KEY_PRESS_PIN) == 0: # button is released
  imagestyle = pagetoshow('next')
  logging.info('changes imagestyle to next')
 elif GPIO.input(KEY_RIGHT_PIN) == 0: # button is released
  imagestyle = pagetoshow('next')
  logging.info('changes imagestyle to next')
 elif GPIO.input(KEY_LEFT_PIN) == 0: # button is released
  imagestyle = pagetoshow('previous')
  logging.info('changes imagestyle to previous')
 elif GPIO.input(KEY_DOWN_PIN) == 0: # button is released
  imagestyle = pagetoshow('stay30')
  logging.info('stay 30 sec. on current imagestyle')
 else:
  imagestyle = pagetoshow()
 
 if imagestyle == 'pretty':
  outputimage = Image.open(scriptroot + '/wp_pretty.gif').convert("RGB")
 else:
  outputimage = Image.new(mode="RGB", size=(imagewidth,imageheight))
 
 draw = ImageDraw.Draw(outputimage)
 y=0
  
 if imagestyle == 'detail':
  detailfont = ImageFont.truetype(cf['font']['ttffile'], 10)#cf['font']['ttfsize'])
  draw.text((0,y),  'consumtion:     ' + str(consumption) + 'W', font = detailfont, fill = 'white')
  y += 10
  draw.text((0,y), 'net now:        ' + str(electricitymeter_now) + 'W', font = detailfont, fill = 'white')
  y += 10
  draw.text((0,y), 'net total in:   ' + str(round(electricitymeter_total_in)) + 'kWh', font = detailfont, fill = 'white')
  y += 10
  draw.text((0,y), 'net total out:  ' + str(round(electricitymeter_total_out)) + 'kWh', font = detailfont, fill = 'white')
  y += 10
  draw.text((0,y), 'net avg per day:' + str(round(electricitymeter_agg_per_day)) + 'kWh', font = detailfont, fill = 'white')
  y += 10
  draw.text((0,y), 'inverter now:   ' + str(inverter_now) + 'W', font = detailfont, fill = 'white')
  y += 10
#  draw.text((0,y), 'inverter total: ' + str(round(inverter_total)) + 'kWh', font = detailfont, fill = 'white')
#  y += 10
  if inverter_adj >= 0:
   draw.text((0,y), 'inverter adj:   ' + str(round(inverter_adj)) + 'kWh', font = detailfont, fill = 'white')
  else:
   draw.text((0,y), 'inverter adj:   0kWh', font = detailfont, fill = 'gray')  
  y += 10
  #########compare current consumption and current provided over inverter to know how much of current consumption cames from sun
  draw.text((0,y), 'cur.req.prov. by sun (' + str(rateconsumptionfromsun) + ')', font = detailfont, fill = 'white')
  y += 12
  try: 
   if rateconsumptionfromsun > 0:
    draw.rectangle(((0,y,int(imagewidth / 100 * rateconsumptionfromsun),y+4)), fill = colorbar(rateconsumptionfromsun), width = 1)
  except: pass
  y += 3
  #########compare current provided over inverter and current consumption to know how much of current solar power are used from my household
  draw.text((0,y), 'cur.use of PV energy (' + str(ratesolarpowerforhousehold) + ')', font = detailfont, fill = 'white')  
  y += 12
  try:
   if ratesolarpowerforhousehold > 0:
    draw.rectangle((0,y,int(imagewidth / 100 * ratesolarpowerforhousehold),y+4), fill = colorbar(ratesolarpowerforhousehold), width = 1)
  except: pass
  y += 3
  #########compare complete provided from interver exclude the adjustemt with the complete provided over electricitymeter out to net to know how much of collected sun energy i use myself
  if (inverter_adj >= 0):
   draw.text((0,y), str(round(inverter_adj - electricitymeter_total_out)) + 'kWh in / ' + str(round(electricitymeter_total_out)) + 'kWh out (' + str(rateinverteradjvselectricimetertotalout) + ')', font = detailfont, fill = 'white')
   y += 12
   draw.rectangle((0,y,int(imagewidth / 100 * rateinverteradjvselectricimetertotalout),y+4), fill = colorbar(rateinverteradjvselectricimetertotalout), width = 1)
  else:
   draw.text((0,y), '...kWh in / ' + str(round(electricitymeter_total_out)) + 'kWh out', font = detailfont, fill = 'gray')
   y += 12
  
 if imagestyle == 'pretty':

  #######house
  draw.text((45,65), str(consumption) + 'W', font = font, fill = 'Yellow')
  draw.text((45,75), str(round(electricitymeter_total_in)) + 'kWh', font = font, fill = 'Yellow')
  #######sun
  if inverter_now >= 1:
   draw.ellipse([(-40-sunbeam,-40-sunbeam),(40+sunbeam,40+sunbeam)], outline = "yellow")
   draw.text((1,11), str(inverter_now) + 'W', font = font, fill = 'black')
   sunbeam=sunbeam+4
   if sunbeam >= 4*4: sunbeam = 0
  else: 
   draw.text((1,2), 'sun\noffl.', font = font, fill = 'black')
  #######powerline
  draw.text((imagewidth-30,50), str(electricitymeter_now) + 'W', font = font, fill = 'white')
  #######note
  draw.text((25,95), 'powered by ' + powersource, font = font, fill = 'Yellow')

  for i in cf['mqtt']['plug']:
   j = (int(i) - 1) * (120/len(cf['mqtt']['plug']))
   draw.text((j,105),  i + '=' + str(plug[int(i)]) + 'W', font = font, fill = 'Yellow')
    
 if imagestyle == 'blank':
  draw.text((45,65), ':-)', font = font, fill = 'darkgray')

#######################################################
#
# output
#
#######################################################

def output(device):
 try:
  device.display(outputimage)
  logging.debug('show on display')
 except:
  loggin.error('show image on display not possible')

#def saveimage():
# exportpathfile = imagepath(page = imagestyle)

def saveimage(exportpathfile = imagepath(page = 'pretty'), force=False):
 
 try:
  lastimageexport = os.path.getmtime(exportpathfile)
  logging.debug('previous image ' + exportpathfile + ' from ' + str(lastimageexport))
 except:
  lastimageexport = datetime(1970, 1, 1).timestamp()
  logging.debug('no previous image ' + exportpathfile + ' found')
 
 if lastimageexport <= datetime.now().timestamp() - cf['imageexport']['intervall'] or force == True:
  logging.info('create new image, in reason of age or force')
  if cf['imageexport']['active'] == True:
   try:
    outputimage.save(exportpathfile)
    logging.info('saved current displaycontent to: ' + exportpathfile)
    lastimageexport = datetime.now()
   except:
    logging.warning('image could not saved to ' + exportpathfile)
  else:
   logging.info('image export is not enabled')
 else:
  logging.info('current image is from now')
  

def on_disconnect(client, userdata, rc):
    logging.info("Disconnected with result code: %s", rc)
    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        logging.info("Reconnecting in %d seconds...", reconnect_delay)
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            logging.info("Reconnected successfully!")
            return
        except Exception as err:
            logging.error("%s. Reconnect failed. Retrying...", err)

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    logging.info("Reconnect failed after %s attempts. Exiting...", reconnect_count)


#######################################################
#
# start
#
#######################################################
 
def main():
 logging.debug('start main')
 prepare()
 device = get_device()

 try:
  client = paho.Client(client_id='', userdata=None, protocol=paho.MQTTv5)

  client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
  client.username_pw_set(cf['mqtt']['broker']['user'], cf['mqtt']['broker']['pw'])
  logging.debug('configure mqtt source')
 except:
  logging.critical('could not configure mqtt source')
  
 online = False
 while online == False:
  try:
   client.connect(cf['mqtt']['broker']['url'], cf['mqtt']['broker']['port']) #mqtt broker
   logging.debug('connect mqtt broker ')
   online = True
  except:
   logging.critical('could not connect mqtt broker ')
   time.sleep(1)
   
  
 try: 
  client.subscribe(cf['mqtt']['em']['subscribe']) #electricitymeter
  for i in cf['mqtt']['plug']:
   client.subscribe(cf['mqtt']['plug'][i]['subscribe']) #plug
  client.on_message = on_mqtt_message
 except:
  logging.critical('could not start to subscribe from mqtt')

 client.on_disconnect = on_disconnect
 
 client.loop_start()
 
 while True:
#  try:
  calculate()
 # except:
 #  logging.warning('issue with calculate')
  try:
   createimage(device.width,device.height)
  except:
   logging.critical('issue with createimage')
  try:
   output(device)
  except:
   logging.critical('issue with output')
  try:
   saveimage()
  except:
   logging.critical('issue with saveimage')

  time.sleep(cf['displayrefresh'])
 client.loop_stop()

if __name__ == '__main__':
 try:
  logging.debug('pass name')
  main()
 except KeyboardInterrupt:
  logging.info('interrupt via ctrl+c')
