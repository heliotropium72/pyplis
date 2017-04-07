# -*- coding: utf-8 -*-
"""Module containing high level functionality for emission rate analysis
"""
from warnings import warn
from numpy import dot, sqrt, mean, nan, isnan, asarray, nanmean, nanmax,\
    nanmin, sum
from matplotlib.dates import DateFormatter
from collections import OrderedDict as od
from matplotlib.pyplot import subplots
from os.path import join, isdir
from os import getcwd

from pandas import Series, DataFrame
try:
    from scipy.constants import N_A
except:
    N_A = 6.022140857e+23

MOL_MASS_SO2 = 64.0638 #g/mol

from .imagelists import ImgList
from .plumespeed import LocalPlumeProperties  
from .processing import LineOnImage  
from .helpers import map_roi, check_roi, exponent

class EmissionRateSettings(object):
    """Class for management of settings for emission rate retrievals"""
    def __init__(self, pcs_lines=[], velo_glob=nan, velo_glob_err=nan, 
                 **settings):
        self.velo_modes = od([("glob"               ,   True),
                              ("farneback_raw"      ,   False),
                              ("farneback_histo"    ,   False),
                              ("farneback_hybrid"   ,   False)])
                              
        self.pcs_lines = od() 
        
        # Dictionary that will be filled with flags (in method add_pcs_line) 
        # specifying whether or not local plume displacement information 
        # (class LocalPlumeProperties, retrieved using optical flow histogram 
        # analysis) are available in within the provided LineOnImage objects
        # along which the emission rates are retrieved.
        self.plume_props_available = od()
        
        self._velo_glob = nan
        self._velo_glob_err = nan
        self.velo_glob = velo_glob
        self.velo_glob_err = velo_glob_err
        
        self.senscorr = True #apply AA sensitivity correction
        self.min_cd = -1e30 #minimum required column density for retrieval [cm-2]
        self.mmol = MOL_MASS_SO2
        
        try:
            len(pcs_lines)
        except:
            pcs_lines = [pcs_lines]
        
        for line in pcs_lines:
            self.add_pcs_line(line)
            
        for key, val in settings.iteritems():
            self[key] = val
        
        if self.velo_modes["glob"]:
            if not self._check_velo_glob_access():
                warn("Deactivating velocity retrieval mode glob, since global"
                    " velocity was not provided")
                self.velo_modes["glob"] = False
        if not sum(self.velo_modes.values()) > 0:
            warn("All velocity retrieval modes are deactivated")
    
    def _check_velo_glob_access(self):
        """Checks if global velocity information is accessible for all lines"""
        vglob = self.velo_glob
        if not isnan(float(vglob)):
            return True
        for l in self.pcs_lines.values():
            try:
                l.velo_glob
            except:
                return False
        return True
        
    @property
    def velo_mode_glob(self):
        """Attribute velo_glob for velocity analysis retrieval"""
        return self.velo_modes["glob"]
        
    @velo_mode_glob.setter
    def velo_mode_glob(self, val):
        self.velo_modes["glob"] = bool(val)
    
    @property
    def velo_mode_farneback_raw(self):
        """Attribute velo_glob for velocity analysis retrieval"""
        return self.velo_modes["farneback_raw"]
        
    @velo_mode_farneback_raw.setter
    def velo_mode_farneback_raw(self, val):
        self.velo_modes["farneback_raw"] = bool(val)
    
    @property
    def velo_mode_farneback_histo(self):
        """Attribute for velocity analysis retrieval"""
        return self.velo_modes["farneback_histo"]
        
    @velo_mode_farneback_histo.setter
    def velo_mode_farneback_histo(self, val):
        self.velo_modes["farneback_histo"] = bool(val)
    
    @property
    def velo_mode_farneback_hybrid(self):
        """Attribute for velocity analysis retrieval"""
        return self.velo_modes["farneback_hybrid"]
        
    @velo_mode_farneback_hybrid.setter
    def velo_mode_farneback_hybrid(self, val):
        self.velo_modes["farneback_hybrid"] = bool(val)
        
    @property
    def velo_glob(self):
        """Global velocity in m/s, assigned to this line
        
        Raises
        ------
        AttributeError
            if current value is not of type float
        """
        return self._velo_glob
        
    @velo_glob.setter
    def velo_glob(self, val):
        try:
            val = float(val)
        except:
            raise ValueError("Invalid input, need float or int...")
        if val < 0:
            raise ValueError("Velocity must be larger than 0")
        elif val > 40:
            warn("Large value warning: input velocity exceeds 40 m/s")
        self._velo_glob = val
        if self.velo_glob_err is None or isnan(self.velo_glob_err):
            warn("Global velocity error not assigned, assuming 50% of "
                 "velocity")
            self.velo_glob_err = val * 0.50
    
    @property
    def velo_glob_err(self):
        """Error of global velocity in m/s, assigned to this line
        """
        return self._velo_glob_err
        
    @velo_glob_err.setter
    def velo_glob_err(self, val):
        try:
            val = float(val)
        except:
            raise ValueError("Invalid input, need float or int...")
        if not isnan(val):
            self._velo_glob_err = val
    
    def add_pcs_line(self, line):
        """Add one analysis line to this list
        
        Parameters
        ----------
        line : LineOnImage
            emission rate retrieval line
        """
        if not isinstance(line, LineOnImage):
            raise TypeError("Invalid input type for PCS line, need "
                "LineOnImage...")
        elif self.pcs_lines.has_key(line.line_id):
            raise KeyError("A PCS line with ID %s already exists"
                            %(line.line_id))
        try:
            line.velo_glob #raises exception if not assigned
        except:
            try:
                line.velo_glob = self.velo_glob
                err = self.velo_glob_err
                if isinstance(err, float) and not isnan(err):
                    line.velo_glob_err = err
            except:
                pass
        try:
            line.plume_props #raises exception if not assigned
            self.plume_props_available[line.line_id] = 1
        except:
            print ("Creating new LocalPlumeProperties object in line %s" 
                    %line.line_id)
            line.plume_props = LocalPlumeProperties(roi_id=line.line_id)
            self.plume_props_available[line.line_id] = 0
            
        self.pcs_lines[line.line_id] = line
        
    def __str__(self):
        """String representation"""
        s = "\npyplis settings for emission rate retrieval\n"
        s+= "--------------------------------------------\n\n"
        s+= "Retrieval lines:\n"
        if bool(self.pcs_lines):
            for v in self.pcs_lines.values():
                s += "%s\n" %(v)             
        else:
            s += "No PCS lines assigned yet ...\n"
        s += "\nVelocity retrieval:\n"
        for k, v in self.velo_modes.iteritems():
            s += "%s: %s\n" %(k,v)
        s+= "\nGlobal velocity: v = (%2f +/- %.2f) m/s" %(self.velo_glob,
                                                        self.velo_glob_err)
        s+= "\nAA sensitivity corr: %s\n" %self.senscorr
        s+= "Minimum considered CD: %s cm-2\n" %self.min_cd
        s+= "Molar mass: %s g/mol\n" %self.mmol
        return s
    
    def __setitem__(self, key, val):
        """Set item method"""
        if self.__dict__.has_key(key):
            self.__dict__[key] = val
        elif self.velo_modes.has_key(key):
            self.velo_modes[key] = val
     
