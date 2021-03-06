#!/usr/bin/python

#################################################################################
#                                                                               #
# Written by Wendy Williams, 9 Jan 2015                                         #
#                                                                               #
#                                                                               #
#       NOTE: THIS finds the median phase offset between XX and YY per station  #
#                                                                               #
#################################################################################


import pyrap.tables as pt
import numpy
import sys
import os
import pylab as pl
import glob



def normalize(phase):
    """
    Normalize phase to the range [-pi, pi].
    """

    # Convert to range [-2*pi, 2*pi].
    out = numpy.fmod(phase, 2.0 * numpy.pi)

    # Convert to range [-pi, pi]
    out[out < -numpy.pi] += 2.0 * numpy.pi
    out[out > numpy.pi] -= 2.0 * numpy.pi

    return out

def smooth(x,window_len=11,window='hanning'):
    """smooth the data using a window with requested size.
    
    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal 
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.
    
    input:
        x: the input signal 
        window_len: the dimension of the smoothing window; should be an odd integer
        window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
            flat window will produce a moving average smoothing.

    output:
        the smoothed signal
        
    example:

    t=linspace(-2,2,0.1)
    x=sin(t)+randn(len(t))*0.1
    y=smooth(x)
    
    see also: 
    
    numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
    scipy.signal.lfilter
 
    TODO: the window parameter could be the window itself if an array instead of a string
    NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
    """

    if x.ndim != 1:
        raise ValueError, "smooth only accepts 1 dimension arrays."

    if x.size < window_len:
        raise ValueError, "Input vector needs to be bigger than window size."


    if window_len<3:
        return x


    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"


    s=numpy.r_[x[window_len-1:0:-1],x,x[-1:-window_len:-1]]
    #print(len(s))
    if window == 'flat': #moving average
        w=numpy.ones(window_len,'d')
    else:
        w=eval('numpy.'+window+'(window_len)')

    y=numpy.convolve(w/w.sum(),s,mode='valid')
    return y

def smooth_array(x, axis=0,window_len=11,window='hanning'):
    
    nx, ny = x.shape
    y = numpy.zeros((nx,ny))
    d = window_len/2
    for i in range(ny):
        xi = x[:,i]
        yi = smooth(xi,window_len=window_len,window='hanning')
        yi = yi[d:-d]
        y[:,i] = yi
    
    return y

#if len(sys.argv) < 2:
    #print 'Please give a parmdb name.'
    #print 'Usage: python fixparmdb_zero_median.py <parmdbname>'

#filename = sys.argv[1]
#outfilename = sys.argv[2]

#if os.path.isdir(outfilename):
    #print 'output file exists'
    #sys.exit()
#os.system('cp -r %s %s' %(filename, outfilename))
#filename = outfilename







########################
###### USER INPUT ######

import config
die=config.die
report=config.report
warn=config.warn

if len(sys.argv)<2:
    die('Need a filename for config file')

filename=sys.argv[1]
if not(os.path.isfile(filename)):
    die('Config file does not exist')

cfg=config.LocalConfigParser()
cfg.read(filename)

rootname=cfg.get('files','calibrator')
processedpath=cfg.get('paths','processed')

os.chdir(processedpath)
globaldbname = 'cal.h5' # input h5 parm file
t = pt.table('globaldb/OBSERVATION', readonly=True, ack=False)
calsource=t[0]['LOFAR_TARGET'][0]

n_chan = 1 # number of channels solved for per subband (i.e., the number of solutions along the frequencies axis of the MS) 

try:
    bad_sblist=eval(cfg.get('calibration','badsblist'))
except:
    bad_sblist=[]

mslist = glob.glob(rootname+'_SB*_uv.filter.MS') # all the calibrator datasets

# no need to touch 
mslist.sort()    #  don't chnage this line
badsb = ['SB{sb:03d}'.format(sb=sb) for sb in bad_sblist ]


index = 1 # element where the SB number is after splitting the ms names with split('_')

# make the subband list, exclude the badsb and ms without instrument tables
sblist = [ int(d.split('_')[index].replace('SB','')) for d in mslist if (d.split('_')[index] not in badsb) and (os.path.exists(d + '/instrument'))] 
     
instlist = [ rootname+'_SB{sb:03d}_uv.filter.MS/instrument'.format(sb=sb) for sb in sblist] 
mslist   = [ rootname+'_SB{sb:03d}_uv.filter.MS'.format(sb=sb) for sb in sblist] # replaces previous list with bad SB removed


#### END USER INPUT ####
########################




#names = parmdbmtable.getNames()
#stationsnames = numpy.array([name.split(':')[-1] for name in names])
#stationsnames = numpy.unique(stationsnames)
#stationsnames = stationsnames[1:] # to remove pesky 3C295


anttab=pt.table(mslist[0] + '/ANTENNA')
stationsnames=anttab.getcol('NAME')
anttab.close()
refstation = stationsnames[1]

