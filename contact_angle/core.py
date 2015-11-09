import mdtraj as md
import numpy as np
from scipy.optimize import leastsq
import pdb


def calc_contact_angle(traj, guess_R=1.0, guess_z0=0.0, guess_rho_n=1.0,
        n_fit=10, left_tol=0.1, z_range=None, surface_normal='z', n_bins=50):
    """Calculate contact angle from atoms in a trajectory

    This function takes a trajectory and calculates the conact angle with a 
    surface assuming the droplet is a spherical cap. This is achieved by fitting
    a parabolic number density profile to the number density profile calculated
    from the trajectory. The "top" of the droplet is taken to be where the fit
    number density profile goes to 0. The location of intersecting plane is 
    taken to be where the relative error between the fit number density profile
    and the measured number density profile falls below some specified
    tolerance. The radius of the base circle of the spherical cap and height are
    used to calculate the contact angle. 
    
    When using this function, note that...
    - erratic behavior may be encountered if the number density profile is noisy
      (e.g., from insufficient sampling, a drifting simulation, etc...), so
      double check that the number density profile is smooth
    - it is assumed that the droplet is spherical and that the vector from the
      base circle to the cap points in a positive direction
    - the values from the fitting are returned - make sure these make sense!
      Always confirm with a visualization of your system.

    Fixes I plan on implementing:
    - Better handling of "top/bottom" sherical cap: allow vector from base
      circle to cap to point in either positive or negative direction. This
      should be a fairly eaxy fix.
    - Calculation for cylindrical droplets.
    - Option to smooth number density profile.

    Args
    ----
    traj : MDTraj.Trajectory
        (Slice of) mdtraj trajectory containing the atoms in the droplet
    guess_R : float, optional, default=1.0
        Initial guess of radius of sphere
    guess_z0 : float, optional, default = 0.0
        Initial guess of center of sphere
    guess_rho_n : float, optional, default=1.0
        Initial guess of number density of droplet
    n_fit : int, optional, default=10
        Fit density profile to this many points from actual number density
    left_tol : float, optinoal, default=0.1
        Relative error used to determin location of intersecting plane
    z_range : (float, float), optional
        Lower and upper range of bins used for density profile
    surface_normal : str, optional, default='z'
        Assume surface normal parallel to this axis (x, y, or z)
    n_bins : int
        Number of bins to use in the histogram for number density profile

    Returns
    -------
    ret_d : dict
        Dictionary containing various values from the calculation, includes:
        - 'theta' : the calculated contact angle
        - 'z_fit' : values used for fitting density profile
        - 'R_fit' : radius of sphere
        - 'z0_fit' : center of sphere
        - 'rho_n_fit' : fitted number density of droplet
        - 'nz_fit' : fitted number density profile
        - 'nz_extrapolated' : fitted number density profile over full z range
        - 'height' : height of spherical cap
        - 'right_intercept' : calculated location of tip of sphere
        - 'left_intercept' : calculated location of intersecting plane
        - 'fit_error' : relative error between fit and measured density profile
        - 'nz' : calculated number density profile
        - 'z' : the z values of the number density profile

    """
    # make sure input parameters are compatible
    if n_bins <= n_fit:
        raise ValueError('n_bins must be greater than n_fit')
    ax3 = {'x': 0, 'y': 1, 'z': 2}
    hist, bins = np.histogram(traj[:, :, ax3[surface_normal]],
            bins=n_bins, range=z_range)
    p0 = [guess_R, guess_z0, guess_rho_n]
    hist = hist / float(len(traj))
    bins = bins[:-1] + 0.5 * (bins[1] - bins[0])
    idx_max = np.argmax(hist) + 1
    z_fit = bins[idx_max:idx_max+n_fit]
    nz_to_fit = hist[idx_max:idx_max+n_fit]
    fnz = leastsq(nz_error, p0, args=(nz_to_fit, z_fit))
    R_fit, z0_fit, rho_n_fit = fnz[0][0], fnz[0][1], fnz[0][2]
    nz_fit = calc_nz(z_fit, z0_fit, R_fit, rho_n_fit)
    full_nz_fit = calc_nz(bins, z0_fit, R_fit, rho_n_fit)
    right_intercept = z0_fit + R_fit
    error = np.absolute((full_nz_fit - hist)/hist)
    left_intercept = find_left_intercept(bins, error, left_tol)
    h = right_intercept - left_intercept
    contact_angle = angle_from_Rh(R_fit, h)
    ret_d = {'z_fit': z_fit, 'R_fit': R_fit, 'z0_fit': z0_fit,
             'rho_n_fit': rho_n_fit, 'nz_fit': nz_fit, 'nz': hist,
             'nz_extrapolated': full_nz_fit, 'height': h, 'z' : bins, 
             'right_intercept': right_intercept, 'left_intercept': left_intercept,
             'fit_error': error, 'theta': contact_angle}
    return ret_d

def angle_from_Rh(R, h):
    """Calculate contanct angle based on sphere radius and height above surface

    Args
    ----
    R : float
        Radius of sphere
    h : float
        Height of sphere above surface

    Returns
    -------
    theta : float
        Contact angle in degrees
    """
    alpha = np.arcsin((R - h) / R)
    if alpha > np.pi:
        alpha -= np.pi
    return np.rad2deg(np.pi/2 - alpha)

def nz_error(p, nz, z):
    R, z0, rho_n = p
    return nz - calc_nz(z, z0, R, rho_n)

def calc_nz(z, z0, R, rho_n):
    dz = np.absolute(z[1] - z[0])
    return rho_n * np.pi * dz * (R**2.0 - (z0 - z)**2.0)

def find_left_intercept(bins, error, tol):
    for i, value in enumerate(error[1:]):
        if value < tol and error[i] > tol:
            return 0.5 * (bins[i+1] + bins[i])

def print_contact_angle_results(ret_d):
    print ''
    print 'Contact angle fitting results'
    print '-----------------------------'
    print 'contact angle = ', ret_d['theta'], ' degrees'
    print 'R_fit = ', ret_d['R_fit']
    print 'z0_fit = ', ret_d['z0_fit']
    print 'rho_n_fit = ', ret_d['rho_n_fit']
    print 'height = ', ret_d['height']
    print 'right intercept = ', ret_d['right_intercept']
    print 'left intercept = ' , ret_d['left_intercept']

def print_contact_angle_fits(ca, filename='fit.txt'):
    x = np.vstack((ca['z'], ca['nz'], ca['nz_extrapolated'], ca['fit_error'])).T
    np.savetxt(filename, x)