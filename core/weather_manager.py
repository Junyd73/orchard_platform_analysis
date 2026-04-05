import requests
import math
import os
from datetime import datetime


DEFAULT_WEATHER_API_KEY = os.getenv(
    "ORCHARD_WEATHER_API_KEY",
    "e1f011a6b33d69b778859ddb1c2b871e8e93024282033ed25f368f047dededb7",
)


class WeatherManager:
    def __init__(self, service_key=None):
        # 키는 core에서 일원화 관리(인자 미전달 시 기본키/환경변수 사용)
        self.service_key = service_key or DEFAULT_WEATHER_API_KEY
        self.base_url = "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

    def get_weather(self, nx, ny, work_dt, lat, lon):
        try:
            target_date = work_dt.replace("-", "")
            params = {
                'serviceKey': self.service_key,
                'pageNo': '1', 'numOfRows': '1000', 'dataType': 'JSON',
                'base_date': target_date, 'base_time': '0200',
                'nx': nx, 'ny': ny
            }
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            if data['response']['header']['resultCode'] != '00': return None
            items = data['response']['body']['items']['item']
            sr_str, ss_str, sr_h, ss_h = self.calculate_sun_times_korea(lat, lon, work_dt)
            wsd_list = []
            sky_list = []
            res = {
                'temp_max': -99.0, 'temp_min': 99.0, 'humidity': 0,
                'precip': 0.0, 'wind_max': 0.0, 'wind_min': 99.0,
                'sun_rise': sr_str, 'sun_set': ss_str, 'sunshine_hr': 0.0,
                'weather_cd': 'WT010100', 'raw_info': ""
            }
            for item in items:
                if item['fcstDate'] != target_date: continue
                cat, val = item['category'], item['fcstValue']
                if cat == 'WSD': wsd_list.append(float(val))
                if cat == 'SKY': sky_list.append(val)
                if cat == 'TMX': res['temp_max'] = float(val)
                if cat == 'TMN': res['temp_min'] = float(val)
                if cat == 'TMP':
                    v = float(val)
                    res['temp_max'] = max(res.get('temp_max', -99), v)
                    res['temp_min'] = min(res.get('temp_min', 99), v)
                if cat == 'REH': res['humidity'] = int(val)
                if cat == 'PCP' and val != '강수없음':
                    try: res['precip'] = float(val.replace('mm', ''))
                    except: pass
                if cat == 'SKY' and item['fcstTime'] == '1200': res['sky_val'] = val
                if cat == 'PTY' and item['fcstTime'] == '1200': res['pty_val'] = val
            if wsd_list:
                res['wind_max'] = max(wsd_list)
                res['wind_min'] = min(wsd_list)
            daylight_duration = ss_h - sr_h
            if sky_list and daylight_duration > 0:
                clear_sky_count = sky_list.count('1') + (sky_list.count('3') * 0.5)
                res['sunshine_hr'] = round(daylight_duration * (clear_sky_count / len(sky_list)), 1)
            res['weather_cd'] = self.match_weather_code_db(res.get('sky_val', '1'), res.get('pty_val', '0'))
            res['raw_info'] = f"SKY:{res.get('sky_val', '1')}, PTY:{res.get('pty_val', '0')}"
            return res
        except Exception as e:
            print(f"Error: {e}"); return None

    def calculate_sun_times_korea(self, lat, lon, date_str):
        d = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_year = d.timetuple().tm_yday
        cos_val = math.cos(math.radians((day_of_year + 10) * 360 / 365))
        lat_adj = (lat - 37.5) * 0.05
        sr_h = 6.45 + (cos_val * 1.35) + lat_adj
        ss_h = 18.65 - (cos_val * 1.25) - lat_adj
        return f"{int(sr_h):02d}:{int((sr_h%1)*60):02d}", f"{int(ss_h):02d}:{int((ss_h%1)*60):02d}", sr_h, ss_h

    def match_weather_code_db(self, sky, pty):
        if pty == '0':
            if sky == '1':   return 'WT010100'
            elif sky == '3': return 'WT010200'
            elif sky == '4': return 'WT010300'
        elif pty == '1':     return 'WT010400'
        elif pty == '2':     return 'WT010500'
        elif pty == '3':     return 'WT010600'
        elif pty == '4':     return 'WT010700'
        return 'WT019900'

def convert_to_grid(lat, lon):
    RE = 6371.00877; GRID = 5.0; SLAT1 = 30.0; SLAT2 = 60.0; OLON = 126.0; OLAT = 38.0; XO = 43; YO = 136
    DEGRAD = math.pi / 180.0; re = RE / GRID; slat1 = SLAT1 * DEGRAD; slat2 = SLAT2 * DEGRAD; olon = OLON * DEGRAD; olat = OLAT * DEGRAD
    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5); sf = math.pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5); ro = re * sf / math.pow(ro, sn)
    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5); ra = re * sf / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi: theta -= 2.0 * math.pi
    if theta < -math.pi: theta += 2.0 * math.pi
    theta *= sn
    nx = int(math.floor(ra * math.sin(theta) + XO + 0.5))
    ny = int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))
    return nx, ny
