# !/usr/bin/env python
#  This plugin includes example functions that are triggered by events in sip.py

# Note: RPi direct interface to sensors is not currently supported even though the option
#  is given in the settings page.  There's some skeleton code ready below where support can
#  be added if we decide it's important.

# Operation: at the lowest level, the flow sensor generates a series of pulses on an input
# pin of the Arduino or RPi that is related to the flow rate by a forumla given by the
# specs for the flow sensor.  This pulse is used to increment a software counter on
# the Arudino or RPi using an interrupt routine.

# This plugin creates a thread that runs every N seconds (e.g. 3 seconds) and that reads
# this counter and determines both the current flow rate (liters or gallons per hour)
# and the total amount of water flow (in liters or gallons) since the counter was reset.

# The flow rates and flow amounts for each station is stored in a gv.plugin_data['fs']
# dictionary.
from __future__ import print_function

import web  # web.py framework
import gv  # Get access to SIP's settings
from urls import urls  # Get access to ospi's URLs
from ospi import template_render  #  Needed for working with web.py templates
from webpages import ProtectedPage  # Needed for security
import json  # for working with data file
import time
import thread
import random
import serial
from blinker import signal

# Add new URLs to access classes in this plugin.
urls.extend([
    u"/flow_sensors-sp", u"plugins.flow_sensors.settings",
    u"/flow_sensors-save", u"plugins.flow_sensors.save_settings"
    ])

gv.plugin_menu.append([u"Flow Sensors Plugin", u"/flow_sensors-sp"])

#CONVERSION_MULTIPLIER = {u"Seeed 1/2 inch": {u"Liters": 60.0/7.5, u"Gallons": 60/7.5/3.78541},
#                         u"Seeed 3/4 inch": {u"Liters": 60.0/5.5, u"Gallons": 60/5.5/3.78541}}

def fixPerHour():  # recalculate settings derived from other settings
    isLiters = gv.plugin_data[u"fs"][u"settings"][u"units"] == u"Liters"
    gv.plugin_data[u"fs"][u"settings"][u"rate_units"] = u"LpH" if isLiters else u"GpH"


print(u"flow sensors plugin loaded...")
# initialize settings and other variables in gv
gv.plugin_data[u"fs"] = {}
gv.plugin_data[u"fs"][u"rates"] = [0]*8
gv.plugin_data[u"fs"][u"settings"] = {}
gv.plugin_data[u"fs"][u"settings"][u"interface"] = u"Simulated"
gv.plugin_data[u"fs"][u"settings"][u"sensor_type"] = u"Seeed/Digiten 1/2 inch"
gv.plugin_data[u"fs"][u"settings"][u"pulses_per_liter"] = 450.0
gv.plugin_data[u"fs"][u"settings"][u"units"] = u"Liters"
gv.plugin_data[u"fs"][u"settings"][u"rate_units"] = u"LpH"
fixPerHour()

print(u"Settings initialized to: " + str(gv.plugin_data[u"fs"][u"settings"]))
try:
    with open(u"./data/flow_sensors.json", u"r") as f:  # Read settings from json file if it exists
        gv.plugin_data[u"fs"][u"settings"] = json.load(f)
        print(u"Updating settings from json file: " + str(gv.plugin_data[u"fs"][u"settings"]))
except IOError:  # If file does not exist return empty value
    print(u"No flow_sensors.json file")
    print(u"my settings here are: " + str(gv.plugin_data[u"fs"][u"settings"]))


# add this plugin's log value to the SIP log
try:
    gv.logged_values.append( [_(u"usage"), lambda : u"{:.2f}".format(gv.plugin_data[u"fs"][u"program_amounts"][gv.lrun[0]]) ])
except AttributeError:
    print(u"gv.logged_values doesn't exist so logging not available for flow_sensor plugin")


# TODO: add support for other types of RPi serial interfaces with different /dev/names

def flow_sensor_loop():
    u"u"u"
    This tread will update the flow sensor values every N seconds.
    u"u""
    delta_t = 3.0 # seconds
    while True:
        update_flow_values()
        time.sleep(delta_t)

def reset_flow_sensors():
    """
    Resets parameters used by this plugin for all three flow_sensor types.
    Used at initialization and at the start of each Program/Run-Once 
    """
    print(u"resetting flow sensors")
    gv.plugin_data[u"fs"][u"start_time"] = time.time()
    gv.plugin_data[u"fs"][u"prev_read_time"] = time.time()
    gv.plugin_data[u"fs"][u"prev_read_cntrs"] = [0]*8
    gv.plugin_data[u"fs"][u"program_amounts"] = [0]*8

    if gv.plugin_data[u"fs"][u"settings"][u"interface"] == u"Simulated":
        gv.plugin_data[u"fs"][u"simulated_counters"] = [0]*8
        return True

    elif gv.plugin_data[u"fs"][u"settings"][u"interface"] == u"Arduino-Serial":
        serial_ch = serial.Serial(u"/dev/ttyACM0", 9600, timeout=1)
        gv.plugin_data[u"fs"][u"serial_chan"] = serial_ch
        time.sleep(0.1)
        serial_ch.write(u"RS\n")
        serial_ch.flush()
        time.sleep(0.1)
        line = serial_ch.readline()
        print(u"values from Arduino on establishing serial port")
        print(line)
        return True

    elif gv.plugin_data[u"fs"][u"settings"][u"interface"] == u"RaspberryPi-GPIO":
        pass
        return True
    print(u"Flow Sensor Type Failed in Reset")
    return False

