
"""
tools for making plots
"""

import time
import algorithms
import numpy as np
from lightning import Lightning


lgn = Lightning()


class RunPlots(object):

    def __init__(self, run_num, qs):

        self.run_num = run_num
        self.qs = qs
        self.session = lgn.create_session('Run %d' % run)
        

        self.las_on_off = lgn.scatter(qs, np.zeros_like(qs),
                                      xaxis='q / A^{-1}', yaxis='Intensity',
                                      description='Run %d laser on minus laser off' % run_num)
        self.dt_vs_shot = lgn.line([0.0], xaxis='Shot Index', yaxis='Laser Delay (fs)',
                               description='Run %d time delay vs shot index' % run_num)
        self.hist = lgn.histogram([0.0, 0.0], 100, zoom=True, xaxis='Laser Delay (fs)',
                                  yaxis='Number of Shots', 
                                  description='Histogram of time delays')

        return


    def update_las_on_off(self, n_laser_on, laser_on_sum, n_laser_off, laser_off_sum):
        diff = algorithms.normalize(qs, laser_on_sum) - algorithms.normalize(qs, laser_off_sum) ]
        self.las_on_off.update(qs, diff)
        return


    def update_dts(self, dts):
        self.dt_vs_shot.update(dts)
        self.hist.update(dts)
        return
    






if __name__ == '__main__':

    qs = np.linspace(0.5, 5.0, 101)
    rp = RunPlots(999, qs)

    for i in range(1000):

        qs = np.linspace(0.5, 5.0, 101)
        lon  = np.random.randn(101)
        loff = np.random.randn(101)
        non  = 100
        noff = 100

        rp.update_las_on_off(qs, non, lon, noff, loff)

        print i
        time.sleep(0.1)


