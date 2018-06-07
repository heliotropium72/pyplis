Pyplis is a Python toolbox for the analysis of UV SO2 camera data. The software includes a comprehensive collection of algorithms for the analysis of such data.

This is a fork of pyplis containing several modifications to allow for multi-layered fits files.

The original repository can be found on the github page of Jonas Gliss (https://github.com/jgliss/pyplis).
General information of the liberary including examples, environment setup and scientific background are listed there.

The state of the original repository is the one of January, 1st 2018. After this the development in this fork deviates.
The API is therefore based on version 1.0.1 .

Add-ons and changes to original fork
===================
- ImgListMultiFits
- ImgList and Image contain skymasks: Binary masks excluding image areas
- Separate calibration class
- Added flexibility in Doas calibration and added functionality when not using custom pydoas library
- Internal restructuring for improved readability
- ...


All added code is compatible with Python 3.6 standard to simplify future upgrading pyplis to python 3.6.
