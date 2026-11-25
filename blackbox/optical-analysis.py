import ROOT
from ROOT import TLatex
import pip
import os
import sys
import math
import argparse
import pandas as pd
import csv
import scipy.optimize as opt
from scipy.optimize import curve_fit
import shutil
from datetime import datetime, timedelta

moddir=os.getcwd()   

os.chdir(moddir)

import h5py
import numpy as np
from optical_summary import write_optical_summary
from spark_detection import draw_plot_statistics, plot_statistics, spark_cut

import ROOT
from ROOT import TLatex

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT.gErrorIgnoreLevel = ROOT.kWarning 
ROOT.gStyle.SetOptStat("emrou")
ROOT.gROOT.SetBatch(True)

path=str(sys.argv[1])
directory=str(sys.argv[2])
data=str(sys.argv[3])

res_folder="signal-integral"

SAVE_SIGNAL_PLOTS = os.environ.get("WARTPC_SIGNAL_PLOTS") == "1"

shutil.rmtree(path+"/"+directory+"/"+res_folder+"_y", ignore_errors=True)
shutil.rmtree(path+"/"+directory+"/"+res_folder+"_x", ignore_errors=True)

input_file_name = path+"/"+directory+"/"+data

step = 1

f = h5py.File(input_file_name, "r")

# Directly slicing the HDF5 file is slow due to limitations
# of the h5py library.
tot = f["PixelHits"]["tot"][::step]
toa = f["PixelHits"]["toa"][::step]
x = f["PixelHits"]["x"][::step]
y = f["PixelHits"]["y"][::step]

# --- Diagnostics (added): everything needed to see why a run fails is saved in
# <run>/diagnostics/, before the steps that can fail.
diag_folder = path+"/"+directory+"/diagnostics"
os.makedirs(diag_folder, exist_ok=True)
keep, time, time_cut = spark_cut(toa, tot, f"{path}/{directory}/diagnostics/spark_status.txt")
spark_cutting = keep is not None and not keep.all()
if spark_cutting:
    removed_hits = int(np.count_nonzero(~keep))
    toa, tot, x, y = toa[keep], tot[keep], x[keep], y[keep]

if len(toa) == 0:
    with open(diag_folder+"/no_hits.txt", "w") as fd:
        fd.write(f"{input_file_name} contains no pixel hits; nothing to analyse.\n")
    print(f"{directory}: no pixel hits in {data} (see {diag_folder}/no_hits.txt)")
    sys.exit(1)

with open(f"{path}/{directory}/settings.csv", "r") as f:
    reader = csv.reader(f)

    for row in reader:
        ID=str(row[0])
        pres=float(row[1])
        FC=float(row[2])
        E1=float(row[3])
        E2=float(row[4])
        E3=float(row[5])
        E4=float(row[6])
        purity=float(row[7])

perChipTOT = np.zeros((256,256), dtype = np.int64)
np.add.at(perChipTOT, (y, x), tot)

y_max, x_max = np.unravel_index(np.argmax(perChipTOT), perChipTOT.shape)

perChipHIT = np.zeros((256,256), dtype = np.int32)
np.add.at(perChipHIT, (y, x), 1)

total_time=time-time_cut

# --- Rebinning test (added): merge REBIN x REBIN pixels into one bin before
# the 2D Gaussian fit. Set with the environment variable WARTPC_REBIN (default
# 1 = no rebinning, the original behaviour). The fit result is converted back
# to original pixel units, so everything after the fit is unchanged.
REBIN = int(os.environ.get("WARTPC_REBIN", "1") or 1)
if REBIN < 1 or 256 % REBIN:
    print(f"warning: WARTPC_REBIN={REBIN} does not divide 256; not rebinning")
    REBIN = 1
# Merge adjacent X pixels for both the 2D Gaussian and X sideband fits.
rebin_x_setting = os.environ.get("WARTPC_REBIN_X", "0").strip().lower()
if rebin_x_setting in ("1", "on", "yes", "true"):
    REBIN_X = 2  # Legacy switch enabled pairwise merging.
elif rebin_x_setting in ("2", "4", "8", "16"):
    REBIN_X = int(rebin_x_setting)
else:
    REBIN_X = 1
if REBIN_X > 1 and REBIN > 1:
    sys.exit("X rebinning and 2D rebinning cannot be combined")
FX, FY = (REBIN_X, 1) if REBIN_X > 1 else (REBIN, REBIN)
if REBIN_X > 1:
    REBIN_LABEL = f"rebinX({REBIN_X}): X pixels merged in the 2D fit and X sideband fits"
    REBIN_SFX = f"-rebinX{REBIN_X}"
elif REBIN > 1:
    REBIN_LABEL, REBIN_SFX = f"{REBIN}x{REBIN} pixels merged (2D fit only)", f"-rebin{REBIN}"
else:
    REBIN_LABEL, REBIN_SFX = "none", ""
