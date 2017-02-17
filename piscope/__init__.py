# -*- coding: utf-8 -*-
from os.path import abspath, dirname
from pkg_resources import get_distribution

__version__ = get_distribution('piscope').version

URL_TESTDATA = ("https://folk.nilu.no/~gliss/piscope_testdata/"
                "piscope_etna_testdata.zip")

try:
    import pydoas
    PYDOASAVAILABLE =True
except:
    PYDOASAVAILABLE = False

try:
    import geonum
    GEONUMAVAILABLE = 1
except:
    GEONUMAVAILABLE = 0

_LIBDIR = abspath(dirname(__file__))

import inout
import geometry
import utils
from image import Img
import dataset
import plumebackground
import cellcalib
import doascalib
import plumespeed
import processing
import dilutioncorr
import fluxcalc
import optimisation
import model_functions
import setupclasses  
 
import helpers
import exceptions

#import gui_features as gui_features