# -*- coding: utf-8 -*-
"""
Created on Thu Oct  7 12:47:39 2021

@author: jkp4
"""
import argparse
import os
import re
import warnings

import plotly.graph_objects as go
import numpy as np
import pandas as pd
import plotly.express as px

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
            self.test_names.append(os.path.basename(fname))
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
        
        # Check for kwargs
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise TypeError(f"{k} is not a valid keyword argument")
        
        self.mean, self.ci = self.eval()

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
        with np.errstate(divide='raise'):
            try:
                self.ci, _ = mcvqoe.math.bootstrap_ci(self.data['Intelligibility'],
                                               p=p,
                                               method=method,
                                               )
            except FloatingPointError:
                warnings.warn(
                    'Floating point error encountered in bootstrap-t'
                     +'uncertainty estimate. Using percentile bootstrap'
                     +'instead.'
                    )
                self.ci, _ = mcvqoe.math.bootstrap_ci(
                    self.data['Intelligibility'],
                    p=p,
                    method='percentile'
                    )
        
        return self.mean, self.ci
    
    def histogram(self, test_name=None, talkers=None,
                  title='Histogram of intelligibility values'):
        df = self.data
        # Filter by session name if given
        if test_name is not None:
            df_filt = pd.DataFrame()
            if not isinstance(test_name, list):
                test_name = [test_name]
            for name in test_name:
                df_filt = df_filt.append(df[df['name'] == name])
            df = df_filt
        # Filter by talkers if given
        if talkers is not None:
            df_filt = pd.DataFrame()
            if isinstance(talkers, str):
                talkers = [talkers]
            for talker in talkers:
                ix = [talker in x for x in df['Filename']]
                df_filt = df_filt.append(df[ix])
            df = df_filt
        fig = go.Figure()
        fig.add_trace(
            go.Histogram(
                x=df['Intelligibility'],
                # color='name',
                xbins={
                    'start': -1/32,
                    'end': 1+1/32,
                    'size': 1/16,
                    }
                )
            )
        fig.add_vline(x=self.mean, line_width=3, line_dash="dash")
        fig.add_vline(x=self.ci[0], line_width=2, line_dash="dot")
        fig.add_vline(x=self.ci[1], line_width=2, line_dash="dot")
        
        fig.add_annotation(xref='x', yref='paper',
                            x=self.mean, y=0.9,
                            text="Mean and confidence interval",
                            showarrow=True,
                            xanchor='right',
                            )

        fig.update_layout(            
            legend=dict(
                yanchor="bottom",
                y=0.99,
                xanchor="left",
                x=0.01,
                ),
            title=title,
            xaxis_title='Intelligibility',
            yaxis_title='count',
        )
        return fig
    
    def plot(self, test_name=None, talkers=None, x=None,
             title='Scatter plot of intelligibility scores'):
        df = self.data
        # Filter by session name if given
        # Filter by session name if given
        if test_name is not None:
            df_filt = pd.DataFrame()
            if not isinstance(test_name, list):
                test_name = [test_name]
            for name in test_name:
                df_filt = df_filt.append(df[df['name'] == name])
            df = df_filt
        # Filter by talkers if given
        if talkers is not None:
            df_filt = pd.DataFrame()
            if isinstance(talkers, str):
                talkers = [talkers]
            for talker in talkers:
                ix = [talker in x for x in df['Filename']]
                df_sub = df[ix]
                df_sub['Talker'] = talker
                df_filt = df_filt.append(df_sub)
                
            df = df_filt
        else:
            # TODO: Consider just dropping this into init/data load, might make things easier
            pattern = re.compile(r'([FM]\d)(?:_b\d{1,2}_w\d)')
            talkers = set()
            talker_v = []
            for index, row in df.iterrows():
                res = pattern.search(row['Filename'])
                if res is not None:
                    talker = res.groups()[0]
                    talkers.add(talker)
                    talker_v.append(talker)
                else:
                    talker_v.append('NA')
            df['Talker'] = talker_v        
            

        fig = px.scatter(df, x=x, y='Intelligibility',
                          color='name',
                          symbol='Talker',
                          hover_name='Filename',
                          title=title,
                          labels={
                              'index': 'Trial Number',
                              },
                          )
        fig.update_layout(legend=dict(
            yanchor="bottom",
            y=0.99,
            xanchor="left",
            x=0.01,
            ),
            legend_orientation="h",
            showlegend=False,
        )
        return fig


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
