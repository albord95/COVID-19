import pandas as pd
import gvar
from autograd import numpy as np
import autograd
import pickle
import tqdm
import sys
import lsqfitgp2 as lgp
from relu import relu
from scipy import optimize
from autograd.scipy import linalg

gvar.BufferDict.add_distribution('arctanh', gvar.tanh)

# Read command line.
regions = sys.argv[1:]
#regions = ['Abruzzo', 'Basilicata', 'Lombardia', 'Veneto']
labels = ['nuovi_positivi', 'nuovi_deceduti']

pcm_github_url = "https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/"
folder = "/dati-json/dpc-covid19-ita-regioni.json"
url = pcm_github_url + folder
data = pd.read_json(url, convert_dates=['data'])
if not regions:
    regions = data['denominazione_regione'].unique()

gdata = data.groupby('denominazione_regione')
# use the name to group because problems with south tirol

# This dictionary will be saved on file at the end.
pickle_dict = dict()

def time_to_number(times):
    try:
        times = pd.to_numeric(times).values
    except TypeError:
        pass
    times = np.array(times, dtype=float)
    times /= 1e9 * 60 * 60 * 24 # ns -> days
    return times

print('Iterating over regions...')
for region in tqdm.tqdm(regions):
    table = gdata.get_group(region)

    # Times for data.
    times = time_to_number(table['data'])
    time_zero = times[0]
    times -= time_zero

    # Times for prediction.
    lastdate = table['data'].max()
    dates_pred = pd.date_range(lastdate, periods=60, freq='1D')[1:]
    times_pred = time_to_number(dates_pred) - time_zero

    # Times for plot.
    firstdate = table['data'].min()
    dates_plot = pd.date_range(firstdate, dates_pred[-1], 600)
    times_plot = time_to_number(dates_plot) - time_zero
    
    # Data.
    data_list = []
    for label in labels:
        if label == 'nuovi_deceduti':
            # Adding 'nuovi_deceduti' column, first value added "manually"
            first_value = 0
            if region == 'Lombardia':
                first_value = 4
            other_values = np.diff(table['deceduti'].values)
            data_list.append([first_value] + list(other_values))
        else:
            data_list.append(table[label].values)
    data = np.stack(data_list)
    
    def makex(times, hyperparams):
        x = np.empty((len(labels), len(times)), dtype=[
            ('time', float),
            ('label', int)
        ])
        x['label'] = np.arange(len(labels)).reshape(-1, 1)
        x = lgp.StructuredArray(x)
        x['time'] = np.stack([times, times - hyperparams['delay']])
        return x
        
    def makegp(hyperparams):
        longscale = hyperparams['longscale']
        shortscale = hyperparams['shortscale']
        longvars = hyperparams['longvars']
        shortvars = hyperparams['shortvars']
        longcorr = hyperparams['longcorr']
        
        sigmax = np.array([[0, 1], [1, 0]])
        longcov = np.diag(longvars) + sigmax * longcorr * np.prod(np.sqrt(longvars))
        kernel = lgp.ExpQuad(scale=longscale, dim='time') * lgp.Categorical(cov=longcov, dim='label')
        kernel += lgp.ExpQuad(scale=shortscale, dim='time') * lgp.Cos(scale=shortscale / np.pi, dim='time') * lgp.Categorical(cov=np.diag(shortvars), dim='label')
        
        gp = lgp.GP(kernel)
        gp.addx(makex(times, hyperparams), 'data')
        
        return gp
    
    # Prior for hyperparameters.
    maxdata = np.max(data, axis=-1) ** 2
    hyperprior = {
        'log(longscale)': gvar.log(gvar.gvar(20, 7)),
        'log(shortscale)': gvar.log(gvar.gvar(2, 1)),
        'arctanh(longcorr)': gvar.arctanh(gvar.gvar(0, 1)),
        'delay': gvar.gvar(0, 10),
        'log(longvars)': gvar.log(gvar.gvar(maxdata, 2 * maxdata)),
        'log(shortvars)': gvar.log(gvar.gvar(maxdata, 2 * maxdata))
    }
    
    hyperparams = lgp.empbayes_fit(hyperprior, makegp, {'data': data})
    params = gvar.BufferDict(**{
        k: hyperparams[k] for k in [
            'longscale',
            'shortscale',
            'longcorr',
            'delay'
        ]
    }, **{
        f'longstd_{label}': gvar.sqrt(hyperparams['longvars'][i])
        for i, label in enumerate(labels)
    }, **{
        f'shortstd_{label}': gvar.sqrt(hyperparams['shortvars'][i])
        for i, label in enumerate(labels)
    })
    
    hpmean = gvar.mean(hyperparams)
    gp = makegp(hpmean)
    xpred = makex(times_pred, hpmean)
    gp.addx(xpred, 'pred')
    xplot = makex(times_plot, hpmean)
    gp.addx(xplot, 'plot')
    pred = gp.predfromdata({'data': data}, 'pred', keepcorr=False)
    plot = gp.predfromdata({'data': data}, 'plot', keepcorr=False)
    
    def tobufdict(uy):
        return gvar.BufferDict({
            label: uy[i]
            for i, label in enumerate(labels)
        })
    
    # Save results.
    pickle_dict[region] = dict(
        params=params,
        y=tobufdict(data),
        table=table,
        time_zero=time_zero,
        pred=tobufdict(pred),
        plot=tobufdict(plot),
        dates=dict(pred=dates_pred, plot=dates_plot)
    )
    
# Save results on file.
# pickle_file = 'fit_' + namedate.file_timestamp() + '.pickle'
pickle_file = 'fit2.pickle'
print(f'Saving to {pickle_file}...')
pickle.dump(pickle_dict, open(pickle_file, 'wb'))
