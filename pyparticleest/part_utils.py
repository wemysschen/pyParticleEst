""" Collection of functions and classes used for Particle Filtering/Smoothing """
import abc
import kalman
import numpy
import copy
import math
# This was slower than kalman.lognormpdf
#from scipy.stats import multivariate_normal

class ParticleFilteringInterface(object):
    """ Base class for particles to be used with particle filtering """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def create_initial_estimate(self, N):
        """ Sample N particle from initial distribution """
        return
     
    @abc.abstractmethod
    def sample_process_noise(self, particles, u):
        """ Return process noise for input u """
        return
    
    @abc.abstractmethod
    def update(self, particles, u, noise):
        """ Update estimate using 'data' as input """
        return
    
    @abc.abstractmethod    
    def measure(self, particles, y):
        """ Return the log-pdf value of the measurement """
        return
    
class FFBSiInterface(ParticleFilteringInterface):
    """ Base class for particles to be used with particle smoothing """
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractmethod
    def next_pdf(self, particles, next_cpart, u=None):
        """ Return the log-pdf value for the possible future state 'next' given input u """
        pass
    
    @abc.abstractmethod
    def sample_smooth(self, particles, next_part, u=None):
        """ Update ev. Rao-Blackwellized states conditioned on "next_part" """
        pass

class FFBSiRSInterface(FFBSiInterface):
    __metaclass__ = abc.ABCMeta
    @abc.abstractmethod
    def next_pdf_max(self, particles, u=None):
        """ Return the log-pdf value for the possible future state 'next' given input u """
        pass
    
class RBPFBase(ParticleFilteringInterface):
    """ Base class for Rao-Blackwellized particles """
    __metaclass__ = abc.ABCMeta
    
    def __init__(self, Az=None, fz=None, Qz=None,
                 C=None ,hz=None, R=None, t0=0):
        
        self.kf = kalman.KalmanSmoother(A=Az, C=C, 
                                        Q=Qz, R=R,
                                        f_k=fz, h_k=hz)
        
        self.t = t0
        
    def set_dynamics(self, Az=None, C=None, Qz=None, R=None, fz=None, hz=None):
        return self.kf.set_dynamics(Az, C, Qz, R, fz, hz)
    
    def get_nonlin_pred_dynamics(self, particles, u):
        """ Return matrices describing affine relation of next
            nonlinear state conditioned on current linear state
            
            xi_{t+1]} = A_xi * z_t + f_xi + v_xi, v_xi ~ N(0,Q_xi)
            
            Return (A_xi, f_xi, Q_xi) where each element is a list
            with the corresponding matrix for each particle. None indicates
            that the matrix is identical for all particles and the value stored
            in this class should be used instead
            """
        return (None, None, None)
    
    def get_nonlin_pred_dynamics_int(self, particles, u):
        (Axi, fxi, Qxi) = self.get_nonlin_pred_dynamics(particles, u)
        N = len(particles)
        # This is probably not so nice performance-wise, but will
        # work initially to profile where the bottlenecks are.
        if (Axi == None):
            Axi=N*(self.Axi,)
        if (fxi == None):
            fxi=N*(self.fxi,)
        if (Qxi == None):
            Qxi= N*(self.Qxi,)
        return (Axi, fxi, Qxi)
    
    def get_condlin_pred_dynamics(self, u, xi_next, particles):
        """ Return matrices describing affine relation of next
            nonlinear state conditioned on current linear state
            
            z_{t+1]} = A_z * z_t + f_z + v_z, v_z ~ N(0,Q_z)
            
            conditioned on the value of xi_{t+1}. 
            (Not the same as the dynamics unconditioned on xi_{t+1})
            when for example there is a noise correlation between the 
            linear and nonlinear state dynamics) 
            """
        return (None, None, None)
    
    def get_lin_pred_dynamics(self, particles, u):
        """ Return matrices describing affine relation of next
            nonlinear state conditioned on current linear state
            
            \z_{t+1]} = A_z * z_t + f_z + v_z, v_z ~ N(0,Q_z)
            
            conditioned on the value of xi_{t+1}. 
            (Not the same as the dynamics unconditioned on xi_{t+1})
            when for example there is a noise correlation between the 
            linear and nonlinear state dynamics) 
            """
        return (None, None, None)
    
    def get_lin_pred_dynamics_int(self, particles, u):
        N = len(particles)
        (Az, fz, Qz) = self.get_lin_pred_dynamics(particles, u)
        if (Az == None):
            #Az=numpy.repeat(self.kf.A[numpy.newaxis,:,:], N, axis=0)
            Az=N*(self.kf.A,)
        if (fz == None):
            #fz=numpy.repeat(self.kf.f_k[numpy.newaxis,:,:], N, axis=0)
            fz=N*(self.kf.f_k,)
        if (Qz == None):
            Qz=numpy.repeat(self.kf.Q[numpy.newaxis,:,:], N, axis=0)
            #Qz=N*(self.kf.Q,)
        return (Az, fz, Qz)
    
    def get_meas_dynamics(self, particles, y):
        return (y, None, None, None)
    
    def get_meas_dynamics_int(self, particles, y):
        N=len(particles)
        (y, Cz, hz, Rz) = self.get_meas_dynamics(particles=particles, y=y)
        if (Cz == None):
            Cz=N*(self.kf.C,)
        if (hz == None):
            hz=N*(self.kf.h_k,)
        if (Rz == None):
            Rz=N*(self.kf.R,)
        return (y, Cz, hz, Rz)
    
# This is not implemented  
#    def get_condlin_meas_dynamics(self, y, xi_next, particles):
#        return (y, None, None, None)
    
    def update(self, particles, u, noise):
        """ Update estimate using noise as input """
        # Calc (xi_{t+1} | xi_t, z_t, y_t)
        xin = self.calc_xi_next(particles=particles, noise=noise, u=u)
        # Calc (z_t | xi_{t+1}, y_t)
        self.meas_xi_next(particles=particles, xi_next=xin, u=u)
        # Calc (z_{t+1} | xi_{t+1}, y_t)
        self.cond_predict(particles=particles, xi_next=xin, u=u)
        
        (_xil, zl, Pl) = self.get_states(particles)
        self.set_states(particles, xin, zl, Pl)
        self.t = self.t + 1.0


    
class RBPSBase(RBPFBase, FFBSiInterface):
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractmethod
    def get_rb_initial(self, xi_initial):
        pass    

