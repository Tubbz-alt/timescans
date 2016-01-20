

"""
For calibration: 20x steps of 100 fs spacing
~30 shots / time


Example
-------
>>> # load defaul parameters for CXI from ~/.timescanrc
>>> tt = Timetool.from_rc()
     
>>> # for a static run, this is useful for control
>>> tt.set_delay(0.001)

>>> # scan specific times, 100 shots/time, random order, 2 repeats
>>> times_in_ns = [ -0.001, 0.0, 0.001 ]
>>> tt.scan_times(times_in_ns, nevents_per_timestep=100, 
                  randomize=True, repeats=2)

>>> # or by (start, stop, step_size)
>>> tt.scan_range(-0.001, 0.001, 0.001)

>>> # run a calibration scan to determine pixel/fs conversion
>>> # should launch an external job that updates the 
>>> # DAQ config & psana calib directory
>>> tt.calibrate()
"""

import os
import time
import epics
import subprocess
import sys

try:
    import pydaq
except:
    daq = None

import numpy as np

CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'

DEBUG = True


def mm_to_ns(path_length):
    """
    Lasers go at the speed of light!
    """
    c = 299792458.0 # m / s
    meters  = path_length / 1000.0
    time_s  = meters / c
    time_ns = time_s * 1.0e9
    return time_ns


def ns_to_mm(time):
    c = 299792458.0 # m / s
    sec = time * 1.0e-9
    meters = sec * c
    mm = meters * 1000.0
    return mm

        
