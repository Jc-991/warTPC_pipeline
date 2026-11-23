#!/usr/bin/env python3
"""Plots after Matt's 2D Gaussian fit, original vs rebinX(2), for one optical run.

    plot-after-fit.py <output.hdf5> <output_dir>

Fits the ToT map the same way as optical-analysis.py (original, 256 x 256) and
optical-analysis-rebin-x.py (rebinX(2): pairs of X columns merged, 256 x 128),
then saves to <output_dir>:
  <run>-after-fit-original.png   data with 1/2/3 sigma fit contours, model,
                                 residual (data - model), X and Y slices
                                 through the fitted centre with the fit
  <run>-after-fit-rebinX2.png    the same for the rebinX(2) fit
  <run>-after-fit-compare.png    both fits on the same slices and projections,
                                 with the signal (-3, +3 sigma) and sideband
                                 (-7, +7 sigma) edges of the 3to7 setting
  <run>-fit-parameters.csv       fit parameters of both fits
Needs only numpy, scipy, h5py and matplotlib (no ROOT).
"""

import argparse
import csv
from pathlib import Path

import h5py
import matplotlib
import numpy as np
from scipy.optimize import curve_fit

matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAMES = ("amplitude", "x0", "y0", "sigma_x", "sigma_y", "theta", "offset")


def two_d_gaussian(xy, amplitude, xo, yo, sigma_x, sigma_y, theta, offset):
    """Matt's twoD_Gaussian (optical-analysis.py)."""
    y, x = xy
    a = np.cos(theta)**2 / (2 * sigma_x**2) + np.sin(theta)**2 / (2 * sigma_y**2)
    b = -np.sin(2 * theta) / (4 * sigma_x**2) + np.sin(2 * theta) / (4 * sigma_y**2)
    c = np.sin(theta)**2 / (2 * sigma_x**2) + np.cos(theta)**2 / (2 * sigma_y**2)
    return offset + amplitude * np.exp(-(a * (x - xo)**2 + 2 * b * (x - xo) * (y - yo)
                                         + c * (y - yo)**2))


def exponent(xy, xo, yo, sigma_x, sigma_y, theta):
    """The Gaussian's exponent; contour at k^2/2 is the k-sigma ellipse."""
    y, x = xy
    a = np.cos(theta)**2 / (2 * sigma_x**2) + np.sin(theta)**2 / (2 * sigma_y**2)
    b = -np.sin(2 * theta) / (4 * sigma_x**2) + np.sin(2 * theta) / (4 * sigma_y**2)
    c = np.sin(theta)**2 / (2 * sigma_x**2) + np.cos(theta)**2 / (2 * sigma_y**2)
    return a * (x - xo)**2 + 2 * b * (x - xo) * (y - yo) + c * (y - yo)**2


def fit(image, width):
    """Fit as Matt's code does. width = pixels merged per X bin (1 or 2).

    Returns the fitted image's coordinates, the raw parameters (ToT per bin)
    and the parameters in ToT per original pixel (amplitude, offset / width).
    """
    y, x_bin = np.indices(image.shape)
    x = width * x_bin + (width - 1) / 2
    peak_y, peak_x = np.unravel_index(image.argmax(), image.shape)
    guess = (width * 10e3, x[peak_y, peak_x], peak_y, 1.0, 1.0, 0.0, 0.0)
    raw, _ = curve_fit(two_d_gaussian, (y.ravel(), x.ravel()), image.ravel(), p0=guess)
    per_pixel = raw.copy()
    per_pixel[[0, 6]] /= width
    return x, y, raw, per_pixel


def projected_sigmas(p):
    sx, sy, th = p[3], p[4], p[5]
    return (np.sqrt(sx**2 * np.cos(th)**2 + sy**2 * np.sin(th)**2),
            np.sqrt(sx**2 * np.sin(th)**2 + sy**2 * np.cos(th)**2))


def edges(width, n):
    return np.arange(n + 1) * width - 0.5


