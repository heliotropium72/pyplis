# -*- coding: utf-8 -*-
"""
pyplis example script no. 11 - Image based signal dilution correction

This script illustrates how extinction coefficients can be retrieved from 
image data using the DilutionCorr class and by specifying suitable terrain
features in the images. 

The extinction coefficients are retrieved from one on an from one off band 
image recorded ~15 mins before the dataset used in the other examples. The 
latter data is less suited for illustrating the feature since it contains 
less terrain (therfore more sky background). 

The two example images are then corrected for dilution and the results are 
plotted (as comparison of the retrieved emission rate along an exemplary 
plume cross section)
"""
from SETTINGS import check_version
# Raises Exception if conflict occurs
check_version()

import pyplis as pyplis
from geonum.base import GeoPoint
from matplotlib.pyplot import show, close, subplots, Rectangle
from datetime import datetime
from os.path import join, exists

from pyplis.dilutioncorr import DilutionCorr
from pyplis.doascalib import DoasCalibData

### IMPORT GLOBAL SETTINGS
from SETTINGS import IMG_DIR, SAVEFIGS, SAVE_DIR, FORMAT, DPI, OPTPARSE
### IMPORTS FROM OTHER EXAMPLE SCRIPTS
from ex10_bg_imglists import get_bg_image_lists

### SCRIPT OPTONS  
# lower boundary for I0 value in dilution fit
I0_MIN = 0.0 
AA_THRESH = 0.03

# exemplary plume cross section line for emission rate retrieval (is also used
# for full analysis in ex12)
PCS_LINE = pyplis.processing.LineOnImage(x0=530,y0=586,x1=910,y1=200,
                                          line_id="pcs")
# Retrieval lines for dilution correction (along these lines, topographic
# distances and image radiances are determined for fitting the atmospheric
# extinction coefficients)
TOPO_LINE1 = pyplis.processing.LineOnImage(1100, 650, 1000, 900,
                                            line_id="flank far",
                                            color="lime",
                                            linestyle="-")
                                      
TOPO_LINE2 = pyplis.processing.LineOnImage(1000, 990, 1100, 990,
                                            line_id="flank close",
                                            color="b",
                                            linestyle="-")

# all lines in this array are used for the analysis
USE_LINES = [TOPO_LINE1, TOPO_LINE2]

# specify pixel resolution of topographic distance retrieval (every nth pixel 
# is used)
SKIP_PIX_LINES = 10

# Specify region of interest used to extract the ambient intensity (required
# for dilution correction)
AMBIENT_ROI = [1240, 10, 1300, 70]

# Specify plume velocity (for emission rate estimate)
PLUME_VELO = 4.14 #m/s (result from ex8)

### RELEVANT DIRECTORIES AND PATHS
CALIB_FILE = join(SAVE_DIR, "ex06_doascalib_aa.fts")

### SCRIPT FUNCTION DEFINITIONS        
def create_dataset_dilution():
    """Create a :class:`pyplis.dataset.Dataset` object for dilution analysis
    
    The test dataset includes one on and one offband image which are recorded
    around 6:45 UTC at lower camera elevation angle than the time series shown
    in the other examples (7:06 - 7:22 UTC). Since these two images contain
    more topographic features they are used to illustrate the image based 
    signal dilution correction.
    
    This function sets up the measurement (geometry, camera, time stamps) for
    these two images and creates a Dataset object.
    """
    
    start = datetime(2015, 9, 16, 6, 43, 00)
    stop = datetime(2015, 9, 16, 6, 47, 00)
    #the camera filter setup
    cam_id = "ecII"
    filters= [pyplis.utils.Filter(type = "on", acronym = "F01"),
              pyplis.utils.Filter(type = "off", acronym = "F02")]
    
    geom_cam = {"lon"           :   15.1129,
                "lat"           :   37.73122,
                "elev"          :   15.0, #from field notes, will be corrected
                "elev_err"      :   5.0,
                "azim"          :   274.0, #from field notes, will be corrected 
                "azim_err"      :   10.0,
                "focal_length"  :   25e-3,
                "alt_offset"    :   7} #meters above topography

    #create camera setup
    cam = pyplis.setupclasses.Camera(cam_id=cam_id, filter_list=filters,
                                      **geom_cam)
    
    ### Load default information for Etna
    source = pyplis.setupclasses.Source("etna")
    
    #### Provide wind direction
    wind_info= {"dir"      : 0.0,
                "dir_err"  : 15.0}


    ### Create BaseSetup object (which creates the MeasGeometry object)
    stp = pyplis.setupclasses.MeasSetup(IMG_DIR, start, stop, camera=cam,
                                         source = source,
                                         wind_info = wind_info)
    return pyplis.dataset.Dataset(stp)

