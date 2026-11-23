#!/bin/bash

module load GCCcore/13.3.0
module load Python/3.12.3
module load GCC/13.3.0
module load SciPy-bundle/2024.05
module load OpenMPI/5.0.3
module load h5py/3.12.1
module load matplotlib/3.9.2

python3 --version
python3 -c "import ROOT, numpy, pandas, scipy, h5py, matplotlib, pip; print('Python dependencies OK')"
