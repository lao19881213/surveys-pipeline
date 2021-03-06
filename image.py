#!/usr/bin/python

# Generate the standard image

import os
import sys
import config
import os.path
import pyrap.tables as pt
import numpy as np

def getfreq(ms):
    t = pt.table(ms+'/SPECTRAL_WINDOW', readonly=True, ack=False)
    freq = t[0]['REF_FREQUENCY']
    t.close()
    return freq

def do_image(run,ms,suffix,npix,cellsize,padding,niter,threshold,uvmin,uvmax,wmax,robust,mask=None,operation='mfclark'):
    imgname=ms.replace('.MS','_'+suffix)
    os.system('rm -r '+imgname+'*')
    c='awimager UseMasks=False ms='+ms
    c+=' image='+imgname
    c+=' weight=briggs robust='+robust
    c+=' npix='+npix
    c+=' cellsize='+cellsize+'arcsec'
    c+=' data=CORRECTED padding='+padding
    c+=' niter='+niter
    c+=' stokes=I operation='+operation
    c+=' UVmin='+uvmin
    if uvmax:
        c+=' UVmax='+uvmax
    c+=' wmax='+str(int(wmax))
    c+=' threshold='+threshold+'Jy'
    if mask:
        c+=' mask='+mask
    run(c)

die=config.die
report=config.report
warn=config.warn

if len(sys.argv)<2:
    die('Need a filename for config file')

filename=sys.argv[1]
if not(os.path.isfile(filename)):
    die('Config file does not exist')

if len(sys.argv)<3:
    die('Need a band number')

band=int(sys.argv[2])

cfg=config.LocalConfigParser()
cfg.read(filename)

troot=cfg.get('files','target')
processedpath=cfg.get('paths','processed')
os.chdir(processedpath)
domask=cfg.getoption('imaging','domask',True)
corrected=cfg.getoption('imaging','corrected',True)
# set false if you don't want calibration applied when you image
applybeam=cfg.getoption('imaging','applybeam',True)
# set false if the beam was already applied, e.g. when applying calibration
if corrected:
    column='CORRECTED_DATA'
else:
    column='DATA'
run=config.runner(cfg.getoption('control','dryrun',False)).run
npix=cfg.get('imaging','npix')
cellsize=cfg.get('imaging','cellsize')
padding=cfg.get('imaging','padding')
totiter=cfg.get('imaging','niter')
if domask:
    maskiter=cfg.get('imaging','maskiter')
threshold=cfg.get('imaging','threshold')
uvmin=cfg.get('imaging','uvmin')
try:
    uvmax=float(cfg.get('imaging','uvmax'))
except:
    uvmax=None
robust=cfg.get('imaging','robust')
suffix=cfg.get('imaging','suffix')

bs='%02i' % band
ms=troot+'_B'+bs+'_concat.MS'
ims=troot+'_B'+bs+'_'+suffix+'.MS'

if uvmax:
    freq=getfreq(ms)
    uvmax*=np.sqrt(150e6/freq)
    uvmaxs='%.1f' % uvmax
    wmax=(3.0e8/freq)*uvmax*1.0e3
    print 'Using uvmax',uvmaxs
else:
    print 'no uvmax, trying for full resolution!'
    uvmaxs=None
    wmax=120000

if applybeam:
    if os.path.isdir(ims):
        warn('Imaging MS exists, not copying it again')
    else:
        report('Copying file '+ms)

        file=open('NDPPP-temp-'+bs,'w')
        file.write('msin=['+ms+']\nmsin.datacolumn = '+column+'\nmsin.baseline = [CR]S*&\nmsout = '+ims+'\nsteps = []\n')
        file.close()

        run('NDPPP NDPPP-temp-'+bs)

        report('Applying beam')
        run('applybeam.py '+ims)
else:
    ims=ms

if domask:
    report('Doing initial unmasked image')
    do_image(run,ims,'img',npix,cellsize,padding,maskiter,threshold,uvmin,uvmaxs,wmax,robust,mask=None)
    imgname=ims.replace('.MS','_img')
    report('Making mask')
    run('/home/mjh/lofar/reinout/makecleanmask_10sb.py --blank '+imgname+'.restored')
    report('Making second image')
    do_image(run,ims,'img_masked',npix,cellsize,padding,totiter,threshold,uvmin,uvmaxs,wmax,robust,mask=imgname+'.restored.maskmodel')
else:
    report('Making image')
    do_image(run,ims,'img',npix,cellsize,padding,totiter,threshold,uvmin,uvmaxs,wmax,robust,mask=None)
    

report('Write FITS files')
if domask:
    imgname=ims.replace('.MS','_img_masked')
else:
    imgname=ims.replace('.MS','_img')

run('/home/mjh/lofar/bin/tofits.py '+imgname+'.restored')
run('/home/mjh/lofar/bin/tofits.py '+imgname+'.restored.corr')
