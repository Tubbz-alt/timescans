

"""
For calibration: 20x steps of 100 fs spacing
~30 shots / time

"""

import epics
import time
import pydaq

CURSOR_UP_ONE = '\x1b[1A'
ERASE_LINE = '\x1b[2K'


# create a global DAQ instance for the app
DAQ = pydaq.Control('cxi-daq', 4) # host, instance


def mm_to_ns(path_length):
    """
    Lasers go at the speed of light!
    """
    c = 299792458.0 # m / s
    meters  = path_length * 1000.0
    time_s  = meters / c
    time_ns = time_s * 1.0e9
    return time_ns


def ns_to_mm(time):
    c = 299792458.0 # m / s
    sec = time * 1.0e-9
    meters = sec * c
    mm = meters / 1000.0
    return mm

        
class Timetool(object):
    """
    Class for managing the timetool delay.
    
    There are three numbers that need to be combined to obtain a
    -- a calibrated t_0 (this is a set PV)
    -- a pixel-to-
    
    """
    
    def __init__(self,
                 laser_delay_pv_name,
                 tt_stage_position_pv_name,
                 t0_pv_name,
                 laser_lock_pv_name):
                 
        self._laser_delay        = epics.PV(laser_delay_pv_name)
        self._tt_stage_position  = epics.PV(tt_stage_position_pv_name)
        self._t0                 = epics.PV(t0_pv_name)
        self._laser_lock         = epics.PV(laser_lock_pv_name)

        self.tt_travel_offset    = 0.0
        self.tt_fit_coeff        = np.array([ 0.0, 1.0, 0.0 ])

        time.sleep(0.1) # time for PVs to connect
        for pv in [self._laser_delay, self._tt_stage_position,
                   self._t0, self._laser_lock]:
            if not pv.connected:
                raise RuntimeError('Cannot connect to PV: %s' % pv.pvname)
        
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
        delay_in_ns = mm_to_ns(mm_travel + self.tt_travel_offset)
        window = (delay_in_ns - 300.0e-6, delay_in_ns + 300.0e-6)

        return window
        
        
    @property
    def current_delay(self):
        delay = self._laser_delay.value
        window = self.tt_window
        if (delay < window[0]) or (delay > window[1]):
            print "WARNING: TT stage out of range for delay!"
        return delay
    
        
    def set_delay(self, delay_in_ns):
        """
        Move both the laser delay and the TT stage for a particular
        delay.
        """

        old_delay = self._laser_delay.value
        old_tt_pos = self._tt_stage_position.value

        tt_pos = self._tt_pos_for_delay(delay)

        self._laser_delay.put(delay)
        self._tt_stage_position.put(tt_pos)

        print "LAS delay: %f --> %f" % (old_delay, delay)
        print "TT  stage: %f --> %f" % (old_tt_pos, tt_pos)
        
        return


    def _tt_pos_for_delay(self, delay_in_ns):

        mm_travel = ns_to_mm(delay_in_ns)
        tt_position = mm_travel + self.tt_travel_offset

        return tt_position
        
        
    def calibrate(self):
        """
        Calibrate the pixel-to-fs conversion.
        """

        # 120 evts/pt | -1 ps to 1 ps, 100 fs window
        nevents_per_timestep = 120
        times = self.laser_delay + np.linspace(-0.001, 0.001, 21)

        run = scan_times(times, nevents_per_timestep)

        # >>> now fit the calibration
        #     if we can launch an external process...

        # >>> make a plot!

        return


    def scan_range(t1, t2, resolution, nevents_per_timestep=100,
                   randomize=False, repeats=1):

        times = np.arange(t1, t2 + resolution, resolution)

        print "scanning from %f --> %f" % (times.min(), times.max())
        print "\t%d bins \\ %f ns between bins \\ %d events per time" % ( len(times),
                                                                          resolution,
                                                                          nevents_per_timestep )
        scan_times(times, nevents_per_timestep=nevents_per_timestep,
                   randomize=randomize, repeats=repeats)
 
        return


    def scan_times(self, times_in_ns, nevents_per_timestep=100,
                   randomize=False, repeats=1):
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

        print "scanning %d timepoints, %d events per timepoint" % (len(times_in_ns),
                                                                   nevents_per_timestep)


        # >>> cycle over tt_motor_positions and collect TT traces
        #     we need to pass a python object telling the daq how many cycles
        #     to run and what to vary. then we launch an external thread to do
        #     that.

        daq_config = { 'record' : True,
                       'events' : nevents_per_timestep,
                       'controls' : [ (self._laser_delay.pvname,
                                       self._laser_delay.value) ],
                       'monitors' : [] # what should be here?
                      }        
        DAQ.configure(**daq_config)
        print "> daq configured"

        for cycle, delay in enumerate(times_in_ns):

            new_tt_pos = self._tt_pos_for_delay(delay)
            print " --> cycle %d / laser delay %f ns / tt stage: %f" % (cycle, delay, new_tt_pos)
            
            self._laser_delay.put(delay)
            self._tt_stage_position.put(new_tt_pos)

            # wait until PVs reach the value we want
            while ((self._laser_delay.value != delay) or \
                   (self._tt_stage_position.value != new_tt_pos)):
                print "\t\t LAS delay: %f --> %f" % (self._laser_delay.value, delay)
                print "\t\t TT  stage: %f --> %f" % (self._tt_stage_position.value, new_tt_pos)
                print CURSOR_UP_ONE + ERASE_LINE
            
            ctrls = [( self._laser_delay.pvname,       delay )
                     ( self._tt_stage_position.pvname, new_tt_pos )]
            DAQ.begin(controls=ctrls)
            DAQ.end()

        print "> finished, daq released" 

        return DAQ.runnumber()


