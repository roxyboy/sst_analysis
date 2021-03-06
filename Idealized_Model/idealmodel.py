import numpy as np
#import netCDF4
from warnings import warn
from scipy import linalg as lin
from scipy import signal as sig
from scipy import fftpack as fft
from scipy import interpolate as naiso
from scipy import io
import gfd

class IDEALFile(object):
    
    def __init__(self, fname):
        """Wrapper for Idealized model matlab files"""
        self.mat = io.loadmat(fname)
        self.Ny, self.Nx = self.mat['bC'].shape     
        #self._ah = ah
        
        # mask
        #self.mask = self.nc.variables['KMT'][:] <= 1

        #self.is3d = is3d
        #if self.is3d:
        #    self.z_t = nc.variables['z_t'][:]
        #    self.z_w_top = nc.variables['z_w_top'][:]
        #    self.z_w_bot = nc.variables['z_w_bop'][:]
        #    self.Nz = len(self.z_t)
        #    kmt = p.nc.variables['KMT'][:]
        #    self.mask3d = np.zeros((self.Nz, self.Ny, self.Nx), dtype='b')
        #    Nz = mask3d.shape[0]
        #    for k in range(Nz):
        #        self.mask3d[k] = (kmt<=k)

    #def mask_field(self, T):
    #    """Apply mask to tracer field T"""
    #    return np.ma.masked_array(T, self.mask)
        
    #def initialize_gradient_operator(self):
    #    """Needs to be called before calculating gradients"""
    #    # raw grid geometry
    #    work1 = (self.nc.variables['HTN'][:] /
    #             self.nc.variables['HUW'][:])
    #    tarea = self.nc.variables['TAREA'][:]
    #    self.tarea = tarea
    #    tarea_r = np.ma.masked_invalid(tarea**-1).filled(0.)
    #    dtn = work1*tarea_r
    #    dts = np.roll(work1,-1,axis=0)*tarea_r
    #    
    #    work1 = (self.nc.variables['HTE'][:] /
    #             self.nc.variables['HUS'][:])
    #    dte = work1*tarea_r
    #    dtw = np.roll(work1,-1,axis=1)*tarea_r
    #    
    #    # boundary conditions
    #    kmt = self.nc.variables['KMT'][:] > 1
    #    kmtn = np.roll(kmt,-1,axis=0)
    #    kmts = np.roll(kmt,1,axis=0)
    #    kmte = np.roll(kmt,-1,axis=1)
    #    kmtw = np.roll(kmt,1,axis=1)
    #    self._cn = np.where( kmt & kmtn, dtn, 0.)
    #    self._cs = np.where( kmt & kmts, dts, 0.)
    #    self._ce = np.where( kmt & kmte, dte, 0.)
    #    self._cw = np.where( kmt & kmtw, dtw, 0.)
    #    self._cc = -(self._cn + self._cs + self._ce + self._cw)
    #    
    #    # mixing coefficients
    #    #self._ah = -0.2e20*(1280.0/self.Nx)
    #    j_eq = np.argmin(self.nc.variables['ULAT'][:,0]**2)
    #    self._ahf = (tarea / self.nc.variables['UAREA'][j_eq,0])**1.5
    #    self._ahf[self.mask] = 0.   
    #    
    #    # stuff for gradient
    #    # reciprocal of dx and dy (in meters)
    #    self._dxtr = 100.*self.nc.variables['DXT'][:]**-1
    #    self._dytr = 100.*self.nc.variables['DYT'][:]**-1
    #    self._kmaske = np.where(kmt & kmte, 1., 0.)
    #    self._kmaskn = np.where(kmt & kmtn, 1., 0.)
    #    
    #    self._dxu = self.nc.variables['DXU'][:]
    #    self._dyu = self.nc.variables['DYU'][:]
                
    def laplacian(self, T):
        """Returns the laplacian of T at the tracer point."""
        return (
            self._cc*T +
            self._cn*np.roll(T,-1,axis=0) +
            self._cs*np.roll(T,1,axis=0) +
            self._ce*np.roll(T,-1,axis=1) +
            self._cw*np.roll(T,1,axis=1)          
        )
        
    def gradient_modulus(self, T):
        """Return the modulus of the gradient of T at the tracer point."""
        dTx = self._kmaske * (np.roll(T,-1,axis=0) - T)
        dTy = self._kmaskn * (np.roll(T,-1,axis=1) - T)
        
        return np.sqrt( 0.5 *
                    (dTx**2 + np.roll(dTx,1,axis=0)**2) * self._dxtr**2
                   +(dTy**2 + np.roll(dTy,1,axis=1)**2) * self._dytr**2
        )        
        
    def power_spectrum_2d(self, varname='bT', nbins=512, detre=False, windw=False,  grad=False):
        """Calculate a two-dimensional power spectrum of netcdf variable 'varname'
           in the box defined by lonrange and latrange.
        """
 
        # step 1: load the data
        #T = np.roll(self.nc.variables[varname],-1000)[..., jmin:jmax, imin:imax]
        T = self.mat[varname][:]
        Ny, Nx = T.shape
        dx = 1e3
        dy = 1e3

        # Wavenumber step
        k = 2*np.pi*fft.fftshift(fft.fftfreq(Nx, dx))
        l = 2*np.pi*fft.fftshift(fft.fftfreq(Ny, dy))

        ##########################################
        ### Start looping through each time step #
        ##########################################
        #Nt = T.shape[0]
        #PSD_2d = np.zeros((Ny,Nx))
        #for n in range(Nt):
        
        Ti = T.copy()
            
        # step 2: detrend the data in three dimensions (least squares plane fit)
        if detre:
            print 'Detrending Data'
            d_obs = np.reshape(Ti, (Nx*Ny,1))
            G = np.ones((Ny*Nx,3))
            for i in range(Ny):
                G[Nx*i:Nx*i+Nx, 0] = i+1
                G[Nx*i:Nx*i+Nx, 1] = np.arange(1, Nx+1)    
            m_est = np.dot(np.dot(lin.inv(np.dot(G.T, G)), G.T), d_obs)
            d_est = np.dot(G, m_est)
            Lin_trend = np.reshape(d_est, (Ny, Nx))
            Ti -= Lin_trend

        # step 3: window the data
        if windw:
            print 'Windowing Data'
            # Hanning window
            windowx = sig.hann(Nx)
            windowy = sig.hann(Ny)
            window = windowx*windowy[:,np.newaxis] 
            Ti *= window
            
        if grad:
            Ti = (np.roll(Ti,1,axis=1)-Ti) / dx
        
        spac2_2d = Ti**2  
        # step 4: do the FFT for each timestep
        Tif = fft.fftshift(fft.fft2(Ti))
        dk = np.diff(k)[0]*0.5/np.pi
        dl = np.diff(l)[0]*0.5/np.pi
        tilde2_2d = np.real(Tif*np.conj(Tif))
        breve2_2d = tilde2_2d/((Nx*Ny)**2*dk*dl)
        np.testing.assert_almost_equal(breve2_2d.sum()/(dx*dy*(spac2_2d.sum())), 1., decimal=5)

        # step 5: derive the isotropic spectrum
        kk, ll = np.meshgrid(k, l)
        K = np.sqrt(kk**2 + ll**2)
        #Ki = np.linspace(0, k.max(), nbins)
        Ki = np.linspace(0, K.max(), nbins)
        deltaKi = np.diff(Ki)[0]
        Kidx = np.digitize(K.ravel(), Ki)
        area = np.bincount(Kidx)
        #isotropic_spectrum = 2.* np.ma.masked_invalid(
        #                                       np.bincount(Kidx, weights=(dx*dy/Nx/Ny*PSD_2d*K*2.*np.pi).ravel()) / area )
        isotropic_spectrum = 2.* np.ma.masked_invalid(
                                               np.bincount(Kidx, weights=(breve2_2d).ravel()) / area )[1:] * Ki*2.*np.pi/deltaKi
        
        # step 6: return the results
        return nbins, Nx, Ny, k, l, spac2_2d, tilde2_2d, breve2_2d, Ki, isotropic_spectrum, area[1:]

    def structure_function(self, varname='bT', q=2, detre=False, windw=False, iso=False):
        """Calculate a structure function of Matlab variable 'varname'
           in the box defined by lonrange and latrange.
        """        

        # load data
        T = self.mat[varname][:]

        # define variables
        Ny, Nx = T.shape
        n = np.arange(0,np.log2(Nx/2), dtype='i4')
        ndel = len(n)
        L = 2**n
        Hi = np.zeros(ndel)
        Hj = np.zeros(ndel)
        sumcounti = np.zeros(ndel)
        sumcountj = np.zeros(ndel)

        Ti = T.copy()
        # detrend data
        if detre:
            print 'Detrending Data'
            d_obs = np.reshape(Ti, (Nx*Ny,1))
            G = np.ones((Ny*Nx,3))
            for i in range(Ny):
                G[Nx*i:Nx*i+Nx, 0] = i+1
                G[Nx*i:Nx*i+Nx, 1] = np.arange(1, Nx+1)
            m_est = np.dot(np.dot(lin.inv(np.dot(G.T, G)), G.T), d_obs)
            d_est = np.dot(G, m_est)
            Lin_trend = np.reshape(d_est, (Ny, Nx))
            Ti -= Lin_trend

        # window the data
        if windw:
            print 'Windowing Data'
            windowx = sig.hann(Nx)
            windowy = sig.hann(Ny)
            window = windowx*windowy[:,np.newaxis]
            Ti *= window

        # Difference with 2^m gridpoints in between
        if iso:
        # Calculate structure functions isotropically
            #print 'Isotropic Structure Function'
            angle = np.arange(0,2.*np.pi,np.pi/180.)
            radi = np.arange(0,Nx/2,1)
            ang_index = len(angle)
            rad_index = len(radi)
            polar_coodx = np.zeros((ang_index,rad_index))
            polar_coody = np.zeros_like(polar_coodx)
            for j in range(ang_index):
                for i in range(rad_index):
                    polar_coodx[j,i] = radi[j,i]*np.cos(angle[j,i])
                    polar_coody[j,i] = radi[j,i]*np.sin(angle[j,i])
            Sq = np.zeros((ang_index/2,Nx))
            # Unfinished script (This option does not work)
        else:
        # Calculate structure functions along each x-y axis
            #print 'Anisotropic Structure Function'
            for m in range(ndel):
                #dSSTi = np.zeros((Ny,Nx))
                #dSSTj = np.zeros((Ny,Nx))
                # Take the difference by displacing the matrices along each axis 
                #dSSTi = np.ma.masked_array((np.absolute(Ti[:,2**m:] - Ti[:,:-2**m]))**2) # .filled(0.)
                #dSSTj = np.ma.masked_array((np.absolute(Ti[2**m:] - Ti[:-2**m]))**2) # .filled(0.)
                # Take the difference by specifying the grid spacing
                #for i in range(Nx):
                #    if i+2**m<Nx:
                #        dSSTi[:,:Nx-2**m] = np.ma.masked_array(
                #                               (np.absolute(Ti[:,2**m:] - Ti[:,:-2**m]))**q)
                #    else:
                #        dSSTi[:,i] = np.ma.masked_array(
                #                               (np.absolute(Ti[:,i+2**m-Nx] - Ti[:,i]))**q)
                #for j in range(Ny):    
                #    if j+2**m<Ny:
                #        dSSTj[:Ny-2**m] = np.ma.masked_array(
                #                               (np.absolute(Ti[2**m:] - Ti[:-2**m]))**q)
                #    else:
                #        dSSTj[j,:] = np.ma.masked_array(
                #                               (np.absolute(Ti[j+2**m-Ny,:] - Ti[j,:]))**q)
                # Use roll function
                dSSTi = np.abs(Ti - np.roll(Ti,2**m,axis=1))**q
                dSSTj = np.abs(Ti - np.roll(Ti,2**m,axis=0))**q
                #counti = (~dSSTi.mask).astype('i4')
                #countj = (~dSSTj.mask).astype('i4'
                #sumcounti[m] = np.sum(counti)
                #sumcountj[m] = np.sum(countj)
                #Hi[m] = np.sum(np.absolute(dSSTi))/sumcounti[m]
                #Hj[m] = np.sum(np.absolute(dSSTj))/sumcountj[m]
                #Hi[m] = np.sum(dSSTi)/Ny
                #Hj[m] = np.sum(dSSTj)/Nx
                Hi[m] = dSSTi.mean()
                Hj[m] = dSSTj.mean()
    
            return L, Hi, Hj
        