def read_flow_counters(reset=False):
    """
    Reads counters corresponding to each flow sensor.
    Supports simulated flow sensors (for testing UI), flow sensors connected to an Arduino and
      perhaps flow sensors connected directly to the Pi.
    """
    print u"reading flow sensors"
    if gv.plugin_data[u"fs"][u"settings"][u"interface"] == u"Simulated":
        if reset:
            gv.plugin_data[u"fs"][u"simulated_counters"] = [0]*8
        else:
            gv.plugin_data[u"fs"][u"simulated_counters"] = [cntr + random.random()*40 + 180 for
                                                          cntr in gv.plugin_data[u"fs"][u"simulated_counters"]]
        return gv.plugin_data[u"fs"][u"simulated_counters"]

    elif gv.plugin_data[u"fs"][u"settings"][u"interface"] == u"Arduino-Serial":
        serial_ch = gv.plugin_data[u"fs"][u"serial_chan"]
        if reset:
            serial_ch.write(u"RS\n")
        else:
            serial_ch.write(u"RD\n")
        serial_ch.flush()
        print(u"Writing to Arduino")
        time.sleep(0.2)
        line = serial_ch.readline().rstrip()
        print(u"serial input from Arduino is: " + line)
        print(u"serial input has been printed")
        if line == u"":
            return [0]*8
        else:
            vals = map(int, line.split(u","))
        return vals

    elif gv.plugin_data[u"fs"][u"settings"][u"interface"] == u"RaspberryPi-GPIO":
        pass
        return [0]*8

    print(u"Flow Sensor Type Failed in Read")
    return False

def update_flow_values():
    """
    Updates gv values for the current flow rate and accumulated flow amount for each flow sensors.
    """
    pulses_per_liter = gv.plugin_data[u"fs"][u"settings"][u"pulses_per_liter"]
    units = gv.plugin_data[u"fs"][u"settings"][u"units"]
    current_time = time.time()

    elapsed_prev_read = current_time - gv.plugin_data[u"fs"][u"prev_read_time"]  # for flow rate
    print(u"elapsed time: " + str(elapsed_prev_read))

    prev_cntrs = gv.plugin_data[u"fs"][u"prev_read_cntrs"]

    curr_cntrs = read_flow_counters()

    # calculate flow amount in Liters as # of pulses * liters_per_pulse
    #  or #_of_pulses / (pulses_per_liter)

    amt_conv_mult = 1.0/pulses_per_liter  # or liters per pulse
    if u"units" == u"Gallons":
        amt_conv_mult /= 3.78541

    gv.plugin_data[u"fs"][u"program_amounts"] = [cntr*amt_conv_mult for cntr in curr_cntrs]

    # calculate flow rate in Liters per hour = pulses_per_second * (seconds_per_hour * liters_per_pulse)
    rate_conv_mult = 60.*60./pulses_per_liter
    if u"units" == u"Gallons":
        rate_conv_mult /= 3.78541

    gv.plugin_data[u"fs"][u"rates"] = [(cntr-prev_cntr)*rate_conv_mult/elapsed_prev_read for \
                                     cntr, prev_cntr in zip(curr_cntrs, prev_cntrs)]
    
    print(u"Rates:" + str(gv.plugin_data[u"fs"][u"rates"]))
    print(u"Amounts:" + str(gv.plugin_data[u"fs"][u"program_amounts"]))

    gv.plugin_data[u"fs"][u"prev_read_time"] = current_time
    gv.plugin_data[u"fs"][u"prev_read_cntrs"] = curr_cntrs
   
### Stations where sheduled to run ###
# gets triggered when:
#       - A program is run (Scheduled or "run now")
#       - Stations are manually started with RunOnce
def notify_station_scheduled(name, **kw):
    """
    Subscribes to the stations_scheduled signal and used to reset the flow_sensor counters
      and flow rate/amount values in the gv.
    """
    reset_flow_sensors()
    #print(u"Some stations have been scheduled: {}".format(str(gv.rs)))

reset_flow_sensors()
thread.start_new_thread(flow_sensor_loop, ())

program_started = signal(u"stations_scheduled") # subscribe to signal when programs/stations start running
program_started.connect(notify_station_scheduled) # specify callback for this signal

 #############################################
 # Web Interface for plugin settings
 #############################################
class settings(ProtectedPage):
    """
    Load an html page for entering plugin settings.
    """
    
    def GET(self):
        settings = gv.plugin_data[u"fs"][u"settings"]
        print(u"settings are:  " + str(settings))
        print (u"GET method in settings class")
        try:
            with open(u"./data/flow_sensors.json", u"r") as f:  # Read settings from json file if it exists
                settings = json.load(f)
                reset_flow_sensors()
        except IOError:  # If file does not exist return empty value
            print(u"No flow_sensors.json file")
            print u"my settings here are: " + str(settings)
        return template_render.flow_sensors(settings)  # open settings page

class save_settings(ProtectedPage):
    """
    Save user input to json file.
    Will create or update file when SUBMIT button is clicked
    CheckBoxes only appear in qdict if they are checked.
    """
    def GET(self):
        settings = gv.plugin_data[u"fs"][u"settings"]
        qdict = web.input()  # Dictionary of values returned as query string from settings page.
        print u"qdict = " + str(qdict)  # for testing
        print u"settings : " + str(settings)
        for key in qdict:
            # watch out for checkboxes since they only return a value in qdict if they're checked!!
            if key == u"pulses_per_liter":
                settings[key] = float(qdict[key])
            else:
                settings[key] = qdict[key]
        fixPerHour()
        reset_flow_sensors()
        print u"after update from qdict, settings = " + str(settings)
        with open(u"./data/flow_sensors.json", u"w") as f:  # Edit: change name of json file
             json.dump(settings, f) # save to file
             print u"flow sensor settings file saved"          
        raise web.seeother(u"/")  # Return user to home page.

