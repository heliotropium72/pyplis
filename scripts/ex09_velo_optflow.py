# -*- coding: utf-8 -*-
"""
pyplis example script no. 9 - Plume velocity retrieval using Farneback optical 
flow algorithm
"""
from SETTINGS import check_version
# Raises Exception if conflict occurs
check_version()

from matplotlib.pyplot import close, show, subplots, figure, xticks, yticks, sca, rcParams
rcParams["font.size"] =16

from os.path import join, basename
import pyplis

### IMPORT GLOBAL SETTINGS
from SETTINGS import SAVEFIGS, SAVE_DIR, FORMAT, DPI, OPTPARSE, LINES

PCS1, PCS2 = LINES

### IMPORTS FROM OTHER EXAMPLE SCRIPTS
from ex04_prep_aa_imglist import prepare_aa_image_list

### SCRIPT OPTIONS  

PEAK_SIGMA_TOL=2

# perform histogram analysis for all images in time series
HISTO_ANALYSIS_ALL = 1
HISTO_ANALYSIS_START_IDX = 1
HISTO_ANALYSIS_STOP_IDX = 207#10

#Gauss pyramid level
PYRLEVEL = 1
BLUR = 0
ROI_CONTRAST = [0, 0, 1344, 730]
MIN_AA = 0.05
   
def analyse_and_plot(lst, lines):
    fig = figure(figsize=(14,8))

    ax0 = fig.add_axes([0.01, 0.15, 0.59, 0.8])
    #ax0.set_axis_off()
    ax1 = fig.add_axes([0.61, 0.15, 0.16, 0.8])
    ax2 = fig.add_axes([0.78, 0.15, 0.16, 0.8])
    mask = lst.get_thresh_mask(MIN_AA)
    fl = lst.optflow
    fl.plot(ax=ax0)#, in_roi=True)
    for line in lines:
        m = mask * line.get_rotated_roi_mask(fl.flow.shape[:2])
        line.plot_line_on_grid(ax=ax0, include_normal=1,
                               include_roi_rot=1)
        try:
            _, mu, sigma = fl.plot_orientation_histo(pix_mask=m, 
                                                     apply_fit=True, ax=ax1, 
                                                     color=line.color)
            ax1.legend_.remove()
            low, high = mu-sigma, mu+sigma
            fl.plot_length_histo(pix_mask=m, ax=ax2, dir_low=low, 
                                 dir_high=high, color=line.color)
        except:
            pass
    #pyplis.helpers.set_ax_lim_roi(roi_disp, ax0)
    ax0.get_xaxis().set_ticks([])
    ax0.get_yaxis().set_ticks([])
    ax0.set_title("")

    ymax = max([ax1.get_ylim()[1], ax2.get_ylim()[1]])
    ax1.set_title("")
    ax1.set_xlabel(r"$\varphi\,[^\circ]$", fontsize=20)
    ax1.set_ylim([0, ymax]) 
    ax1.get_yaxis().set_ticks([])
    ax2.yaxis.tick_right()
    ax2.yaxis.set_label_position("right")
    ax2.set_xlabel(r"$|\mathbf{f}|$ [pix]", fontsize=20)
    ax2.set_ylabel("Counts / bin", fontsize=20)
    ax2.set_ylim([0, ymax])
 
    ax2.set_title("")
    ax2.legend_.remove()
    
    sca(ax1)
    xticks(rotation=40, ha="right")
    sca(ax2)
    yticks(rotation=90, va="center")

    return fig

