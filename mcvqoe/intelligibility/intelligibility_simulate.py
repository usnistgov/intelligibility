#!/usr/bin/env python

import argparse
import os.path
import mcvqoe.simulation
import mcvqoe.gui
import sys
import mcvqoe.hardware

import mcvqoe.intelligibility as intell
import numpy as np


def simulate(
             test_id=None,
             **kwargs,
             ):
    """
    Simulate intelligibility measurement.

    Returns
    -------
    None.

    """
    # ---------------------------[Create Test object]--------------------------

    # create sim object
    sim_obj = mcvqoe.simulation.QoEsim()

    # create object here to use default values for arguments
    test_obj = intell.measure()
    # set wait times to zero for simulation
    test_obj.ptt_wait = 0
    test_obj.ptt_gap = 0
    # don't save audio for simulation
    test_obj.save_tx_audio = False
    test_obj.save_audio = False
    # no need to pause
    test_obj.pause_trials = np.inf
    # only get test notes on error
    test_obj.get_post_notes = lambda : mcvqoe.gui.post_test(error_only=True)

    for k, v in kwargs.items():
        if hasattr(test_obj, k):
            setattr(test_obj, k, v)
        if hasattr(sim_obj, k):
            setattr(sim_obj, k, v)
    # set audioInterface to sim object
    test_obj.audio_interface = sim_obj
    # set radio interface object to sim object
    test_obj.ri = sim_obj

    # -----------------------------[Log Info]--------------------------
    test_obj.info['codec'] = sim_obj.channel_tech
    test_obj.info['codec-rate'] = sim_obj.channel_rate

    if test_id is not None:
        test_obj.info['test-ID'] = test_id

    test_obj.info['test_type'] = "simulation"
    test_obj.info['tx_dev'] = "none"
    test_obj.info['rx_dev'] = "none"

    # construct string for system name
    system = sim_obj.channel_tech
    if sim_obj.channel_rate is not None:
        system += ' at ' + str(sim_obj.channel_rate)
    test_obj.info['system'] = system

    test_obj.info['test_loc'] = "N/A"
    # --------------------------------[Run Test]------------------------------

    intell_est = test_obj.run()

    test_path = os.path.join(test_obj.outdir, "data")

    print(f"Test complete. Data stored in {test_path}")
    return intell_est, test_obj, sim_obj


