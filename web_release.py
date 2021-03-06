# -*- coding: utf-8 -*-
"""
Created on Fri Feb 03 15:12:32 2017

@author: MAJV
"""

import pandas as pd
import requests
import numpy as np
from datetime import datetime, timedelta, time

#import querySenslopeDb as q

def RoundTime(date_time):
    # rounds time to 4/8/12 AM/PM
    time_hour = int(date_time.strftime('%H'))

    quotient = time_hour / 4
    if quotient == 5:
        date_time = datetime.combine(date_time.date() + timedelta(1), time(0,0,0))
    else:
        date_time = datetime.combine(date_time.date(), time((quotient+1)*4,0,0))
            
    return date_time

def release_time(df, ts):
    if df['release_time'].values[0] < time(20, 0):
        df['ts_release'] = df['release_time'].apply(lambda x: datetime.combine(ts.date()+timedelta(1), x))
    else:
        df['ts_release'] = df['release_time'].apply(lambda x: datetime.combine(ts.date(), x))
    return df

def target_time(df, release_ext):
    ts = pd.to_datetime(df['data_timestamp'].values[0]).time()
    if ts >= time(11, 30) and ts < time(12, 0):
        df['ts_target'] = df['data_timestamp'].apply(lambda x: RoundTime(x) + timedelta(hours=(5+release_ext)/60.))
    else:
        df['ts_target'] = df['data_timestamp'].apply(lambda x: RoundTime(x) + timedelta(hours=release_ext/60.))
    return df

def feedback(df, AllReleases, MonTeam):
    ts = pd.to_datetime(df['ts'].values[0])
    ts_mon = ts + timedelta(hours=7.5)
    try:
        mon_end = ts + timedelta(hours=20)
        mon_start = mon_end - timedelta(0.5)
    
        CurrReleases = AllReleases[(AllReleases.data_timestamp >= mon_start)&(AllReleases.data_timestamp < mon_end)]
        
        if ts.time() == time(0, 0):
            CurrReleases['ts_release'] = CurrReleases['release_time'].apply(lambda x: datetime.combine(ts.date(), x))
        else:
            CurrReleasesTS = CurrReleases.groupby('release_time')
            CurrReleases = CurrReleasesTS.apply(release_time, ts=ts)
        
        CurrSiteMon = len(set(CurrReleases.site_id))
        if CurrSiteMon > 15:
            if CurrSiteMon != len(CurrReleases[CurrReleases.reporter_id_mt.isin(MonTeam)]):
                CurrReleases = CurrReleases[~CurrReleases.reporter_id_mt.isin(MonTeam)]
                CurrSiteMon = len(set(CurrReleases.site_id))
#            else:
#                CurrReleases
#                CurrSiteMon
    
        if CurrSiteMon <= 5:
            release_ext = 0
        else:
            release_ext = CurrSiteMon - 5
        
        CurrReleasesDataTS = CurrReleases.groupby('data_timestamp')
        CurrReleases = CurrReleasesDataTS.apply(target_time, release_ext=release_ext)
        CurrReleases['time_diff'] = CurrReleases['ts_release'] - CurrReleases['ts_target']
        CurrReleases['time_diff'] = CurrReleases['time_diff'].apply(lambda x: x / np.timedelta64(1,'D'))
        
        Releases = pd.DataFrame({'ts': [ts_mon], 'num_site': [CurrSiteMon], 'MT': [sorted(set(CurrReleases.reporter_id_mt))], 'CT': [sorted(set(CurrReleases.reporter_id_ct))], 'delay_release': [max(CurrReleases['time_diff'].values) * 24 * 60]})
    except:
        Releases = pd.DataFrame({'ts': [ts_mon], 'num_site': ['no monitored sites'], 'MT': ['-'], 'CT': ['-'], 'delay_release': ['-']})
    
    return Releases

def main(start='', end=''):
    
    if start == '' and end == '':
        ts_now = datetime.now()
        if ts_now.time() >= time(12,0):
            end = datetime.combine(ts_now.date(), time(12, 0))
            start = end
        else:
            end = pd.to_datetime(ts_now.date())
            start = end
    elif start == '' or end == '':
        try:
            start = pd.to_datetime(pd.to_datetime(start).date())
            end = start
        except:
            end = pd.to_datetime(pd.to_datetime(end).date())
            start = end
    else:
        start = pd.to_datetime(pd.to_datetime(start).date())
        end = pd.to_datetime(pd.to_datetime(end).date())
    date_range = pd.date_range(start=start, end=end, freq='12H')
    df = pd.DataFrame({'ts':date_range})
    dfts = df.groupby('ts')
    
    r = requests.get('http://dewslandslide.com/api2/getAllReleases')    
    AllReleases = pd.DataFrame(r.json())
    AllReleases = AllReleases[~AllReleases.internal_alert_level.isin(['A0', 'ND'])]
    AllReleases['data_timestamp'] = AllReleases['data_timestamp'].apply(lambda x: pd.to_datetime(x))
    AllReleases['release_time'] = AllReleases['release_time'].apply(lambda x: pd.to_datetime(x).time())
    AllReleases['reporter_id_mt'] = AllReleases['reporter_id_mt'].apply(lambda x: int(x))
    AllReleases['reporter_id_ct'] = AllReleases['reporter_id_ct'].apply(lambda x: int(x))
    
    r = requests.get('http://dewslandslide.com/api2/getStaff')    
    StaffID = pd.DataFrame(r.json())
    StaffID['id'] = StaffID['id'].apply(lambda x: int(x))
    
    MonTeam = StaffID[StaffID.last_name.isin(['Viernes', 'Bontia', 'Lorenzo'])]['id'].values
        
    Releases = dfts.apply(feedback, AllReleases=AllReleases, MonTeam=MonTeam)
    Releases = Releases[Releases.delay_release != '-']
    Releases = Releases.sort_values('delay_release')
    
    return Releases.reset_index(drop=True), AllReleases, StaffID
    
if __name__ == '__main__':
    Releases, AllReleases, StaffID = main(start = '2017-01-01', end = '2017-04-03')
    print '\n\n'
    print 'Average Delay =', np.average(list(Releases[Releases.delay_release > 0].delay_release)), 'mins'
    print 'Maximum Delay =', max(list(Releases[Releases.delay_release > 0].delay_release)), 'mins'
    print '\n\n'
#    temp = AllReleases[(AllReleases.reporter_id_ct.isin([27]))&(AllReleases.reporter_id_mt.isin([9]))]
#    temp[temp.data_timestamp >= pd.to_datetime('2017-01-01')]