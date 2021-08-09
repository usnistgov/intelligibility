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

from distutils.util import strtobool
from mcvqoe.base.terminal_user import terminal_progress_update

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

class measure:
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
    intell_est : {'trial','aggregate','none'}, default='aggregate'
        Control when, and how, intelligibility and mouth to ear estimations are
        done.
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
    data_fields={"Timestamp":str,"Filename":str,"channels":parse_audio_chans,"Over_runs":int,"Under_runs":int,'Intelligibility':float}
    no_log=('y','clipi','data_dir','wav_data_dir','csv_data_dir','data_fields')
    
    def __init__(self, **kwargs):

        self.rng = np.random.default_rng()
        # set default values
        self.trials = 100
        self.outdir = ''
        self.ri = None
        self.info = {'Test Type': 'default', 'Pre Test Notes': None}
        self.ptt_wait = 0.68
        self.ptt_gap = 3.1
        self.audio_interface = None
        self.full_audio_dir = False
        self.progress_update = terminal_progress_update
        self.intell_est = 'aggregate'
        self.save_tx_audio = False
        self.save_audio = True

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
    
    def run(self):
        """
        run a test with the properties of the class.

        Returns
        -------
        string
            name of the .csv file without path or extension
            

        """
        #-----------------------[Check audio sample rate]-----------------------
        if(self.audio_interface.sample_rate != abcmrt.fs):
            raise ValueError(f'audio_interface sample rate is {self.audio_interface.sample_rate} Hz but only {abcmrt.fs} Hz is supported')
        #------------------[Check for correct audio channels]------------------
        if('tx_voice' not in self.audio_interface.playback_chans.keys()):
            raise ValueError('self.audio_interface must be set up to play tx_voice')
        if('rx_voice' not in self.audio_interface.rec_chans.keys()):
            raise ValueError('self.audio_interface must be set up to record rx_voice')
        #---------------------[Load Audio Files if Needed]---------------------
        if(not hasattr(self,'y')):
            self.load_audio()

        if(self.full_audio_dir):
            #overide trials to use all the trials
            self.trials=len(self.y)
        
        #generate clip index
        self.clipi=self.rng.permutation(self.trials)%len(self.y)

        #-------------------------[Get Test Start Time]-------------------------
        self.info['Tstart']=datetime.datetime.now()
        dtn=self.info['Tstart'].strftime('%d-%b-%Y_%H-%M-%S')
        
        #--------------------------[Fill log entries]--------------------------
        #set test name
        self.info['test']='Intelligibility'
        #add abcmrt version
        self.info['abcmrt version']=abcmrt.version
        #fill in standard stuff
        self.info.update(mcvqoe.base.write_log.fill_log(self))
        #-----------------------[Setup Files and folders]-----------------------
        
        #generate data dir names
        data_dir=os.path.join(self.outdir,'data')
        wav_data_dir=os.path.join(data_dir,'wav')
        csv_data_dir=os.path.join(data_dir,'csv')
        
        
        #create data directories 
        os.makedirs(csv_data_dir, exist_ok=True)
        os.makedirs(wav_data_dir, exist_ok=True)
        
        
        #generate base file name to use for all files
        base_filename='capture_%s_%s'%(self.info['Test Type'],dtn);
        
        #generate test dir names
        wavdir=os.path.join(wav_data_dir,base_filename) 
        
        #create test dir
        os.makedirs(wavdir, exist_ok=True)
        
        # get name of audio clip without path or extension
        clip_names=[os.path.basename(os.path.splitext(a)[0]) for a in self.audio_files]

        #get name of csv files with path and extension
        self.data_filename=os.path.join(csv_data_dir,f'{base_filename}.csv')

        #get name of temp csv files with path and extension
        temp_data_filename = os.path.join(csv_data_dir,f'{base_filename}_TEMP.csv')

        if(self.save_tx_audio):
            #write out Tx clips to files
            for dat,name in zip(self.y,clip_names):
                out_name=os.path.join(wavdir,f'Tx_{name}')
                mcvqoe.base.audio_write(out_name+'.wav', int(self.audio_interface.sample_rate), dat)
            
        #---------------------------[write log entry]---------------------------
        
        mcvqoe.base.write_log.pre(info=self.info, outdir=self.outdir)
        
        #---------------[Try block so we write notes at the end]---------------
        
        try:
            #---------------------------[Turn on RI LED]---------------------------
            
            self.ri.led(1,True)
            
            #-------------------------[Generate csv header]-------------------------
            
            header,dat_format=self.csv_header_fmt()
            
            #-----------------------[write initial csv file]-----------------------
            with open(temp_data_filename,'wt') as f:
                f.write(header)
            #--------------------------[Measurement Loop]--------------------------
            for trial in range(self.trials):
                #-----------------------[Update progress]-------------------------
                if(not self.progress_update('test',self.trials,trial)):
                    #turn off LED
                    self.ri.led(1, False)
                    print('Exit from user')
                    break
                #-----------------------[Get Trial Timestamp]-----------------------
                ts=datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')
                #--------------------[Key Radio and play audio]--------------------
                
                #push PTT
                self.ri.ptt(True)
                
                #pause for access
                time.sleep(self.ptt_wait)
                
                clip_index=self.clipi[trial]
                
                #generate filename
                clip_name=os.path.join(wavdir,f'Rx{trial+1}_{clip_names[clip_index]}.wav')
                
                #play/record audio
                rec_chans=self.audio_interface.play_record(self.y[clip_index],clip_name)
                
                #un-push PTT
                self.ri.ptt(False)
                #-----------------------[Pause Between runs]-----------------------
                
                time.sleep(self.ptt_gap)
                
                #-------------------------[Process Audio]-------------------------

                trial_dat=self.process_audio(clip_name,rec_chans)
                
                #check if we will need audio later
                if(self.intell_est!='aggregate'):
                    #done with processing, delete file
                    if(not self.save_audio):
                        os.remove(clip_name)

                #---------------------------[Write File]---------------------------
                
                trial_dat['Filename']   = clip_names[self.clipi[trial]]
                trial_dat['Timestamp']  = ts
                trial_dat['Over_runs']  = 0
                trial_dat['Under_runs'] = 0
                
                with open(temp_data_filename,'at') as f:
                    f.write(dat_format.format(**trial_dat))
                    
            #-------------------------------[Cleanup]-------------------------------
            
            if(self.intell_est=='aggregate'):
                #process audio from temp file into real file
                
                #load temp file data
                test_dat=self.load_test_data(temp_data_filename,load_audio=False)
                
                #process data and write to final filename
                intell_est=self.post_process(test_dat,self.data_filename,wavdir)
            
                #remove temp file
                os.remove(temp_data_filename)
                
                #remove all audio files from wavdir
                for name in glob.iglob(os.path.join(wavdir,'*.wav')):
                    os.remove(name)
                    
            elif(self.intell_est=='trial'):
                #move temp file to real file
                shutil.move(temp_data_filename,self.data_filename)
                #load file data
                test_dat=self.load_test_data(self.data_filename,load_audio=False)
                
                #no intelligibility estimation needed
                self.intell_est='none'
                
                #process data and get intelligibility estimate
                intell_est=self.post_process(test_dat,os.devnull,wavdir)

            else:
                #move temp file to real file
                shutil.move(temp_data_filename,self.data_filename)
                #dummy intell_est
                intell_est=np.nan
            
            #---------------------------[Turn off RI LED]---------------------------
            
            self.ri.led(1,False)
        
        finally:
            if(self.get_post_notes):
                #get notes
                info=self.get_post_notes()
            else:
                info={}
            #finish log entry
            mcvqoe.base.post(outdir=self.outdir,info=info)
            
        return (intell_est)
        
    def process_audio(self,fname,rec_chans):
        """
        estimate intelligibility for an audio clip.

        Parameters
        ----------
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
        
        #check if we should process audio
        if(self.intell_est=='trial'):
            phi_hat,success=abcmrt.process(voice_dat,word_num)
            
            #only one element in list, convert to scalar
            success=success[0]
        else:
            success=np.nan

            
        return {
                    'Intelligibility':success,
                    'channels':chans_to_string(rec_chans),
                    'voice':voice_dat,
                    'wnum':word_num,
                }
        
    def load_test_data(self,fname,load_audio=True,audio_path=None):
        """
        load test data from .csv file.

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
            dat_name,_=os.path.splitext(os.path.basename(fname))
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
    
    # TODO: Can we delete this? doesn't seem used
    #get the clip index given a partial clip name
    def find_clip_index(self,name):
        """
        find the index of the matching transmit clip.

        Parameters
        ----------
        name : string
            base name of audio clip

        Returns
        -------
        int
            index of matching tx clip

        """
        
        #match a string that has the chars that are in name
        #this 
        name_re=re.compile(re.escape(name)+'(?![^.])')
        #get all matching indices
        match=[idx for idx,clip in enumerate(self.audio_files) if  name_re.search(clip)]
        #check that a match was found
        if(not match):
            raise RuntimeError(f'no audio clips found matching \'{name}\' found in {self.audio_files}')
        #check that only one match was found
        if(len(match)!=1):
            raise RuntimeError(f'multiple audio clips found matching \'{name}\' found in {self.audio_files}')
        #return matching index
        return match[0]
        
    def post_process(self,test_dat,fname,audio_path):
        """
        process csv data.

        Parameters
        ----------
        test_data : list of dicts
            csv data for trials to process
        fname : string
            file name to write processed data to
        audio_path : string
            where to look for recorded audio clips

        Returns
        -------

        """
        
        #get .csv header and data format
        header,dat_format=self.csv_header_fmt()
        
        with open(fname,'wt') as f_out:

            f_out.write(header)

            speech=[]
            clip_num=[]
            success=[]

            for n,trial in enumerate(test_dat):
                
                #update progress
                self.progress_update('proc',self.trials,n)
                #create clip file name
                clip_name='Rx'+str(n+1)+'_'+trial['Filename']+'.wav'
                
                try:
                    #attempt to get channels from data
                    rec_chans=trial['channels']
                except KeyError:
                    #fall back to only one channel
                    rec_chans=('rx_voice')

                #check if we skip audio loading/intelligibility estimation
                if(not (self.intell_est=='none')):
                    new_dat=self.process_audio(
                            os.path.join(audio_path,clip_name),
                            rec_chans
                            )
                
                #default, take data from csv
                merged_dat=trial
                
                if(self.intell_est=='trial'):
                    #overwrite new data with old and merge
                    merged_dat={**trial, **new_dat}
                    #save success
                    success.append(new_dat['Intelligibility'])
                else:
                    #make audio channels correct
                    merged_dat['channels']=chans_to_string(trial['channels'])
                    
                    if(self.intell_est=='aggregate'):
                        speech.append(new_dat['voice'])
                        clip_num.append(new_dat['wnum'])
                    else:
                        #take success from original data
                        success.append(trial['Intelligibility'])

                #write line with new data
                f_out.write(dat_format.format(**merged_dat))                

            if(not (self.intell_est=='aggregate')):
                phi_hat=abcmrt.guess_correction(np.mean(success))
            else:
                phi_hat,success=abcmrt.process(speech,clip_num)
                
            return phi_hat