def analyze_calibration_run(exp, run, las_stg_pvname, eventcode_nobeam=162):
    """
    Analyze a run where the timetool camera is fixed but the laser delay
    changes by a known amount in order to calibrate the TT camera pixel-
    time conversion.
    """

    import psana

    ds = psana.DataSource('exp=%s:run=%d:dir=/reg/d/ffb/%s/%s:smd:live'
                          '' % (exp, run, exp[:3], exp))

    las_stg   = psana.Detector(las_stg_pvname, ds.env())

    ttOptions = TimeTool.AnalyzeOptions(get_key='TSS_OPAL',
                                        eventcode_nobeam=eventcode_nobeam,
                                        calib_poly='0 1 0',
                                        sig_roi_x='0 1023',
                                        sig_roi_y='425 724',
                                        ref_avg_fraction=0.5)
    ttAnalyze = TimeTool.PyAnalyze(ttOptions)


    # loop over events and pull out (delay, pixel) tuples
    delay_pxl_data = []
    for evt in ds.events():

        las_stg_pos = las_stg(evt)
        ttdata = ttAnalyze(evt)

        # >>> TJL note, may want to perform some checks on e.g. TT peak heights, etc
        delay_pxl_data.append([las_stg_pos, ttdata.position_pixel()])
        

    # perform a regression
    # >>> TJL note, can we be smart about setting the other TT params?

    # push results upstream to DAQ config

    # save results to calib dir

    return a, b, c, r_sq, jpg


if __name__ == '__main__':


     cxi_pvs = ('LAS:FS5:VIT:FS_TGT_TIME_DIAL',   # laser_delay_motor_pv_name   # THIS IS IN ns
                'CXI:LAS:MMN:06',                  # tt_stage_position_pv_name  # THIS IS IN mm
                'LAS:FS5:VIT:FS_TGT_TIME_OFFSET',  # t0_pv_name 
                'LAS:FS5:VIT:PHASE_LOCKED' )       # laser_lock_pv_name

     tt = Timetool(*cxi_pvs)
     times_in_ns = [ -0.001, 0.0, 0.001 ]
     tt.scan_times(times_in_ns, 1000)