def find_view_dir(geom):
    """Performs a correction of the viewing direction using crater in img
    
    :param MeasGeometry geom: measurement geometry
    :param str which_crater: use either "ne" (northeast) or "se" (south east)
    :return: - MeasGeometry, corrected geometry
    """
    # Use position of NE crater in image
    posx, posy = 1051, 605 #pixel position of NE crate in image
    # Geo location of NE crater (info from Google Earth)
    ne_crater = GeoPoint(37.754788,  14.996673, 3287, name = "NE crater")
    
    geom.find_viewing_direction(pix_x=posx, pix_y=posy, pix_pos_err=100,
                                   geo_point=ne_crater, draw_result=True)
    return geom

def prepare_lists(dataset):
    """Prepare on and off lists for dilution analysis
    
    Steps:
        
        1. get on and offband list
        #. load background image list on and off (from ex10)
        #. set image preparation and assign background images to on / off list
        #. configure plume background model settings
    
    :param Dataset dataset: the dilution dataset (see 
        :func:`create_dataset_dilution`)
    :return:
        - ImgList, onlist
        - ImgList, offlist
        
    """
    onlist = dataset.get_list("on")
    offlist = dataset.get_list("off")
    bg_onlist, bg_offlist = get_bg_image_lists() #dark_corr_mode already active
    
    # prepare img pre-edit
    onlist.darkcorr_mode = True
    onlist.gaussian_blurring = 2
    offlist.darkcorr_mode = True
    offlist.gaussian_blurring = 2
    
    # prepare background images in lists (when assigning a background image 
    # to a ImgList, then the blurring amount of the BG image is automatically
    # set to the current blurring level of the list, and if the latter is 
    # zero, then the BG image is blurred using filter width=1)
    onlist.bg_img = bg_onlist.current_img()
    offlist.bg_img = bg_offlist.current_img()
    
    #prepare plume background modelling setup in both lists
    onlist.bg_model.CORR_MODE = 6
    onlist.bg_model.guess_missing_settings(onlist.current_img())
    onlist.bg_model.xgrad_line_startcol = 10
    offlist.bg_model.update(**onlist.bg_model.settings_dict())
    
    return onlist, offlist
    
def plot_lines_into_image(img):
    """Helper method plotting terrain distance retrieval lines into an image"""
    ax = img.show(zlabel=r"$S_{SO2}$ [cm$^{-2}$]")
    ax.set_title("Retrieval lines")
    for line in USE_LINES:
        line.plot_line_on_grid(ax=ax, marker="", color=line.color,
                               lw=2, ls=line.linestyle) 
    return ax

    