class EmissionRateResults(object):
    """Class to store results from emission rate analysis"""
    def __init__(self, pcs_id, velo_mode="glob", settings=None):
        self.pcs_id = pcs_id
        self.settings = settings
        self.velo_mode = velo_mode
        self._start_acq = []
        self._phi = [] #array containing emission rates
        self._phi_err = [] #emission rate errors
        self._velo_eff = [] #effective velocity through cross section
        self._velo_eff_err = [] #error effective velocity 
        
        self.pix_dist_mean = None
        self.pix_dist_mean_err = None
        self.cd_err_rel = None
    
    
    @property
    def meta_header(self):
        """Return string containing available meta information
        
        Returns
        -------
        str
            string containing relevant meta information (e.g. for txt export)
        """
        
        date, i, f = self.get_date_time_strings()
        s = ("pcs_id=%s\ndate=%s\nstart=%s\nstop=%s\nvelo_mode=%s\n"
             "pix_dist_mean=%s m\npix_dist_mean_err=%s m\ncd_err_rel=%s cm-2"
             %(self.pcs_id, date, i, f, self.velo_mode, self.pix_dist_mean, 
               self.pix_dist_mean_err, self.cd_err_rel))
        return s
    
    def get_date_time_strings(self):
        """Returns string reprentations of date and start / stop times
        
        Returns
        -------
        tuple
            3-element tuple containing
            
            - date string
            - start acq. time string
            - stop acq. time string
        """
        try:
            date = self.start.strftime("%d-%m-%Y")
            start = self.start.strftime("%H:%M")
            stop = self.stop.strftime("%H:%M")
        except:
            date, start, stop = "", "", ""
        return date, start, stop
        
    def to_dict(self):
        """Write all data attributes into dictionary 
        
        Keys of the dictionary are the private class names
        
        Returns
        -------
        dict
            Dictionary containing results 
        """
        return dict(_phi            =   self.phi,
                    _phi_err        =   self.phi_err,
                    _velo_eff       =   self.velo_eff,
                    _velo_eff_err   =   self.velo_eff_err,
                    _start_acq      =   self.start_acq)
            
    def to_pandas_dataframe(self):
        """Converts object into pandas dataframe
        
        This can, for instance be used to store the data as csv (cf.
        :func:`from_pandas_dataframe`)        
        """
        d = self.to_dict()
        del d["_start_acq"]
        try:
            df = DataFrame(d, index=self.start_acq)
            return df
        except:
            warn("Failed to convert EmissionRateResults into pandas DataFrame")
    
    @property
    def default_save_name(self):
        """Returns default name for txt export"""
        try:
            d = self.start.strftime("%Y%m%d")
            i = self.start.strftime("%H%M")
            f = self.stop.strftime("%H%M")
        except:
            d, i, f = "", "", ""    
        return "pyplis_EmissionRateResults_%s_%s_%s.txt" %(d, i, f)
        
    def save_txt(self, path=None):
        """Save this object as text file"""       
        
        try:
            if isdir(path): # raises exception in case path is not valid loc
                path = join(path, self.default_save_name)
        except:
            path = join(getcwd(), self.default_save_name)
            
        self.to_pandas_dataframe().to_csv(path)
        
    def from_pandas_dataframe(self, df):
        """Import results from pandas :class:`DataFrame` object
        
        Parameters
        ----------
        df : DataFrame
            pandas dataframe containing emisison rate results
        
        Returns
        -------
        EmissionRateResults
            this object
        """
        self._start_acq = df.index.to_pydatetime()
        for key in df.keys():
            if self.__dict__.has_key(key):
                self.__dict__[key] = df[key].values
        return self
        
    @property
    def start(self):
        """Returns acquisistion time of first image"""
        return self.start_acq[0]
        
    @property
    def stop(self):
        """Returns start acqusition time of last image"""
        return self.start_acq[-1]
        
    @property
    def start_acq(self):
        """Return array containing acquisition time stamps"""
        return asarray(self._start_acq)
    
    @property
    def phi(self):
        """Return array containing emission rates"""
        return asarray(self._phi)
    
    @property
    def phi_err(self):
        """Return array containing emission rate errors"""
        return asarray(self._phi_err)
    
    @property
    def velo_eff(self):
        """Return array containing effective plume velocities"""
        return asarray(self._velo_eff)
    
    @property
    def velo_eff_err(self):
        """Return array containing effective plume velocitie errors"""
        return asarray(self._velo_eff_err)
        
    @property
    def as_series(self):
        """Return emission rate as pandas Series"""
        return Series(self.phi, self.start_acq)
    
    def plot_velo_eff(self, yerr=True, label=None, ax=None, date_fmt=None, 
                      **kwargs):
        """Plots emission rate time series
                
        Parameters
        ----------
        yerr : bool
            Include uncertainties
        label : str
            optional, string argument specifying label 
        ax
            optional, matplotlib axes object
        date_fmt : str
            optional, x label datetime formatting string, passed to 
            :class:`DateFormatter` (e.g. "%H:%M")
        **kwargs
            additional keyword args passed to plot function of :class:`Series`
            object
            
        Returns
        -------
        axes
            matplotlib axes object
            
        """
        if ax is None:
            fig, ax = subplots(1,1)
            
        if not "color" in kwargs:
            kwargs["color"] = "b" 
        if label is None:
            label = ("velo_mode: %s" %(self.velo_mode))
        
        v, verr = self.velo_eff, self.velo_eff_err
    
        s = Series(v, self.start_acq)
        try:
            s.index = s.index.to_pydatetime()
        except:
            pass
        
        s.plot(ax=ax, label=label, **kwargs)
        try:
            if date_fmt is not None:
                ax.xaxis.set_major_formatter(DateFormatter(date_fmt))
        except:
            pass
        
        if yerr:
            phi_upper = Series(v + verr, self.start_acq)
            phi_lower = Series(v - verr, self.start_acq)
        
            ax.fill_between(s.index, phi_lower, phi_upper, alpha=0.1,
                            **kwargs)
        ax.set_ylabel(r"$v_{eff}$ [m/s]", fontsize=16)
        ax.grid()
        return ax
        
    def plot(self, yerr=True, label=None, ax=None, date_fmt=None, ymin=None, 
             ymax=None, alpha_err=0.1, **kwargs):
        """Plots emission rate time series
        
        Parameters
        ----------
        yerr : bool
            Include uncertainties
        label : str
            optional, string argument specifying label 
        ax
            optional, matplotlib axes object
        date_fmt : str
            optional, x label datetime formatting string, passed to 
            :class:`DateFormatter` (e.g. "%H:%M")
        ymin : :obj:`float`, optional
            lower limit of y-axis
        ymax : :obj:`float`, optional
            upper limit of y-axis
        alpha_err : float
            transparency of uncertainty range
        **kwargs
            additional keyword args passed to plot call
            
        Returns
        -------
        axes
            matplotlib axes object
            
        """
        if ax is None:
            fig, ax = subplots(1,1)
        if not "color" in kwargs:
            kwargs["color"] = "b" 
        if label is None:
            label = ("velo_mode: %s" %(self.velo_mode))
        
        phi, phierr = self.phi, self.phi_err
        s = self.as_series
        try:
            s.index = s.index.to_pydatetime()
        except:
            pass
    
        pl = ax.plot(s.index, s.values, label=label, **kwargs)
        try:
            if date_fmt is not None:
                ax.xaxis.set_major_formatter(DateFormatter(date_fmt))
        except:
            pass
        if yerr:
            phi_upper = Series(phi + phierr, self.start_acq)
            phi_lower = Series(phi - phierr, self.start_acq)
        
            ax.fill_between(s.index, phi_lower, phi_upper, alpha=alpha_err,
                            color = pl[0].get_color())
        ax.set_ylabel(r"$\Phi$ [g/s]", fontsize=16)
        ax.grid()
        ylim = list(ax.get_ylim())
        if ymin is not None:
            ylim[0] = ymin
        if ymax is not None:
            ylim[1] = ymax
        ax.set_ylim(ylim)
        return ax
    
    def __add__(self, other):
        """Add emission rate results from two result classes
        
        The values of the emission rates ``phi`` are added, the other data 
        (``phi_err, velo_eff, velo_eff_err``) are averaged between this and 
        the other time series.
        
        Parameters
        ----------
        other : EmissionRateResults
            emission rate results from a different position in the image
            
        Returns
        -------
        EmissionRateResults
            added results
        """
        if not isinstance(other, EmissionRateResults):
            raise ValueError("Invalid input, need EmissionRateResults class")
        df = self.to_pandas_dataframe()
        df1 = other.to_pandas_dataframe()
        df["_phi"] += df1["_phi"]
        df["_phi_err"] = (df["_phi_err"] + df1["_phi_err"]) / 2.
        df["_velo_eff"] = (df["_velo_eff"] + df1["_velo_eff"]) / 2.
        df["_velo_eff"] = (df["_velo_eff_err"] + df1["_velo_eff_err"]) / 2.
        new_id = "%s + %s" %(self.pcs_id, other.pcs_id)
        
        
        new = EmissionRateResults(new_id)
        new.from_pandas_dataframe(df)
        pdm_diff = abs( self.pix_dist_mean - other.pix_dist_mean)
        new.pix_dist_mean = nanmean([self.pix_dist_mean, other.pix_dist_mean])
        pdm_err = nanmean([self.pix_dist_mean_err, other.pix_dist_mean_err])
        new.pix_dist_mean_err = max([pdm_diff, pdm_err])
        new.cd_err_rel =  nanmean([self.cd_err_rel, other.cd_err_rel])
        return new

    def __sub__(self, other):
        """Subtract emission rate results from two result classes
        
        The values of the emission rates ``phi`` are subtracted, the other data 
        (``phi_err, velo_eff, velo_eff_err``) are averaged between this and 
        the other time series.
        
        Parameters
        ----------
        other : EmissionRateResults
            emission rate results from a different position in the image
            
        Returns
        -------
        EmissionRateResults
            added results
        """
        if not isinstance(other, EmissionRateResults):
            raise ValueError("Invalid input, need EmissionRateResults class")
        df = self.to_pandas_dataframe()
        df1 = other.to_pandas_dataframe()
        df["_phi"] -= df1["_phi"]
        df["_phi_err"] = (df["_phi_err"] + df1["_phi_err"]) / 2.
        df["_velo_eff"] = (df["_velo_eff"] + df1["_velo_eff"]) / 2.
        df["_velo_eff"] = (df["_velo_eff_err"] + df1["_velo_eff_err"]) / 2.
        new_id = "%s - %s" %(self.pcs_id, other.pcs_id)
        
        new = EmissionRateResults(new_id)
        new.from_pandas_dataframe(df)
        pdm_diff = abs( self.pix_dist_mean - other.pix_dist_mean)
        new.pix_dist_mean = nanmean([self.pix_dist_mean, other.pix_dist_mean])
        pdm_err = nanmean([self.pix_dist_mean_err, other.pix_dist_mean_err])
        new.pix_dist_mean_err = max([pdm_diff, pdm_err])
        new.cd_err_rel =  nanmean([self.cd_err_rel, other.cd_err_rel])
        return new
        
    
    def __str__(self):
        """String representation"""
        s = "pyplis EmissionRateResults\n--------------------------------\n\n"
        s += self.meta_header
        s += ("\nphi_min=%.2f g/s\nphi_max=%.2f g/s\n"
              %(nanmin(self.phi), nanmax(self.phi)))
        s += "phi_err=%.2f g/s\n" %nanmean(self.phi_err)
        s += ("v_min=%.2f m/s\nv_max=%.2f m/s\n"
              %(nanmin(self.velo_eff), nanmax(self.velo_eff)))
        s += "v_err=%.2f m/s" %nanmean(self.velo_eff_err)
        return s
        