tot_fit_map = perChipTOT.reshape(256 // FY, FY, 256 // FX, FX).sum(axis=(1, 3))
hit_fit_map = perChipHIT.reshape(256 // FY, FY, 256 // FX, FX).sum(axis=(1, 3))
if REBIN_LABEL != "none":
    print(f"{directory}: rebinning: {REBIN_LABEL}; 2D fit map {tot_fit_map.shape[0]} (Y) x {tot_fit_map.shape[1]} (X) bins")


def save_map_plots(tot_map, hit_map, fx=1, fy=1, sfx=""):
    """Map, X/Y slices through the peak, and map with slices, for a map whose
    bins are fx (X) x fy (Y) pixels (1, 1: original). Axes are always in pixel units."""
    unit = "pixel" if fx == fy == 1 else f"{fx}x{fy}-pixel bin"
    by, bx = np.unravel_index(np.argmax(tot_map), tot_map.shape)
    cen_x = lambda b: fx * b + (fx - 1) / 2         # bin index -> pixel coordinate
    cen_y = lambda b: fy * b + (fy - 1) / 2
    px, py = cen_x(bx), cen_y(by)
    t_sum = float(tot_map.sum())
    frac = 100 * tot_map[by, bx] / t_sum if t_sum else 0
    ext = (-0.5, 255.5, 255.5, -0.5)
    title_bin = "" if fx == fy == 1 else (f", rebinX({fx})" if fy == 1 else f", rebinned by {fx}")
    centres_x, centres_y = cen_x(np.arange(tot_map.shape[1])), cen_y(np.arange(tot_map.shape[0]))
    edges_x = np.arange(tot_map.shape[1] + 1) * fx - 0.5
    edges_y = np.arange(tot_map.shape[0] + 1) * fy - 0.5

    # (a) the map, linear colour scale
    fig, ax = plt.subplots(figsize=(11, 9))
    im = ax.imshow(tot_map, interpolation="nearest", extent=ext)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=f"Summed ToT per {unit}")
    ax.plot(px, py, "r+", ms=16, mew=2)
    ax.set_xlabel("X Pixel", fontsize=14)
    ax.set_ylabel("Y Pixel", fontsize=14)
    ax.set_title(f"{ID}: integrated ToT before the 2D Gaussian fit{title_bin}\n{len(tot):,} hits, "
                 f"+ = hottest {unit} ({px:g}, {py:g}), {frac:.1f}% of total ToT", fontsize=13)
    fig.tight_layout()
    fig.savefig(diag_folder+f"/ToT-image-raw{sfx}.png")
    plt.close(fig)

    # Slices through the peak bin: X slice = the row through it, Y slice = the
    # column through it. Error bars sqrt(hits) * 10.2 as in tpx_analysis.
    slices = {"X": (tot_map[by, :], hit_map[by, :], px, f"row Y = {py:g}"),
              "Y": (tot_map[:, bx], hit_map[:, bx], py, f"column X = {px:g}")}
    with open(diag_folder+f"/projections-raw{sfx}.csv", "w") as fd:
        fd.write(f"axis,pixel_centre,slice_tot(X: row y={py:g}; Y: column x={px:g}),slice_hits,sum_tot\n")
        sum_x, sum_y = tot_map.sum(axis=0), tot_map.sum(axis=1)
        for k in range(len(centres_x)):
            fd.write(f"X,{centres_x[k]:g},{slices['X'][0][k]},{slices['X'][1][k]},{sum_x[k]}\n")
        for k in range(len(centres_y)):
            fd.write(f"Y,{centres_y[k]:g},{slices['Y'][0][k]},{slices['Y'][1][k]},{sum_y[k]}\n")

    def slice_hist(ax, axis_name, tot_p, hit_p, horizontal=False):
        centres, edges_f = (centres_x, edges_x) if axis_name == "X" else (centres_y, edges_y)
        err_p = np.sqrt(hit_p) * 10.2
        orient = "horizontal" if horizontal else "vertical"
        ax.stairs(tot_p, edges_f, orientation=orient, fill=True, color="tab:red", alpha=0.3)
        ax.stairs(tot_p, edges_f, orientation=orient, color="tab:red", lw=1)
        if horizontal:
            ax.errorbar(tot_p, centres, xerr=err_p, fmt="none", ecolor="0.4", lw=0.6)
            ax.set_xlim(left=0)
        else:
            ax.errorbar(centres, tot_p, yerr=err_p, fmt="none", ecolor="0.4", lw=0.6)
            ax.set_ylim(bottom=0)

    # (b) X and Y slices through the peak
    fig, axs = plt.subplots(1, 2, figsize=(20, 7))
    for ax, (axis_name, (tot_p, hit_p, hot, where)) in zip(axs, slices.items()):
        slice_hist(ax, axis_name, tot_p, hit_p)
        ax.axvline(hot, color="tab:blue", ls="--", lw=1, label=f"peak {axis_name} = {hot:g}")
        ax.set_xlim(-0.5, 255.5)
        ax.set_xlabel(f"{axis_name} Pixel", fontsize=14)
        ax.set_ylabel(f"Summed ToT per {unit}", fontsize=14)
        ax.set_title(f"{axis_name} slice through the peak ({where})", fontsize=14)
        ax.legend(fontsize=11)
        ax.grid(alpha=.2)
    fig.suptitle(f"{ID}: X and Y slices through the peak ({px:g}, {py:g}){title_bin}, "
                 f"before fit and background subtraction", fontsize=15)
    fig.tight_layout()
    fig.savefig(diag_folder+f"/projections-raw{sfx}.png")
    plt.close(fig)

    # (c) the map with the X slice above and the Y slice to the right
    fig = plt.figure(figsize=(14, 13))
    gs = fig.add_gridspec(2, 2, width_ratios=(4, 1.3), height_ratios=(1.3, 4), wspace=0.04, hspace=0.04)
    ax_img = fig.add_subplot(gs[1, 0])
    ax_x = fig.add_subplot(gs[0, 0], sharex=ax_img)
    ax_y = fig.add_subplot(gs[1, 1], sharey=ax_img)
    ax_info = fig.add_subplot(gs[0, 1])
    ax_info.axis("off")
    im = ax_img.imshow(tot_map, aspect="auto", interpolation="nearest", extent=ext)
    ax_img.axhline(py, color="w", ls="--", lw=0.8)
    ax_img.axvline(px, color="w", ls="--", lw=0.8)
    ax_img.plot(px, py, "r+", ms=16, mew=2)
    ax_img.set_xlabel("X Pixel", fontsize=14)
    ax_img.set_ylabel("Y Pixel", fontsize=14)
    slice_hist(ax_x, "X", slices["X"][0], slices["X"][1])
    slice_hist(ax_y, "Y", slices["Y"][0], slices["Y"][1], horizontal=True)
    ax_x.axvline(px, color="tab:blue", ls="--", lw=1)
    ax_y.axhline(py, color="tab:blue", ls="--", lw=1)
    ax_x.set_ylabel(f"ToT, row Y={py:g}", fontsize=11)
    ax_y.set_xlabel(f"ToT, column X={px:g}", fontsize=11)
    ax_x.tick_params(labelbottom=False)
    ax_y.tick_params(labelleft=False)
    ax_x.grid(alpha=.2)
    ax_y.grid(alpha=.2)
    ax_img.set_xlim(-0.5, 255.5)
    cax = ax_info.inset_axes([0.08, 0.62, 0.84, 0.1])
    fig.colorbar(im, cax=cax, orientation="horizontal", label=f"Summed ToT per {unit}")
    ax_info.text(0.0, 0.42,
                 f"{ID}\n{len(tot):,} hits\npeak ({px:g}, {py:g})\n= {frac:.1f}% of total ToT\n"
                 f"slices through the peak{title_bin};\nbefore fit and background subtraction",
                 transform=ax_info.transAxes, va="top", fontsize=11)
    fig.suptitle(f"{ID}: integrated ToT with X and Y slices through the peak{title_bin}", fontsize=15, y=0.93)
    fig.savefig(diag_folder+f"/ToT-image-projections{sfx}.png", bbox_inches="tight")
    plt.close(fig)


# --- Diagnostics (added): save the integrated ToT map BEFORE the 2D Gaussian fit,
# so runs that fail in the fit or later still leave the map to inspect.
# A failure here only prints a warning; it never stops the analysis.
try:
    np.save(diag_folder+"/perChipTOT.npy", perChipTOT)
    np.save(diag_folder+"/perChipHIT.npy", perChipHIT)
    tot_sum = int(perChipTOT.sum())
    max_val = int(perChipTOT[y_max, x_max])
    with open(diag_folder+"/summary.txt", "w") as fd:
        fd.write(f"run: {directory} (settings ID {ID})\n"
                 f"hits: {len(tot)}\n"
                 f"pixels with hits: {int((perChipHIT > 0).sum())} of 65536\n"
                 f"total ToT: {tot_sum}\n"
                 f"hottest pixel (x, y): ({x_max}, {y_max}), ToT {max_val}"
                 f" = {100 * max_val / tot_sum if tot_sum else 0:.2f}% of total\n"
                 f"exposure (total_time): {total_time}\n"
                 f"rebinning: {REBIN_LABEL}\n")
    save_map_plots(perChipTOT, perChipHIT)
    if REBIN_SFX:
        np.save(diag_folder+f"/perChipTOT{REBIN_SFX}.npy", tot_fit_map)
        save_map_plots(tot_fit_map, hit_fit_map, FX, FY, REBIN_SFX)
except Exception as e:
    print(f"warning: could not save ToT diagnostics for {directory}: {e}")

###get the 1 sigma range of the y value of the fit

def twoD_Gaussian(xy, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    y,x  = xy
    xo = float(xo)
    yo = float(yo)
    a = (np.cos(theta)**2)/(2*sigma_x**2) + (np.sin(theta)**2)/(2*sigma_y**2)
    b = -(np.sin(2*theta))/(4*sigma_x**2) + (np.sin(2*theta))/(4*sigma_y**2)
    c = (np.sin(theta)**2)/(2*sigma_x**2) + (np.cos(theta)**2)/(2*sigma_y**2)
    g = offset + amplitude*np.exp( - (a*((x-xo)**2) + 2*b*(x-xo)*(y-yo) 
                            + c*((y-yo)**2)))
    return g

xFit = []
yFit = []
dataFit = []
for YY in np.arange(0,256,1):
    for XX in np.arange(0,256,1):
        dataFit.append(perChipTOT[YY, XX])
        xFit.append(XX)
        yFit.append(YY)
xFit = np.array(xFit)
yFit = np.array(yFit)
dataFit = np.array(dataFit)

initial_guess = (10E+3, x_max, y_max, 1.0, 1.0,0.,0.)#amp,xmean,ymean,xsig,ysig,theta,offset

twoD_Gaussian((yFit,xFit), *initial_guess).shape

# --- Rebinning (added): the fit runs on the rebinned map, with each bin placed
# at its centre in pixel coordinates (FX*k + (FX-1)/2), so the centre and
# widths come out in pixels; amplitude and offset are converted from per bin
# to per pixel. With no rebinning this is exactly the original fit.
yb_grid, xb_grid = np.indices(tot_fit_map.shape)
xFitR = (FX * xb_grid + (FX - 1) / 2).ravel()
yFitR = (FY * yb_grid + (FY - 1) / 2).ravel()
dataFitR = tot_fit_map.ravel()
yb_max, xb_max = np.unravel_index(np.argmax(tot_fit_map), tot_fit_map.shape)
if FX == FY == 1:
    initial_guess_fit = initial_guess
else:
    initial_guess_fit = (10E+3 * FX * FY, FX * xb_max + (FX - 1) / 2, FY * yb_max + (FY - 1) / 2,
                         1.0, 1.0, 0., 0.)

try:
    popt, pcov = opt.curve_fit(twoD_Gaussian, (yFitR, xFitR), dataFitR, p0=initial_guess_fit)
    if FX * FY > 1:
        scale = np.array([1 / (FX * FY), 1, 1, 1, 1, 1, 1 / (FX * FY)])
        popt = popt * scale
        pcov = pcov * np.outer(scale, scale)
except Exception as e:
    # --- Diagnostics (added): record why the fit failed, then fail as before.
    with open(diag_folder+"/fit_failed.txt", "w") as fd:
        fd.write(f"2D Gaussian fit failed: {type(e).__name__}: {e}\n"
                 f"rebinning: {REBIN_LABEL}\n"
                 f"initial guess (amp per bin, x0, y0, sigma_x, sigma_y in pixels, theta, offset): "
                 f"{initial_guess_fit}\n"
                 f"See ToT-image-raw.png and summary.txt in this folder.\n")
    print(f"{directory}: 2D Gaussian fit failed: {e} (see {diag_folder}/fit_failed.txt)")
    raise

# --- Diagnostics (added): record the fit result; flag values that make the
# later signal/sideband regions meaningless.
with np.errstate(invalid="ignore"):
    perr = np.sqrt(np.diag(pcov))
fit_names = ["amplitude", "x0", "y0", "sigma_x", "sigma_y", "theta", "offset"]
fit_flags = []
if not np.all(np.isfinite(popt)) or not np.all(np.isfinite(perr)):
    fit_flags.append("non-finite parameter or uncertainty")
if not (0 <= popt[1] < 256 and 0 <= popt[2] < 256):
    fit_flags.append("centre outside the 256x256 chip")
if abs(popt[3]) < 0.5 or abs(popt[4]) < 0.5:
    fit_flags.append("width below half a pixel (fit may have locked onto a hot pixel)")
if abs(popt[3]) > 128 or abs(popt[4]) > 128:
    fit_flags.append("width larger than half the chip")
with open(diag_folder+"/fit_parameters.txt", "w") as fd:
    for n, v, err in zip(fit_names, popt, perr):
        fd.write(f"{n:10s} {v:14.6g} +- {err:.3g}\n")
    fd.write("flags: " + ("; ".join(fit_flags) if fit_flags else "none") + "\n")
    fd.write(f"rebinning: {REBIN_LABEL}; parameters above are per original pixel\n")
if fit_flags:
    print(f"{directory}: 2D Gaussian fit looks suspicious: {'; '.join(fit_flags)} "
          f"(see {diag_folder}/fit_parameters.txt)")


ymean= popt[2]
ysig=popt[4]
xmean=popt[1]
xsig=popt[3]
fig_amp=popt[0]
fig_theta=popt[5]
fig_offset=popt[6]

xsig_proj=np.sqrt(xsig**2 *np.cos(fig_theta)**2+ysig**2 * np.sin(fig_theta)**2)
ysig_proj=np.sqrt(xsig**2*np.sin(fig_theta)**2+ysig**2 * np.cos(fig_theta)**2)

tot_x_collapse = np.ascontiguousarray(np.sum(perChipTOT[:,:], axis=0),dtype=np.float64)/1E6
hit_x_collapse = np.sum(perChipHIT[:,:], axis=0)
if REBIN_X > 1:
    tot_x_collapse = tot_x_collapse.reshape(-1, REBIN_X).sum(axis=1)
    hit_x_collapse = hit_x_collapse.reshape(-1, REBIN_X).sum(axis=1)

def x_positions(n):
    """Return the centres of the projection bins in original pixel coordinates."""
    width = 256 // n
    return width * np.arange(n, dtype=float) + (width - 1) / 2

tot_y_collapse = np.ascontiguousarray(np.sum(perChipTOT[:,:], axis=1),dtype=np.float64)/1E6
hit_y_collapse = np.sum(perChipHIT[:,:], axis=1)

def tpx_analysis(poly_type,mean,sig,tot_collapse,hit_collapse,signal_sig, sideband_sig,twoD_Gaussian,perChipTOT,order,directory,axis,res_folder,exposure,spa_cut):

    folder=path+"/"+directory+"/"+res_folder+"/"+str(poly_type)+"/"+str(signal_sig)+"to"+str(sideband_sig)
    csvfolder=path+"/"+directory+"/"+res_folder+"/"+str(poly_type)
    
    save_standard_plot = order == 2 and signal_sig == 4 and sideband_sig == 8

    try:
        os.makedirs(folder if save_standard_plot or SAVE_SIGNAL_PLOTS else csvfolder)
    except:
        #print("error making folder at "+folder)
        pass

    sideband_low = int(round(mean-7*np.abs(sig),0))#int(round(ymean-9*np.abs(ysig),0))
    signal_low = int(round(mean-3*np.abs(sig),0))

    signal_high = int(round(mean+signal_sig*np.abs(sig),0))
    sideband_high = int(round(mean+sideband_sig*np.abs(sig),0))
        
    if SAVE_SIGNAL_PLOTS or (save_standard_plot and axis == 0):
        tot = plt.figure(figsize=(10,10))
        plt.imshow(perChipTOT)
        plt.tick_params(axis='both', which='major', labelsize=20)
        plt.xlabel('X Pixel', fontsize=25)
        plt.ylabel('Y Pixel', fontsize=25)
        plt.title('Integrated Time-over-Threshold Image', fontsize=25)
        if axis == 0:
            plt.axvline(sideband_low)
            plt.axvline(signal_low)
            plt.axvline(signal_high)
            plt.axvline(sideband_high)
        if axis == 1:
            plt.axhline(sideband_low)
            plt.axhline(signal_low)
            plt.axhline(signal_high)
            plt.axhline(sideband_high)
        plt.contour(np.arange(0,256,1), np.arange(0,256,1), twoD_Gaussian((yFit,xFit), *popt).reshape(256,256), 3, colors='w')
        draw_plot_statistics(plt.gca(), plot_statistics(perChipTOT, quantity="ToT per pixel"))
        plt.savefig(folder+"/ToT-image.png")
        plt.close()

    ycomp_3sig=[]
    ycomp_3sig_err=[]

    ycomp_combined=np.array([])
    ycomp_err_combined=np.array([])
    
    ycomp_3sig = tot_collapse
    hit_3sig = hit_collapse

    for ll in range (len(ycomp_3sig)):
        err_3sig=np.sqrt((hit_3sig[ll]*(10.2/1E6)**2))#+ycomp_3sig[ll])
        ycomp_3sig_err=np.append(ycomp_3sig_err,err_3sig)

    xpos_3sig=[]

    xpos_3sig = x_positions(len(ycomp_3sig))
    
    sig3_full=[]
    sig3_full_bins=[]
    sig3_full_err=[]
    sig3_signal=[]
    sig3_signal_err=[]
    sig3_signal_bins=[]
    sig3_bkg=np.array([])
    sig3_bkg_err=np.array([])
    sig3_bkg_bins=np.array([])

    for rr in range (len(xpos_3sig)):
        if signal_low<=xpos_3sig[rr]<=signal_high:
            sig3_signal=np.append(sig3_signal,ycomp_3sig[rr])
            sig3_signal_err=np.append(sig3_signal_err,ycomp_3sig_err[rr])
            sig3_signal_bins=np.append(sig3_signal_bins,xpos_3sig[rr])
            sig3_full=np.append(sig3_full,ycomp_3sig[rr])
            sig3_full_err=np.append(sig3_full_err,ycomp_3sig_err[rr])
            sig3_full_bins=np.append(sig3_full_bins,xpos_3sig[rr])
        elif(sideband_low<=xpos_3sig[rr]<signal_low) or (signal_high<xpos_3sig[rr]<=sideband_high):
            sig3_bkg=np.append(sig3_bkg,ycomp_3sig[rr])
            sig3_bkg_err=np.append(sig3_bkg_err,ycomp_3sig_err[rr])
            sig3_bkg_bins=np.append(sig3_bkg_bins,xpos_3sig[rr])
            sig3_full=np.append(sig3_full,ycomp_3sig[rr])
            sig3_full_err=np.append(sig3_full_err,ycomp_3sig_err[rr])
            sig3_full_bins=np.append(sig3_full_bins,xpos_3sig[rr])

    full_data_sig3 = ROOT.TGraphErrors(len(xpos_3sig), xpos_3sig, ycomp_3sig,0,ycomp_3sig_err)

    data_sig3 = ROOT.TGraphErrors(len(sig3_bkg_bins), sig3_bkg_bins, sig3_bkg,0,sig3_bkg_err)
    
    if order == 4:
        dat_fit_sig3 = ROOT.TF1("dat_fit_sig3", "[0]+[1]*x+[2]*pow(x,2)+[3]*pow(x,3)+[4]*pow(x,4)",min(sig3_bkg_bins),max(sig3_bkg_bins) )
        eq = f"y = a+bx+cx^2+dx^3+ex^4"
    elif order == 3:
        dat_fit_sig3 = ROOT.TF1("dat_fit_sig3", "[0]+[1]*x+[2]*pow(x,2)+[3]*pow(x,3)",min(sig3_bkg_bins),max(sig3_bkg_bins) )
        eq = f"y = a+bx+cx^2+dx^3"
    elif order ==2:
        dat_fit_sig3 = ROOT.TF1("dat_fit_sig3", "[0]+[1]*x+[2]*pow(x,2)",min(sig3_bkg_bins),max(sig3_bkg_bins) )
        eq = f"y = a+bx+cx^2"
        
    dat_fit_sig3.SetLineColor(4)
    sig3_fit_res = data_sig3.Fit("dat_fit_sig3", "S Q R")# "S"=store result, "Q"=quiet (no spam)
    f3 = data_sig3.GetFunction("dat_fit_sig3")
    ndf3=f3.GetNDF()
    chi3=f3.GetChisquare()
    chindf3=chi3/ndf3
    #print("chi2 = "+str(chi3)+"\n")
    #print("ndf = "+str(ndf3)+"\n")
    #print("chi2/NDF = "+str(chindf3)+"\n")

    if SAVE_SIGNAL_PLOTS:
        canvas_sig3 = ROOT.TCanvas("c3", "TGraph Example", 800, 600)

        if axis == 0:
            full_data_sig3.SetTitle("Full Data with Upper Sideband Between "+str(signal_sig)+"#sigma and "+str(sideband_sig)+"#sigma;X Pixel;ToT (ms)")
        if axis == 1:
            full_data_sig3.SetTitle("Full Data with Upper Sideband Between "+str(signal_sig)+"#sigma and "+str(sideband_sig)+"#sigma;Y Pixel;ToT (ms)")
        full_data_sig3.GetYaxis().SetRangeUser(0,1.1*max(ycomp_3sig));
        full_data_sig3.SetMarkerStyle(8)
        full_data_sig3.SetMarkerSize(1.3)
        full_data_sig3.SetMarkerColor(2)
        full_data_sig3.Draw("APE")
        data_sig3.SetMarkerStyle(8)
        data_sig3.SetMarkerSize(1.3)
        data_sig3.SetMarkerColor(4)

        latex_fit = ROOT.TLatex()
        latex_fit.SetNDC()
        latex_fit.SetTextSize(0.03)
        latex_fit.DrawLatex(0.55, 0.85, "Fit: "+eq)

        latex_int = ROOT.TLatex()
        latex_int.SetNDC()
        latex_int.SetTextSize(0.03)
        latex_int.DrawLatex(0.55, 0.80, "Integral is: "+str(round(sum(ycomp_3sig,0))))
        if spa_cut == True:
            latex_info = ROOT.TLatex()
            latex_info.SetNDC()
            latex_info.SetTextSize(0.03)
            latex_info.DrawLatex(0.55, 0.75, f"Hits removed by spark cut: {removed_hits:,}")

        latex_ID = ROOT.TLatex()
        latex_ID.SetNDC()
        latex_ID.SetTextSize(0.03)
        latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")
        if len(ycomp_3sig) != 256:
            latex_ID.DrawLatex(0.15, 0.80, f"RebinX({REBIN_X}): {len(ycomp_3sig)} bins")

        data_sig3.Draw("PE SAME")
        dat_fit_sig3.Draw("SAME")

        canvas_sig3.SaveAs(folder+"/"+str(signal_sig)+"to"+str(sideband_sig)+".png")
        canvas_sig3.SaveAs(folder+"/"+str(signal_sig)+"to"+str(sideband_sig)+".eps")

        full_data_sig3.GetYaxis().SetRangeUser(0,0.75*max(ycomp_3sig));

        canvas_sig3.SaveAs(folder+"/"+str(signal_sig)+"to"+str(sideband_sig)+"_zoom.png")
        canvas_sig3.SaveAs(folder+"/"+str(signal_sig)+"to"+str(sideband_sig)+"_zoom.eps")

        canvas_sig3.Update()
        canvas_sig3.Close()
        del canvas_sig3

    for yy in range(len(sig3_full_bins)):
        bkg_est=dat_fit_sig3.Eval(sig3_full_bins[yy])#var0+var1*sig3_full_bins[yy]+var2*sig3_full_bins[yy]**2+var3*sig3_full_bins[yy]**3#+var4*sig3_full_bins[yy]
        sig3_full[yy]=sig3_full[yy]-bkg_est
    
    ADU3=sum(sig3_full)/exposure

    #print(sum(sig3_full))
    #print(exposure)

    if SAVE_SIGNAL_PLOTS or save_standard_plot:
        signal3 = ROOT.TGraphErrors(len(sig3_full_bins), sig3_full_bins, sig3_full,0,sig3_full_err)

        canvas_signal3 = ROOT.TCanvas("c4", "TGraph Example", 800, 600)
        signal3.SetTitle("Background Subtracted Signal with "+str(signal_sig)+"#sigma and "+str(sideband_sig)+"#sigma upper sideband;X Pixel;ToT (ms)")
        signal3.SetMarkerStyle(8)
        signal3.SetMarkerSize(1.3)
        signal3.SetMarkerColor(2)
        # Pad outward even if all the residuals have the same sign.
        minimum, maximum = min(sig3_full), max(sig3_full)
        margin = 0.1 * max(abs(minimum), abs(maximum)) or 1.0
        lower, upper = minimum - margin, maximum + margin
        signal3.GetYaxis().SetRangeUser(lower, upper)
        signal3.Draw("APE")

        latex_fit2 = ROOT.TLatex()
        latex_fit2.SetNDC()
        latex_fit2.SetTextSize(0.03)
        latex_fit2.DrawLatex(0.55, 0.85, "Fit: "+eq)

        latex_int2 = ROOT.TLatex()
        latex_int2.SetNDC()
        latex_int2.SetTextSize(0.03)
        latex_int2.DrawLatex(0.55, 0.80, f"Integral is: {sum(sig3_full):.0f}")
        if spa_cut == True:
            latex_info2 = ROOT.TLatex()
            latex_info2.SetNDC()
            latex_info2.SetTextSize(0.03)
            latex_info2.DrawLatex(0.55, 0.75, f"Hits removed by spark cut: {removed_hits:,}")

        line = ROOT.TLine(signal3.GetXaxis().GetXmin(), 0, signal3.GetXaxis().GetXmax(), 0) #y=0 from x=0 to x=100
        line.SetLineColor(11)
        line.SetLineWidth(2)
        line.Draw("same")

        latex_ID = ROOT.TLatex()
        latex_ID.SetNDC()
        latex_ID.SetTextSize(0.03)
        latex_ID.DrawLatex(0.15, 0.85, f"ID: {ID}")
        if len(ycomp_3sig) != 256:
            latex_ID.DrawLatex(0.15, 0.80, f"RebinX({REBIN_X}): {len(ycomp_3sig)} bins")

        stats_signal = ROOT.TPaveText(0.64, 0.44, 0.89, 0.63, "NDC")
        stats_signal.SetTextSize(0.025)
        stats_signal.SetTextAlign(12)
        stats_signal.SetFillColor(ROOT.kWhite)
        for statistic in plot_statistics(sig3_full, lower, upper, "residual ToT"):
            stats_signal.AddText(statistic)
        stats_signal.Draw()

        canvas_signal3.SaveAs(folder+"/"+str(signal_sig)+"to"+str(sideband_sig)+"_signal.png")
        if SAVE_SIGNAL_PLOTS:
            canvas_signal3.SaveAs(folder+"/"+str(signal_sig)+"to"+str(sideband_sig)+"_signal.eps")

        canvas_signal3.Update()
        canvas_signal3.Close()
        del canvas_signal3

    out = pd.DataFrame([[str(signal_sig)+"to"+str(sideband_sig)],[ADU3]])
    raw = pd.DataFrame([[str(signal_sig)+"to"+str(sideband_sig)],[sum(sig3_full)]])

    out.T.to_csv(csvfolder+"/integrals.csv", mode="a", index=False, header=False)
    raw.T.to_csv(csvfolder+"/raw.csv", mode="a", index=False, header=False)

    #for canvas in ROOT.gROOT.GetListOfCanvases():
        #canvas.Close()
        #canvas.Delete()

    #return(ADU3)
    
signal_sig_list=[3,3,3,3,4,4,4,5,5,6]

sideband_sig_list=[7,8,9,10,8,9,10,9,10,10]

# --- Diagnostics (added): the X and Y projections exactly as tpx_analysis uses
# them, with its signal and sideband regions marked, for EVERY setting, saved
# BEFORE any sideband/background fit. They exist even if that fit crashes.
# A failure here only prints a warning; it never stops the analysis.
try:
    sb_folder = diag_folder+"/sideband_regions"
    os.makedirs(sb_folder, exist_ok=True)
    axes_info = [("X", xmean, xsig_proj, tot_x_collapse, hit_x_collapse),
                 ("Y", ymean, ysig_proj, tot_y_collapse, hit_y_collapse)]
    sb_rows = []
    for aa in range(len(signal_sig_list)):
        s_sig, b_sig = signal_sig_list[aa], sideband_sig_list[aa]
        fig, axs = plt.subplots(1, 2, figsize=(20, 7))
        for ax, (axis_name, mean, sig, tot_p, hit_p) in zip(axs, axes_info):
            # Same region definitions as in tpx_analysis
            sideband_low = int(round(mean-7*np.abs(sig), 0))
            signal_low = int(round(mean-3*np.abs(sig), 0))
            signal_high = int(round(mean+s_sig*np.abs(sig), 0))
            sideband_high = int(round(mean+b_sig*np.abs(sig), 0))
            pix = x_positions(len(tot_p))
            in_signal = (pix >= signal_low) & (pix <= signal_high)
            in_side = ((pix >= sideband_low) & (pix < signal_low)) | ((pix > signal_high) & (pix <= sideband_high))
            err_p = np.sqrt(hit_p * (10.2 / 1E6) ** 2)
            ax.errorbar(pix, tot_p, yerr=err_p, fmt="o", ms=3, color="tab:red", ecolor="0.7",
                        lw=0.6, label="full projection")
            ax.errorbar(pix[in_side], tot_p[in_side], yerr=err_p[in_side], fmt="o", ms=4,
                        color="tab:blue", ecolor="tab:blue", lw=0.6,
                        label=f"sideband points used for the fit ({int(in_side.sum())})")
            ax.axvspan(signal_low - 0.5, signal_high + 0.5, color="gold", alpha=0.25,
                       label=f"signal region {signal_low}..{signal_high}")
            for b in (sideband_low, sideband_high):
                ax.axvline(b, color="tab:blue", ls="--", lw=1)
            ax.axvline(mean, color="k", ls=":", lw=1, label=f"2D fit centre {mean:.1f}, sigma {abs(sig):.2f}")
            ax.set_xlim(-0.5, 255.5)
            ax.set_ylim(bottom=0)
            ax.set_xlabel(f"{axis_name} Pixel", fontsize=13)
            ax.set_ylabel("ToT (ms)", fontsize=13)
            binning = f" (rebinX({REBIN_X}), {len(tot_p)} bins)" if len(tot_p) != 256 else ""
            ax.set_title(f"{axis_name} projection{binning}, "
                         f"signal to {s_sig} sigma, sideband to {b_sig} sigma", fontsize=13)
            ax.legend(fontsize=9)
            ax.grid(alpha=.2)
            problems = []
            if sideband_low < 0 or sideband_high > 255:
                problems.append("sideband region extends off the chip")
            if in_side.sum() < 5:   # a 4th-degree polynomial needs at least 5 points
                problems.append(f"only {int(in_side.sum())} sideband points (4th-degree fit needs 5)")
            if not np.isfinite(sig) or abs(sig) < 0.5:
                problems.append("2D fit sigma below half a pixel")
            sb_rows.append((axis_name, f"{s_sig}to{b_sig}", f"{mean:.3f}", f"{abs(sig):.3f}", sideband_low,
                            signal_low, signal_high, sideband_high, int(in_signal.sum()),
                            int(in_side.sum()), "; ".join(problems)))
        fig.suptitle(f"{ID}: projections and regions used by the sideband fit "
                     f"({s_sig}to{b_sig}), before that fit", fontsize=14)
        fig.tight_layout()
        fig.savefig(f"{sb_folder}/{s_sig}to{b_sig}.png")
        plt.close(fig)
    with open(sb_folder+"/regions.csv", "w") as fd:
        fd.write("axis,setting,centre,sigma,sideband_low,signal_low,signal_high,sideband_high,"
                 "signal_points,sideband_points,problems\n")
        for row in sb_rows:
            fd.write(",".join(str(v) for v in row) + "\n")
    bad = [r for r in sb_rows if r[-1]]
    if bad:
        print(f"{directory}: sideband regions look problematic for {len(bad)} of {len(sb_rows)} "
              f"axis/setting combinations (see {sb_folder}/regions.csv)")
except Exception as e:
    print(f"warning: could not save sideband-region diagnostics for {directory}: {e}")


def tpx_analysis_checked(*args):
    """tpx_analysis, recording which setting failed and why (added diagnostics)."""
    try:
        return tpx_analysis(*args)
    except Exception as e:
        import traceback
        poly_type, s_sig, b_sig, axis = args[0], args[5], args[6], ("X" if args[11] == 0 else "Y")
        with open(diag_folder+"/sideband_failed.txt", "w") as fd:
            fd.write(f"tpx_analysis failed: {poly_type}, {axis} projection, signal to {s_sig} sigma, "
                     f"sideband to {b_sig} sigma\n{type(e).__name__}: {e}\n\n{traceback.format_exc()}\n"
                     f"See sideband_regions/{s_sig}to{b_sig}.png and sideband_regions/regions.csv.\n")
        print(f"{directory}: sideband step failed at {poly_type} {axis} {s_sig}to{b_sig}: {e} "
              f"(see {diag_folder}/sideband_failed.txt)")
        raise


for aa in range(len(signal_sig_list)):
    tpx_analysis_checked("4th_degree",xmean, xsig_proj, tot_x_collapse,hit_x_collapse, signal_sig_list[aa], sideband_sig_list[aa],twoD_Gaussian,perChipTOT,4,directory,0,res_folder+"_x",total_time,spark_cutting)
    tpx_analysis_checked("4th_degree",ymean, ysig_proj, tot_y_collapse,hit_y_collapse, signal_sig_list[aa], sideband_sig_list[aa],twoD_Gaussian,perChipTOT,4,directory,1,res_folder+"_y",total_time,spark_cutting)
    tpx_analysis_checked("3rd_degree",xmean, xsig_proj, tot_x_collapse,hit_x_collapse, signal_sig_list[aa], sideband_sig_list[aa],twoD_Gaussian,perChipTOT,3,directory,0,res_folder+"_x",total_time,spark_cutting)
    tpx_analysis_checked("3rd_degree",ymean, ysig_proj, tot_y_collapse,hit_y_collapse, signal_sig_list[aa], sideband_sig_list[aa],twoD_Gaussian,perChipTOT,3,directory,1,res_folder+"_y",total_time,spark_cutting)
    tpx_analysis_checked("2nd_degree",xmean, xsig_proj, tot_x_collapse,hit_x_collapse, signal_sig_list[aa], sideband_sig_list[aa],twoD_Gaussian,perChipTOT,2,directory,0,res_folder+"_x",total_time,spark_cutting)
    tpx_analysis_checked("2nd_degree",ymean, ysig_proj, tot_y_collapse,hit_y_collapse, signal_sig_list[aa], sideband_sig_list[aa],twoD_Gaussian,perChipTOT,2,directory,1,res_folder+"_y",total_time,spark_cutting)

v2x=np.array([])
v3x=np.array([])
v4x=np.array([])

v2y=np.array([])
v3y=np.array([])
v4y=np.array([])

raw2x=np.array([])
raw3x=np.array([])
raw4x=np.array([])

raw2y=np.array([])
raw3y=np.array([])
raw4y=np.array([])



with open(path+"/"+directory+"/"+res_folder+"_x/2nd_degree/integrals.csv", "r") as f2x:
    reader2x = csv.reader(f2x)

    for row2x in reader2x:
        x2x = float(row2x[1])
        v2x=np.append(v2x,x2x)

with open(path+"/"+directory+"/"+res_folder+"_x/3rd_degree/integrals.csv", "r") as f3x:
    reader3x = csv.reader(f3x)

    for row3x in reader3x:
        x3x = float(row3x[1])
        v3x=np.append(v3x,x3x)

with open(path+"/"+directory+"/"+res_folder+"_x/4th_degree/integrals.csv", "r") as f4x:
    reader4x = csv.reader(f4x)

    for row4x in reader4x:
        x4x = float(row4x[1])
        v4x=np.append(v4x,x4x)

with open(path+"/"+directory+"/"+res_folder+"_y/2nd_degree/integrals.csv", "r") as f2y:
    reader2y = csv.reader(f2y)

    for row2y in reader2y:
        x2y = float(row2y[1])
        v2y=np.append(v2y,x2y)


with open(path+"/"+directory+"/"+res_folder+"_y/3rd_degree/integrals.csv", "r") as f3y:
    reader3y = csv.reader(f3y)

    for row3y in reader3y:
        x3y = float(row3y[1])
        v3y=np.append(v3y,x3y)

with open(path+"/"+directory+"/"+res_folder+"_y/4th_degree/integrals.csv", "r") as f4y:
    reader4y = csv.reader(f4y)

    for row4y in reader4y:
        x4y = float(row4y[1])
        v4y=np.append(v4y,x4y)
        
xmin = min(min(v2x), min(v3x), min(v2y), min(v3y), min(v4y))
xmax = max(max(v2x), max(v3x), max(v2y), max(v3y), max(v4y))

xmin *= 0.75
xmax *= 1.25

#xmin = 10 * math.floor(xmin / 10)
#xmax = 10 * math.ceil(xmax / 10)

h2x = ROOT.TH1F("h2x", "Poly2 Signal Histogram (X Collapse);Signal Integral (ms/s);Counts", 20,   xmin, xmax)
h3x = ROOT.TH1F("h3x", "Poly3 Signal Histogram (X Collapse);Signal Integral (ms/s);Counts", 20,   xmin, xmax)
h4x = ROOT.TH1F("h4x", "Poly4 Signal Histogram (X Collapse);Signal Integral (ms/s);Counts", 20,   xmin, xmax)

h2y = ROOT.TH1F("h2y", "Poly2 Signal Histogram (Y Collapse);Signal Integral (ms/s);Counts", 20,   xmin, xmax)
h3y = ROOT.TH1F("h3y", "Poly3 Signal Histogram (Y Collapse);Signal Integral (ms/s);Counts", 20,   xmin, xmax)
h4y = ROOT.TH1F("h4y", "Poly4 Signal Histogram (Y Collapse);Signal Integral (ms/s);Counts", 20,   xmin, xmax)

#h2.SetCanExtend(ROOT.TH1.kAllAxes)
#h3.SetCanExtend(ROOT.TH1.kAllAxes)
#h4.SetCanExtend(ROOT.TH1.kAllAxes)

for vx in v4x:
    h4x.Fill(vx)

for vvx in v2x:
    h2x.Fill(vvx)

for vvvx in v3x:
    h3x.Fill(vvvx)

for vy in v4y:
    h4y.Fill(vy)

for vvy in v2y:
    h2y.Fill(vvy)

for vvvy in v3y:
    h3y.Fill(vvvy)
    
# Style
h2x.SetFillColor(ROOT.kBlue)
h3x.SetFillColor(ROOT.kBlue)
h4x.SetFillColor(ROOT.kBlue)

h2x.SetLineColor(ROOT.kBlue)
h3x.SetLineColor(ROOT.kBlue)
h4x.SetLineColor(ROOT.kBlue)

h2y.SetFillColor(ROOT.kRed)
h3y.SetFillColor(ROOT.kRed)
h4y.SetFillColor(ROOT.kRed)

h2y.SetLineColor(ROOT.kRed)
h3y.SetLineColor(ROOT.kRed)
h4y.SetLineColor(ROOT.kRed)

# Create stack
hs = ROOT.THStack("hs", "Optical Signal Strength;Signal Integral (ms/s);Counts")
hsx = ROOT.THStack("hs", "Optical Signal Strength (X Collapse);Signal Integral (ms/s);Counts")
hsy = ROOT.THStack("hs", "Optical Signal Strength (Y Collapse);Signal Integral (ms/s);Counts")

# Order matters:
# h1 is drawn first (bottom)
# h2 stacks on top
hs.Add(h2x)
hs.Add(h3x)
hs.Add(h4x)
hsx.Add(h2x)
hsx.Add(h3x)
hsx.Add(h4x)

hs.Add(h2y)
hs.Add(h3y)
hs.Add(h4y)
hsy.Add(h2y)
hsy.Add(h3y)
hsy.Add(h4y)

hsum = h2x.Clone("hsum")
hsum.Reset()

hsum.Add(h4x)
hsum.Add(h2x)
hsum.Add(h3x)

hsum.Add(h4y)
hsum.Add(h2y)
hsum.Add(h3y)

mean_tot = hsum.GetMean()
rms_tot  = hsum.GetRMS()
percent= (rms_tot/mean_tot)*100

# Draw
c = ROOT.TCanvas("c", "c", 800, 600)
hs.Draw("HIST")

# Legend
leg = ROOT.TLegend(0.2, 0.7, 0.4, 0.9)
leg.AddEntry(h2x, "X Collapse", "f")
#leg.AddEntry(h3x, "3rd Degree Polynomial (X Collapse)", "f")
#leg.AddEntry(h4x, "4th Degree Polynomial (X Collapse)", "f")
leg.AddEntry(h2y, "Y Collapse", "f")
#leg.AddEntry(h3y, "3rd Degree Polynomial (Y Collapse)", "f")
#leg.AddEntry(h4y, "4th Degree Polynomial (Y Collapse)", "f")
leg.Draw()

stats = ROOT.TPaveText(0.75, 0.75, .95, .95, "NDC")
stats.AddText(f"Entries = {hsum.GetEntries()}")
stats.AddText(f"Mean = {hsum.GetMean():.3f}")
stats.AddText(f"RMS = {hsum.GetRMS():.3f}")
stats.AddText(f"Percent = {(hsum.GetRMS()/hsum.GetMean())*100:.1f}%")
stats.AddText(f"Underflow = {hsum.GetBinContent(0)}")
stats.AddText(f"overflow = {hsum.GetBinContent(hsum.GetNbinsX()+1)}")
stats.Draw()

latex_ID = ROOT.TLatex()
latex_ID.SetNDC()
latex_ID.SetTextSize(0.03)
latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

c.Update()
c.Draw()
ROOT.gPad.Update()
c.SaveAs(f"{path}/{directory}/Total-Stacked-{res_folder}.png")
c.SaveAs(f"{path}/{directory}/Total-Stacked-{res_folder}.eps")

if SAVE_SIGNAL_PLOTS:
    # Draw
    cx = ROOT.TCanvas("cx", "cx", 800, 600)
    hsx.Draw("HIST")

    hsum.Reset()

    hsum.Add(h4x)
    hsum.Add(h2x)
    hsum.Add(h3x)

    # Legend
    #legx = ROOT.TLegend(0.2, 0.7, 0.4, 0.9)
    #legx.AddEntry(h2x, "2nd Degree Polynomial (X Collapse)", "f")
    #legx.AddEntry(h3x, "3rd Degree Polynomial (X Collapse)", "f")
    #legx.AddEntry(h4x, "4th Degree Polynomial (X Collapse)", "f")
    #legx.Draw()

    statsx = ROOT.TPaveText(0.75, 0.75, 0.95, 0.95, "NDC")
    statsx.AddText(f"Entries = {hsum.GetEntries():.0f}")
    statsx.AddText(f"Mean = {hsum.GetMean():.3f}")
    statsx.AddText(f"RMS = {hsum.GetRMS():.3f}")
    statsx.AddText(f"Percent = {(hsum.GetRMS()/hsum.GetMean())*100:.1f}%")
    statsx.AddText(f"Underflow = {hsum.GetBinContent(0)}")
    statsx.AddText(f"overflow = {hsum.GetBinContent(hsum.GetNbinsX()+1)}")
    statsx.Draw()

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.10, 0.85, f"ID: {ID}")

    cx.Update()
    cx.Draw()
    cx.SaveAs(path+"/"+directory+"/"+res_folder+"_x/Stacked-"+res_folder+".png")
    cx.SaveAs(path+"/"+directory+"/"+res_folder+"_x/Stacked-"+res_folder+".eps")

    hsum.Reset()

    hsum.Add(h4y)
    hsum.Add(h2y)
    hsum.Add(h3y)

    cy = ROOT.TCanvas("cy", "cy", 800, 600)
    hsy.Draw("HIST")

    # Legend
    legy = ROOT.TLegend(0.2, 0.7, 0.4, 0.9)
    legy.AddEntry(h2y, "2nd Degree Polynomial (Y Collapse)", "f")
    legy.AddEntry(h3y, "3rd Degree Polynomial (Y Collapse)", "f")
    legy.AddEntry(h4y, "4th Degree Polynomial (Y Collapse)", "f")
    legy.Draw()

    statsy = ROOT.TPaveText(0.75, 0.75, 0.95, 0.95, "NDC")
    statsy.AddText(f"Entries = {hsum.GetEntries():.0f}")
    statsy.AddText(f"Mean = {hsum.GetMean():.3f}")
    statsy.AddText(f"RMS = {hsum.GetRMS():.3f}")
    statsy.AddText(f"Percent = {(hsum.GetRMS()/hsum.GetMean())*100:.1f}%")
    statsy.AddText(f"Underflow = {hsum.GetBinContent(0)}")
    statsy.AddText(f"overflow = {hsum.GetBinContent(hsum.GetNbinsX()+1)}")
    statsy.Draw()

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    cy.Update()
    cy.Draw()
    cy.SaveAs(path+"/"+directory+"/"+res_folder+"_y/Stacked-"+res_folder+".png")
    cy.SaveAs(path+"/"+directory+"/"+res_folder+"_y/Stacked-"+res_folder+".eps")

    c2x = ROOT.TCanvas("c2x", "c2x", 800, 600)
    h2x.Draw("HIST")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    c2x.SaveAs(path+"/"+directory+"/"+res_folder+"_x/2nd_degree/poly2-signal-hist_x.png")
    c2x.SaveAs(path+"/"+directory+"/"+res_folder+"_x/2nd_degree/poly2-signal-hist_x.eps")

    c3x = ROOT.TCanvas("c3x", "c3x", 800, 600)
    h3x.Draw("HIST")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    c3x.SaveAs(path+"/"+directory+"/"+res_folder+"_x/3rd_degree/poly3-signal-hist_x.png")
    c3x.SaveAs(path+"/"+directory+"/"+res_folder+"_x/3rd_degree/poly3-signal-hist_x.eps")

    c4x = ROOT.TCanvas("c4x", "c4x", 800, 600)
    h4x.Draw("HIST")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    c4x.SaveAs(path+"/"+directory+"/"+res_folder+"_x/4th_degree/poly4-signal-hist_x.png")

    c2y = ROOT.TCanvas("c2y", "c2y", 800, 600)
    h2y.Draw("HIST")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    c2y.SaveAs(path+"/"+directory+"/"+res_folder+"_y/2nd_degree/poly2-signal-hist_y.png")
    c2y.SaveAs(path+"/"+directory+"/"+res_folder+"_y/2nd_degree/poly2-signal-hist_y.eps")

    c3y = ROOT.TCanvas("c3y", "c3y", 800, 600)
    h3y.Draw("HIST")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    c3y.SaveAs(path+"/"+directory+"/"+res_folder+"_y/3rd_degree/poly3-signal-hist_y.png")
    c3y.SaveAs(path+"/"+directory+"/"+res_folder+"_y/3rd_degree/poly3-signal-hist_y.eps")

    c4y = ROOT.TCanvas("c4y", "c4y", 800, 600)
    h4y.Draw("HIST")

    latex_ID = ROOT.TLatex()
    latex_ID.SetNDC()
    latex_ID.SetTextSize(0.03)
    latex_ID.DrawLatex(0.1, 0.85, f"ID: {ID}")

    c4y.SaveAs(path+"/"+directory+"/"+res_folder+"_y/4th_degree/poly4-signal-hist_y.png")
    c4y.SaveAs(path+"/"+directory+"/"+res_folder+"_y/4th_degree/poly4-signal-hist_y.eps")

#print(time)
#print(time_cut)
#print(total_time)
#print(mean_tot)
#print(rms_tot)
#print((rms_tot/mean_tot)*100)

rms_round=round(rms_tot, 1 - int(np.floor(np.log10(abs(rms_tot)))) - 1)
decimal_places = -int(np.floor(np.log10(abs(rms_tot))))
mean_round = round(mean_tot, decimal_places)
now = datetime.now()
now = (now + timedelta(microseconds=500_000)).replace(microsecond=0)

sig_out = pd.DataFrame([[ID],[pres],[FC],[E1],[E2],[E3],[E4],[purity],[mean_tot],[rms_tot],[percent],[xmean],[ymean],[time],[time_cut],[total_time]])
inspect = pd.DataFrame([[f"{ID} Mean = {mean_round} RMS = {rms_round} ({round(percent,1)}%). Analysis performed at {now}"]])

sig_out.T.to_csv(f"{path}/{directory}/integral.csv", mode="w", index=False, header=False)
write_optical_summary(f"{path}/{directory}")
inspect.T.to_csv(f"{path}/{directory}/integral-inspect.csv", mode="w", index=False, header=False)

sig_out.T.to_csv(f"{path}/results/signals.csv", mode="a", index=False, header=False)
inspect.T.to_csv(f"{path}/results/signals_inspect.csv", mode="a", index=False, header=False)









    



'''
with open(directory+"/"+res_folder+"_x/2nd_degree/raw.csv", "r") as f2x:
    reader2x = csv.reader(f2x)

    for row2x in reader2x:
        x2x = float(row2x[1])
        raw2x=np.append(raw2x,x2x)

with open(directory+"/"+res_folder+"_x/3rd_degree/raw.csv", "r") as f3x:
    reader3x = csv.reader(f3x)

    for row3x in reader3x:
        x3x = float(row3x[1])
        raw3x=np.append(raw3x,x3x)

with open(directory+"/"+res_folder+"_x/4th_degree/raw.csv", "r") as f4x:
    reader4x = csv.reader(f4x)

    for row4x in reader4x:
        x4x = float(row4x[1])
        raw4x=np.append(raw4x,x4x)

with open(directory+"/"+res_folder+"_y/2nd_degree/raw.csv", "r") as f2y:
    reader2y = csv.reader(f2y)

    for row2y in reader2y:
        x2y = float(row2y[1])
        raw2y=np.append(raw2y,x2y)


with open(directory+"/"+res_folder+"_y/3rd_degree/raw.csv", "r") as f3y:
    reader3y = csv.reader(f3y)

    for row3y in reader3y:
        x3y = float(row3y[1])
        raw3y=np.append(raw3y,x3y)

with open(directory+"/"+res_folder+"_y/4th_degree/raw.csv", "r") as f4y:
    reader4y = csv.reader(f4y)

    for row4y in reader4y:
        x4y = float(row4y[1])
        raw4y=np.append(raw4y,x4y)

        
rawxmin = min(min(raw2x), min(raw3x), min(raw2y), min(raw3y), min(raw4y))
rawxmax = max(max(raw2x), max(raw3x), max(raw2y), max(raw3y), max(raw4y))

rawxmin *= 0.8
rawxmax *= 1.1

rawxmin = 10 * math.floor(rawxmin / 10)
rawxmax = 10 * math.ceil(rawxmax / 10)

rawh2x = ROOT.TH1F("rawh2x", "Poly2 Raw Signal Histogram (X Collapse);Signal Integral (ms);Counts", 20,   rawxmin, rawxmax)
rawh3x = ROOT.TH1F("rawh3x", "Poly3 Raw Signal Histogram (X Collapse);Signal Integral (ms);Counts", 20,   rawxmin, rawxmax)
rawh4x = ROOT.TH1F("rawh4x", "Poly4 Raw Signal Histogram (X Collapse);Signal Integral (ms);Counts", 20,   rawxmin, rawxmax)

rawh2y = ROOT.TH1F("rawh2y", "Poly2 Raw Signal Histogram (Y Collapse);Signal Integral (ms);Counts", 20,   rawxmin, rawxmax)
rawh3y = ROOT.TH1F("rawh3y", "Poly3 Raw Signal Histogram (Y Collapse);Signal Integral (ms);Counts", 20,   rawxmin, rawxmax)
rawh4y = ROOT.TH1F("rawh4y", "Poly4 Raw Signal Histogram (Y Collapse);Signal Integral (ms);Counts", 20,   rawxmin, rawxmax)


for vx in raw4x:
    rawh4x.Fill(vx)

for vvx in raw2x:
    rawh2x.Fill(vvx)

for vvvx in raw3x:
    rawh3x.Fill(vvvx)

for vy in raw4y:
    rawh4y.Fill(vy)

for vvy in raw2y:
    rawh2y.Fill(vvy)

for vvvy in raw3y:
    rawh3y.Fill(vvvy)
    
# Style
h2x.SetFillColor(ROOT.kBlue)
h3x.SetFillColor(ROOT.kYellow)
h4x.SetFillColor(ROOT.kRed)

h2x.SetLineColor(ROOT.kBlue)
h3x.SetLineColor(ROOT.kYellow)
h4x.SetLineColor(ROOT.kRed)

h2y.SetFillColor(ROOT.kCyan)
h3y.SetFillColor(ROOT.kOrange)
h4y.SetFillColor(ROOT.kMagenta)

h2y.SetLineColor(ROOT.kCyan)
h3y.SetLineColor(ROOT.kOrange)
h4y.SetLineColor(ROOT.kMagenta)

# Create stack
rawhs = ROOT.THStack("rawhs", "Optical Signal Strength;Signal Integral (ms/s);Counts")
rawhsx = ROOT.THStack("rawhsx", "Optical Signal Strength (X Collapse);Signal Integral (ms/s);Counts")
rawhsy = ROOT.THStack("rawhsy", "Optical Signal Strength (Y Collapse);Signal Integral (ms/s);Counts")

# Order matters:
# h1 is drawn first (bottom)
# h2 stacks on top
rawhs.Add(rawh2x)
rawhs.Add(rawh3x)
rawhs.Add(rawh4x)
rawhsx.Add(rawh2x)
rawhsx.Add(rawh3x)
rawhsx.Add(rawh4x)

rawhs.Add(rawh2y)
rawhs.Add(rawh3y)
rawhs.Add(rawh4y)
rawhsy.Add(rawh2y)
rawhsy.Add(rawh3y)
rawhsy.Add(rawh4y)

rawhsum = rawh2x.Clone("rawhsum")
rawhsum.Reset()

rawhsum.Add(rawh4x)
rawhsum.Add(rawh2x)
rawhsum.Add(rawh3x)

rawhsum.Add(rawh4y)
rawhsum.Add(rawh2y)
rawhsum.Add(rawh3y)

mean_tot = rawhsum.GetMean()
rms_tot  = rawhsum.GetRMS()
percent= (rms_tot/mean_tot)*100
'''
'''
# Draw
c = ROOT.TCanvas("c", "c", 800, 600)
#hs.Draw("HIST")

# Legend
leg = ROOT.TLegend(0.2, 0.7, 0.4, 0.9)
leg.AddEntry(h2x, "2nd Degree Polynomial (X Collapse)", "f")
leg.AddEntry(h3x, "3rd Degree Polynomial (X Collapse)", "f")
leg.AddEntry(h4x, "4th Degree Polynomial (X Collapse)", "f")
leg.AddEntry(h2y, "2nd Degree Polynomial (Y Collapse)", "f")
leg.AddEntry(h3y, "3rd Degree Polynomial (Y Collapse)", "f")
leg.AddEntry(h4y, "4th Degree Polynomial (Y Collapse)", "f")
leg.Draw()

stats = ROOT.TPaveText(0.75, 0.75, .95, .95, "NDC")
stats.AddText(f"Entries = {hsum.GetEntries():.0f}")
stats.AddText(f"Mean = {hsum.GetMean():.0f}")
stats.AddText(f"RMS = {hsum.GetRMS():.0f}")
stats.AddText(f"Percent = {(hsum.GetRMS()/hsum.GetMean())*100:.1f}%")
stats.AddText(f"Underflow = {hsum.GetBinContent(0)}")
stats.AddText(f"overflow = {hsum.GetBinContent(hsum.GetNbinsX()+1)}")
stats.Draw()

#c.Update()
#c.Draw()
#ROOT.gPad.Update()
#c.SaveAs(directory+"/Total-Stacked-"+res_folder+".png")

# Draw
#cx = ROOT.TCanvas("cx", "cx", 800, 600)
#hsx.Draw("HIST")

#hsum.Reset()

#hsum.Add(h4x)
#hsum.Add(h2x)
#hsum.Add(h3x)

# Legend
#legx = ROOT.TLegend(0.2, 0.7, 0.4, 0.9)
#legx.AddEntry(h2x, "2nd Degree Polynomial (X Collapse)", "f")
#legx.AddEntry(h3x, "3rd Degree Polynomial (X Collapse)", "f")
#legx.AddEntry(h4x, "4th Degree Polynomial (X Collapse)", "f")
#legx.Draw()

statsx = ROOT.TPaveText(0.75, 0.75, 0.95, 0.95, "NDC")
statsx.AddText(f"Entries = {hsum.GetEntries():.0f}")
statsx.AddText(f"Mean = {hsum.GetMean():.0f}")
statsx.AddText(f"RMS = {hsum.GetRMS():.0f}")
statsx.AddText(f"Percent = {(hsum.GetRMS()/hsum.GetMean())*100:.1f}%")
statsx.AddText(f"Underflow = {hsum.GetBinContent(0)}")
statsx.AddText(f"overflow = {hsum.GetBinContent(hsum.GetNbinsX()+1)}")
statsx.Draw()

cx.Update()
cx.Draw()
cx.SaveAs(directory+"/"+res_folder+"_x/Stacked-"+res_folder+".png")

hsum.Reset()

hsum.Add(h4y)
hsum.Add(h2y)
hsum.Add(h3y)

cy = ROOT.TCanvas("cy", "cy", 800, 600)
hsy.Draw("HIST")

# Legend
legy = ROOT.TLegend(0.2, 0.7, 0.4, 0.9)
legy.AddEntry(h2y, "2nd Degree Polynomial (Y Collapse)", "f")
legy.AddEntry(h3y, "3rd Degree Polynomial (Y Collapse)", "f")
legy.AddEntry(h4y, "4th Degree Polynomial (Y Collapse)", "f")
legy.Draw()

statsy = ROOT.TPaveText(0.75, 0.75, 0.95, 0.95, "NDC")
statsy.AddText(f"Entries = {hsum.GetEntries():.0f}")
statsy.AddText(f"Mean = {hsum.GetMean():.0f}")
statsy.AddText(f"RMS = {hsum.GetRMS():.0f}")
statsy.AddText(f"Percent = {(hsum.GetRMS()/hsum.GetMean())*100:.1f}%")
statsy.AddText(f"Underflow = {hsum.GetBinContent(0)}")
statsy.AddText(f"overflow = {hsum.GetBinContent(hsum.GetNbinsX()+1)}")
statsy.Draw()

cy.Update()
cy.Draw()
cy.SaveAs(directory+"/"+res_folder+"_y/Stacked-"+res_folder+".png")

c2x = ROOT.TCanvas("c2x", "c2x", 800, 600)
h2x.Draw("HIST")

c2x.SaveAs(directory+"/"+res_folder+"_x/2nd_degree/poly2-signal-hist_x.png")

c3x = ROOT.TCanvas("c3x", "c3x", 800, 600)
h3x.Draw("HIST")

c3x.SaveAs(directory+"/"+res_folder+"_x/3rd_degree/poly3-signal-hist_x.png")

c4x = ROOT.TCanvas("c4x", "c4x", 800, 600)
h4x.Draw("HIST")

c4x.SaveAs(directory+"/"+res_folder+"_x/4th_degree/poly4-signal-hist_x.png")

c2y = ROOT.TCanvas("c2y", "c2y", 800, 600)
h2y.Draw("HIST")

c2y.SaveAs(directory+"/"+res_folder+"_y/2nd_degree/poly2-signal-hist_y.png")

c3y = ROOT.TCanvas("c3y", "c3y", 800, 600)
h3y.Draw("HIST")

c3y.SaveAs(directory+"/"+res_folder+"_y/3rd_degree/poly3-signal-hist_y.png")

c4y = ROOT.TCanvas("c4y", "c4y", 800, 600)
h4y.Draw("HIST")

c4y.SaveAs(directory+"/"+res_folder+"_y/4th_degree/poly4-signal-hist_y.png")

#print(time)
#print(time_cut)
#print(total_time)
#print(mean_tot)
#print(rms_tot)
#print((rms_tot/mean_tot)*100)
'''
'''
raw_out = pd.DataFrame([[mean_tot],[rms_tot],[percent],[xmean],[ymean],[time],[time_cut],[total_time]])
inspect_raw = pd.DataFrame([[f"Raw Mean = {round(mean_tot,0)} RMS = {round(rms_tot,0)} ({round(percent,1)}%)"]])


#print(mean_tot, rms_tot, (rms_tot/mean_tot)*100)

raw_out.T.to_csv(f"{directory}/{res_folder}_raw.csv", mode="w", index=False, header=False)
inspect_raw.T.to_csv(directory+"/"+res_folder+".csv", mode="w", index=False, header=False)

if printout == True:
    print("writing")
    raw_out.T.to_csv(f"{list_folder}/{res_file}_raw.csv", mode="a", index=False, header=False)
    inspect_raw.T.to_csv(f"{list_folder}/{res_file}_inspect_raw.csv", mode="a", index=False, header=False)
'''

