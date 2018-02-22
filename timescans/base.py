

"""
For calibration: 20x steps of 100 fs spacing
~30 shots / time


Example
-------
>>> # load defaul parameters for CXI from ~/.timescanrc
>>> tt = Timescaner.from_rc()
     
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
import subprocess
import sys
import threading

try:
    import epics
    _EPICS_IMPORT = True
except:
    _EPICS_IMPORT = False
    print 'warning, EPICS not imported'

try:
    import pydaq
except:
    daq = None

import numpy as np

CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'

DEBUG = False


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

        
class Timescaner(object):
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
                 laser_lock_pv_name):
        """
        Create a Timescaner instance, providing control over the timetool
        and laser delay stages.

        Parameters
        ----------
        daq_host : str
        daq_platform : int
        laser_delay_pv_name : str
        tt_stage_position_pv_name : str
        t0_pv_name : str
        laser_lock_pv_name : str

        See Also
        --------
        Timescaner.from_rc() : function
            Create a timescaner instance from a file.
        """


        self._daq_host = daq_host
        self._daq_platform = daq_platform
        self.daq = pydaq.Control(daq_host, daq_platform)
                 
        self._laser_delay        = epics.PV(laser_delay_pv_name)
        self._tt_stage_position  = epics.PV(tt_stage_position_pv_name)
        self._t0                 = epics.PV(t0_pv_name)
        self._laser_lock         = epics.PV(laser_lock_pv_name)

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
    def from_rc(cls, rc_path=None):
        """
        Create a Timescaner instance from a configuration saved in an rc
        file.

        Optional Parameters
        -------------------
        rc_path : str
            The rc file to load. If `None`, will look for $HOME/.timescanrc

        Returns
        -------
        ts : Timescaner
            The timescaner instance.

        See Also
        --------
        set_rc : function
            Create a timescaner rc file from current instance/settings.
        """


        if rc_path is None:
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
                       settings['laser_lock_pv_name'])

            inst.tt_travel_offset  = float(settings['tt_travel_offset'])
            inst.tt_fit_coeff      = np.fromstring(settings['tt_fit_coeff'].strip('[]'), sep=' ')
            inst.calibrated        = bool(settings['calibrated'])


        except KeyError as e:
            raise IOError(str(e) + ' key missing in timescanrc file!')

        except Exception as e:
            raise IOError('Corrupted/incomplete rc file, regenerate it,'
                          ' got error: ' + str(e))

        return inst


    def set_rc(self, rc_path=None):
        """
        Create a timescan rc file with parameters from the current
        Timescaner instance.

        Optional Parameters
        -------------------
        rc_path : str
            The rc file to load. If `None`, will look for $HOME/.timescanrc

        See Also
        --------
        from_rc : function
            Load an rc file.
        """

        settings = {
                    'daq_host'                  : self._daq_host,
                    'daq_platform'              : self._daq_platform,
                    'laser_delay_pv_name'       : self._laser_delay.pvname,
                    'tt_stage_position_pv_name' : self._tt_stage_position.pvname,
                    't0_pv_name'                : self._t0.pvname,
                    'laser_lock_pv_name'        : self._laser_lock.pvname,
                    'tt_travel_offset'          : self.tt_travel_offset,
                    'tt_fit_coeff'              : self.tt_fit_coeff,
                    'calibrated'                : self.calibrated
                   }

        if rc_path is None:
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

        Parameters
        ----------
        delay_in_ns : float
            Value to set delay to.
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

        This function will perform a scan between -1 ps and +1 ps, taking 1200
        shots at 21 intermediate timesteps. A psana job will then be launched
        on the psana cluster to analyze the results and configure both the
        DAQ and psana calib dir.

        NOTE 1/22/16, TJL
        >> the part about config the DAQ and psana is currently a lie, coming
           soon
        """

        print ""
        print "-"*40
        print "Calibrating..."

        # 120 evts/pt | -1 ps to 1 ps, 100 fs window
        nevents_per_timestep = 120
        times_in_ns = np.linspace(-0.001, 0.001, 41)

        daq_config = { 'record' : True,
                       'events' : nevents_per_timestep,
                       'controls' : [ (self._laser_delay.pvname,
                                       self._laser_delay.value) ],
                       'monitors' : [] # what should be here?
                      }
        self.daq.configure(**daq_config)
        print "> daq configured"

        for cycle, delay in enumerate(times_in_ns):

            print " --> cycle %d / laser delay %f ns / tt stage: STATIC" % (cycle, delay)

            if not DEBUG:
                self._laser_delay.put(delay)

                # wait until PVs reach the value we want
                while (np.abs(self._laser_delay.value - delay) > 1e-9):
                    time.sleep(0.001)

            ctrls = [( self._laser_delay.pvname, delay )]
            try:
                self.daq.begin(controls=ctrls)
                self.daq.end()
            except KeyboardInterrupt:
                print 'Rcv ctrl-c, interrupting DAQ scan...'
                self.daq.stop()
            finally:
            run = self.daq.runnumber()
            self.daq.disconnect()

        # >>> now fit the calibration
        #     if we can launch an external process...
        #     this is messy. in the future if data are available on teh local
        #     machine that would be MUCH better!
        try:

            # TJL note to self: these make the code CXI-specific... :(
            python = "/reg/neh/operator/cxiopr/cxipy/bin/python"
            script = "/reg/neh/operator/cxiopr/timescans/scripts/ts.calibrun"
            args = "-e %s -r %d -l %s" % (exp, run, self._laser_delay.pvname)

            cmd = "%s %s %s" % (python, script, args)
            print "> Executing: %s" % cmd
            print "> on a psana machine..."
            
            ssh = subprocess.Popen(["ssh", "-A", "psdev",
                                    "ssh", "-A", "psana",
                                    ] + cmd.split(),
                                   shell=False,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)

            for line in ssh.stdout.readlines() + ssh.stderr.readlines():
                print '\t* ' + line.strip()

        except:
            print "Automatic submission of job analyzing run %d failed" % run
            print "Run:"
            print "\t", cmd
            print "on any psana machine"

        return


    def scan_range(self, t1, t2, resolution, nevents_per_timestep=100,
                   randomize=False, repeats=1):
        """
        Scan a range of equally spaced timepoints.

        Calling this function will take control of the DAQ, timetool stage,
        and laser delay stage to perform scans as specified by the following
        parameters.

        Parameters
        ----------
        t1, t2 : float
            The starting and ending times (in ns), respectively for the scan.

        resolution : float
            The spacing between timepoints (in ns).

        nevents_per_timestep : int
            The number of shots to take at each timestep.

        randomize : bool
            If `True`, the order in which the timepoints are visited will be
            randomized. Useful for avoiding systematic errors due to drift.

        repeats : int
            The number of times to repeat the scan.
        """

        times = np.arange(t1, t2 + resolution, resolution)

        print "scanning from %f --> %f" % (times.min(), times.max())
        print "\t%d bins \\ %f ns between bins \\ %d events per time" % ( len(times),
                                                                          resolution,
                                                                          nevents_per_timestep )
        self.scan_times(times, nevents_per_timestep=nevents_per_timestep,
                        randomize=randomize, repeats=repeats)
 
        return


    def scan_times(self, times_in_ns, nevents_per_timestep=100,
                   randomize=False, repeats=1, record=True):
        """
        Scan a list of specific time points, `times_in_ns`.

        Calling this function will take control of the DAQ, timetool stage,
        and laser delay stage to perform scans as specified by the following
        parameters.

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

        daq_config = { 'record' : (record and not DEBUG),
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
            try:
                self.daq.begin(controls=ctrls)
                self.daq.end()
            except KeyboardInterrupt:
                print 'Rcv crtl-C, interrupting DAQ scan'
                self.daq.stop()

        rn = self.daq.runnumber()

        self.daq.disconnect()
        print "> finished, daq released" 

        return rn


    def _scan_back_and_forth(self, window_size_fs):
        
        set_delay = self._laser_delay.value
        while self._SCAN:
            if not DEBUG:
                delay = np.random.uniform(set_delay - window_size_fs/2.0 * 1e6,
                                          set_delay + window_size_fs/2.0 * 1e6)
                self._laser_delay.put(delay)
                while (np.abs(self._laser_delay.value - delay) > 1e-9):
                    time.sleep(0.001)
            time.sleep(1.0) # give EPICs a 1 second break, may update this
                    
        return
        

    def get_jitter(self, nevents, window_size_fs=500):
        """
        
        """

        print ""
        print "="*40
        print "SCAN REQUESTED\n"

        if (record is False) or DEBUG:
            print "*** WARNING: not recording!"

        print "> scanning %d fs window for %d events" % (window_size_fs,
                                                         nevents)

        daq_config = { 'record' : (record and not DEBUG),
                       'events' : nevents,
                       'controls' : [],
                       'monitors' : []
                      }        
        self.daq.configure(**daq_config)
        print "> daq configured"
      

        # start a thread to do the 
        initial_delay = self._laser_delay.value
        t = threading.Thread(target=self._scan_back_and_forth, 
                             args=(window_size_fs,))
            
        try:
            t.start()
            self.daq.begin()
            self.daq.end()
        except KeyboardInterrupt:
            print 'Rcv crtl-C, interrupting DAQ scan'
            self.daq.stop()
        finally:
            self._SCAN = False # stops thread
            self._laser_delay.put(initial_delay)
            
            rn = self.daq.runnumber()

            self.daq.disconnect()
            print "> finished, daq released" 

        return rn


# --------------
# debugging




def _timetool_smoketest():

     tt = Timescaner.from_rc()
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
     tt = Timescaner(*cxi_pvs)
     tt.set_rc()

     tt2 = Timescaner.from_rc()

if __name__ == '__main__':
    _timetool_smoketest()
    #_rc_smoketest()