class EmissionRateAnalysis(object):
    """Class to perform emission rate analysis
    
    The analysis is performed by looping over images in an image list which
    is in ``calib_mode``, i.e. which loads images as gas CD images. 
    Emission rates can be retrieved for an arbitrary amount of plume cross 
    sections (defined by a list of :class:`LineOnImage` objects which can be 
    provided on init or added later). The image list needs to include a valid
    measurement geometry (:class:`MeasGeometry`) object which is used to 
    determine pixel to pixel distances (on a pixel column basis) and 
    corresponding uncertainties. 
    
    Parameters
    ----------
    imglist : ImgList
        onband image list prepared such, that at least ``aa_mode`` and 
        ``calib_mode`` can be activated. If emission rate retrieval is supposed 
        to be performed using optical flow, then also ``optflow_mode`` needs to 
        work. Apart from setting these modes, no further changes are applied to 
        the list (e.g. dark correction, blurring or choosing the pyramid level) 
        and should therefore be set before. A warning is given, in case dark 
        correction is not activated.
    
    pcs_lines : list
        python list containing :class:`LineOnImage` objects supposed to be used 
        for retrieval of emission rates (can also be a :class:`LineOnImage` 
        object directly)
    velo_glob : float
        global plume velocity in m/s (e.g. retrieved using cross correlation 
        algorithm)
    velo_glob_err : float
        uncertainty in global plume speed estimate
    bg_roi : list
        region of interest specifying gas free area in the images. It is used 
        to extract mean, max, min values from each of the calibrated images 
        during the analysis as a quality check for the performance of the plume 
        background retrieval or to detect disturbances in this region (e.g. due 
        to clouds). If unspecified, the ``scale_rect`` of the plume background 
        modelling class is used (i.e. ``self.imglist.bg_model.scale_rect``).
    **settings : 
        analysis settings (passed to :class:`EmissionRateSettings`)
        
    Todo
    ----

        1. Include light dilution correction - automatic correction for light 
        dilution is currently not supported in this object. If you wish
        to perform light dilution, for now, please calculate dilution
        corrected on and offband images first (see example script ex11) and 
        save them locally. The new set of images can then be used normally
        for the analysis by creating a :class:`Dataset` object and an 
        AA image list from that (see example scripts 1 and 4). 
            
    """
    def __init__(self, imglist, bg_roi=None, **settings):

        if not isinstance(imglist, ImgList):
            raise TypeError("Need ImgList, got %s" %type(imglist))
           
        self.imglist = imglist
        self.settings = EmissionRateSettings(**settings)

        #Retrieved emission rate results are written into the following 
        #dictionary, keys are the line_ids of all PCS lines
        self.results = od()
        
        if not check_roi(bg_roi):
            try:
                bg_roi = map_roi(imglist.bg_model.scale_rect,
                              pyrlevel_rel=imglist.pyrlevel)
                if not check_roi(bg_roi):
                    raise ValueError("Fatal: check scale rectangle in "
                        "background model of image list...")
            except:
                warn("Failed to access scale rectangle in background model "
                    "of image list, setting bg_roi to lower left image corner")
                bg_roi = [5, 5, 20, 20]
        self.bg_roi = bg_roi
        self.bg_roi_info = {"mean"  :   None, 
                            "std"   :   None}
        
        self.warnings = []
            
        if not self.pcs_lines:
            self.warnings.append("No PCS analysis lines available for emission" 
                                 " rate analysis")
        try:
            self.check_and_init_list()
        except:
            self.warnings.append("Failed to initate image list for analysis "
                "check previous warnings...")
        for warning in self.warnings:
            warn(warning)
    
    @property
    def pcs_lines(self):
        """Dictionary containing PCS retrieval lines assigned to settings class
        """
        return self.settings.pcs_lines
        
    @property
    def velo_glob(self):
        """Global velocity"""
        return self.settings.velo_glob
    
    @property
    def velo_glob_err(self):
        """Return error of current global velocity"""
        return self.settings.velo_glob_err    
        
    @property
    def farneback_required(self):
        """Checks if current velocity mode settings require farneback algo"""
        s = self.settings
        if s.velo_modes["farneback_raw"] or s.velo_modes["farneback_hybrid"]:
            return True
        elif s.velo_modes["farneback_histo"]:
            d = s.plume_props_available
            if not sum(d.values()) == len(d):
                return True
        return False
    
    
    def get_results(self, line_id=None, velo_mode=None):
        """Return emission rate results (if available)
        
        :param str line_id: ID of PCS line 
        :param str velo_mode: velocity retrieval mode (see also
            :class:`EmissionRateSettings`)
        :return: - EmissionRateResults, class containing emission rate 
            results for specified line and velocity retrieval
        :raises: - KeyError, if result for the input constellation cannot be
            found
        """
        if line_id is None:
            try:
                line_id = self.results.keys()[0]
                print "Input line ID unspecified, using: %s" %line_id
            except IndexError:
                raise IndexError("No emission rate results available...")
        if velo_mode is None:
            try:
                velo_mode = self.results[line_id].keys()[0]
                print "Input velo_mode unspecified, using: %s" %velo_mode
            except:
                raise IndexError("No emission rate results available...")
        if not self.results.has_key(line_id):
            raise KeyError("No results available for pcs with ID %s" %line_id)
        elif not self.results[line_id].has_key(velo_mode):
            raise KeyError("No results available for line %s and velocity mode"
                " %s" %(line_id, velo_mode))
        return self.results[line_id][velo_mode]
        
    def check_and_init_list(self):
        """Checks if image list is ready and includes all relevant info"""
        
        lst = self.imglist
        
        if not lst.darkcorr_mode:
            self.warnings.append("Dark image correction is not activated in "
                "image list")
        if self.settings.senscorr:
            # activate sensitivity correcion mode: images are divided by 
            try:
                lst.sensitivity_corr_mode = True
            except:
                self.warnings.append("AA sensitivity correction was deactivated"
                    "because it could not be succedfully activated in imglist")
                self.settings.senscorr = False
        
        # activate calibration mode: images are calibrated using DOAS 
        # calibration polynomial. The fitted curve is shifted to y axis 
        # offset 0 for the retrieval
        lst.calib_mode = True
        
        if self.settings.velo_glob:
            try:
                float(self.velo_glob)
            except:
                self.warnings.append("Global velocity is not available, try "
                    " activating optical flow")
                lst.optflow_mode = True
                lst.optflow.plot_flow_histograms()
                
                self.settings.velo_farneback_histo = True
        try:
            lst.meas_geometry.get_all_pix_to_pix_dists(pyrlevel=lst.pyrlevel)
        except ValueError:
            raise ValueError("measurement geometry in image list is not ready"
                "for pixel distance access")
        
    def get_pix_dist_info_all_lines(self):
        """Retrieve pixel distances and uncertainty for all pcs lines
        
        Returns
        -------
        tuple
            2-element tuple containing
            
            - :obj:`dict`, keys are line ids, vals are arrays with pixel dists
            - :obj:`dict`, keys are line ids, vals are distance uncertainties
            
        """
        lst = self.imglist
        PYR = self.imglist.pyrlevel
        # get pixel distance image
        dist_img = lst.meas_geometry.get_all_pix_to_pix_dists(pyrlevel=PYR)[0]
        #init dicts
        dists, dist_errs = {}, {}
        for line_id, line in self.pcs_lines.iteritems():
            dists[line_id] = line.get_line_profile(dist_img)
            col = line.center_pix[0] #pixel column of center of PCS
            dist_errs[line_id] = lst.meas_geometry.pix_dist_err(col, PYR)
            
        return dists, dist_errs
    
    def init_results(self):
        """Reset results
        
        Returns
        -------
        tuple
            2-element tuple containing
            
            - :obj:`dict`, keys are line ids, vals are empty result classes
            - :obj:`dict`, keys are line ids, vals are empty \
                :class:`LocalPlumeProperties` objects
        """
        if sum(self.settings.velo_modes.values()) == 0:
            raise ValueError("Cannot initiate result structure: no velocity "
                "retrieval mode is activated, check self.settings.velo_modes "
                "dictionary.")
    
        res = od()
        for line_id, line in self.pcs_lines.iteritems():
            res[line_id] = od()
            for mode, val in self.settings.velo_modes.iteritems():
                if val:
                    res[line_id][mode] = EmissionRateResults(line_id, mode)
        self.results = res
        self.check_pcs_plume_props()
        self.bg_roi_info = {"mean"  :   None, 
                            "std"   :   None}
        return res
    
    def check_pcs_plume_props(self):
        """Checks if plume displacement information is available for all PCS
        
        Tries to access :class:`LocalPlumeProperties` objects in each of the
        assigned plume cross section retrieval lines (:attr:`pcs_lines`). If
        so and if a considerable datetime index overlap is given in the
        corresponding object (with datetime indices in :attr:`imglist`), then
        the object is interpolated onto the time stamps of the list and the 
        corresponding displacement information is used (and not re-calculated)
        while performing emission rate retrieval when using 
        ``velo_mode = farneback_histo``. If no significant overlap can be 
        detected, the :class:`LocalPlumeProperties` object in the corresponding
        :class:`LineOnImage` object is initiated and filled while performing 
        the analysis.
        """
        lst = self.imglist
        span = (lst.stop - lst.start).total_seconds()
        
        for key, line in self.pcs_lines.iteritems():
            try:
                p = line.plume_props
                dt0 = (p.start - lst.start).total_seconds()
                if dt0 > 0 and dt0 / span > 0.05:
                    raise IndexError("Insufficient overlap of time stamps in "
                        "plume properties of line %s with time stamps in list...")
                dt1 = (lst.stop - p.stop).total_seconds()
                if dt1 > 0 and dt1 / span > 0.05:
                    raise IndexError("Insufficient overlap of time stamps in "
                        "plume properties of line %s with time stamps in list...")
                line.plume_props = p.interpolate(time_stamps=lst.start_acq,
                                                 how="time")
                self.settings.plume_props_available[key] = 1
            except:
                self.settings.plume_props_available[key] = 0
                line.plume_props = LocalPlumeProperties(roi_id=key)
                                                 
        
    def _write_meta(self, dists, dist_errs, cd_err_rel):
        """Write meta info in result classes"""
        for line_id, mode_dict in self.results.iteritems():
            for mode, resultclass in mode_dict.iteritems():
                resultclass.pix_dist_mean = mean(dists[line_id])
                resultclass.pix_dist_mean_err = dist_errs[line_id]
                resultclass.cd_err_rel = cd_err_rel
        
    def calc_emission_rate(self, **kwargs):
        """Old name of :func:`run_retrieval`"""
        warn("Old name of method run_retrieval")
        return self.run_retrieval(**kwargs)
        
    def run_retrieval(self, start_index=0, stop_index=None, check_list=False):
        """Calculate emission rates of image list
        
        Performs emission rate analysis for each line in ``self.pcs_lines`` 
        and for all plume velocity retrievals activated in 
        ``self.settings.velo_modes``. The results for each line and 
        velocity mode are stored within :class:`EmissionRateResults` objects
        which are saved in ``self.results[line_id][velo_mode]``, e.g.::
        
            res = self.results["bla"]["farneback_histo"]
            
        would yield emission rate results for line with ID "bla" using 
        histogram based plume speed analysis. 
        
        The results can also be easily accessed using :func:`get_results`.
        
        Parameters
        ----------
        start_index : int
            index of first considered image in ``self.imglist``, defaults to 0
        stop_index : int
            index of last considered image in ``self.imglist``, defaults to 
            last image in list
        check_list : bool
            if True, :func:`check_and_init_list` is called before analysis
        
        Returns
        -------
        tuple
            2-element tuple containing
            
            - :obj:`dict`, keys are line ids, vals are corresponding results
            - :obj:`dict`, keys are line ids, vals are \
                :class:`LocalPlumeProperties` objects
                
        """
        if check_list:
            self.check_and_init_list()
        lst = self.imglist
        if stop_index is None:
            stop_index = lst.nof - 1 
        
        s = self.settings
        results = self.init_results()
        dists, dist_errs = self.get_pix_dist_info_all_lines()
        lst.goto_img(start_index)
        try:
            cd_err_rel = lst.calib_data.slope_err / lst.calib_data.slope
        except:
            cd_err_rel = None
            
        self._write_meta(dists, dist_errs, cd_err_rel)
        
        # init parameters for main loop
        mmol = s.mmol    
        if self.farneback_required:
            lst.optflow_mode = True
        else:
            lst.optflow_mode = False #should be much faster
        ts, bg_mean, bg_std = [], [], []
        roi_bg = self.bg_roi
        velo_modes = s.velo_modes
        min_cd = s.min_cd
        lines = self.pcs_lines
        for k in range(start_index, stop_index):
            print "Progress: %d (%d)" %(k, stop_index)
            img = lst.current_img()
            t = lst.current_time()
            ts.append(t)
            sub = img.img[roi_bg[1] : roi_bg[3], roi_bg[0] : roi_bg[2]]
            
            bg_std.append(sub.std())
            bg_mean.append(sub.mean())

            for pcs_id, pcs in lines.iteritems():
                res = results[pcs_id]
                n = pcs.normal_vector
                cds = pcs.get_line_profile(img)
                cond = cds > min_cd
                cds = cds[cond]
                cds_err = cds * cd_err_rel
                distarr = dists[pcs_id][cond]
                disterr = dist_errs[pcs_id]
                
                if velo_modes["glob"]:
                    try:
                        vglob, vglob_err = pcs.velo_glob, pcs.velo_glob_err
                    except:
                        vglob, vglob_err = self.velo_glob, self.velo_glob_err
                    phi, phi_err = det_emission_rate(cds, vglob, distarr,
                                                     cds_err, vglob_err, 
                                                     disterr, mmol)
                    if isnan(phi):
                        print cds
                        raise ValueError
                    res["glob"]._start_acq.append(t)
                    res["glob"]._phi.append(phi)
                    res["glob"]._phi_err.append(phi_err)
                    res["glob"]._velo_eff.append(vglob)
                    res["glob"]._velo_eff_err.append(vglob_err)
                
                if velo_modes["farneback_raw"]:
                    delt = lst.optflow.del_t
                    
                    # retrieve diplacement vectors along line
                    dx = pcs.get_line_profile(lst.optflow.flow[:,:,0])
                    dy = pcs.get_line_profile(lst.optflow.flow[:,:,1])
                    
                    # detemine array containing effective velocities 
                    # through the line using dot product with line normal
                    veff_arr = dot(n, (dx, dy))[cond] * distarr / delt
                    
                    # Calculate mean of effective velocity through l and 
                    # uncertainty using 2 sigma confidence of standard deviation
                    veff = veff_arr.mean()
                    veff_err = veff_arr.std() * 2
                    
                    phi, phi_err = det_emission_rate(cds, veff_arr,
                                                     distarr, cds_err, 
                                                     veff_err, disterr, mmol)
                    res["farneback_raw"]._start_acq.append(t)                                
                    res["farneback_raw"]._phi.append(phi)
                    res["farneback_raw"]._phi_err.append(phi_err)

                    
                    #note that the velocity is likely underestimated due to
                    #low contrast regions (e.g. out of the plume, this can
                    #be accounted for by setting an appropriate CD minimum
                    #threshold in settings, such that the retrieval is
                    #only applied to pixels exceeding a certain column 
                    #density)
                    res["farneback_raw"]._velo_eff.append(veff)
                    res["farneback_raw"]._velo_eff_err.append(veff_err)
                
                props = pcs.plume_props
                if velo_modes["farneback_histo"]:                    
                    if s.plume_props_available[pcs_id]:
                        idx = k
                    else:                            
                        # get mask specifying plume pixels
                        mask = lst.get_thresh_mask(min_cd)
                        props.get_and_append_from_farneback(lst.optflow,
                                                            line=pcs,
                                                            pix_mask=mask)
                        idx = -1
                        
                    v, verr = props.get_velocity(idx, distarr.mean(),
                                                 disterr, 
                                                 pcs.normal_vector)
                    
                    phi, phi_err = det_emission_rate(cds, v, distarr, 
                                                     cds_err, verr, disterr, 
                                                     mmol)
                                                     
                    res["farneback_histo"]._start_acq.append(t)                                
                    res["farneback_histo"]._phi.append(phi)
                    res["farneback_histo"]._phi_err.append(phi_err)
                    res["farneback_histo"]._velo_eff.append(v)
                    res["farneback_histo"]._velo_eff_err.append(verr)
                    
                if velo_modes["farneback_hybrid"]:
                    # get results from local plume properties analysis
                    if not velo_modes["farneback_histo"]:
                        if s.plume_props_available[pcs_id]:
                            idx = k
                        else:                            
                            # get mask specifying plume pixels
                            mask = lst.get_thresh_mask(min_cd)
                            props.get_and_append_from_farneback(lst.optflow,
                                                                line=pcs,
                                                                pix_mask=mask)
                            idx = -1
            
                    min_len = props.len_mu[idx] - props.len_sigma[idx]
                    dir_min = props.dir_mu[idx] - 3 * props.dir_sigma[idx]
                    dir_max = props.dir_mu[idx] + 3 * props.dir_sigma[idx]
                    
                    vec = props.displacement_vector(idx)
                                        
                    flc = lst.optflow.replace_trash_vecs(displ_vec=vec, 
                                                         min_len=min_len,
                                                         dir_low=dir_min, 
                                                         dir_high=dir_max)
                    
                    delt = lst.optflow.del_t
                    dx = pcs.get_line_profile(flc.flow[:,:,0])
                    dy = pcs.get_line_profile(flc.flow[:,:,1])
                    veff_arr = dot(n, (dx, dy))[cond] * distarr / delt
                    
                    # Calculate mean of effective velocity through l and 
                    # uncertainty using 2 sigma confidence of standard deviation
                    veff = veff_arr.mean()
                    veff_err = veff_arr.std()
                    
                    phi, phi_err = det_emission_rate(cds, veff_arr,
                                                     distarr, cds_err, 
                                                     veff_err, disterr, mmol)
                    res["farneback_hybrid"]._start_acq.append(t)                                
                    res["farneback_hybrid"]._phi.append(phi)
                    res["farneback_hybrid"]._phi_err.append(phi_err)
                    res["farneback_hybrid"]._velo_eff.append(veff)
                    res["farneback_hybrid"]._velo_eff_err.append(veff_err)
                    
            lst.next_img()  
    
        self.bg_roi_info["mean"] = Series(bg_mean, ts)
        self.bg_roi_info["std"] = Series(bg_std, ts)
        
        return self.results

    def add_pcs_line(self, line):
        """Add one analysis line to this list
        
        :param LineOnImage line: the line object
        """
        self.settings.add_pcs_line(line)
        
    def plot_pcs_lines(self):
        """Plots all current PCS lines onto current list image"""
        # plot current image in list and draw line into it
        ax = self.imglist.show_current()
        for line_id, line in self.pcs_lines.iteritems():
            line.plot_line_on_grid(ax=ax, include_normal=True, label=line_id)
        ax.legend(loc='best', fancybox=True, framealpha=0.5, fontsize=12)
        return ax
    
    def plot_bg_roi_vals(self, ax=None, date_fmt=None, **kwargs):
        """Plots emission rate time series
        
        Parameters
        ----------
        ax
            optional, matplotlib axes object
        date_fmt : str
            optional, x label datetime formatting string, passed to 
            :class:`DateFormatter` (e.g. "%H:%M")
        **kwargs
            additional keyword args passed to plot function of :class:`Series`
            object
            
        Returns
        -------
        axes
            ax, matplotlib axes object
            
        """
        if ax is None:
            fig, ax = subplots(1,1)
        if not "color" in kwargs:
            kwargs["color"] = "r" 
        
        s = self.bg_roi_info["mean"]
        try:
            s.index = s.index.to_pydatetime()
        except:
            pass
        err = self.bg_roi_info["std"]
        lower = s - err
        upper = s +err
        exp = exponent(upper.values.max())

        s_disp = s * 10**-exp
        lower_disp = lower * 10**-exp
        upper_disp = upper * 10**-exp
        
        s_disp.plot(ax=ax, label="mean", **kwargs)
        try:
            if date_fmt is not None:
                ax.xaxis.set_major_formatter(DateFormatter(date_fmt))
        except:
            pass
        ax.fill_between(s.index, lower_disp, upper_disp, alpha=0.1, **kwargs)
        ax.set_ylabel(r"$ROI_{BG}\,[E%+d\,cm^{-2}]$" %exp)
        ax.grid()
        return ax
        
