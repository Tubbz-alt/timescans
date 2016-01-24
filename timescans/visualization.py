
"""
tools for making plots
"""

import time
import algorithms
import numpy as np
from lightning import Lightning


lgn = Lightning(host='http://psdb3:3000')


class RunPlots(object):

    def __init__(self, run_num, qs):

        self.run_num = run_num
        self.qs = qs
        self.session = lgn.create_session('Run %d' % run_num)
        

        self.las_diff = lgn.line(np.zeros_like(qs), index=qs,
                                 xaxis='q / A^{-1}', yaxis='Intensity',
                                 description='Run %d laser on minus laser off' % run_num)
        self.las_on_off = lgn.line([np.zeros_like(qs),]*2, index=qs,
                                   xaxis='q / A^{-1}', yaxis='Intensity',
                                   description='Run %d laser on (purple) / off (teal)' % run_num)

        #self.dt_vs_shot = lgn.linestreaming([0.0], max_width=10000,
        #                                     xaxis='Shot Index', yaxis='Laser Delay (fs)',
        #                                     description='Run %d time delay vs shot index' % run_num)
        #self.hist = lgn.histogram([0.0, 0.0], 100, zoom=True,
        #                          description='Histogram of time delays')

        self.image = None

        return


    def update_las_on_off(self, n_laser_on, laser_on_sum, n_laser_off, laser_off_sum):
        self.las_on_off.update([laser_on_sum/n_laser_on, laser_off_sum/n_laser_off])
        diff = laser_on_sum / n_laser_on - laser_off_sum / n_laser_off
        self.las_diff.update(diff)
        return


    def update_dts(self, dts):
        self.dt_vs_shot.append(dts)
        self.hist.update(dts)
        return


    def update_image(self, imagedata):
        if self.image is None:
            self.image = lgn.image(imagedata)
        else:
            self.image.update(imagedata)


if __name__ == '__main__':

    qs = np.linspace(0.5, 5.0, 101)
    rp = RunPlots(999, qs)

    for i in range(1000):

        qs = np.linspace(0.5, 5.0, 101)
        lon  = np.random.randn(101)
        loff = np.random.randn(101)
        non  = 100
        noff = 100

        rp.update_las_on_off(non, lon, noff, loff)
        rp.update_dts(np.random.randn(10))

        print i
        time.sleep(0.1)


