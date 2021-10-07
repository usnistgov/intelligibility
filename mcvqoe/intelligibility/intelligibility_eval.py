# -*- coding: utf-8 -*-
"""
Created on Thu Oct  7 12:47:39 2021

@author: jkp4
"""
import argparse
import os
import warnings

import numpy as np
import pandas as pd

import mcvqoe.math


# Main class for evaluating
class evaluate():
    """
    Class to evaluate intelligibility.

    Parameters
    ----------
    test_names : str or list of str
        File names of intelligibility tests.

    test_path : str
        Full path to the directory containing the sessions within a test.

    use_reprocess : bool
        Whether or not to use reprocessed data, if it exists.

    Attributes
    ----------
    full_paths : list of str
        Full file paths to the sessions.

    mean : float
        Average of all the intelligibility data.

    ci : numpy array
        Lower and upper confidence bound on the mean.

    Methods
    -------
    eval()
        Determine the intelligibility of a test.

    See Also
    --------
        mcvqoe.intelligibility.measure : 
            Measurement class for generating intelligibility data.
    """

    def __init__(self,
                 test_names,
                 test_path='',
                 use_reprocess=False,
                 **kwargs):
        # If only one test, make a list for iterating
        if isinstance(test_names, str):
            test_names = [test_names]
        # TODO Make this more like psud
        # Initialize full paths attribute
        self.full_paths = []
        self.test_names = []
        for test_name in test_names:
            # split name to get path and name
            # if it's just a name all goes into name
            dat_path, name = os.path.split(test_name)
            
            # If no extension given use csv
            fname, fext = os.path.splitext(test_name)
            self.test_names.append(fname)
            # check if a path was given to a .csv file
            if not dat_path and not fext == '.csv':
                # generate using test_path
                dat_path = os.path.join(test_path, 'csv')
                dat_file = os.path.join(dat_path, fname +'.csv')
            else:
                dat_file = test_name

            self.full_paths.append(dat_file)

        self.data = None
        self.load_data()
        
        self.mean = None
        self.ci = None
        
        # Check for kwargs
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise TypeError(f"{k} is not a valid keyword argument")

    def load_data(self):
        """
        Load data stored in test_names and test_paths, stores it in self.data
        """
        data = pd.DataFrame()
        for fpath in self.full_paths:
            # Load data
            test = pd.read_csv(fpath)
            # Extract test name
            _, tname = os.path.split(fpath)
            name, ext = os.path.splitext(tname)
            # Store testname
            test['name'] = name
            data = data.append(test)
        # Ensure that tests has unique row index
        nrow, _ = data.shape
        data.index = np.arange(nrow)
        
        self.data = data
        
    
    def eval(self, p=0.95, method='t'):
        """
        Evaluate mouth to ear test data provided.

        Returns
        -------
        float
            Mean of test data.
        numpy array
            Upper and lower confidence bound on the mean of the test data.

        """
        self.mean = np.mean(self.data['Intelligibility'])
        self.ci, _ = mcvqoe.math.bootstrap_ci(self.data['Intelligibility'],
                                           p=p,
                                           method=method,
                                           )
        
        return self.mean, self.ci


# Main definition
def main():
    """
    Evaluate intelligibility with command line arguments.

    Returns
    -------
    None.

    """
    # Set up argument parser
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('test_names',
                        type=str,
                        nargs="+",
                        action="extend",
                        help=("Test names (same as name of folder for wav"
                              "files)"))
    parser.add_argument('-p', '--test-path',
                        default='',
                        type=str,
                        help=("Path where test data is stored. Must contain"
                              "wav and csv directories."))
    parser.add_argument('-n', '--no-reprocess',
                        default=True,
                        action="store_false",
                        help="Do not use reprocessed data if it exists.")

    
    args = parser.parse_args()
    t = evaluate(args.test_names, test_path=args.test_path,
                 use_reprocess=args.no_reprocess)

    res = t.eval()

    print(res)

    return(res)


if __name__ == "__main__":
    main()