print stationsnames 

import lofar.parmdb as lp
parmdbmtable = lp.parmdb(instlist[0])

freq_per_sb = numpy.zeros(len(instlist))
for iinst,inst in enumerate(instlist):

    ms = mslist[iinst] 
    print inst, ms
    t          = pt.table(ms, readonly=False)
    freq_tab   = pt.table(ms + '/SPECTRAL_WINDOW')
    freq       = freq_tab.getcol('REF_FREQUENCY')
    t.close()
    #print 'Frequency of MS', freq

    freq_per_sb[iinst] = freq

    stat_offsets = numpy.zeros(len(stationsnames))
    
    parmdbmtable = lp.parmdb(inst)

    names = parmdbmtable.getNames()
    dictionary = parmdbmtable.getValuesGrid('*')
    trange = parmdbmtable.getRange()
    #stationsnames = numpy.array([name.split(':')[-1] for name in names])
    #stationsnames = numpy.unique(stationsnames)

    real_values_00_ref = dictionary['Gain:0:0:Real:'+refstation]['values']
    imaginary_values_00_ref = dictionary['Gain:0:0:Imag:'+refstation]['values']
    real_values_11_ref = dictionary['Gain:1:1:Real:'+refstation]['values']
    imaginary_values_11_ref = dictionary['Gain:1:1:Imag:'+refstation]['values']
    times = dictionary['Gain:1:1:Imag:'+refstation]['times']

    vals_00_ref = real_values_00_ref +1.j*imaginary_values_00_ref
    vals_11_ref = real_values_11_ref +1.j*imaginary_values_11_ref
    phases_00_ref = numpy.angle(vals_00_ref)
    amps_00_ref = numpy.abs(vals_00_ref)
    phases_11_ref = numpy.angle(vals_11_ref)
    amps_11_ref = numpy.abs(vals_11_ref)

    ntimes, nfreqs = real_values_00_ref.shape

    #Nr=8
    #Nc=8
    #f, axs = pl.subplots(Nr, Nc, sharex=True, sharey=True, figsize=(16,12))
    #ax = axs.reshape((Nr*Nc,1))

    #parmdbmtable.deleteValues('*')
    for istat,station in enumerate(stationsnames):
  
        real_values_00 = dictionary['Gain:0:0:Real:'+station]['values']
        imaginary_values_00 = dictionary['Gain:0:0:Imag:'+station]['values']
        real_values_11 = dictionary['Gain:1:1:Real:'+station]['values']
        imaginary_values_11 = dictionary['Gain:1:1:Imag:'+station]['values']
        
        vals_00 = real_values_00 +1.j*imaginary_values_00
        vals_11 = real_values_11 +1.j*imaginary_values_11

        phases_00 = normalize(numpy.angle(vals_00) - phases_00_ref)
        phases_11 = normalize(numpy.angle(vals_11) - phases_11_ref)
        #phases_00 = normalize(numpy.angle(vals_00))
        #phases_11 = normalize(numpy.angle(vals_11))
        amps_00 = numpy.abs(vals_00)
        amps_11 = numpy.abs(vals_11)
        
        phase_diff = phases_00 - phases_11
        phase_diff = normalize(phase_diff)
        med_phase_diff = numpy.median(phase_diff)
        #smooth_phase_diff = smooth_array(phase_diff,window_len=11)
        
        stat_offsets[istat] = med_phase_diff
        
        #print "{s}: {f:.3f} rad".format(s=station, f=med_phase_diff)
        
        
        #ax[istat][0].set_title(station)
        ##ax[istat].plot(range(ntimes), phases_00,'b.')
        #ax[istat][0].plot(times, phase_diff,'g.')
        #ax[istat][0].plot(times, smooth_phase_diff,'b')
        #ax[istat][0].plot(times, med_phase_diff*numpy.ones(ntimes),'r')

        #ax[istat][0].set_ylim(-3.2,3.2)
        #ax[istat][0].set_xlim(times.min(), times.max())
        
        ##new_real_values = numpy.sqrt(real_values**2. + imaginary_values**2.)
        ###new_imaginary_values = numpy.zeros(dictionary[imaginary_name]['values'].shape)
        ##new_real_value = numpy.median(new_real_values)
        ### if the average is 1 and they are not all 1, use the ones that aren't 1
        ###if new_real_value == 1.0:
            ###if numpy.sum(new_real_values==new_real_value) != len(new_real_values):
                ###new_real_values = numpy.ma.masked_where(new_real_values==1, new_real_values).compressed()
                ###new_real_value = numpy.median(new_real_values)
        ###new_imaginary_value = numpy.median(new_imaginary_values)
        ##new_imaginary_value = 0.
        
        #smooth_phase_diff[numpy.isnan(smooth_phase_diff)] = 0.
        #smooth_phase_diff *= -1  # test case
        
        #new_real_values_00 = numpy.ones_like(smooth_phase_diff)
        #new_real_values_11 = numpy.cos(smooth_phase_diff)
        #new_imaginary_values_00 =  numpy.zeros_like(smooth_phase_diff)
        #new_imaginary_values_11 =  numpy.sin(smooth_phase_diff)
        
        #real_dict_00 = dictionary['Gain:0:0:Real:'+station]
        #imaginary_dict_00 = dictionary['Gain:0:0:Imag:'+station]
        #real_dict_11 = dictionary['Gain:1:1:Real:'+station]
        #imaginary_dict_11 = dictionary['Gain:1:1:Imag:'+station]
        
        #real_dict_00['values'] = new_real_values_00
        
        #parmdbmtable.addValues('Gain:0:0:Real:'+station,new_real_values_00, sfreq=trange[0], efreq=trange[1], stime=trange[2], etime=trange[3])
        #parmdbmtable.addValues('Gain:1:1:Real:'+station,new_real_values_11, sfreq=trange[0], efreq=trange[1], stime=trange[2], etime=trange[3])
        #parmdbmtable.addValues('Gain:0:0:Imag:'+station,new_imaginary_values_00, sfreq=trange[0], efreq=trange[1], stime=trange[2], etime=trange[3])
        #parmdbmtable.addValues('Gain:1:1:Imag:'+station,new_imaginary_values_11, sfreq=trange[0], efreq=trange[1], stime=trange[2], etime=trange[3])
        #print '%s %.5f %.5f' %(name, new_real_value, new_imaginary_value)

    #parmdbmtable.flush()
    
    if iinst == 0:
        global_stat_offsets = stat_offsets
    else:
        global_stat_offsets = numpy.vstack((global_stat_offsets, stat_offsets))

