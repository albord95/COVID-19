import pandas as pd
import lsqfit
import gvar
import numpy as np
import pickle
import namedate
import fitlsqdefs
import tqdm
import sys
import os

from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()

# Read command line.
assert len(sys.argv) >= 2
prior_option = sys.argv[1]
assert prior_option in ('weakpop', 'truepop')
regions = sys.argv[2:]

# Read region data.
data = pd.read_csv(
    '../pcm-dpc-COVID-19/dati-regioni/dpc-covid19-ita-regioni.csv',
    parse_dates=['data'],
    infer_datetime_format=True
)

def rounddate(date):
    # removes hours, minutes, etc.
    return pd.Timestamp(year=date.year, month=date.month, day=date.day)

# Get date to be used.
lastdateindata = data['data'].max()
if os.getenv('LASTDATE'):
    lastdate = pd.Timestamp(os.getenv('LASTDATE'))
    ok = rounddate(lastdateindata) >= lastdate
    lastdate += pd.Timedelta(23, 'H')
else:
    lastdate = pd.Timestamp.today()
    ok = lastdate - lastdateindata < pd.Timedelta(1, 'D') + pd.Timedelta(1, 'H')
if not ok:
    raise ValueError(f'Data is not update, last date in data is {lastdateindata}, requested date is {lastdate}')
data = data[data['data'] <= lastdate]
print(f'last date used is {data["data"].max()}')

# Read additional csv to know the population of each region.
regioninfo = pd.read_csv('../shared_data/dati_regioni.csv')

# This dictionary will be saved on file at the end.
pickle_dict = dict(prior_option=prior_option)

# Group data by region.
gdata = data.groupby('denominazione_regione')
# (use the name to group because problems with south tirol)

print('Iterating over regions...')
for region in tqdm.tqdm(regions if regions else data['denominazione_regione'].unique()):
    table = gdata.get_group(region)

    # Times.
    times = fitlsqdefs.time_to_number(table['data'])
    time_zero = times[0]
    times -= time_zero

    # Data.
    I_data = table['totale_positivi'].values
    H_data = table['dimessi_guariti'].values
    D_data = table['deceduti'].values
    I_data = fitlsqdefs.make_poisson_data(I_data)
    H_data = fitlsqdefs.make_poisson_data(H_data)
    D_data = fitlsqdefs.make_poisson_data(D_data)
    fitdata = gvar.BufferDict(I=I_data, D=D_data, H=H_data)
    
    # Population prior.
    totpop = regioninfo[regioninfo['denominazione_regione'] == region]['popolazione'].values[0]
    min_pop = np.max(gvar.mean(D_data + I_data + H_data))
    _totpop = totpop - min_pop
    if prior_option == 'weakpop':
        popprior = gvar.gvar(np.log(_totpop), np.log(20))
    elif prior_option == 'truepop':
        popprior = gvar.log(gvar.gvar(_totpop, 10))

    # Prior.
    prior = gvar.BufferDict({
        'log(R0)': gvar.gvar(np.log(1), np.log(10)),
        'log(gamma)': gvar.gvar(np.log(1), np.log(10)),
        'log(yupsilon)': gvar.gvar(np.log(1), np.log(10)),
        'log(_population)': popprior,
        'log(I0_pop)': gvar.gvar(np.log(10), np.log(100))
    })

    # Run fit.
    args = dict(times=times, min_pop=min_pop)
    fit = lsqfit.nonlinear_fit(data=(args, fitdata), prior=prior, fcn=fitlsqdefs.fcn)

    # Save results.
    pickle_dict[region] = dict(
        y=fitdata,
        p=fit.palt,
        prior=prior,
        log=fit.format(maxline=True),
        chi2=fit.chi2,
        dof=fit.dof,
        pvalue=fit.Q,
        table=table,
        min_pop=min_pop,
        time_zero=time_zero,
    )

# Save results on file.
pickle_file = 'fitlsq_' + namedate.file_timestamp() + '.pickle'
print(f'Saving to {pickle_file}...')
pickle.dump(pickle_dict, open(pickle_file, 'wb'))
