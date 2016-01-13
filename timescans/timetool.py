
import control
from daq import DAQ


def calibrate_t0():
    """
    I am not sure if this is possible just yet... it is a low priority.
    """
    raise NotImplementedError()
    return


ttOptions = TimeTool.AnalyzeOptions(get_key='TSS_OPAL',
                                    eventcode_nobeam=162,
                                    calib_poly='0 1 0',
                                    sig_roi_x='0 1023',
                                    sig_roi_y='425 724',
                                    ref_avg_fraction=0.05,
                                    eventcode_skip=0,
                                    ipm_get_key='',
                                    ipm_beam_threshold=0.0)
                                    
ttAnalyze = TimeTool.PyAnalyze(ttOptions)
ttAnalyze.process(evt)

        
class Timetool(object):
    """
    Class for managing the timetool delay.
    
    There are three numbers that need to be combined to obtain a
    -- a calibrated t_0 (this is a set PV)
    -- a pixel-to-
    
    """
    
    def __init__(self,
                 laser_delay_motor_pv_name,
                 tt_stage_position_pv_name,
                 t0_pv_name,
                 target_delay_pv_name,
                 laser_lock_pv_name):
                 
        
        self._laser_delay_motor  = EpicsPV(laser_delay_motor_pv_name)
        self._tt_stage_position  = EpicsPV(tt_stage_position_pv_name)
        self._t0                 = EpicsPV(t0_pv_name)
        self._target_delay       = EpicsPV(target_delay_pv_name)
        self._laser_lock         = EpicsPV(laser_lock_pv_name)
        
        self._tt_options = {get_key='TSS_OPAL',
                            eventcode_nobeam=162,
                            calib_poly='0 1 0',
                            sig_roi_x='0 1023',
                            sig_roi_y='425 724',
                            ref_avg_fraction=0.05,
                            eventcode_skip=0,
                            ipm_get_key='',
                            ipm_beam_threshold=0.0}
        self._set_options() # creates self._tt_analyze
        
        return
        
        
    def _set_options(**kwargs):
        
        for k in kwargs.keys():
            if k in self._tt_options:
                print 'Timetool option %s changed: %s --> %s' % (str(k),
                                                                 str(self._tt_options[k]),
                                                                 str(kwargs[k]))
            else:
                print 'Timetool option %s set: %s' % (str(k), str(kwargs[k]))
            self._tt_options[k] = kwargs[k]
        
        ttopt = TimeTool.AnalyzeOptions(self._tt_options)
        self._tt_analyze = TimeTool.PyAnalyze(ttopt)
        return
        
        
    def __call__(self, psana_event):
        """
        Filter the TT data and return the delay ** in fs units **.
        """
        tt_data = self._tt_analyze(psana_event)
        if not tt_data:
            return None
            
        else:
            
        
        
    @property
    def measurable_window(self):
        """
        Returns the time delay window (reliably) measurable in the current 
        position.
        """
        return
        
        
    @property
    def motor_position(self):
        return self._tt_stage_position.value
    
        
    def move_for_delay(self, delay_in_fs):
        
        return
        
        
    def calibrate(self, nevents_per_timestep=100):
        """
        Calibrate the pixel-to-fs conversion.
        """
        
        laser_motor_positions = [1,2,3] # FIGURE THIS OUT!
        
        # lock on to the FFB
        # hopefully there is a better way to get the run info...
        exp = DAQ.experiment()
        run = DAQ.runnumber()
        hutch = exp[:3]
        
        ds = psana.DataSource('exp=%s:run=%s:smd:dir=/reg/d/ffb/%s/%s/xtc:live'
                              '' % (exp, run, hutch, exp), module=self._tt_analyze)

        # >>> cycle over tt_motor_positions and collect TT traces
        #     we need to pass a python object telling the daq how many cycles
        #     to run and what to vary. then we launch an external thread to do
        #     that.
        for cycle in range(len(laser_motor_positions)):
            
            self._tt_stage_position.set( laser_motor_positions[cycle] )
            
            daq_config = { record=True,       
                           events=nevents_per_timestep,
                           controls=[ (self._laser_delay_motor.name, 
                                       self._laser_delay_motor.value) ]),
                           monitors=[]
                         }
            daq.threaded_scan(daq_config)
            
        # <<<
        
        # now we loop over events using psana and get the TT data out
        tt_calib_data = [] # list of tuples of (motor_pos, tt_edge)
        
        for evt in ds.events():
            
            # get
            tt_data = self._tt_analyze.process(evt)
            if tt_data:
                if not IS_REF_SHOT:
                    tt_calib_data.append( (motor_pos, tt_edge) )
            
        # now fit the calibration
        
        
        return