def main():
    #---------------------------[Create Test object]---------------------------

    #create sim object
    sim_obj=mcvqoe.simulation.QoEsim()

    #create object here to use default values for arguments
    test_obj=intell.measure()
    #set wait times to zero for simulation
    test_obj.ptt_wait=0
    test_obj.ptt_gap=0
    #don't save audio for simulation
    test_obj.save_tx_audio=False
    test_obj.save_audio=False
    #no need to pause
    test_obj.pause_trials = np.inf
    #only get test notes on error
    test_obj.get_post_notes=lambda : mcvqoe.gui.post_test(error_only=True)
    
    #set audioInterface to sim object
    test_obj.audio_interface=sim_obj
    #set radio interface object to sim object
    test_obj.ri=sim_obj

    #-----------------------[Setup ArgumentParser object]-----------------------

    parser = argparse.ArgumentParser(
        description=__doc__)
    parser.add_argument('-t', '--trials', type=int, default=test_obj.trials,metavar='T',
                        help='Number of trials to use for test. Defaults to %(default)d')
    parser.add_argument('-p', '--overplay', type=float, default=sim_obj.overplay,metavar='DUR',
                        help='The number of seconds to play silence after the audio is complete'+
                        '. This allows for all of the audio to be recorded when there is delay'+
                        ' in the system')
    parser.add_argument('-o', '--outdir', default='', metavar='DIR',
                        help='Directory that is added to the output path for all files')
    parser.add_argument('-P','--use-probabilityiser', default=False,dest='use_probabilityiser',action='store_true',
                        help='Use probabilityiesr to make channel "flaky"')
    parser.add_argument('--no-use-probabilityiser',dest='use_probabilityiser',action='store_false',
                        help='don\'t use probabilityiesr')
    parser.add_argument('--P-a1',dest='P_a1',type=float,default=1,
                        help='P_a1 for probabilityiesr')
    parser.add_argument('--P-a2',dest='P_a2',type=float,default=1,
                        help='P_a2 for probabilityiesr')
    parser.add_argument('--P-r',dest='P_r',type=float,default=1,
                        help='P_r for probabilityiesr')
    parser.add_argument('--P-interval',dest='pInterval',type=float,default=1,
                        help='Time interval for probabilityiesr in seconds')
    parser.add_argument('-c','--channel-tech', default=sim_obj.channel_tech, metavar='TECH',dest='channel_tech',
                        help='Channel technology to simulate (default: %(default)s)')
    parser.add_argument('--channel-rate', default=sim_obj.channel_rate, metavar='RATE',dest='channel_rate',
                        help='Channel technology rate to simulate. Passing \'None\' will use the technology default. (default: %(default)s)')
    parser.add_argument('--channel-m2e', type=float, default=sim_obj.m2e_latency, metavar='L',dest='m2e_latency',
                        help='Channel mouth to ear latency, in seconds, to simulate. (default: %(default)s)')
 
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
            

    #-------------------------[Set simulation settings]-------------------------

    sim_obj.channel_tech=args.channel_tech
    
    sim_obj.overplay=args.overplay
    
    #set channel rate, check for None
    if(args.channel_rate=='None'):
        sim_obj.channel_rate=None
    else:
        sim_obj.channel_rate=args.channel_rate
        
    sim_obj.m2e_latency=args.m2e_latency
    
    #set correct channels    
    sim_obj.playback_chans={'tx_voice':0}
    sim_obj.rec_chans={'rx_voice':0}
        
    #------------------------------[Get test info]------------------------------
    
    gui=mcvqoe.gui.TestInfoGui(write_test_info=False)
    
    gui.chk_audio_function=lambda : mcvqoe.hardware.single_play(sim_obj,sim_obj,
                                                    playback=True,
                                                    ptt_wait=test_obj.ptt_wait)

    #construct string for system name
    system=sim_obj.channel_tech
    if(sim_obj.channel_rate is not None):
        system+=' at '+str(sim_obj.channel_rate)

    gui.info_in['test_type'] = "simulation"
    gui.info_in['tx_dev'] = "none"
    gui.info_in['rx_dev'] = "none"
    gui.info_in['system'] = system
    gui.info_in['test_loc'] = "N/A"
    test_obj.info=gui.show()

    #check if the user canceled
    if(test_obj.info is None):
        print(f"\n\tExited by user")
        sys.exit(1)
    
    #---------------------------[add probabilityiesr]---------------------------
    
    if(args.use_probabilityiser):
        #TODO: Move this outside of if so can be used to validate results
        prob=mcvqoe.simulation.PBI()
        
        prob.P_a1=args.P_a1
        prob.P_a2=args.P_a2
        prob.P_r=args.P_r
        prob.interval=args.pInterval
        
        
        test_obj.info['PBI P_a1']=str(args.P_a1)
        test_obj.info['PBI P_a2']=str(args.P_a2)
        test_obj.info['PBI P_r'] =str(args.P_r)
        test_obj.info['PBI interval']=str(args.pInterval)
        
        sim_obj.pre_impairment=prob.process_audio
    
    
    #--------------------------------[Run Test]--------------------------------
    intell_file = test_obj.run()
    eval_obj = intell.evaluate(intell_file)
    intell_est, ci = eval_obj.eval()
    print(f'Intelligibility estimate and confidenc tnterval = {intell_est}, {ci}')
    print(f'Test complete, data saved in \'{intell_file}\'')
    

#-----------------------------[main function]-----------------------------
if __name__ == "__main__":
    main()