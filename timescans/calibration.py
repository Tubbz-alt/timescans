
import os
import numpy as np
from matplotlib import pyplot as plt


def fit_errors(x, y, y_hat, bin_size):
    """
    Compute errors for fit both 'locally' and 'globally'.

    Specifically, the R^2 statistic is computed as usual (global).
    Additionally, the data are binned across the domain (x > bin_size)
    and for each bin an RMSE is computed.

    Parameters
    ----------
    x, y, y_hat : np.ndarray
       Equal-length 1D arrays of the domain, range, and prediction
       respectively.

    bin_size : float
       The resolution in which to bin `x` for local error computation.


    Returns
    -------
    r_sq : float
        The usual R^2 statistic.

    rmes : np.ndarray
        A 2D array of local errors. The first column is the bin center of
        mass (mean of x's in the bin), the second column is the prediction
        averaged across that bin (mean of y_hat's in the bin), the final
        column is the RMSE for the prediction in that bin.

    Example
    -------
    >>> r_sq, rmes = fit_errors(x, y, y_hat)

    >>> plot(x,y,'.')
    >>> plot(x,y_hat,'-')
    
    >>> plot(rmes[:,0],rmes[:,1] - rmes[:,2],'k-')
    >>> plot(rmes[:,0],rmes[:,1] + rmes[:,2],'k-')
    """

    ssq = lambda x : np.sum(np.square(x))
    
    # global R^2
    ssres = ssq(y - y_hat)
    sstot = ssq(y - np.mean(y))
    r_sq = 1.0 - ssres / sstot
    
    # per-bin RME
    bins = np.arange(x.min(), x.max()+bin_size*2, bin_size)
    assign = np.digitize(x, bins)
    uq = np.unique(assign)
    rmes = np.zeros((len(uq), 3))
    
    # get all x's that fall in a bin & compute rme
    for i,u in enumerate(uq):
        idx = (assign == u) # index of pts in bin
        rmes[i,0] = np.mean(x[idx])
        rmes[i,1] = np.mean(y_hat[idx])
        rmes[i,2] = np.sqrt(ssq( y[idx] - y_hat[idx] ) / np.sum(idx) )
    
    return r_sq, rmes


def analyze_calibration_run(exp, run, las_delay_pvname, px_cutoffs=(200, 800)):
    """
    Analyze a run where the timetool camera is fixed but the laser delay
    changes by a known amount in order to calibrate the TT camera pixel-
    time conversion.
    """

    import psana
    ds = psana.DataSource('exp=%s:run=%d:smd' % (exp, run))


    las_dly = psana.Detector(las_delay_pvname, ds.env())
    tt_edge = psana.Detector('CXI:TTSPEC:FLTPOS', ds.env())
    tt_famp = psana.Detector('CXI:TTSPEC:AMPL', ds.env())
    tt_fwhm = psana.Detector('CXI:TTSPEC:FLTPOSFWHM', ds.env())

    delay_pxl_data = []
    for i,evt in enumerate(ds.events()):
        print "analyzing event: %d\r" % (i+1),

        # perform some checks on the fit amp and fwhm
        if (tt_fwhm(evt) > 300.0) or (tt_fwhm(evt) < 50.0): continue
        if (tt_famp(evt) < 0.05): continue

        edge = tt_edge(evt)
        if (px_cutoffs[0] <= edge) and (edge <= px_cutoffs[1]):
            delay_pxl_data.append([ tt_edge(evt), las_dly(evt) ])

        #if i == 5000: break # debugging

        
    delay_pxl_data = np.array(delay_pxl_data)
    print "Analyzing in-range %d events" % delay_pxl_data.shape[0]

    out_path = os.path.join(os.environ['HOME'], 
                            'tt_calib_data_%s_r%d.txt' % (exp, run))
    print "saving raw calibration data --> %s" % out_path
    np.savetxt(out_path, delay_pxl_data)


    # from docs >> fs_result = a + b*x + c*x^2, x is edge position
    fit = np.polyfit(delay_pxl_data[:,0], delay_pxl_data[:,1], 2)
    c, b, a = fit * 1000.0
    p = np.poly1d(fit)

    r_sq, rmes = fit_errors(delay_pxl_data[:,0], delay_pxl_data[:,1], 
                            p(delay_pxl_data[:,0]), 50)

    print "\nFIT RESULTS"
    print "ps_result = a + b*x + c*x^2,  x is edge position"
    print "------------------------------------------------"
    print "a = %.12f" % a
    print "b = %.12f" % b
    print "c = %.12f" % c
    print "R^2 = %f" % r_sq
    print "------------------------------------------------"
    print "fit range (tt pixels): %d <> %d" % px_cutoffs
    print "time range (fs):       %f <> %f" % ( p(px_cutoffs[0]), 
                                                p(px_cutoffs[1]) )
    print "------------------------------------------------"


    x = np.linspace(delay_pxl_data[:,0].min(), delay_pxl_data[:,0].max(), 101)

    # make a plot
    plt.figure()
    plt.plot(delay_pxl_data[:,0], delay_pxl_data[:,1], '.')
    plt.plot(x, p(x),'r-')
    plt.plot(rmes[:,0], rmes[:,1] - rmes[:,2]*3,'k-')
    plt.plot(rmes[:,0], rmes[:,1] + rmes[:,2]*3,'k-')
    plt.legend(['events', 'fit', '-3 $\sigma$', '+3 $\sigma$'])
    plt.xlabel('Edge Position (pixels) [TTSPEC:FLTPOS]')
    plt.ylabel('Laser Delay (ps) [%s]' % las_delay_pvname)
    plt.xlim([0, 1024])

    plt.show()


    # push results upstream to DAQ config


    # save results to calib dir



    return



if __name__ == '__main__':
    analyze_calibration_run('cxii2415', 65, 'LAS:FS5:VIT:FS_TGT_TIME_DIAL', ffb=False)
    