def plot_one(run, label, image, width, x, y, raw, per_pixel, out):
    model = two_d_gaussian((y, x), *raw)
    resid = image - model
    extent = (-0.5, 255.5, 255.5, -0.5)
    fine_y, fine_x = np.mgrid[0:256:0.5, 0:256:0.5]
    q = exponent((fine_y, fine_x), *raw[1:6])
    unit = f"ToT per {width}×1 pixel bin"

    fig, ax = plt.subplots(2, 3, figsize=(17, 10), layout="constrained")
    vmax = image.max()
    for a, data, title in ((ax[0, 0], image, "Data + fit contours (1, 2, 3 σ)"),
                           (ax[0, 1], model, "Fitted 2D Gaussian")):
        im = a.imshow(data, extent=extent, interpolation="nearest", vmin=0, vmax=vmax)
        fig.colorbar(im, ax=a, label=unit)
        a.set(title=title, xlabel="X pixel", ylabel="Y pixel")
    ax[0, 0].contour(fine_x, fine_y, q, levels=[0.5, 2.0, 4.5], colors="red", linewidths=1)
    ax[0, 0].plot(raw[1], raw[2], "r+", ms=12)
    lim = np.percentile(np.abs(resid), 99.5)
    im = ax[0, 2].imshow(resid, extent=extent, interpolation="nearest",
                         cmap="RdBu_r", vmin=-lim, vmax=lim)
    fig.colorbar(im, ax=ax[0, 2], label=f"data − fit ({unit})")
    ax[0, 2].set(title="Residual (data − fit)", xlabel="X pixel", ylabel="Y pixel")

    # Slices through the fitted centre
    row = int(np.clip(round(raw[2]), 0, image.shape[0] - 1))
    col = int(np.clip(np.floor((raw[1] + 0.5) / width), 0, image.shape[1] - 1))
    xe, ye = edges(width, image.shape[1]), edges(1, image.shape[0])
    xs = np.linspace(-0.5, 255.5, 1000)
    ax[1, 0].stairs(image[row], xe, label="data")
    ax[1, 0].plot(xs, two_d_gaussian((np.full_like(xs, row), xs), *raw), "r", label="fit")
    ax[1, 0].set(title=f"X slice through the fitted centre (row y = {row})",
                 xlabel="X pixel", ylabel=unit)
    xc = x[0, col]
    ax[1, 1].stairs(image[:, col], ye, label="data")
    ax[1, 1].plot(xs, two_d_gaussian((xs, np.full_like(xs, xc)), *raw), "r", label="fit")
    cols = f"x = {int(xc - 0.5)}–{int(xc + 0.5)}" if width == 2 else f"x = {col}"
    ax[1, 1].set(title=f"Y slice through the fitted centre (column {cols})",
                 xlabel="Y pixel", ylabel=unit)
    for a in (ax[1, 0], ax[1, 1]):
        a.set_xlim(-0.5, 255.5)
        a.legend()

    sx_p, sy_p = projected_sigmas(per_pixel)
    text = "\n".join([
        f"{label} fit (per original pixel)", "",
        f"amplitude = {per_pixel[0]:.1f}",
        f"x0        = {per_pixel[1]:.3f}",
        f"y0        = {per_pixel[2]:.3f}",
        f"sigma_x   = {per_pixel[3]:.3f}",
        f"sigma_y   = {per_pixel[4]:.3f}",
        f"theta     = {per_pixel[5]:.4f}",
        f"offset    = {per_pixel[6]:.1f}", "",
        f"projected sigma X = {sx_p:.3f}",
        f"projected sigma Y = {sy_p:.3f}", "",
        f"residual sum / data sum = {resid.sum() / image.sum():+.2e}",
    ])
    ax[1, 2].axis("off")
    ax[1, 2].text(0.02, 0.98, text, va="top", family="monospace", fontsize=12,
                  transform=ax[1, 2].transAxes)
    fig.suptitle(f"{run} · after the 2D Gaussian fit · {label}", fontsize=15)
    fig.savefig(out, dpi=130)
    plt.close(fig)