class Timetool(object):
    """
    Class for managing the timetool delay.
    
    There are three numbers that need to be combined to obtain a
    -- a calibrated t_0 (this is a set PV)
    -- a pixel-to-
    
    """
    
    def __init__(self,
                 daq_host,
                 daq_platform,
                 laser_delay_pv_name,
                 tt_stage_position_pv_name,
                 t0_pv_name,
                 laser_lock_pv_name,
                 eventcode_nobeam):


        self._daq_host = daq_host
        self._daq_platform = daq_platform
        self.daq = pydaq.Control(daq_host, daq_platform)
                 
        self._laser_delay        = epics.PV(laser_delay_pv_name)
        self._tt_stage_position  = epics.PV(tt_stage_position_pv_name)
        self._t0                 = epics.PV(t0_pv_name)
        self._laser_lock         = epics.PV(laser_lock_pv_name)
        self.eventcode_nobeam    = eventcode_nobeam

        self.tt_travel_offset    = 0.0
        self.tt_fit_coeff        = np.array([ 0.0, 1.0, 0.0 ])
        self.calibrated          = False

        time.sleep(0.1) # time for PVs to connect
        for pv in [self._laser_delay, self._tt_stage_position,
                   self._t0, self._laser_lock]:
            if not pv.connected:
                raise RuntimeError('Cannot connect to PV: %s' % pv.pvname)
        
        return


    @classmethod
    def from_rc(cls):

        rc_path = os.path.join(os.environ['HOME'], '.timescanrc')
        print "\ninitialized from %s" % rc_path

        settings = {}
        with open(rc_path, 'r') as f:
            for line in f:
                k,v = [x.strip() for x in line.split('=')]
                print '\t%s --> %s' % (k,v)
                settings[k] = v
        print ""

        try:
            inst = cls(settings['daq_host'],
                       int(settings['daq_platform']),
                       settings['laser_delay_pv_name'],
                       settings['tt_stage_position_pv_name'],
                       settings['t0_pv_name'],
                       settings['laser_lock_pv_name'],
                       int(settings['eventcode_nobeam']))

            inst.tt_travel_offset  = float(settings['tt_travel_offset'])
            inst.tt_fit_coeff      = np.fromstring(settings['tt_fit_coeff'].strip('[]'), sep=' ')
            inst.calibrated        = bool(settings['calibrated'])


        except KeyError as e:
            raise IOError(str(e) + ' key missing in timescanrc file!')

        except Exception as e:
            raise IOError('Corrupted/incomplete rc file, regenerate it,'
                          ' got error: ' + str(e))

        return inst


    def set_rc(self):

        settings = {
                    'daq_host'                  : self._daq_host,
                    'daq_platform'              : self._daq_platform,
                    'laser_delay_pv_name'       : self._laser_delay.pvname,
                    'tt_stage_position_pv_name' : self._tt_stage_position.pvname,
                    't0_pv_name'                : self._t0.pvname,
                    'laser_lock_pv_name'        : self._laser_lock.pvname,
                    'eventcode_nobeam'          : self.eventcode_nobeam,
                    'tt_travel_offset'          : self.tt_travel_offset,
                    'tt_fit_coeff'              : self.tt_fit_coeff,
                    'calibrated'                : self.calibrated
                   }

        rc_path = os.path.join(os.environ['HOME'], '.timescanrc')
        with open(rc_path, 'w') as f:
            for k in settings.keys():
                f.write('%s = %s\n' % (k, str(settings[k])))

        return

        
    @property
    def tt_window(self):
        """
        Returns the time delay window (reliably) measurable in the current 
        position.
        """

        # currently let's just say +/- 300 fs, to be replaced --TJL
        # could be fancy and take an error tol arg, etc etc
        mm_travel = self._tt_stage_position.value
        print '^^^^^^^', mm_travel- self.tt_travel_offset
        delay_in_ns = mm_to_ns(mm_travel - self.tt_travel_offset)
        window = (delay_in_ns - 300.0e-6, delay_in_ns + 300.0e-6)

        return window
        
        
    @property
    def current_delay(self):
        delay = self._laser_delay.value
        window = self.tt_window
        if (delay < window[0]) or (delay > window[1]):
            print "*** WARNING: TT stage out of range for delay!"
        return delay
    
        
    def set_delay(self, delay_in_ns):
        """
        Move both the laser delay and the TT stage for a particular
        delay.
        """

        old_delay = self._laser_delay.value
        old_tt_pos = self._tt_stage_position.value

        tt_pos = self._tt_pos_for_delay(delay_in_ns)

        self._laser_delay.put(delay_in_ns)
        self._tt_stage_position.put(tt_pos)

        print "LAS delay: %f --> %f" % (old_delay, delay_in_ns)
        print "TT  stage: %f --> %f" % (old_tt_pos, tt_pos)
        
        return


    def _tt_pos_for_delay(self, delay_in_ns):

        # TT delay stage doubles path length
        mm_travel = ns_to_mm(delay_in_ns) / 2.0
        tt_position = mm_travel + self.tt_travel_offset

        return tt_position
        
        
    def calibrate(self):
        """
        Calibrate the pixel-to-fs conversion.
        """

        print ""
        print "-"*40
        print "Calibrating..."

        # 120 evts/pt | -1 ps to 1 ps, 100 fs window
        nevents_per_timestep = 12
        times = np.linspace(-0.001, 0.001, 21)

        run = self.scan_times(times, nevents_per_timestep)

        # >>> now fit the calibration
        #     if we can launch an external process...
        try:

            cmd = "ts.analyze_calib_run -e %s -r %d -l %s -n %d" % (exp, run, 
                                                                    self._laser_delay.pvname,
                                                                    self.eventcode_nobeam)
            
            ssh = subprocess.Popen(["ssh", "-A", "psdev",
                                    "ssh", "-A", "psana",
                                    "bsub", "-q", "psfehhiprioq"
                                    ].append(cmd.split()),
                                   shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
            result = ssh.stdout.readlines()
            if result == []:
                error = ssh.stderr.readlines()
                print error
                print "Automatic submission of job analyzing run %d failed" % run
                print "Run '%s' on any psana machine" % cmd
            else:
                print '> ts.analyze_calib_run job submitted to psana queue'
                print '> \t', result

        except:
            print "Automatic submission of job analyzing run %d failed" % run
            print "Run 'ts.analyze_calib_run -r %d' on any psana machine" % run

        # >>> monitor that job for completion


        return


    def scan_range(self, t1, t2, resolution, nevents_per_timestep=100,
                   randomize=False, repeats=1):

        times = np.arange(t1, t2 + resolution, resolution)

        print "scanning from %f --> %f" % (times.min(), times.max())
        print "\t%d bins \\ %f ns between bins \\ %d events per time" % ( len(times),
                                                                          resolution,
                                                                          nevents_per_timestep )
        self.scan_times(times, nevents_per_timestep=nevents_per_timestep,
                        randomize=randomize, repeats=repeats)
 
        return


    def scan_times(self, times_in_ns, nevents_per_timestep=100,
                   randomize=False, repeats=1, record=False):
        """
        Parameters
        ----------
        times_in_ns : np.ndarray (or list)
            A list of timepoints to scan

        nevents_per_timestep : int
            The number of events to measure at each timepoint

        randomize : bool
            If true, the order in which the timepoints are visited will be
            randomly scrambled (good for removing systematic errors)

        repeats : int
            How many times to repeat each timepoint
        """

        print ""
        print "="*40
        print "SCAN REQUESTED\n"

        if (record is False) or DEBUG:
            print "*** WARNING: not recording!"

        times_in_ns = np.repeat(times_in_ns, repeats)
        print "> scanning %d timepoints, %d events per timepoint" % (len(times_in_ns),
                                                                   nevents_per_timestep)

        # >>> cycle over tt_motor_positions and collect TT traces
        #     we need to pass a python object telling the daq how many cycles
        #     to run and what to vary. then we launch an external thread to do
        #     that.

        daq_config = { 'record' : record,
                       'events' : nevents_per_timestep,
                       'controls' : [ (self._laser_delay.pvname,
                                       self._laser_delay.value),
                                      (self._tt_stage_position.pvname,
                                       self._tt_stage_position.value) ],
                       'monitors' : [] # what should be here?
                      }        
        self.daq.configure(**daq_config)
        print "> daq configured"

        if randomize:
            print "> randomizing timepoints"
            np.random.shuffle(times_in_ns) # in-place

        for cycle, delay in enumerate(times_in_ns):

            new_tt_pos = self._tt_pos_for_delay(delay)
            print " --> cycle %d / laser delay %f ns / tt stage: %f" % (cycle, delay, new_tt_pos)
           
            if not DEBUG: 
                self._laser_delay.put(delay)
                self._tt_stage_position.put(new_tt_pos)

                # wait until PVs reach the value we want
                while ( (np.abs(self._laser_delay.value - delay) > 1e-9 ) or \
                        (np.abs(self._tt_stage_position.value - new_tt_pos) > 1e-9) ):
                    time.sleep(0.001)
            
            ctrls = [( self._laser_delay.pvname,       delay ),
                     ( self._tt_stage_position.pvname, new_tt_pos )]
            self.daq.begin(controls=ctrls)
            self.daq.end()

        print "> finished, daq released" 

        return self.daq.runnumber()




# --------------
# debugging




def _timetool_smoketest():

     tt = Timetool.from_rc()
     print "window", tt.tt_window

     tt.set_delay(0.001)
     print 'delay (should be 0.001)', tt.current_delay

     print 'should be ~1.5 (mm):', tt._tt_pos_for_delay(0.01)

     #print 'test scan...'
     #times_in_ns = [ -0.001, 0.0, 0.001 ]
     #print tt.scan_times(times_in_ns, 100, randomize=True, repeats=2)
     #print tt.scan_range(-0.001, 0.001, 0.001)

     tt.calibrate()

     return

def _rc_smoketest():

     cxi_pvs = ('cxi-daq', 4,
                'LAS:FS5:VIT:FS_TGT_TIME_DIAL',   # laser_delay_motor_pv_name   # THIS IS IN ns
                'CXI:LAS:MMN:04',                  # tt_stage_position_pv_name  # THIS IS IN mm
                'LAS:FS5:VIT:FS_TGT_TIME_OFFSET',  # t0_pv_name 
                'LAS:FS5:VIT:PHASE_LOCKED',        # laser_lock_pv_name
                42 )   
     tt = Timetool(*cxi_pvs)
     tt.set_rc()

     tt2 = Timetool.from_rc()

if __name__ == '__main__':
    _timetool_smoketest()
    #_rc_smoketest()

