#!/bin/bash

mkdir -p "$1/charge/results"
> "$1"/charge/results/signals.csv
> "$1"/charge/results/signals_inspect.csv

echo "Performing Charge Analysis"

for folder in "$1"/optical/*/
do
    folder_name=$(basename "$folder")
    if [[ "$folder_name" != "results" ]]; then

	echo "Processing: $folder_name"
	python3 waveform-integrator.py "$1"/charge "$folder_name" waveforms.csv
	python3 waveform-plotting.py "$1"/charge "$folder_name" waveforms.root
        
    fi
    ((i++))
done