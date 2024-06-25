#!/usr/bin/python3

def colorbar(rate):
 if rate > 80: color = 'green'
 elif rate > 70: color = 'yellowgreen'
 elif rate > 60: color = 'yellow'
 elif rate > 40: color = 'orange'
 else: color = 'red'
 return(color)


def is_json(myjson):
 import json
 try:
   json.loads(myjson)
 except ValueError as e:
   return False
 return True


def pomessage(msg = '', prio = 0, attachment = '', apikey = '', userkey = '', logging = ''):
# import sys
 import logging
 import os
 import requests
 import time


 logging.debug('will send message')
 if msg == '':
  logging.warning('no message text found, set ...')
  msg = '...'
 
 if attachment == '':
  logging.info('will send po message without attachment')
  r = requests.post(
   "https://api.pushover.net/1/messages.json", data = {
    "token": apikey,
    "user": userkey,
    "html": 1,
    "priority": prio,
    "message": "Status of hh-em:" + msg ,
    "title": "hh-em",
   }
  )
 else:
  if os.path.isfile(attachment) == True:
   logging.info('Attachment ' + attachment + ' requested and found')
   time.sleep(1)
   logging.debug('will send po message with attachment')
   r = requests.post(
    "https://api.pushover.net/1/messages.json", data = {
     "token": apikey,
     "user": userkey,
     "html": 1,
     "priority": prio,
     "message": "Status of hh-em:" + msg ,
     "title": "hh-em",
    }
    ,
    files = {
     "attachment": ("status.gif", open(str(attachment), "rb"), "image/gif")
    }
   )
  else:
   logging.warning('Attachment ' + attachment + ' requested but not found')
   logging.debug('will send po message without attachment')
   r = requests.post(
    "https://api.pushover.net/1/messages.json", data = {
     "token": apikey,
     "user": userkey,
     "html": 1,
     "priority": prio,
     "message": "Status of hh-em:" + msg ,
     "title": "hh-em",
    }
   )


if __name__ == '__main__':
 pass