def plot_compare(run, fits, out):
    fig, ax = plt.subplots(2, 2, figsize=(15, 10), layout="constrained")
    colours = {"original": "C0", "rebinX(2)": "C1"}
    xs = np.linspace(-0.5, 255.5, 1000)
    for label, (image, width, x, y, raw, pp) in fits.items():
        c = colours[label]
        xe, ye = edges(width, image.shape[1]), edges(1, image.shape[0])
        # Slices through the peak, per original pixel so both are comparable
        row = int(np.clip(round(raw[2]), 0, 255))
        col = int(np.clip(np.floor((raw[1] + 0.5) / width), 0, image.shape[1] - 1))
        ax[0, 0].stairs(image[row] / width, xe, color=c, alpha=0.6, label=f"{label} data")
        ax[0, 0].plot(xs, two_d_gaussian((np.full_like(xs, row), xs), *pp), color=c,
                      lw=2, label=f"{label} fit")
        ax[0, 1].stairs(image[:, col] / width, ye, color=c, alpha=0.6, label=f"{label} data")
        ax[0, 1].plot(xs, two_d_gaussian((xs, np.full_like(xs, x[0, col])), *pp), color=c,
                      lw=2, label=f"{label} fit")
        # Projections (sums), per original pixel, with the 3to7 regions
        sx_p, sy_p = projected_sigmas(pp)
        ax[1, 0].stairs(image.sum(axis=0) / width / 1e6, xe, color=c, label=label)
        ax[1, 1].stairs(image.sum(axis=1) / 1e6, ye, color=c, label=label)
        for a, mean, sig in ((ax[1, 0], pp[1], sx_p), (ax[1, 1], pp[2], sy_p)):
            for k, ls in ((-7, ":"), (-3, "--"), (3, "--"), (7, ":")):
                a.axvline(mean + k * sig, color=c, ls=ls, lw=1)
    ax[0, 0].set(title="X slice through the fitted centre", xlabel="X pixel",
                 ylabel="ToT per original pixel")
    ax[0, 1].set(title="Y slice through the fitted centre", xlabel="Y pixel",
                 ylabel="ToT per original pixel")
    ax[1, 0].set(title="X projection; signal ±3σ (dashed), sideband −7σ/+7σ (dotted)",
                 xlabel="X pixel", ylabel="summed ToT per original pixel (×10⁶)")
    ax[1, 1].set(title="Y projection; signal ±3σ (dashed), sideband −7σ/+7σ (dotted)",
                 xlabel="Y pixel", ylabel="summed ToT per pixel (×10⁶)")
    for a in ax.flat:
        a.set_xlim(-0.5, 255.5)
        a.legend(fontsize=9)
    fig.suptitle(f"{run} · original vs rebinX(2) fit", fontsize=15)
    fig.savefig(out, dpi=130)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("hdf5", type=Path, help="output.hdf5 of one optical run")
    p.add_argument("output", type=Path, help="folder for the plots (created if needed)")
    p.add_argument("--run", help="run name for titles/files (default: the HDF5's folder)")
    args = p.parse_args()
    run = args.run or args.hdf5.resolve().parent.name
    args.output.mkdir(parents=True, exist_ok=True)

    with h5py.File(args.hdf5, "r") as f:
        hits = f["PixelHits"]
        original = np.zeros((256, 256), dtype=np.int64)
        np.add.at(original, (hits["y"][:], hits["x"][:]), hits["tot"][:])
    rebinned = original[:, 0::2] + original[:, 1::2]

    fits = {}
    for label, image, width, tag in (("original", original, 1, "original"),
                                     ("rebinX(2)", rebinned, 2, "rebinX2")):
        x, y, raw, pp = fit(image, width)
        fits[label] = (image, width, x, y, raw, pp)
        out = args.output / f"{run}-after-fit-{tag}.png"
        plot_one(run, label, image, width, x, y, raw, pp, out)
        print(f"saved {out}")
    out = args.output / f"{run}-after-fit-compare.png"
    plot_compare(run, fits, out)
    print(f"saved {out}")

    out = args.output / f"{run}-fit-parameters.csv"
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fit", *NAMES, "projected_sigma_x", "projected_sigma_y"])
        for label, (*_, pp) in fits.items():
            w.writerow([label, *(f"{v:.6g}" for v in pp),
                        *(f"{v:.6g}" for v in projected_sigmas(pp))])
    print(f"saved {out}")


if __name__ == "__main__":
    main()
