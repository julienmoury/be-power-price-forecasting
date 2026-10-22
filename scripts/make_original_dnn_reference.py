"""Run the paper's ORIGINAL DNN on a few BE test days and save its forecasts to
tests/reference/original_dnn_reference.csv (reference for scripts/check_dnn_port.py).

The original module is executed with the mechanical Keras 3 fixes only (``learning_rate``
instead of ``lr``, no ``batch_input_shape`` on hidden layers) and the seeding of the port:
numpy seeded with the published ``seed`` before the validation draw, and
``keras.utils.set_random_seed`` (numpy, Python, TensorFlow) where the original calls
``np.random.seed``. TensorFlow runs with deterministic ops, one thread per process. The
number of epochs of each training is saved with the forecast. ``--samples`` only saves the
SHA-256 of the training, validation and test arrays of the same days
(tests/reference/original_dnn_samples.json, machine-independent, checked in CI).

Reproducibility (not part of the package or CI): a clone of the paper's code at commit
47d6e06 and a Python 3.12 environment with tensorflow, keras, pandas, scikit-learn and
statsmodels; results depend on the machine (float rounding of TensorFlow kernels), so the
port must be checked on the machine that produced the reference:

    EPFTOOLBOX_DIR=epftoolbox python scripts/make_original_dnn_reference.py [--jobs 8]
"""
import argparse, os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EPF = Path(os.environ.get("EPFTOOLBOX_DIR", "epftoolbox"))
OUT = REPO / 'tests' / 'reference' / 'original_dnn_reference.csv'
DNNS = {'SF': (1, 0), 'SF_DA': (1, 1), 'SF_SF': (2, 0), 'SF_SF_DA': (2, 1)}
DAYS = [0, 400, 727]  # days after 2015-01-04


def original():
    """Namespace of the original _dnn.py (with the fixes above) and the BE dataset."""
    import numpy as np, pandas as pd
    S = str(EPF / 'epftoolbox') + '/'
    ns = {}; exec(open(S + 'data/_wrangling.py').read(), ns)
    src = open(S + 'models/_dnn.py').read()
    seed = "int(self.best_hyperparameters['seed'])"
    for a, b in [('from epftoolbox.evaluation import MAE, sMAPE', ''),
                 ('from epftoolbox.data import scaling', ''), ('from epftoolbox.data import read_data', ''),
                 ('(lr=lr,', '(learning_rate=lr,'), ('batch_input_shape=inputShape,', ''),
                 (f'np.random.seed({seed})', f'kr.utils.set_random_seed({seed})'),
                 ('        Xtrain, Ytrain, Xval, Yval, Xtest, _, _ = \\',
                  f'        np.random.seed({seed})\n        Xtrain, Ytrain, Xval, Yval, Xtest, _, _ = \\'),
                 ('if countNoImprovement >= self.epochs_early_stopping:',
                  'self.n_epochs = epoch + 1\n            if countNoImprovement >= self.epochs_early_stopping:')]:
        assert a in src, a
        src = src.replace(a, b)
    ns2 = {'scaling': ns['scaling'], 'MAE': lambda p_real, p_pred: np.mean(np.abs(p_real - p_pred)),
           'sMAPE': None, 'read_data': None}
    exec(src, ns2)
    df = pd.read_csv(REPO / 'data' / 'raw' / 'BE.csv', index_col=0, parse_dates=True)
    df.columns = ['Price', 'Exogenous 1', 'Exogenous 2']
    return ns2, df


def available(df, k):
    import numpy as np, pandas as pd
    date = pd.Timestamp('2015-01-04') + pd.Timedelta(days=k)
    data = df.loc[:date + pd.Timedelta(hours=23)].copy(); data.loc[date:, 'Price'] = np.nan
    return date, data


def run(job):
    name, k = job
    import numpy as np, tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.experimental.enable_op_determinism()
    ns2, df = original()
    date, data = available(df, k)
    sf, da = DNNS[name]
    model = ns2['DNN'](experiment_id=1, path_hyperparameter_folder=str(EPF / 'examples' / 'experimental_files'),
                       nlayers=2, dataset='BE', years_test=2, shuffle_train=sf, data_augmentation=da,
                       calibration_window=4)
    yp = np.ravel(model.recalibrate_and_forecast_next_day(data, date))
    return [name, str(date.date()), model.model.n_epochs] + list(yp)


def samples():
    """SHA-256 of the original training/validation/test arrays (no training; machine-free)."""
    import hashlib, json, numpy as np, pandas as pd
    ns2, df = original()
    out = {}
    for name, (sf, da) in DNNS.items():
        f = REPO / 'data' / 'raw' / 'dnn_hyperparameters_BE.json'
        hp = json.loads(f.read_text())[name]['hyperparameters']
        for k in DAYS:
            date, data = available(df, k)
            df_train = data.loc[:date - pd.Timedelta(hours=1)].loc[date - pd.Timedelta(hours=4 * 364 * 24):]
            np.random.seed(int(hp['seed']))
            arrays = ns2['_build_and_split_XYs'](dfTrain=df_train, features=hp, shuffle_train=True,
                                                dfTest=data.loc[date - pd.Timedelta(weeks=2):], date_test=date,
                                                data_augmentation=da, n_exogenous_inputs=2)[:5]
            out[f'{name} {date.date()}'] = {n: [list(a.shape), hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()]
                                           for n, a in zip(['Xtrain', 'Ytrain', 'Xval', 'Yval', 'Xtest'], arrays)}
    (OUT.parent / 'original_dnn_samples.json').write_text(json.dumps(out, indent=1) + '\n')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--jobs', type=int, default=os.cpu_count())
    p.add_argument('--samples', action='store_true', help='only the sample arrays (fast)')
    if p.parse_args().samples:
        samples(); raise SystemExit
    jobs = [(n, k) for n in sorted(DNNS, key=lambda n: 'DA' not in n) for k in DAYS]
    with ProcessPoolExecutor(p.parse_args().jobs) as pool:
        rows = list(pool.map(run, jobs))
    import pandas as pd
    out = pd.DataFrame(rows, columns=['dnn', 'date', 'epochs'] + [f'h{h}' for h in range(24)])
    out.to_csv(OUT, index=False, float_format='%.10g')
    print(out.iloc[:, :6])
