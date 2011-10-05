#!/usr/bin/env python

"""
StormSiren

StormSiren is a utility for scanning severe weather bulletins issued 
by the National Weather Service and sending notification via pager,
wireless phone or e-mail when there is an outbreak or potential for
severe weather.

This software was originally released Copyright (c) 2002
Rory McManus <slorf@users.sourceforge.org>. It was later re-written by cfreeze and published to http://www.cfreeze.com/trac/stormsiren/ where you can currently find his re-write and documentation. Copyright (c) 2011 Brandon Pierce <brandon.pierce@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

# Revision and author information
__authors__    = "Rory McManus <slorf@users.sourceforge.net>, cfreeze (http://www.cfreeze.com), Brandon Pierce <brandon.pierce@gmail.com>"
__copyright__  = "Copyright 2011, Brandon Pierce"
__credits__	   = "Ed Blackman"
__license__    = "GPL"
__version__    = "1.0"
__maintainer__ = "Brandon Pierce"
__email__      = "brandon.pierce@gmail.com"
__status__     = "development"

# Import local modules
import sys
import os
import re
import string
import time
import urllib
import smtplib

# Build some time stamps
now = time.strftime("%Y-%m-%d.%H:%M:%S",time.localtime(time.time()))
year = time.strftime("%Y", time.localtime(time.time()))
  
# Define a class for alert data
class wxalert:
  def __init__(self):
    self.bulletin   = []
    self.sms        = ''
    self.warning    = ''
    self.cities     = ''
    self.counties   = ''
    self.type       = ''
    self.time       = ''
    self.id         = ''
    self.exp        = ''
    self.prestring  = ''
    self.valid      = 0
    
  def validate(self):
    if self.counties:
      self.valid = 1

      if self.warning:
        pre_chunks   = string.split(self.prestring)
        pre_len      = len(pre_chunks)
        self.id      = year + '_' + pre_chunks[pre_len - 1]
        self.sms     = self.id +  ' ' + self.warning + ' WARNING '
        self.sms     = self.sms + ' for counties ' + self.counties
        if self.cities:
          self.sms = self.sms + ' cities ' + self.cities
        self.sms = self.sms + 'issued at ' + self.time
        if self.exp:
          self.sms = self.sms + ' expires ' + self.exp
        
      else:
        self.sms = self.id +  ' ' + self.type + ' WATCH '
        self.sms = self.sms + ' for counties ' + self.counties
        if self.cities:
          self.sms = self.sms + ' cities ' + self.cities
        self.sms = self.sms + 'issued at ' + self.time
        if self.exp:
          self.sms = self.sms + ' expires ' + self.exp

    return self.valid

# Program configuration information
if os.name == 'posix':
  home_dir     = os.environ.get('HOME')
  config_dir   = home_dir + '/.StormSiren'
elif os.name == 'os2':
  home_dir     = os.environ.get('HOME')
  config_dir   = home_dir + '/StormSiren'
elif os.name == 'nt':
  home_dir     = os.environ.get('USERPROFILE') # NT/2K/XP
  if home_dir == None:
    home_dir = os.environ.get('WINDIR') # 95/98/ME
  config_dir   = home_dir + '/Application Data/StormSiren'

if not os.path.exists(config_dir):
  os.mkdir(config_dir)

config_file  = os.path.normpath(config_dir + '/StormSiren.conf')
log_file     = os.path.normpath(config_dir + '/StormSiren.log')
state_file   = os.path.normpath(config_dir + '/StormSiren.state')
log_buffer   = []
interactive_copyright = """
StormSiren version """ + __version__ + """
Copyright (C) 2011 Brandon Pierce
StormSiren comes with ABSOLUTELY NO WARRANTY;
This is free software, and you are welcome to redistribute it
under certain conditions; see the included license file for details.
"""

# URLs to the National Weather Service data

# Main: 	http://www.weather.gov/view/states.php?state=[two-letter state code]
# Watches: 	http://www.weather.gov/view/prodsByState.php?state=[two-letter state code]&prodtype=watches
# Warnings: http://www.weather.gov/view/prodsByState.php?state=[two-letter state code]&prodtype=warnings

iwin_url     = 'http://iwin.nws.noaa.gov/iwin/'
watch_url    = '/watches.html'
warn_url     = '/allwarnings.html'
urls         = []

# Load user configuration file
states              = []
cities              = []
counties            = []
device_id           = ''
notification_system = ''
email_address       = ''
smtp_server         = ''
alert_level         = 2			# Use an enum
debug_level         = 0			# Use an enum
devices             = {}

# Try to open user configuration file
try:
  conf_f = open(config_file, 'r')
  config_contents = conf_f.readlines() 
  conf_f.close()
  
  print "Config file opened..."

# Set argument for debug to output config options

# Parse config file data
  for i in range(len(config_contents)):
    chk_comment   = string.count(config_contents[i][0:1], '#')
    chk_states    = string.count(string.lower(config_contents[i]), 'states: ')
    chk_cities    = string.count(string.lower(config_contents[i]), 'cities: ')
    chk_counties  = string.count(string.lower(config_contents[i]), 'counties: ')
    chk_device    = string.count(string.lower(config_contents[i]), 'device: ')
    chk_email     = string.count(string.lower(config_contents[i]), 'email: ')
    chk_smtp      = string.count(string.lower(config_contents[i]), 'smtp: ')
    chk_alert     = string.count(string.lower(config_contents[i]), 'alert: ')
    chk_debug     = string.count(string.lower(config_contents[i]), 'debug: ')
    if chk_comment:
      continue
    if chk_states:
      xstates = string.split(config_contents[i][7:], ',')
      for j in range(len(xstates)):
        states.append(string.strip(xstates[j]))
    if chk_counties:
      xcounties = string.split(config_contents[i][9:], ',')
      for j in range(len(xcounties)):
        counties.append(string.strip(xcounties[j]))        
    if chk_cities:
      xcities = string.split(config_contents[i][7:], ',')
      for j in range(len(xcities)):
        cities.append(string.strip(xcities[j]))        
    if chk_device:
      device_info = string.split(string.strip(config_contents[i][7:]))
      devices[device_info[0]] = device_info[1]      
    if chk_email:
      email_address = string.strip(config_contents[i][6:])      
    if chk_smtp:
      smtp_server = string.strip(config_contents[i][5:])      
    if chk_alert:
      alert_level = int(string.strip(config_contents[i][6:]))      
    if chk_debug:
      debug_level = int(string.strip(config_contents[i][6:]))
      
  if debug_level >= 2:
  	print "States:"
  	for state in states:
  	  print "\t" + state  	
  	print "Counties:"
  	for county in counties:
  	  print "\t" + county  	  
  	print "Cities:"
  	for city in cities:
  	  print "\t" + city  	
  	print "Devices:"
  	print "\t" + device_info[0] + ", " + device_info[1]
  	print "\t" + devices[device_info[0]]
  	print "Email:"
  	print "\t" + email_address
  	print "SMTP"
  	print "\t" + smtp_server
  	print "Debug Level"
  	print "\t" + str(debug_level)

# Validate configuration file. Lecture user if missing directives.
  error_string = ''
  if not devices:
    error_string = 'No notification device specified.'
  elif not states:
    error_string = 'State or states not specified.'
  elif not counties:
    error_string = 'Counties not specified.'
  elif not email_address:
    error_string = 'Return e-mail address not specified.'
  elif not smtp_server:
    error_string = 'SMTP gateway not specified.'

  if error_string:
    print '*ERROR* - ' + error_string
    print 'You may want to remove the file' + config_file
    print 'and then rerun StormSiren.py to regenerate it.'
    sys.exit(1)

# If config file doesn't exist, build one for them!
except IOError:
  print interactive_copyright
  print """
