import pandas as pd


def overrule_winter(series, timespan=(12, 5), value=0):
    series = series.copy()

    series.loc[(series.index.month >= timespan[0]) | (series.index.month <= timespan[1])] = value

    return series
