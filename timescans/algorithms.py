#!/usr/bin/env python

"""
A grab-bag of algorithms we'll need...
"""

import os
import h5py

import numpy as np


class RadialAverager(object):

    def __init__(self, q_values, mask, n_bins=101):
        """
        Parameters
        ----------
        q_values : np.ndarray (float)
            For each pixel, this is the momentum transfer value of that pixel
        mask : np.ndarray (int)
            A boolean (int) saying if each pixel is masked or not
        n_bins : int
            The number of bins to employ. If `None` guesses a good value.
        """

        self.q_values = q_values
        self.mask = mask
        self.n_bins = n_bins

        self.q_range = self.q_values.max() - self.q_values.min()
        self.bin_width = self.q_range / (float(n_bins) - 1)

        self._bin_assignments = np.floor( (self.q_values - self.q_values.min()) / self.bin_width ).astype(np.int32)
        self._normalization_array = (np.bincount( self._bin_assignments.flatten(), weights=self.mask.flatten() ) \
                                    + 1e-100).astype(np.float)

        assert self.n_bins >= self._bin_assignments.max() + 1, 'incorrect bin assignments'
        self._normalization_array = self._normalization_array[:self.n_bins]

        return
    

    def __call__(self, image):
        """
        Bin pixel intensities by their momentum transfer.
        
        Parameters
        ----------            
        image : np.ndarray
            The intensity at each pixel, same shape as pixel_pos


        Returns
        -------
        bin_centers : ndarray, float
            The q center of each bin.

        bin_values : ndarray, int
            The average intensity in the bin.
        """

        if not (image.shape == self.q_values.shape):
            raise ValueError('`image` and `q_values` must have the same shape')
        if not (image.shape == self.mask.shape):
            raise ValueError('`image` and `mask` must have the same shape')

        weights = image.flatten() * self.mask.flatten()
        bin_values = np.bincount(self._bin_assignments.flatten(), weights=weights)
        bin_values /= self._normalization_array

        assert bin_values.shape[0] == self.n_bins

        return bin_values
    

    @property
    def bin_centers(self):
        return (np.arange(self.n_bins) + 0.5) * self.bin_width + self.q_values.min()
        
        
def update_average(n, A, B):
    """
    updates a numpy matrix A that represents an average over the previous n-1 shots
    by including B into the average, B being the nth shot
    """
    if n == 0:
        A += B
        return
    else:
        A *= (n-1)/float(n)
        A += (1.0/float(n))*B
        return
        
        
def normalize(q_values, intensities, q_min=0.5, q_max=3.5):
    """
    Crop and normalize an I(q) vector st. the area under the curve is one.
    """
    assert q_values.shape == intensities.shape
    inds = (q_values > q_min) * (q_values < q_max)
    factor = float(np.sum(intensities[inds])) / float(np.sum(inds))
    return intensities / factor


def differential_integral(laser_on, laser_off, q_values, q_min=1.0, q_max=2.5):
    """
    Compute the following
    
        DI = \int_{q0}^{q1} | lazer_on(q) - lazer_off(q) | dq
        
    Useful for tracking changes in the scattering.
    """
    percent_diff = (laser_on - laser_off) / laser_on
    inds = (q_values > q_min) * (q_values < q_max)
    di = np.abs(np.sum( precent_diff[inds] ))
    return di


def thor_to_psana(thor_fmt_intensities):

    if thor_fmt_intensities.shape == (4, 16, 185, 194):
        ii = thor_fmt_intensities
    elif thor_fmt_intensities.shape == (2296960,):
        ii = thor_fmt_intensities.reshape((4, 16, 185, 194))
    else:
        raise ValueError('did not understand intensity shape: '
                         '%s' % str(thor_fmt_intensities.shape))

    ix = np.zeros((32, 185, 388), dtype=thor_fmt_intensities.dtype)
    for i in range(4):
        for j in range(8):
            a = i * 8 + j
            ix[a,:,:] = np.hstack(( ii[i,j*2,:,:], ii[i,j*2+1,:,:] ))

    return ix
   

def recpolar_convert(thor_recpolar):
    if thor_recpolar.shape != (2296960, 3):
        raise ValueError()

    new = np.zeros((3, 32, 185, 388), dtype=thor_recpolar.dtype)
    for i in range(3):
        new[i,:,:,:] = thor_to_psana(thor_recpolar[:,i])
    
    return new