### SCRIPT MAIN FUNCTION
if __name__ == "__main__":
    close("all")
    figs = []
    # Prepare aa image list (see example 4)
    aa_list = prepare_aa_image_list()
    
    # the aa image list includes the measurement geometry, get pixel
    # distance image where pixel values correspond to step widths in the plume, 
    # obviously, the distance values depend on the downscaling factor, which
    # is calculated from the analysis pyramid level (PYRLEVEL)
    dist_img, _, _ = aa_list.meas_geometry.get_all_pix_to_pix_dists(
                                            pyrlevel=PYRLEVEL)
    # set the pyramid level in the list
    aa_list.pyrlevel = PYRLEVEL
    # add some blurring.. or not (if BLUR = 0)
    aa_list.add_gaussian_blurring(BLUR)
    
    # Access to the optical flow module in the image list. If optflow_mode is 
    # active in the list, then, whenever the list index changes (e.g. using
    # list.next_img(), or list.goto_img(100)), the optical flow field is 
    # calculated between the current list image and the next one
    fl = aa_list.optflow 
    #(! note: fl is only a pointer, i.e. the "=" is not making a copy of the 
    # object, meaning, that whenever something changes in "fl", it also does
    # in "aa_list.optflow")
    
    # Now activate optical flow calculation in list (this slows down the 
    # speed of the analysis, since the optical flow calculation is 
    # comparatively slow    
    s = aa_list.optflow.settings
    s.hist_dir_gnum_max = 10
    s.hist_dir_binres = 10
    s.hist_sigma_tol=PEAK_SIGMA_TOL
    
    s.roi_rad = ROI_CONTRAST
    

    aa_list.optflow_mode = True

    plume_mask = pyplis.Img(aa_list.get_thresh_mask(MIN_AA))
    plume_mask.show(tit="AA threshold mask")
    
    figs.append(analyse_and_plot(aa_list, LINES))
        
    figs.append(fl.plot_flow_histograms(PCS1, plume_mask.img))
    figs.append(fl.plot_flow_histograms(PCS2, plume_mask.img))
    
    #Show an image containing plume speed magnitudes (ignoring direction)
    velo_img = pyplis.Img(fl.to_plume_speed(dist_img))
    velo_img.show(vmin=0, vmax = 10, cmap = "Greens",
                  tit = "Optical flow plume velocities",
                  zlabel ="Plume velo [m/s]")
    
    # Create two objects used to store time series information about the 
    # retrieved plume properties
    plume_props_l1 = pyplis.plumespeed.LocalPlumeProperties(PCS1.line_id)
    plume_props_l2 = pyplis.plumespeed.LocalPlumeProperties(PCS2.line_id)
    
    if HISTO_ANALYSIS_ALL:
        for k in range(HISTO_ANALYSIS_START_IDX, HISTO_ANALYSIS_STOP_IDX):
            plume_mask = aa_list.get_thresh_mask(MIN_AA)
            plume_props_l1.get_and_append_from_farneback(fl, line=PCS1,
                                                         pix_mask=plume_mask)
            plume_props_l2.get_and_append_from_farneback(fl, line=PCS2,
                                                         pix_mask=plume_mask)
            aa_list.next_img()
            
        plume_props_l1 = plume_props_l1.interpolate()
        plume_props_l2 = plume_props_l2.interpolate()
        
        fig, ax = subplots(2, 1, figsize=(10, 9))
    
        plume_props_l1.plot_directions(ax=ax[0], 
                                       color=PCS1.color, 
                                       label="PCS1")
        plume_props_l2.plot_directions(ax=ax[0], color=PCS2.color, 
                                       label="PCS2")
       
        plume_props_l1.plot_magnitudes(normalised=True, ax=ax[1], 
                                      date_fmt="%H:%M:%S", color=PCS1.color, 
                                      label="PCS1")
        plume_props_l2.plot_magnitudes(normalised=True, ax=ax[1], 
                                      date_fmt="%H:%M:%S", color=PCS2.color, 
                                      label="PCS2") 
        ax[0].set_xticklabels([])
        #ax[0].legend(loc='best', fancybox=True, framealpha=0.5, fontsize=14) 
        #ax[0].set_title("Movement direction")
        #ax[1].set_title("Displacement length")
        figs.append(fig)
        # Save the time series as txt
        plume_props_l1.save_txt(join(SAVE_DIR, 
                                     "ex09_plumeprops_young_plume.txt"))
        plume_props_l2.save_txt(join(SAVE_DIR, 
                                     "ex09_plumeprops_aged_plume.txt"))
        
    if SAVEFIGS:
        for k in range(len(figs)):
            figs[k].savefig(join(SAVE_DIR, "ex09_out_%d.%s" 
                            %((k+1), FORMAT)),
                            format=FORMAT, dpi=DPI)

    # Display images or not    
    (options, args)   =  OPTPARSE.parse_args()
    try:
        if int(options.show) == 1:
            show()
    except:
        print "Use option --show 1 if you want the plots to be displayed"
        
        
        
        
