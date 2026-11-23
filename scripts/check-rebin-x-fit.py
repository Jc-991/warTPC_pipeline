#!/usr/bin/env python3
"""Compare the original and X-rebinned Gaussian fits on one optical HDF5 file."""

import argparse

import h5py
import numpy as np
from scipy.optimize import curve_fit


def gaussian(coordinates, amplitude, x0, y0, sigma_x, sigma_y, theta, offset):
    y, x = coordinates
    a = np.cos(theta)**2 / (2 * sigma_x**2) + np.sin(theta)**2 / (2 * sigma_y**2)
    b = -np.sin(2 * theta) / (4 * sigma_x**2) + np.sin(2 * theta) / (4 * sigma_y**2)
    c = np.sin(theta)**2 / (2 * sigma_x**2) + np.cos(theta)**2 / (2 * sigma_y**2)
    return offset + amplitude * np.exp(
        -(a * (x - x0)**2 + 2 * b * (x - x0) * (y - y0) + c * (y - y0)**2)
    )


def fit(image, x_bin_width):
    y, x_bin = np.indices(image.shape)
    x = x_bin_width * x_bin + (x_bin_width - 1) / 2
    peak_y, peak_x = np.unravel_index(image.argmax(), image.shape)
    guess = (1e4 * x_bin_width, x[peak_y, peak_x], peak_y, 1., 1., 0., 0.)
    params, _ = curve_fit(gaussian, (y.ravel(), x.ravel()), image.ravel(), p0=guess)
    params[[0, 6]] /= x_bin_width
    return params


def regions(centre, width):
    return [
        tuple(round(centre + multiplier * width) for multiplier in (-7, -3, signal, sideband))
        for signal, sideband in SETTINGS
    ]


SETTINGS = [(3, 7), (3, 8), (3, 9), (3, 10), (4, 8),
            (4, 9), (4, 10), (5, 9), (5, 10), (6, 10)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hdf5", help="output.hdf5 from a single optical run")
    args = parser.parse_args()
    with h5py.File(args.hdf5, "r") as source:
        hits = source["PixelHits"]
        original = np.zeros((256, 256), dtype=np.int64)
        np.add.at(original, (hits["y"][:], hits["x"][:]), hits["tot"][:])
    rebinned = original[:, 0::2] + original[:, 1::2]
    print(f"Input: {args.hdf5}")
    print(f"Original Y×X shape: {original.shape}; rebinned: {rebinned.shape}")
    print(f"Total ToT: {original.sum()} / {rebinned.sum()}")

    measurements = []
    for label, image, width in (("Original", original, 1), ("RebinX(2)", rebinned, 2)):
        amplitude, x, y, sx, sy, theta, offset = fit(image, width)
        x_width = np.hypot(sx * np.cos(theta), sy * np.sin(theta))
        y_width = np.hypot(sx * np.sin(theta), sy * np.cos(theta))
        print(f"{label}: x0={x:.8f} y0={y:.8f} projected sigma X={x_width:.8f} "
              f"Y={y_width:.8f} amplitude={amplitude:.8g} offset={offset:.8g}")
        measurements.append((regions(x, x_width), regions(y, y_width)))

    for axis, before, after in zip(("X", "Y"), *measurements):
        changed = [(setting, a, b) for setting, a, b in zip(SETTINGS, before, after) if a != b]
        print(f"{axis}: {len(changed)}/{len(SETTINGS)} rounded region settings changed")
        for (signal, sideband), a, b in changed:
            print(f"  {signal}to{sideband}: {a} -> {b}")


if __name__ == "__main__":
    main()
