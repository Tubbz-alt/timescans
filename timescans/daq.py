
"""
https://confluence.slac.stanford.edu/display/PCDS/Python+Scripting#PythonScripting-ControllingtheDAQ-the%27pydaq%27module
"""

import pydaq

HOST     = 'cxi-daq'
PLATFORM = 0
DAQ      = pydaq.Control(host, platform)
        

def threaded_cycle(daq_config):
    return scan(daq_config)
    

def cycle(daq_config):
    """
    Perform a calibcycle.
    
    daq_config : dict
    """
    daq.configure(**daq_config)
    daq.begin()
    daq.end()    
    return