#!/usr/bin/env python

import argparse
import mcvqoe.gui
import mcvqoe.hardware

import mcvqoe.intelligibility as intell

def main():
    #---------------------------[Create Test object]---------------------------

    #create object here to use default values for arguments
    test_obj=intell.measure()
    #set end notes function
    test_obj.get_post_notes=mcvqoe.gui.post_test
            
    #-------------------------[Create audio interface]-------------------------
    ap=mcvqoe.hardware.AudioPlayer()
    test_obj.audio_interface=ap

    #-----------------------[Setup ArgumentParser object]-----------------------

    parser = argparse.ArgumentParser(
        description=__doc__)
    parser.add_argument(
                        '-a', '--audio-files', default=[],action="extend", nargs="+", type=str,metavar='FILENAME',
                        help='Path to audio files to use for test. Cutpoint files must also be present')
    parser.add_argument(
                        '-f', '--audio-path', default=test_obj.audio_path, type=str,
                        help='Path to look for audio files in. All audio file paths are relative to this unless they are absolute')
    parser.add_argument('-t', '--trials', type=int, default=test_obj.trials,metavar='T',
                        help='Number of trials to use for test. Defaults to %(default)d')
    parser.add_argument("-r", "--radioport", default="",metavar='PORT',
                        help="Port to use for radio interface. Defaults to the first"+
                        " port where a radio interface is detected")
    parser.add_argument('-b', '--blocksize', type=int, default=ap.blocksize,metavar='SZ',
                        help='Block size for transmitting audio (default: %(default)d)')
    parser.add_argument('-q', '--buffersize', type=int, default=ap.buffersize,metavar='SZ',
                        help='Number of blocks used for buffering audio (default: %(default)d)')
    parser.add_argument('-p', '--overplay', type=float, default=ap.overplay,metavar='DUR',
                        help='The number of seconds to play silence after the audio is complete'+
                        '. This allows for all of the audio to be recorded when there is delay'+
                        ' in the system')
    parser.add_argument('--trial-intell-est', default=test_obj.intell_est,dest='intell_est',action='store_const',const='trial',
                        help='Compute intelligibility estimation for audio at end of each trial')
    parser.add_argument('--aggregate-intell-est',dest='intell_est',action='store_const',const='aggregate',
                        help='Compute intelligibility on audio after test is complete')
    parser.add_argument('--no-intell-est',dest='intell_est',action='store_const',const='none',
                        help='don\'t compute intelligibility for audio')
    parser.add_argument('-o', '--outdir', default='', metavar='DIR',
                        help='Directory that is added to the output path for all files')
    parser.add_argument('-w', '--PTTWait', type=float, default=test_obj.ptt_wait, metavar='T',dest='ptt_wait',
                        help='Time to wait between pushing PTT and playing audio')
    parser.add_argument('-g', '--PTTGap', type=float, default=test_obj.ptt_gap, metavar='GAP',dest='ptt_gap',
                        help='Time to pause between trials')
    parser.add_argument('-F','--full-audio-dir',dest='full_audio_dir',action='store_true',default=False,
                        help='ignore --audioFiles and use all files in --audioPath')
    parser.add_argument('--no-full-audio-dir',dest='full_audio_dir',action='store_false',
                        help='use --audioFiles to determine which audio clips to read')
    parser.add_argument('--no-save-tx-audio', dest='save_tx_audio',
                        action='store_false',
                        help='Don\'t save transmit audio in wav directory')
    parser.add_argument('--save-audio', dest='save_audio', action='store_true',
                        help='Save audio in the wav directory')
    parser.add_argument('--no-save-audio', dest='save_audio', action='store_false',
                        help='Don\'t save audio in the wav directory, implies'+
                        '--no-save-tx-audio')
                                                
                        
    #-----------------------------[Parse arguments]-----------------------------

    args = parser.parse_args()
    
    #set object properties that exist
    for k,v in vars(args).items():
        if hasattr(test_obj,k):
            setattr(test_obj,k,v)
    
    #---------------------[Set audio interface properties]---------------------
    test_obj.audio_interface.blocksize=args.blocksize
    test_obj.audio_interface.buffersize=args.buffersize
    test_obj.audio_interface.overplay=args.overplay
    
    #set correct audio channels
    test_obj.audio_interface.playback_chans={'tx_voice':0}
    test_obj.audio_interface.rec_chans={'rx_voice':0}
    
    #---------------------------[Open RadioInterface]---------------------------
    
    with mcvqoe.hardware.RadioInterface(args.radioport) as test_obj.ri:
                                                    
        #------------------------------[Get test info]------------------------------
        test_obj.info=mcvqoe.gui.pretest(args.outdir,
                    check_function=lambda : mcvqoe.hardware.single_play(
                                                    test_obj.ri,test_obj.audio_interface,
                                                    ptt_wait=test_obj.ptt_wait))
        #------------------------------[Run Test]------------------------------
        intell_est=test_obj.run()
    
    print(f'Intelligibility estimate = {intell_est}')    
    print(f'Test complete, data saved in \'{test_obj.data_filename}\'')


# %%---------------------------------[main]-----------------------------------
if __name__ == "__main__":
    main()
