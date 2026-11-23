#!/bin/bash

mkdir -p "$1/optical/results"
> "$1"/optical/results/signals.csv
> "$1"/optical/results/signals_inspect.csv

echo "Performing Optical Analysis"

for folder in "$1"/optical/*/
do
    folder_name=$(basename "$folder")
    if [[ "$folder_name" != "results" ]]; then

	echo "Processing: $folder_name"
	./tpx3dump -i "$1"/optical/"$folder_name"/rawdata_000000.tpx3 -o "$1"/optical/"$folder_name"/output.hdf5
	python3 optical-analysis.py "$1"/optical "$folder_name" output.hdf5
        
    fi
    ((i++))
done