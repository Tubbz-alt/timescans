
import epics

class EpicsPV(object):
    
    def __init__(self, name):
        self.name = name
        self.chid = epics.ca.create_channel(name)
        self._value = epics.ca.get(self.chid)
        return
        
    def set(self ,value):                          # Step the motor/actuator
        epics.ca.put(self.chid,value,wait=True)
        self._value = value
        self._check()
        return
        
    def value(self):
        self._check_value()
        return self._value
        
    def _check(self):
        if not self._value == epics.ca.get(self.chid):
            raise RuntimeError('PV: %s setting does not match expected!' 
                               '' % self.name)
        return