import scipy.signal as s
global_stat_offsets_smoothed = numpy.zeros_like(global_stat_offsets)
for istat, stat in enumerate(stationsnames):
    global_stat_offsets_smoothed[:,istat] = s.medfilt(global_stat_offsets[:,istat], kernel_size=15)
#global_stat_offsets_smoothed = smooth_array(global_stat_offsets,window_len=11)

station_offsets = numpy.median(global_stat_offsets,axis=0)
station_offset_dev = numpy.std(global_stat_offsets-station_offsets, axis=0)
for istat, stat in enumerate(stationsnames):
    print "{s:9s}: {med:6.3f} ({std:6.3f})".format(s=stat, med=station_offsets[istat], std=station_offset_dev[istat])

numpy.save('freqs_for_phase_array.npy', freq_per_sb)
numpy.save(calsource +'_phase_array.npy', global_stat_offsets_smoothed)


Nr=8
Nc=8
f, axs = pl.subplots(Nr, Nc, sharex=True, sharey=True, figsize=(16,12))
ax = axs.reshape((Nr*Nc,1))
for istat, stat in enumerate(stationsnames):
    ax[istat][0].set_title(stat)
    #ax[istat].plot(range(ntimes), phases_00,'b.')
    #ax[istat][0].plot(times, phase_diff,'g.')
    #ax[istat][0].plot(times, smooth_phase_diff,'b')
    ax[istat][0].plot(sblist, global_stat_offsets[:,istat],'b')
    ax[istat][0].plot(sblist, global_stat_offsets_smoothed[:,istat],'g')
    ax[istat][0].set_ylim(-3.2,3.2)
    ax[istat][0].set_xlim(0, len(instlist))

f.savefig('offsets.png')

##import matplotlib.pyplot as plt
#for name in real_names:
    #imaginary_name = name.replace('Real','Imag')
    #real_values = dictionary[name]['values']
    #imaginary_values = dictionary[imaginary_name]['values']
    ##plt.figure()
    
    #ntimes, nfreqs = real_values.shape
    #vals = real_values +1.j*imaginary_values

    #phases = numpy.angle(vals)
    #amps = numpy.abs(vals)
    
    #medamp = numpy.median(amps, axis=0)  ## for each frequency
    ##smoothphases = smooth_array(phases)
    ##smoothphase = scipy.signal.medfilt(phases.flatten(), 5 * 2 - 1)
    #smedphase = phases[-1,:]  # take the last phase value... avoid edge
    
    ##plt.plot(phases)
    ##plt.plot(smoothphases)
    
    #new_real_values = medamp*numpy.cos(smedphase)
    #new_imaginary_values = medamp*numpy.sin(smedphase)
    #parmdbmtable.addDefValues(name,new_real_values)
    #parmdbmtable.addDefValues(imaginary_name,new_imaginary_values)
    #print name, ": ", new_real_values, new_imaginary_values
    
    ##if 'RS' in name:
        ##pl.figure()
        ##pl.plot(phases)
        ##pl.plot(smoothphase)
        ##pl.plot(len(smoothphase)-5, phase,'ko')
        
    ##pl.show()
#parmdbmtable.deleteValues('*')
#parmdbmtable.flush()
