"""Evaluate the published BE forecasts with the ORIGINAL epftoolbox metric code and save
the values to tests/reference/original_metrics_reference.json.

Reproducibility (not part of the package or CI): needs a clone of jeslago/epftoolbox at
commit 47d6e06 and a Python 3.8 environment with scikit-learn==0.23.2, numpy==1.19.5,
pandas==1.1.5, scipy==1.5.4, statsmodels==0.12.1, matplotlib==3.3.4 (e.g. with uv):

    git clone https://github.com/jeslago/epftoolbox && git -C epftoolbox checkout 47d6e06
    uv venv -p 3.8 legacy && uv pip install -p legacy/bin/python <the pins above>
    EPFTOOLBOX_DIR=epftoolbox legacy/bin/python scripts/make_original_metrics_reference.py

The original modules are executed as-is (only their `from epftoolbox ...` imports are
resolved by hand, to avoid importing the package's TensorFlow dependencies).
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EPF = Path(os.environ.get("EPFTOOLBOX_DIR", "epftoolbox"))
import json, numpy as np, pandas as pd
S=str(EPF / 'epftoolbox' / 'evaluation') + '/'
ns={}
exec(open(S+'_ancillary_functions.py').read(), ns)
for f in ['_mae.py','_smape.py','_rmae.py','_dm.py']:
    src=open(S+f).read()
    src='\n'.join(l for l in src.splitlines() if not l.startswith('from epftoolbox'))
    exec(src, ns)
f=pd.read_csv(REPO / 'tests' / 'reference' / 'Forecasts_BE_DNN_LEAR_ensembles.csv',index_col=0,parse_dates=True)
real=f[['Real price']]
out={}
for c in ['LEAR 56','LEAR 84','LEAR 1092','LEAR 1456','LEAR Ensemble','DNN Ensemble']:
    p=f[[c]].rename(columns={c:'Real price'})
    out[c]={'MAE':ns['MAE'](real,p),'sMAPE':ns['sMAPE'](real,p),
            'rMAE':ns['rMAE'](real,p),'rMAE_W':ns['rMAE'](real,p,m='W'),'rMAE_D':ns['rMAE'](real,p,m='D')}
R=real.values.reshape(-1,24)
uni=ns['DM'](R,f['LEAR Ensemble'].values.reshape(-1,24),f['DNN Ensemble'].values.reshape(-1,24),norm=1,version='univariate')
multi=ns['DM'](R,f['LEAR Ensemble'].values.reshape(-1,24),f['DNN Ensemble'].values.reshape(-1,24),norm=1,version='multivariate')
multi2=ns['DM'](R,f['LEAR 56'].values.reshape(-1,24),f['LEAR Ensemble'].values.reshape(-1,24),norm=2,version='multivariate')
out['DM_LEARens_vs_DNNens_univariate_norm1']=list(map(float,uni))
out['DM_LEARens_vs_DNNens_multivariate_norm1']=float(multi)
out['DM_LEAR56_vs_LEARens_multivariate_norm2']=float(multi2)
json.dump(out,open(REPO / 'tests' / 'reference' / 'original_metrics_reference.json','w'),indent=1)
print(json.dumps({k:v for k,v in out.items() if 'univariate' not in k},indent=1))
