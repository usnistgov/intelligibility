import abcmrt
import csv
import datetime
import glob
import mcvqoe.base
import os.path
import pkg_resources
import re
import shutil
import sys
import time

import numpy as np
import scipy.signal

from distutils.util import strtobool
from mcvqoe.base.terminal_user import terminal_progress_update, terminal_user_check
from mcvqoe.delay.ITS_delay import active_speech_level
from fractions import Fraction

#version import for logging purposes
from .version import version

def chans_to_string(chans):
    #check if we got a string
    if(isinstance(chans, str)):
        raise ValueError('Input can not be str')
    #channel string
    return '('+(';'.join(chans))+')'


def parse_audio_chans(csv_str):
    '''
    Function to parse audio channels from csv file
    '''
    match=re.search('\((?P<chans>[^)]+)\)',csv_str)

    if(not match):
        raise ValueError(f'Unable to parse chans {csv_str}, expected in the form "(chan1;chan2;...)"')

    return tuple(match.group('chans').split(';'))

class measure(mcvqoe.base.Measure):
    """
    Class to run and reprocess ABC_MRT Intelligibility tests.

    The Intelligibility measure class is used to measure intelligibility of a real or simulated push to talk communications system

    Attributes
    ----------
    audio_files : list
        List of names of audio files. relative paths are relative to audio_path
    audio_path : string
        Path where audio is stored
    overPlay : float
        Number of extra seconds of audio to record at the end of a trial
    trials : int
        Number of times audio will be run through the system in the run method
    bgnoise_file : string
        Name of audio file to use as background noise during measurement.
    bgnoise_snr : float, default=50
        Signal to noise ratio for voice vs noise.
    outdir : string
        Base directory where data is stored.
    ri : mcvqoe.RadioInterface or mcvqoe.QoEsim
        Object to use to key the audio channel
    info : dict
        Dictionary with test info to for the log entry
    ptt_wait : float
        Time to wait, in seconds, between keying the channel and playing audio
    ptt_gap : float
        Time to pause, in seconds, between one trial and the next
    rng : Generator
        Generator to use for random numbers
    audio_interface : mcvqoe.AudioPlayer or mcvqoe.simulation.QoEsim
        interface to use to play and record audio on the communication channel
    get_post_notes : function or None
        Function to call to get notes at the end of the test. Often set to
        mcvqoe.post_test to get notes with a gui popup.
        lambda : mcvqoe.post_test(error_only=True) can be used if notes should
        only be gathered when there is an error
    data_fields : dict
        static property that has info on the standard .csv columns. Column names
        are dictionary keys and the values are conversion functions to get from
        string to the appropriate type. This should not be modified in most
        cases
    no_log : tuple of strings
        static property that is a tuple of property names that will not be added
        to the 'Arguments' field in the log. This should not be modified in most
        cases
    y : list of audio vectors
        Audio data for transmit clips. This is set by the load_audio function.
    data_filename : string
        This is set in the `run` method to the path to the output .csv file.
    full_audio_dir : bool, default=False
        read, and use, .wav files in audio_path, ignore audio_files and trials
    progress_update : function, default=terminal_progress_update
        function to call to provide updates on test progress. This function
        takes three arguments, progress type, total number of trials, current
        trial number. The first argument, progress type is a string that will be
        one of {'test','proc'} to indicate that the test is running trials or
        processing data.
    save_tx_audio : bool, default=False
        If true, tx audio will be saved in `outdir/data/wav/[test string]/`.
        Otherwise tx audio will not be saved. Ignored if save_audio is False.
    save_audio : bool, default=True
        If true audio from the test will remain in `outdir/data/wav/[test string]/`.
        Otherwise audio will be deleted once it is no longer used. If false then
        save_tx_audio=False is also implied.

    Methods
    -------

    run()
        run a test with the properties of the class
    load_test_data(fname,load_audio=True)
        load dat from a .csv file. If load_audio is true then the Tx clips from
        the wav dir is loaded into the class. returns the .csv data as a list of
        dicts
    post_process(test_dat,fname,audio_path)
        process data from load_test_dat and write a new .csv file.

    Examples
    --------
    example of running a test with simulated devices.

    >>>from mcvqoe.intelligibility import measure as intell
    >>>import mcvqoe.simulation
    >>>sim_obj=mcvqoe.simulation.QoEsim()
    >>>test_obj=intell(ri=sim_obj,audio_interface=sim_obj,trials=10,
    ...     audio_path='path/to/audio/',
    ...     audio_files=('F1_PSuD_Norm_10.wav','F3_PSuD_Norm_10.wav',
    ...         'M3_PSuD_Norm_10.wav','M4_PSuD_Norm_10.wav'
    ...         )
    ... )
    >>>test_obj.run()

    Example of reprocessing  a test file, 'test.csv', to get 'rproc.csv'

    >>>from PSuD_1way_1loc import PSuD
    >>>test_obj=PSuD()
    >>>test_dat=test_obj.load_test_data('[path/to/outdir/]data/csv/test.csv')
    >>>test_obj.post_process(test_dat,'rproc.csv',test_obj.audio_path)
    """



    #on load conversion to datetime object fails for some reason
    #TODO : figure out how to fix this, string works for now but this should work too:
    #row[k]=datetime.datetime.strptime(row[k],'%d-%b-%Y_%H-%M-%S')
    data_fields={"Timestamp":str,"Filename":str,"channels":parse_audio_chans,'Intelligibility':float}
    no_log = ('y', 'clipi', 'data_dir', 'wav_data_dir', 'csv_data_dir',
              'data_fields', '_audio_order')

    measurement_name = "Intelligibility"

    def __init__(self, **kwargs):

        self.rng = np.random.default_rng()
        # set default values
        self.trials = 1200
        self.pause_trials = 450
        self.outdir = ''
        self.ri = None
        self.info = {'Test Type': 'default', 'Pre Test Notes': None}
        self.ptt_wait = 0.68
        self.ptt_gap = 3.1
        self.test = "1loc"
        self.bgnoise_file = ""
        self.bgnoise_snr = 50
        self.audio_interface = None
        self.full_audio_dir = False
        self.progress_update = terminal_progress_update
        self.user_check = terminal_user_check
        self.save_tx_audio = False
        self.save_audio = True
        self._pause_count = 0

        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise TypeError(f"{k} is not a valid keyword argument")
        # Get all included audio files
        audio_files = pkg_resources.resource_listdir(
            'mcvqoe.intelligibility', 'audio_clips'
            )
        # Initialize dictionary for audio files
        self._audio_order = dict()
        for fname in audio_files:
            num = abcmrt.file2number(fname)
            # Store audio file name with the key of its number
            self._audio_order[num] = fname

    def load_audio(self):
        """
        Load audio files for use in test.

        This loads audio and stores values in self.y,
        self.cutpoints and self.keyword_spacings
        In most cases run() will call this automatically but, it can be called
        in the case that self.audio_files is changed after run() is called
        TODO: Update this documentation

        Raises
        ------
        RuntimeError
            If clip fs is not 48 kHz
        """
        if self.trials < 0 or self.trials > 1200:
            raise ValueError(
                f'Trials must be between 1-1200, {self.trials} is invalid.'
                )

        # Get bgnoise_file and resample
        if self.bgnoise_file:
            nfs, nf = mcvqoe.base.audio_read(self.bgnoise_file)
            rs = Fraction(abcmrt.fs / nfs)
            nf = scipy.signal.resample_poly(nf, rs.numerator, rs.denominator)

        # Get file order
        file_order = abcmrt.file_order()
        # Initialize where audio will be stored
        self.y = []
        self.audio_files = []

        for k in range(self.trials):
            file_num = file_order[k]
            file_name = self._audio_order[file_num]
            file_path = pkg_resources.resource_filename(
                'mcvqoe.intelligibility',
                f'audio_clips/{file_name}'
                )
            fs, audio_data = mcvqoe.base.audio_read(file_path)
            # TODO: Can probably delete this check?
            # check fs
            if(fs != abcmrt.fs):
                raise RuntimeError((
                    f'Expected fs to be {abcmrt.fs} but got {fs} for'
                    f' {file_path}'
                    ))

            # check if we are adding noise
            if self.bgnoise_file:

                # measure amplitude of signal and noise
                sig_level = active_speech_level(audio_data, abcmrt.fs)
                noise_level = active_speech_level(nf, abcmrt.fs)

                # calculate noise gain required to get desired SNR
                noise_gain = sig_level - (self.bgnoise_snr + noise_level)

                # set noise to the correct level
                noise_scaled = nf * (10 ** (noise_gain / 20))

                # add noise (repeated to audio file size)
                audio_data = audio_data + np.resize(noise_scaled, audio_data.size)

            self.y.append(audio_data)
            self.audio_files.append(file_name)

    def csv_header_fmt(self):
        """
        Generate header and format for .csv files.

        This generates a header for .csv files along with a format (that can be
        used with str.format()) to generate each row in the .csv

        Returns
        -------
        hdr : string
            csv header string
        fmt : string
            format string for data lines for the .csv file
        """
        hdr=','.join(self.data_fields.keys())
        fmt='{'+'},{'.join(self.data_fields.keys())+'}'
        #add newlines at the end
        hdr+='\n'
        fmt+='\n'

        return (hdr,fmt)

    def log_extra(self):
        #add abcmrt version
        self.info['abcmrt version'] = abcmrt.version

        # Add blocksize and buffersize
        self.blocksize = self.audio_interface.blocksize
        self.buffersize = self.audio_interface.buffersize

    def test_setup(self):
        #-----------------------[Check audio sample rate]-----------------------
        if self.audio_interface is not None and \
            self.audio_interface.sample_rate != abcmrt.fs:
            raise ValueError(f'audio_interface sample rate is {self.audio_interface.sample_rate} Hz but only {abcmrt.fs} Hz is supported')

    def process_audio(self, clip_index, fname, rec_chans):
        """
        estimate intelligibility for an audio clip.

        Parameters
        ----------
        clip_index : int
            Clip index, not used for intelligibility.
        fname : str
            audio file to process.
        rec_chans : tuple
            tuple of recived channel names.

        Returns
        -------
        dict
            returns a dictionary with estimated values

        """

        #---------------------[Load in recorded audio]---------------------
        fs,rec_dat = mcvqoe.base.audio_read(fname)
        if(abcmrt.fs != fs):
            raise RuntimeError('Recorded sample rate does not match!')

        #check if we have more than one channel
        if(rec_dat.ndim !=1 ):
            #get the index of the voice channel
            voice_idx=rec_chans.index('rx_voice')
            #get voice channel
            voice_dat=rec_dat[:,voice_idx]
        else:
            voice_dat=rec_dat

        rec_dat=mcvqoe.base.audio_float(voice_dat)

        #---------------------[Compute intelligibility]---------------------

        word_num=abcmrt.file2number(fname)

        phi_hat,success=abcmrt.process(voice_dat,word_num)

        #only one element in list, convert to scalar
        success=success[0]

        return {
                    'Intelligibility':success,
                    'channels':chans_to_string(rec_chans),
                    'voice':voice_dat,
                    'wnum':word_num,
                }

    # overide so we don't need to load audio
    def find_clip_index(self, name):
        """
        Dummy function, to return a fake clip index.

        Clip index is not needed for Intelligibility reprocess, so this returns
        a dummy value

        Parameters
        ----------
        name : string
            base name of audio clip

        Returns
        -------
        int
            Dummy index.

        """

        return -1

    def load_test_data(self,fname,load_audio=True,audio_path=None):
        """
        load test data from .csv file.

        This exists here because we don't need to load the Tx audio.

        Parameters
        ----------
        fname : string
            filename to load
        load_audio : bool, default=True
            if True, finds and loads audio clips and cutpoints based on fname
        audio_path : str, default=None
            Path to find audio files at. Guessed from fname if None.

        Returns
        -------
        list of dicts
            returns data from the .csv file

        """

        #set audio path for reprocess
        if(audio_path is not None):
            self.audio_path=audio_path
        else:
            #get datafile name for test
            dat_name = mcvqoe.base.get_meas_basename(fname)
            #set audio_path based on filename
            self.audio_path=os.path.join(os.path.dirname(os.path.dirname(fname)),'wav',dat_name)

        with open(fname,'rt') as csv_f:
            #create dict reader
            reader=csv.DictReader(csv_f)
            #create empty list
            data=[]
            #create set for audio clips
            clips=set()
            for row in reader:
                #convert values proper datatype
                for k in row:
                    #check for clip name
                    if(k=='Filename'):
                        #save clips
                        clips.add(row[k])
                    try:
                        #check for None field
                        if(row[k]=='None'):
                            #handle None correctly
                            row[k]=None
                        else:
                            #convert using function from data_fields
                            row[k]=self.data_fields[k](row[k])
                    except KeyError:
                        #not in data_fields, convert to float
                        row[k]=float(row[k]);

                #append row to data
                data.append(row)

        #set total number of trials, this gives better progress updates
        #set total number of trials, this gives better progress updates
        self.trials=len(data)

        return data