### SCRIPT MAIN FUNCTION       
if __name__ == "__main__":
    if not exists(CALIB_FILE):
        raise IOError("Calibration file could not be found at specified "
            "location:\n %s\nYou might need to run example 6 first")

    close("all")
    pcs_line = PCS_LINE
    calib = DoasCalibData()    
    calib.load_from_fits(CALIB_FILE)
    
    # create dataset and correct viewing direction
    ds = create_dataset_dilution()
    geom = find_view_dir(ds.meas_geometry)
    
    #get plume distance image    
    pix_dists, _, plume_dists = geom.get_all_pix_to_pix_dists()  
        
    # Create dilution correction class
    dil = DilutionCorr(USE_LINES, geom, skip_pix=SKIP_PIX_LINES)
    
    # Determine distances to the two lines defined above (every 6th pixel)
    for line_id in dil.line_ids:
        dil.det_topo_dists_line(line_id)
    
    # Plot the results in a 3D map
    basemap = dil.plot_distances_3d(alt_offset_m=10, axis_off=False, color="b")                                                          
    
    # retrieve pixel distances for pixels on the line 
    # (for emission rate estimate)
    pix_dists_line = pcs_line.get_line_profile(pix_dists)
    
    #get pixel coordinates of PCS center position ...
    col, row = pcs_line.center_pix
    
    # ... and get uncertainty in plume distance estimate for the column
    pix_dist_err = geom.pix_dist_err(col)
    
    # Prepare on and off-band list for retrieval of extinction coefficients
    onlist, offlist = prepare_lists(ds)
    
    # Activate vignetting correction in both lists (required to extract
    # measured intensities along the terrain features)
    onlist.vigncorr_mode = True
    offlist.vigncorr_mode = True
    
    # get the vignetting corrected images 
    on_vigncorr = onlist.current_img()
    off_vigncorr = offlist.current_img()
    
    # estimate ambient intensity for both filters
    ia_on = on_vigncorr.crop(AMBIENT_ROI, True).mean()
    ia_off = off_vigncorr.crop(AMBIENT_ROI, True).mean()
    
    # perform dilution anlysis and retrieve extinction coefficients (on-band)
    ext_on, _, _, ax0 = dil.apply_dilution_fit(img=on_vigncorr,
                                               rad_ambient=ia_on, 
                                               i0_min=I0_MIN,
                                               plot=True)
                                               
    ax0.set_ylabel("Terrain radiances (on band)", fontsize=14)
    ax0.set_ylim([0, 2500])                                                  
    
    # perform dilution anlysis and retrieve extinction coefficients (off-band)
    ext_off, i0_off, _, ax1 = dil.apply_dilution_fit(img=off_vigncorr,
                                                   rad_ambient=ia_off,
                                                   i0_min=I0_MIN,
                                                   plot=True)
    ax1.set_ylabel("Terrain radiances (off band)", fontsize=14)     
    ax1.set_ylim([0, 2500])
    
    #determine plume pixel mask from AA image
    onlist.aa_mode = True
    plume_pix_mask = onlist.get_thresh_mask(AA_THRESH)
    plume_pix_mask[840:, :] = 0 #remove tree in lower part of the image
    onlist.aa_mode = False
    
    # this method checks relevant parameters for dilution correction and 
    # gets those missing, e.g. the mask specifying plume pixels
    _, _, bg_on, _, _ =\
        onlist.prep_data_dilutioncorr(plume_pix_mask=plume_pix_mask,
                                      plume_dists=plume_dists, 
                                      ext_coeff=ext_on)
    
    # do the same for the off band. Here, the plume pixel mask from the on band
    # is used and is therefore provided as input of the method
    _, _, bg_off, _, _ =\
        offlist.prep_data_dilutioncorr(plume_pix_mask=plume_pix_mask,
                                       plume_dists=plume_dists, 
                                       ext_coeff=ext_off)
                                         
    #get dilution corrected on and off-band image
    on_corr = dil.correct_img(on_vigncorr, ext_on, bg_on,
                              plume_dists, plume_pix_mask)

    off_corr = dil.correct_img(off_vigncorr, ext_off, bg_off,
                              plume_dists, plume_pix_mask)
                              
    # convert the corrected images into tau images
    tau_on_corr = on_corr.to_tau(bg_on)
    tau_off_corr = off_corr.to_tau(bg_off)
    
    # determine corrected SO2-CD image from the image lists
    so2_img_corr = calib(tau_on_corr - tau_off_corr)
    so2_img_corr.edit_log["is_tau"] = True #for plotting
    so2_cds_corr = pcs_line.get_line_profile(so2_img_corr)
    
    (phi_corr, 
     phi_corr_err) = pyplis.fluxcalc.det_emission_rate(cds=so2_cds_corr,
                                                       velo=PLUME_VELO,
                                                       pix_dists=
                                                       pix_dists_line,
                                                       cds_err=
                                                       calib.slope_err,
                                                       pix_dists_err=
                                                       pix_dist_err)
    
    # determine uncorrected so2-CD image from the image lists
    onlist.tau_mode=True
    offlist.tau_mode=True
    # the "this" attribute returns the current list image (same as 
    # method "current_img()")
    so2_img_uncorr = calib(onlist.this - offlist.this)
    
    # Retrieve column density profile along PCS in uncorrected image
    so2_cds_uncorr = pcs_line.get_line_profile(so2_img_uncorr)    
    # Calculate flux and uncertainty
    (phi_uncorr, 
     phi_uncorr_err) = pyplis.fluxcalc.det_emission_rate(cds=so2_cds_uncorr,
                                                         velo=PLUME_VELO,
                                                         pix_dists=
                                                         pix_dists_line,
                                                         cds_err=
                                                         calib.slope_err,
                                                         pix_dists_err=
                                                         pix_dist_err)    
    
    ### IMPORTANT STUFF FINISHED (below follow some plots)
    ax2 = plot_lines_into_image(so2_img_corr)
    pcs_line.plot_line_on_grid(ax=ax2, ls="-", color="g")
    ax2.legend(loc="best", framealpha=0.5, fancybox=True, fontsize=20)   
    ax2.set_title("Dilution corrected AA image", fontsize = 12)
    ax2.get_xaxis().set_ticks([])
    ax2.get_yaxis().set_ticks([])
    
    x0, y0, w, h = pyplis.helpers.roi2rect(AMBIENT_ROI)
    ax2.add_patch(Rectangle((x0, y0), w, h, fc="none", ec="c"))
    
    fig, ax3 = subplots(1,1)                                 
    ax3.plot(so2_cds_uncorr, "--b", label=r"Uncorr: $\Phi_{SO2}=$"
        "%.2f (+/- %.2f) kg/s" %(phi_uncorr/1000.0, phi_uncorr_err/1000.0))
    ax3.plot(so2_cds_corr, "-g", label=r"Corr: $\Phi_{SO2}=$"
        "%.2f (+/- %.2f) kg/s" %(phi_corr/1000.0, phi_corr_err/1000.0))
    
    ax3.set_title("Cross section profile", fontsize = 12)
    ax3.legend(loc="best", framealpha=0.5, fancybox= True, fontsize = 12)
    ax3.set_xlim([0, len(pix_dists_line)])
    ax3.set_ylim([0, 5e18])
    ax3.set_ylabel(r"$S_{SO2}$ [cm$^{-2}$]", fontsize=14)
    ax3.set_xlabel("PCS", fontsize=14)
    ax3.grid()
    
    # also plot plume pixel mask
    ax4 = pyplis.Img(plume_pix_mask).show(cmap="gray", tit="Plume pixel mask")
    
    if SAVEFIGS:
        ax = [ax0, ax1, ax2, ax3, ax4]
        for k in range(len(ax)):
            ax[k].set_title("") #remove titles for saving
            ax[k].figure.savefig(join(SAVE_DIR, "ex11_out_%d.%s" %(k, FORMAT)),
                                 format=FORMAT, dpi=DPI)
        basemap.ax.set_axis_off()
        basemap.ax.view_init(15, 345)
        basemap.ax.figure.savefig(join(SAVE_DIR, "ex11_out_5.%s" %FORMAT),
                                  format=FORMAT, dpi=DPI)


    # Display images or not    
    (options, args)   =  OPTPARSE.parse_args()
    try:
        if int(options.show) == 1:
            show()
    except:
        print "Use option --show 1 if you want the plots to be displayed"