Welcome to the StormSiren configuration wizard.

This program scans the severe weather bulletins issued by the National Weather
Weather Service and sends alerts in the form of text messages to your pager,
wireless phone and/or electronic mailbox.  
  """

  device_selection = 4
  while device_selection:
    print "Select a Notification Method."
    print "1.  Mobile Phone/Pager with an e-mail address"
    print "2.  Regular Internet E-Mail Address"
    print "Enter the number of the notification method to use.  Enter a "
    print "zero (0) if you are all done entering devices."
    print "Method? ",
    
    try:
      device_selection = int(raw_input())
      print " "
    except ValueError:
      print "\nSorry, that response didn't make sense.\n"
      device_selection = 4
      continue

    if device_selection == 0:
      break
    elif device_selection == 1:
      notification_system = 'sms'
      print "What is the e-mail address of your phone/pager? "
    elif device_selection == 2:
      notification_system = 'email'
      print "What is your e-mail address? "
    else:
      print "\nI don't recognize that option, please try again."
      device_selection = 4
      continue
    device_id = raw_input()
    devices[device_id] = notification_system
    print " "

  print "What state do you live in or wish to monitor?  You can enter multiple "
  print "states, separated by commas.  Please use the two letter postal "
  print "abbrevion."
  print "States? ",
  states = raw_input()
  print "\nOn which counties would you like to be alerted regarding severe "
  print "weather watches and warnings?  You can enter multiple counties, "
  print "separated by commas."  
  print "Counties? ",
  counties = raw_input()
  print "\nYou can also opt to have specific cities appear in the alert if "
  print "those cities are listed in the NWS bulletins.  Enter multiple cities "
  print "by separating them by commas."
  print "Cities? ",
  cities = raw_input()
  print "\nWhat is your e-mail address?  This is needed for setting the "
  print "originator address for the message?"
  print "E-Mail? ",
  email = raw_input()
  print "\nWhat SMTP server do you use for outbound mail? "
  print "SMTP server? ",
  smtp = raw_input()
  print "\nWhat types of alerts would you like to receive? "
  print "1.  Warnings only (imminent severe weather threat)"
  print "2.  Warnings and watches (approaching or potential threat)"
  print "Alert Level? ",
  alert_level = raw_input()
  print "\nWould you like any debugging information written to the screen "
  print "or to a logfile? "
  print "0.  No logging"
  print "1.  Write to " + log_file
  print "2.  Write to computer screen (stdout)"
  print "Debug Level? ",
  debug_level = raw_input()
  print "\nThanks.  Writing configuration file to " + config_file
  conf_f = open(config_file, 'w')
  conf_f.write("# Autogenerated Storm configuration file\n")
  conf_f.write("STATES: " + str(states) + "\n")
  conf_f.write("COUNTIES: " + str(counties) + "\n")
  conf_f.write("CITIES: " + str(cities) + "\n")
  conf_f.write("EMAIL: " + email + "\n")
  conf_f.write("SMTP: " + smtp + "\n")
  devkeys = devices.keys()
  for i in range(len(devkeys)):
    conf_f.write("DEVICE: " + devkeys[i] + " " + devices[devkeys[i]] + "\n")
  conf_f.write("ALERT: " + alert_level + "\n")
  conf_f.write("DEBUG: " + debug_level + "\n")
  conf_f.close()
  sys.exit()

# Initialize Alarm Info
if debug_level >= 2:
  print interactive_copyright
alarms       = []
state_exists = 0
new_state    = []
page_queue   = []
weather_data = []

# Note program initialization
if debug_level >= 2:
  print "StormSiren initiated"

# Build list of URLs to fetch.
for i in range(len(states)):
  urls.append(iwin_url + states[i] + warn_url)
  if alert_level > 1:
    urls.append(iwin_url + states[i] + watch_url)

try:
  if debug_level >= 2:
    print "Fetching the following urls:"
  for i in range(len(urls)):
    if debug_level >= 2:
      print "...fetching " + urls[i] + "..."
    stormwatch = urllib.urlopen(urls[i])
    stormwatch_data = stormwatch.readlines()
    stormwatch.close()
    weather_data = weather_data + stormwatch_data

except IOError:
  # No net connection available, exit.
  if debug_level >= 2:
    print "Internet connection not available, exiting"
  else:
    log_buffer.append("Internet connection not available, exiting")
  sys.exit()
  
# Developer Mode, read data from local saved file on disk
if debug_level == 9:
  print "...fetching test data from local disk..."
  testwatch = open(config_dir + '/testwatch.txt')
  testwatch_data = testwatch.readlines()
  testwatch.close()
  weather_data = weather_data + testwatch_data

# Initialize some flags and counters
pre          = 0
city         = 0
cnty         = 0
eas_cnty     = 0
eas_city     = 0
watch_count  = 0
alert_count  = 0

# Compile regular expression objects
#KANSAS AREAL OUTLINE FOR SEVERE THUNDERSTORM WATCH 158
#MINNESOTA OUTLINE FOR SEVERE THUNDERSTORM WATCH NUMBER 566
#THE NATIONAL WEATHER SERVICE HAS ISSUED SEVERE THUNDERSTORM WATCH 527
watch_info_e  = re.compile('.*(?:OUTLINE FOR|HAS ISSUED) (.*) WATCH.*\s+(\d+)\s*$')
watch_time_e  = re.compile('^(\d+\s+(AM|PM)\s+[A-Z]{1}(D|S){1}T{1}\s+.*)')
watch_expir_e = re.compile('(?:IS\s+IN\s+EFFECT\s+)?UNTIL\s+(\d+\s+[A-Z]{2}\s+[A-Z]{3})')
date_pattern     = re.compile("^(\d{4})\s+(AM|PM)\s+([A-Z]{1}(D|S){1}T{1})\s+(\w{3})\s+(\w{3})\s+(\d{2})\s+(\d{4})\s*$")
splat_warn_pat   = re.compile("^\*\s+(.*)\s+WARNING\s+FOR")
county_pattern   = re.compile("^\s*(.+)\s+COUNTY.*$")
splat_until      = re.compile("^\*\s+UNTIL\s+(.*)$")
splat_at         = re.compile("^\*\s+AT\s+(.*)\.\.\.(.*)$")
watch_counties   = re.compile("(INCLUDES|^IN\s+|^...IN\s+)")

# Parse watch data that we retrieved from the NWS
for i in range(len(weather_data)):
  pre_on      = string.count(string.upper(weather_data[i]), '<PRE>')
  pre_off     = string.count(string.upper(weather_data[i]), '</PRE>')

# The preformatted tags appear to consistently indicate the beginning of each
# bulletin.  The text bulletins are htmlized as far as the presentation pages
# go, but the data is still preformatted text
  if pre_on:
    pre = 1
    wx = wxalert()
    wx.bulletin.append(weather_data[i][9:])
    wx.prestring  = weather_data[i]
    watch_count = watch_count + 1
    continue

# Turn pre off if we match a preformatted close tag.  This indicated the end of
# a bulletin, so we can also package the alarm we were just reading.
  elif pre_off:
    pre = 0
    valid = wx.validate()
    if valid:
      alarms.append(wx)
    wx = ''

# Re-initialize loop variables    
    cnty         = ''
    city         = ''
    eas_locations = ''
    eas_cnty     = ''
    eas_city     = ''
    eas_warning  = ''  
    pre_string   = ''
    pre_chunks   = []

# This indicates we're reading the bulletin.  Start doing string and regular
# expression matches.
  if pre:
    wx.bulletin.append(weather_data[i])
    cities_on   = string.count(weather_data[i], 'SOME CITIES INCLUDED IN THE WATCH ARE...')
    cities_on   = cities_on + string.count(weather_data[i], 'THIS INCLUDES THE CITIES OF')
    counties_on = watch_counties.search(weather_data[i])
    eas_warning_on = splat_warn_pat.search(weather_data[i])
    eas_locations_on = string.count(weather_data[i], 'SOME LOCATIONS AFFECTED BY THIS')
    
# Parse the included cities section
    if cities_on:
      city = 1
      continue
    
# Parse the affected counties section
    if counties_on:
      city = 0
      cnty = 1
      continue

    if eas_warning_on:
      wx.warning = eas_warning_on.group(1)
      eas_cnty = 1
      continue

    if eas_locations_on:
      eas_city = 1
      continue

# See if we match
    if city:
        for j in range(len(cities)):
	  if string.count(weather_data[i], string.upper(cities[j])):
	    wx.cities = wx.cities + string.upper(cities[j]) + ' ' 
# Match for county
    elif cnty:
        for j in range(len(counties)):
	  if string.count(weather_data[i], string.upper(counties[j])):
	    wx.counties = wx.counties + string.upper(counties[j]) + ' '
# Warning cities
    if eas_city:
        for j in range(len(cities)):
	  if string.count(weather_data[i], string.upper(cities[j])):
	    wx.cities = wx.cities + string.upper(cities[j]) + ' ' 
# Match for counties in warnings
    elif eas_cnty:
        eas_cnty_test = county_pattern.search(weather_data[i])
        if eas_cnty_test:
          for j in range(len(counties)):
	    cnty_test = string.count(string.upper(eas_cnty_test.group(1)), string.upper(counties[j])) 
	    if cnty_test:
              wx.counties = wx.counties + string.upper(counties[j]) + ' '

# This is the main part of the bulletin
    else:
      watch_info  = watch_info_e.search(weather_data[i])
      watch_time  = watch_time_e.search(weather_data[i])
      watch_expir = watch_expir_e.search(weather_data[i])
      eas_until   = splat_until.search(weather_data[i])
      eas_at      = splat_at.search(weather_data[i])
      if watch_info:
	wx.id = year + '_' + string.strip(watch_info.group(2))
	wx.type = string.strip(watch_info.group(1))
      elif watch_time:
	wx.time = string.strip(watch_time.group(1))
      elif watch_expir:
	wx.exp  = string.strip(watch_expir.group(1))
      elif eas_until:
        wx.exp  = string.strip(eas_until.group(1))
	eas_cnty = 0
      elif eas_at:
        wx.time  = string.strip(eas_at.group(1))

# We're in the html formatted presentation stuff, no bulletins there.
  else:
    continue

# See if we can open the state file.  
try:
  state = open(state_file, 'r')
  state_data = state.readlines()
  state.close()
  state_exists = 1

# Don't worry if we can't open it.  We'll open it later during the writing stage
except IOError:
  pass

# Check if the user has requested a test page.
try:
  if sys.argv[1] == '-testpage':
    test_alarm     = wxalert()
    test_alarm.id  = str(time.time())
    test_alarm.sms = test_alarm.id + ' TEST storm alert issued at ' + now
    test_alarm.bulletin.append(test_alarm.sms + '\n') 
    test_alarm.bulletin.append('\nTest text bulletin\n')
    page_queue.append(test_alarm)
except IndexError:
  pass # No arguments provided

# Loop through all identified alarms affecting our counties
for i in range(len(alarms)):
  paged = 0
  wxo = alarms[i]
  print "wxo: " + wxo

# If there is a state file, open it and check if we've already paged on this
# bulletin.
  if state_exists:
    for j in range(len(state_data)):
      if wxo.id == string.strip(state_data[j]):
	paged = 1
        alert_count = alert_count + 1
    if paged:
      log_buffer.append('Already paged on state data ' + wxo.id)
    else:
      log_buffer.append('Paging on new watch, ' + wxo.id + ' ' + wxo.sms)
      page_queue.append(wxo)
      # Add the alarm to both the new state data and the existing state file 
      # to avoid double paging.
      new_state.append(wxo.id)
      state_data.append(wxo.id)

# If not, no problem.  We'll skip the matching and add any pageable stuff to be
# written and start the state file
  else:
    log_buffer.append('Paging on new watch, ' + wxo.sms)
    page_queue.append(wxo)
    new_state.append(wxo.id)

msg_to        = []
sms_to        = []
device_keys = devices.keys()
mail_results  = ''

for i in range(len(device_keys)):
  if devices[device_keys[i]] == 'sms':
    sms_to.append(device_keys[i])
  elif devices[device_keys[i]] == 'email':
    msg_to.append(device_keys[i])
  else:
    log_buffer.append('Unrecognized ' + device_keys[i])

sms_recp = string.join(sms_to, ', ')
msg_recp = string.join(msg_to, ', ')

for page in page_queue:
  print page

try:
  print "Trying to send message..."
  while (page_queue[0]):
    print "in the while"
    wxp = page_queue.pop(0)
    print wxp
    alert_count = alert_count + 1
	
# Create mail server object
    msg_headers = 'From: ' + email_address + '\n'
    msg_headers = msg_headers + 'Subject: StormSiren Alert\n'
    msg_headers = msg_headers + 'X-Mailer: StormSiren ' + __version__ + '\n\n'
    
    if sms_recp:
      msg_address  = 'To: ' + sms_recp + '\n'
      msg = msg_address + msg_headers + wxp.sms
      if debug_level >= 2:
        print "Attempting to send to " + sms_recp
      mailhost = smtplib.SMTP(smtp_server)
      mailhost.sendmail(email_address, sms_to, msg)
      mailhost.quit
      log_buffer.append('Paged ' + sms_recp + ' on ' + wxp.sms)
      
    if msg_recp:
      msg_address  = 'To: ' + msg_recp + '\n'
      msg = msg_address + msg_headers + string.join(wxp.bulletin, '')
      if debug_level >= 2:
        print "Attempting to send to " + msg_recp
      mailhost = smtplib.SMTP(smtp_server)
      mailhost.sendmail(email_address, msg_to, msg)
      mailhost.quit
      log_buffer.append('E-Mailed ' + msg_recp + ' on bulletin ' + str(wxp.id))    
    
except IndexError:
  log_buffer.append('No more devices available for paging')
  pass

# Write the state file if there were alarms.
if not mail_results:
  if (alert_count):
    state = open(state_file, 'a')
    for i in range(len(new_state)):
      state.write(new_state[i] + '\n')
    state.close()
#  else:
#    if (state_exists):
#      os.unlink(state_file)

# Note how many bulletins were counted
log_buffer.append("Counted " + str(watch_count) + " active NWS bulletins")

# Finally, write out the log buffer
if debug_level == 1:
  logw = open(log_file, 'a')

for i in range(len(log_buffer)):  
  if debug_level == 1:
    logw.write("StormSiren " + now + ": " + log_buffer[i] + "\n")
  elif debug_level > 1:
    print log_buffer[i]