def det_emission_rate(cds, velo, pix_dists, cds_err=None, velo_err=None,
                      pix_dists_err=None, mmol=MOL_MASS_SO2):
    """Determine emission rate
    
    :param cds: column density in units cm-2 (float or ndarray)
    :param velo: effective plume velocity in units of m/s (float or ndarray)
        Effective means, that it is with respect to the direction of the normal 
        vector of the plume cross section used (e.g. by performing a scalar 
        product of 2D velocity vectors with normal vector of the PCS)
    :param pix_dists: pixel to pixel distances in units of m (float or ndarray)
    
    """
    if cds_err is None:
        print ("Uncertainty in column densities unspecified, assuming 20 % of "
                "mean CD")
        cds_err = mean(cds) * 0.20
    if velo_err is None:
        print ("Uncertainty in plume velocity unspecified, assuming 20 % of "
                "mean velocity")
        velo_err = mean(velo) * 0.20
        
    if pix_dists_err is None:
        print ("Uncertainty in pixel distance unspecified, assuming 10 % of "
                "mean pixel distance")
        pix_dists_err = mean(pix_dists) * 0.10
        
    C = 100**2 * mmol / N_A
    phi = sum(cds * velo * pix_dists) * C
    dphi1 = sum(velo * pix_dists * cds_err)**2
    dphi2 = sum(cds * pix_dists * velo_err)**2
    dphi3 = sum(cds * velo *pix_dists_err)**2
    phi_err = C * sqrt(dphi1 + dphi2 + dphi3)
    return phi, phi_err