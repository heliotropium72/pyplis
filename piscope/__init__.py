# -*- coding: utf-8 -*-
from os.path import abspath, dirname
from pkg_resources import get_distribution

__version__ = get_distribution('piscope').version

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

import inout as io
import geometry
import utils
from image import Img
import dataset
import plumebackground
import calibration
import plumespeed
import processing
#import evaluation
import optimisation
import model_functions
import setupclasses as setup   
import doasfov 
import helpers
import exceptions

import gui_features as gui_features