# KPIC Data Reduction Pipeline

## Install
Run in the top level of this repo:

    > pip install -r requirements.txt -e .

This will create a configuration file at `~/.kpicdrp` that will specify the path to where the KPIC DRP calibration databases live. By default, it is where the source code for the KPIC DRP lives. The following calibration databases will be defined:

  * caldb_detector.csv
  * caldb_traces.csv
  * caldb_wavecal.csv
