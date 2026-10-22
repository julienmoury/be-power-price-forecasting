"""Run the paper's ORIGINAL LEAR under scikit-learn 0.23.2 on a few BE test days and
save its forecasts to tests/reference/original_lear_reference.csv.

Reproducibility (not part of the package or CI): needs a clone of the paper's code at
commit 47d6e06 and a Python 3.8 environment with scikit-learn==0.23.2, numpy==1.19.5,
pandas==1.1.5, scipy==1.5.4, statsmodels==0.12.1, matplotlib==3.3.4 (e.g. with uv):

    # the paper's code, checked out at commit 47d6e06 in ./epftoolbox
    uv venv -p 3.8 legacy && uv pip install -p legacy/bin/python <the pins above>
    EPFTOOLBOX_DIR=epftoolbox legacy/bin/python scripts/make_original_reference.py

The original modules are executed as-is (only their `from epftoolbox ...` imports are
resolved by hand, to avoid importing the package's TensorFlow dependencies).
"""
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EPF = Path(os.environ.get("EPFTOOLBOX_DIR", "epftoolbox"))
import numpy as np, pandas as pd, warnings
warnings.filterwarnings('ignore')
S=str(EPF / 'epftoolbox') + '/'
ns={}; exec(open(S+'data/_wrangling.py').read(), ns)
src=open(S+'models/_lear.py').read()
for l in ['from epftoolbox.data import scaling','from epftoolbox.data import read_data','from epftoolbox.evaluation import MAE, sMAPE']: src=src.replace(l,'')
ns2={'scaling':ns['scaling']}; exec(src, ns2)
df=pd.read_csv(REPO / 'data' / 'raw' / 'BE.csv',index_col=0,parse_dates=True); df.columns=['Price','Exogenous 1','Exogenous 2']
rows=[]
for cw in [56,84,1092,1456]:
  for k in [0,1,2,100,400,727]:
    date=pd.Timestamp('2015-01-04')+pd.Timedelta(days=k)
    data=df.loc[:date+pd.Timedelta(hours=23)].copy(); data.loc[date:,'Price']=np.nan
    p=ns2['LEAR'](cw).recalibrate_and_forecast_next_day(data,cw,date)[0]
    rows.append([cw,str(date.date())]+list(p))
out=pd.DataFrame(rows,columns=['calibration_window','date']+[f'h{h}' for h in range(24)])
out.to_csv(REPO / 'tests' / 'reference' / 'original_lear_reference.csv',index=False,float_format='%.10g')
print(out.iloc[:,:5])
