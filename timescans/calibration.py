
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
    ssreg = ssq(y_hat - np.mean(y))
    sstot = ssq(y     - np.mean(y))
    r_sq = ssreg / sstot
    
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


def analyze_calibration_run(exp, run, las_delay_pvname, ffb=True):
    """
    Analyze a run where the timetool camera is fixed but the laser delay
    changes by a known amount in order to calibrate the TT camera pixel-
    time conversion.
    """

    import psana

    if ffb:
        ds = psana.DataSource('exp=%s:run=%d:dir=/reg/d/ffb/%s/%s:smd:live'
                              '' % (exp, run, exp[:3], exp))
    else:
        ds = psana.DataSource('exp=%s:run=%d' % (exp, run))

    las_dly = psana.Detector(las_delay_pvname, ds.env())
    tt_edge = psana.Detector('CXI:TTSPEC:FLTPOS', ds.env())

    print 'analyzing shots...'    
    delay_pxl_data = []
    for i,evt in enumerate(ds.events()):
        # >>> TJL note, may want to perform some checks on e.g. TT peak heights, etc
        delay_pxl_data.append([ tt_edge(evt), las_dly(evt) ])
        #if i == 1000: break # debugging
        
    delay_pxl_data = np.array(delay_pxl_data)
    print "Analyzing %d events" % delay_pxl_data.shape[0]

    # from docs >> fs_result = a + b*x + c*x^2, x is edge position
    fit = np.polyfit(delay_pxl_data[:,0], delay_pxl_data[:,1], 2)
    c, b, a = fit
    p = np.poly1d(fit)

    r_sq, rmes = fit_errors(delay_pxl_data[:,0], delay_pxl_data[:,1], 
                            p(delay_pxl_data[:,1]), 0.0001)

    plt.figure()
    plt.plot(delay_pxl_data[:,0], delay_pxl_data[:,1], '.')
    plt.plot(delay_pxl_data[:,0], p(delay_pxl_data[:,1]),'r-')
    plt.plot(rmes[:,0], rmes[:,1] - rmes[:,2],'k-')
    plt.plot(rmes[:,0], rmes[:,1] + rmes[:,2],'k-')
    plt.xlabel('Edge Position (pixels) [TTSPEC:FLTPOS]')
    plt.ylabel('Laser Delay (ps) [%s]' % las_delay_pvname)
    plt.show()

    # push results upstream to DAQ config

    # save results to calib dir

    return



if __name__ == '__main__':
    analyze_calibration_run('cxii2415', 65, 'LAS:FS5:VIT:FS_TGT_TIME_OFFSET', ffb=False)
    

