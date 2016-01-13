
"""
right now just a list of visualizations:
-- tt trace w/edge
-- scan/run computed delays over time, w/histogram
-- calibration: px to fs
-- options/parameters
"""

import os

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui

import numpy as np



def plot_calibration(edge_position_data, fit, slope, intercept, r_sq):

    raise NotImplementedError()
    return



def TimescanWidget(QtGui.QWidget):

    def __init__(self, communication_freq=50):
        
        super(TimescanWidget, self).__init__()
        
        self.setWindowTitle('Timescan Monitoring')
        self._draw_canvas()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.recv_data)
        self.timer.start(communication_freq)
        
        return


# - setting up the inital frame --------------------------------

    def _draw_canvas(self):
        """
        A catch-all function that draws all the sub-widgets that make up the GUI
        """
        
        layout = QtGui.QGridLayout()
        
        self.resize(1000, 600)
        
        self._draw_edge_fitting(layout)
        self._draw_parameters(layout)
        self._draw_delay_vs_shot(layout)
        
        self.setLayout(layout)
        
        return


    def _draw_edge_fitting(self, layout):

        graphics_layout = pg.GraphicsLayoutWidget(border=(100,100,100))
        
        self._edge_plot = graphics_layout.addPlot(title='TT Trace')
        self._edge_plot.setLabel('bottom', 'Pixels')
        self._edge_plot.setLabel('left', 'Intensity', units='AU')
        self._edge_plot.setYRange(0, 1024, update=False)

        return


    def _draw_delay_vs_shot(self, layout):
        """ includes the histgram """


        # delay vs shot


        # tilted histogram

        h = np.histogram2d(x, y, 30)
        w = pg.ImageView(view=pg.PlotItem())
        w.setImage(h[0])



        return


    def _draw_parameters(self, layout):
        """
        Generates a GUI that can accept parameter values.
        """
        
        params = [
                  {'name': 'events_per_bin', 'type': 'int', 
                       'value': 1000, 'suffix': 'ADU'},
                  {'name': 'bin_width', 'type': 'int',                
                       'value': 100, 'suffix': 'fs'},

                  {'name': 'shortest_delay', 'type': 'int',     
                       'value': -50, 'suffix': 'fs'},
                  {'name': 'longest_delay', 'type': 'int',     
                       'value': 1000, 'suffix': 'fs'},

                  {'name': 'scan_delay_list', 'type': 'str',
                       'value': os.path.abspath(os.curdir)},

                  {'name': 'randomize_bins', 'type': 'bool',
                       'value': True, 'suffix': '?'}
                 ]

        self._params = Parameter.create(name='params', type='group', 
                                        children=params)
        # self._params.sigTreeStateChanged.connect(...fxn...)

        t = ParameterTree()
        t.setParameters(self._params, showTop=False)
        
        layout.addWidget(t, 0, 1)
        
        return


    def _draw_scan_button(self, layout):
        
        self._scan_btn = QtGui.QPushButton('Scan')
        self._scan_btn.clicked.connect(self.scan)
        self._scan_btn.setStyleSheet("background-color: green")
        
        layout.addWidget(self._scan_btn, 4, 1)
        
        return
    
        
    def _draw_calibrate_button(self, layout):
        
        self._calibrate_btn = QtGui.QPushButton('Calibrate')
        self._calibrate_btn.clicked.connect(self.calibrate)
        self._calibrate_btn.setStyleSheet("background-color: red")
        
        layout.addWidget(self._calibrate_btn, 5, 1)
        
        return


# - taking action ---------------------------------------------

    # these should call external code, get the results, and
    # update the relevant plots

    def calibrate(self):
        return NotImplementedError()

    def scan(self):
        return NotImplementedError()

# - setting data/updating plots -------------------------------

    def _set_plot_data(self, hitrates, window_size):
 
        time_axis = np.arange(0.0, hitrates.shape[0], float(window_size)/120.0)
        
        for i,n in enumerate(self.threshold_names):
            self._lower_curves[i].setData( hitrates[:,i,0] )
            self._upper_curves[i].setData( hitrates[:,i,1] )
            
        return



def main():
    
    app = QtGui.QApplication(sys.argv)
    
    test_gui = TrapdoorWidget()
    test_gui._set_plot_data( np.zeros((300,3,2)), 120 )
    test_gui.show()
    
    print test_gui.hosts
    print test_gui.monitor_list
    
    sys.exit(app.exec_())
    
    return
    

if __name__ == '__main__':
    main()
