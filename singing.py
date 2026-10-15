"""A short original pitched vocalise using the selected local speech voice.

This is a small la-la melody, not a general song-generation model.
"""
import re
import numpy as np
import soundfile as sf


def requested(text):
    return bool(re.fullmatch(r"(?:(?:hey )?sakura[, ]+)?(?:(?:can|could|would|will) (?:you|u) |please |(?:i want|i'd like) (?:you|u) to )*(?:sing|hum)(?:\s+.{1,120})?[.!? ]*",text.strip(),re.I))


def named_song(text):
    return bool(re.search(r'\b(?:sing|hum)\s+(?!(?:a (?:little|bit|song|short (?:song|tune)|lullaby)|something|for me|please)\b)[a-z]',text,re.I))


def make_vocalise(source,destination):
    samples,rate=sf.read(str(source),always_2d=True)
    samples=samples.mean(axis=1)
    active=np.flatnonzero(np.abs(samples)>.01)
    if not len(active):raise ValueError('The selected voice produced no audible vocal.')
    samples=samples[max(0,active[0]-int(rate*.02)):min(len(samples),active[-1]+int(rate*.03))]
    size=min(len(samples),int(rate*.06))
    start=max(0,int(np.argmax(np.convolve(samples*samples,np.ones(size)/size,mode='same')))-size//2)
    frame=samples[start:start+size];frame=(frame-frame.mean())*np.hanning(len(frame))
    correlation=np.correlate(frame,frame,mode='full')[len(frame)-1:]
    low=max(1,int(rate/600));high=min(len(correlation),int(rate/70))
    lag=low+int(np.argmax(correlation[low:high]));base=rate/lag
    notes=[60,62,64,67,64,62,60]
    octave=round(12*np.log2(base/(440*2**((64-69)/12)))/12)*12
    chunks=[]
    for index,note in enumerate(notes):
        target=440*2**((note+octave-69)/12)
        shifted=np.interp(np.arange(0,len(samples)-1,target/base),np.arange(len(samples)),samples)
        duration=int(rate*(.7 if index==len(notes)-1 else .46))
        chunk=np.zeros(duration)
        count=min(duration,len(shifted));chunk[:count]=shifted[:count]
        fade=min(int(rate*.025),count//2)
        chunk[:fade]*=np.linspace(0,1,fade);chunk[count-fade:count]*=np.linspace(1,0,fade)
        chunks.extend([chunk,np.zeros(int(rate*.06))])
    output=np.concatenate(chunks)
    peak=float(np.max(np.abs(output)))
    if peak>.95:output*=.95/peak
    sf.write(str(destination),output,rate,subtype='PCM_16')
    return str(destination)
