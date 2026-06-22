import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import concurrent.futures
import os
import json

# --- TradingView Scanner API Config ---
TV_SCANNER_URL = "https://scanner.tradingview.com/vietnam/scan"
CACHE_FILE = "fundamental_cache.json"

def get_tradingview_stocks():
    """
    Fetch all Vietnamese stocks from TradingView Screener API
    with basic pricing, fundamental, and industry fields.
    """
    payload = {
        "filter": [
            {"left": "type", "operation": "equal", "right": "stock"},
            {"left": "is_primary", "operation": "equal", "right": True}
        ],
        "options": {"lang": "en"},
        "markets": ["vietnam"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name",
            "close",
            "volume",
            "description",
            "exchange",
            "average_volume_30d_calc",
            "price_52_week_high",
            "price_52_week_low",
            "return_on_equity_fy",
            "debt_to_equity_fy",
            "market_cap_basic",
            "sector",
            "industry"
        ],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
        "range": [0, 1800]  # Tăng lên 1800 để lấy toàn bộ HOSE, HNX và UPCOM
    }
    
    try:
        response = requests.post(TV_SCANNER_URL, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        rows = []
        for item in data.get("data", []):
            d_vals = item.get("d", [])
            # Map columns to values
            if len(d_vals) >= 13:
                rows.append({
                    "ticker": d_vals[0],
                    "close": d_vals[1],
                    "volume": d_vals[2],
                    "name": d_vals[3],
                    "exchange": d_vals[4],
                    "avg_vol_30d": d_vals[5],
                    "high_52w": d_vals[6],
                    "low_52w": d_vals[7],
                    "roe": d_vals[8],
                    "de": d_vals[9],
                    "market_cap": d_vals[10],
                    "sector": d_vals[11],
                    "industry": d_vals[12]
                })
        
        df = pd.DataFrame(rows)
        if not df.empty:
            numeric_cols = ["close", "volume", "avg_vol_30d", "high_52w", "low_52w", "roe", "de", "market_cap"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except Exception as e:
        print(f"Error fetching data from TradingView: {e}")
        return pd.DataFrame()

# --- VNDirect Historical Price Fetcher ---
def get_historical_prices_tcbs(ticker, days=380):
    """
    Fetch daily historical prices for a given ticker from VNDirect Chart API.
    Returns a pandas DataFrame sorted by date ascending.
    """
    to_time = int(time.time())
    from_time = int((datetime.now() - timedelta(days=days)).timestamp())
    
    url = f"https://dchart-api.vndirect.com.vn/dchart/history?symbol={ticker}&resolution=D&from={from_time}&to={to_time}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://banggia.vndirect.com.vn/"
    }
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("s") != "ok" or "t" not in data:
                return pd.DataFrame()
                
            df = pd.DataFrame({
                "date": pd.to_datetime(data["t"], unit="s"),
                "open": data["o"],
                "high": data["h"],
                "low": data["l"],
                "close": data["c"],
                "volume": data["v"]
            })
            
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            df = df.sort_values('date').reset_index(drop=True)
            return df
        except Exception as e:
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            else:
                print(f"Error fetching historical data for {ticker} from VNDirect: {e}")
                return pd.DataFrame()

# --- Cache & Fundamental API Fetching ---
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def check_fundamental_criteria_api(ticker):
    """
    Check if the company has positive quarterly EPS growth OR positive quarterly net profit growth
    in all of the last 4 quarters (compared YoY to the same quarter of the previous year).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://banggia.vndirect.com.vn/"
    }
    
    # 1. Kiểm tra tăng trưởng EPS từ financial_indicators
    url_ind = f"https://finfo-api.vndirect.com.vn/v4/financial_indicators?q=code:{ticker}"
    eps_ok = False
    try:
        r = requests.get(url_ind, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if len(data) >= 8:
                df = pd.DataFrame(data)
                df = df.sort_values(by=["fiscalYear", "fiscalQuarter"]).reset_index(drop=True)
                
                # Tạo từ điển tra cứu
                lookup = {(row['fiscalYear'], row['fiscalQuarter']): row['quarterlyEps'] for _, row in df.iterrows()}
                recent = df.tail(4)
                
                growth_checks = []
                for _, row in recent.iterrows():
                    y, q = row['fiscalYear'], row['fiscalQuarter']
                    curr = lookup.get((y, q))
                    prev = lookup.get((y-1, q))
                    if curr is not None and prev is not None and prev != 0:
                        growth = (curr - prev) / abs(prev)
                        growth_checks.append(growth > 0)
                    else:
                        growth_checks.append(False)
                
                if len(growth_checks) == 4 and all(growth_checks):
                    eps_ok = True
    except Exception:
        pass
        
    if eps_ok:
        return True
        
    # 2. Kiểm tra tăng trưởng lợi nhuận sau thuế từ financial_reports
    url_rep = f"https://finfo-api.vndirect.com.vn/v4/financial_reports?q=code:{ticker}~type:QUARTER"
    np_ok = False
    try:
        r = requests.get(url_rep, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if len(data) >= 8:
                df = pd.DataFrame(data)
                df = df.sort_values(by=["fiscalYear", "fiscalQuarter"]).reset_index(drop=True)
                
                lookup = {(row['fiscalYear'], row['fiscalQuarter']): row['netProfit'] for _, row in df.iterrows()}
                recent = df.tail(4)
                
                growth_checks = []
                for _, row in recent.iterrows():
                    y, q = row['fiscalYear'], row['fiscalQuarter']
                    curr = lookup.get((y, q))
                    prev = lookup.get((y-1, q))
                    if curr is not None and prev is not None and prev != 0:
                        growth = (curr - prev) / abs(prev)
                        growth_checks.append(growth > 0)
                    else:
                        growth_checks.append(False)
                
                if len(growth_checks) == 4 and all(growth_checks):
                    np_ok = True
    except Exception:
        pass
        
    return np_ok

def check_fundamental_criteria(ticker):
    """
    Check fundamental criteria with retry logic and 15-day caching.
    """
    cache = load_cache()
    now = datetime.now()
    
    # Đọc từ cache nếu chưa hết hạn 15 ngày
    if ticker in cache:
        cached_data = cache[ticker]
        cached_time_str = cached_data.get("timestamp", "")
        try:
            cached_time = datetime.fromisoformat(cached_time_str)
            if now - cached_time < timedelta(days=15):
                return cached_data.get("growth_positive", False)
        except Exception:
            pass
            
    # Thử gọi API với cơ chế retry tối đa 3 lần
    success = False
    result = False
    for attempt in range(3):
        try:
            result = check_fundamental_criteria_api(ticker)
            success = True
            break
        except Exception:
            time.sleep(0.5 * (attempt + 1))
            
    if success:
        cache[ticker] = {
            "timestamp": now.isoformat(),
            "growth_positive": result
        }
        save_cache(cache)
        return result
    else:
        # Nếu gọi API thất bại, dùng giá trị cũ trong cache hoặc mặc định là False
        if ticker in cache:
            return cache[ticker].get("growth_positive", False)
        return False

# --- Technical Signal Calculations ---
def check_distribution_days(df_stock, period=25):
    """
    Count distribution days in the last 25 sessions.
    A distribution day is a down day (close < prev_close) on higher volume than the previous day.
    """
    if len(df_stock) < period + 1:
        return 0
    recent = df_stock.iloc[-(period + 1):].reset_index(drop=True)
    dist_days = 0
    for i in range(1, len(recent)):
        curr_close = recent.loc[i, 'close']
        prev_close = recent.loc[i-1, 'close']
        curr_vol = recent.loc[i, 'volume']
        prev_vol = recent.loc[i-1, 'volume']
        
        # Giá đóng cửa giảm và khối lượng tăng so với phiên trước
        if curr_close < prev_close and curr_vol > prev_vol:
            dist_days += 1
    return dist_days

def check_breakout_volume(df_stock):
    """
    Check breakout signals in the last 2 sessions:
    - Close is higher than the 20-day high close
    - Volume is >= 1.5 times the 20-day average volume
    """
    if len(df_stock) < 21:
        return False, 0.0
    latest_close = df_stock['close'].iloc[-1]
    latest_vol = df_stock['volume'].iloc[-1]
    
    avg_vol_20d = df_stock['volume'].iloc[-21:-1].mean()
    vol_ratio = latest_vol / avg_vol_20d if avg_vol_20d > 0 else 0.0
    
    max_close_20d = df_stock['close'].iloc[-21:-1].max()
    is_breakout = latest_close > max_close_20d and vol_ratio >= 1.5
    
    return is_breakout, round(vol_ratio, 2)

def check_pullback_recovery(df_stock):
    if len(df_stock) < 20:
        return False, 0.0
    close = df_stock['close']
    ma10 = close.rolling(10).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    high_20d = close.iloc[-20:].max()
    current_price = close.iloc[-1]
    
    pullback_pct = (high_20d - current_price) / high_20d * 100
    is_pullback_ok = pullback_pct < 8.0 and (current_price > ma20 or current_price > ma10)
    return is_pullback_ok, round(pullback_pct, 2)

# --- Sanitize Values for UI Serialization ---
def sanitize_value(val):
    if isinstance(val, dict):
        return {k: sanitize_value(v) for k, v in val.items()}
    if isinstance(val, list):
        return [sanitize_value(v) for v in val]
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        if np.isnan(val):
            return None
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return val

# --- Master Screener Pipeline ---
def run_sepa_screener(progress_callback=None):
    """
    Run stock screening and scoring system (0-10 points) on HOSE, HNX, UPCOM.
    """
    if progress_callback:
        progress_callback("Đang lấy danh sách mã cổ phiếu từ TradingView...", 0.05)
        
    df_tv = get_tradingview_stocks()
    if df_tv.empty:
        if progress_callback:
            progress_callback("Lỗi: Không lấy được dữ liệu từ TradingView.", 1.0)
        return []
        
    # Bộ lọc thanh khoản tối thiểu để giảm tải hệ thống (Vol TB 30 ngày > 10k, Giá > 2 (2,000đ))
    df_filtered = df_tv[
        (df_tv['volume'] > 10000) &
        (df_tv['close'] > 2.0) &
        (df_tv['high_52w'] > 0)
    ].copy()
    
    tickers = df_filtered['ticker'].tolist()
    total_tickers = len(tickers)
    
    if progress_callback:
        progress_callback(f"Tìm thấy {total_tickers} mã hoạt động. Đang tải VNINDEX làm mốc so sánh RS...", 0.15)
        
    df_index = get_historical_prices_tcbs("VNINDEX", days=380)
    if df_index.empty:
        df_index = get_historical_prices_tcbs("VN30", days=380)
    if df_index.empty:
        dates = pd.date_range(end=datetime.now(), periods=380)
        df_index = pd.DataFrame({'date': dates, 'close': [1200.0] * 380})
        
    results = []
    processed_count = 0
    
    if progress_callback:
        progress_callback(f"Đang phân tích kỹ thuật & chấm điểm 0-10 cho {total_tickers} mã...", 0.20)
        
    def process_ticker(ticker_info):
        ticker = ticker_info['ticker']
        df_hist = get_historical_prices_tcbs(ticker, days=380)
        if df_hist.empty or len(df_hist) < 200:
            return None
            
        close = df_hist['close']
        volume = df_hist['volume']
        high = df_hist['high']
        low = df_hist['low']
        
        # 1. Tính toán MA
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        
        c_price = close.iloc[-1]
        c_ma20 = ma20.iloc[-1]
        c_ma50 = ma50.iloc[-1]
        c_ma200 = ma200.iloc[-1]
        
        # 2. Đánh giá 10 tiêu chí (mỗi tiêu chí đạt được 1 điểm)
        points = 0
        details = {}
        
        # Tiêu chí 1: Giá đóng cửa hiện tại > MA20
        c1 = c_price > c_ma20
        points += int(c1)
        details["c1"] = c1
        
        # Tiêu chí 2: MA20 > MA50
        c2 = c_ma20 > c_ma50
        points += int(c2)
        details["c2"] = c2
        
        # Tiêu chí 3: MA50 > MA200
        c3 = c_ma50 > c_ma200
        points += int(c3)
        details["c3"] = c3
        
        # Tiêu chí 4: MA200 có độ dốc dương trong ít nhất 20 phiên gần nhất
        ma200_diff = ma200.diff().iloc[-20:]
        c4 = (ma200_diff >= -1e-6).all() and c_ma200 > ma200.iloc[-20]
        points += int(c4)
        details["c4"] = c4
        
        # Tiêu chí 5: Giá hiện tại cách đỉnh 52 tuần không quá 15%
        high_52w = close.iloc[-250:].max() if len(close) >= 250 else close.max()
        pct_from_high = (high_52w - c_price) / high_52w * 100
        c5 = pct_from_high <= 15.0
        points += int(c5)
        details["c5"] = c5
        
        # Tiêu chí 6: RS cao hơn VNINDEX trong 3 tháng gần nhất (63 phiên)
        stock_perf_3m = (c_price - close.iloc[-63]) / close.iloc[-63] if len(close) >= 63 else 0.0
        index_perf_3m = (df_index['close'].iloc[-1] - df_index['close'].iloc[-63]) / df_index['close'].iloc[-63] if len(df_index) >= 63 else 0.0
        c6 = stock_perf_3m > index_perf_3m
        points += int(c6)
        details["c6"] = c6
        
        # Tiêu chí 7: Khối lượng giao dịch TB 20 phiên cao hơn TB 60 phiên
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        avg_vol_60 = volume.rolling(60).mean().iloc[-1]
        c7 = avg_vol_20 > avg_vol_60
        points += int(c7)
        details["c7"] = c7
        
        # Tiêu chí 8: Có nền giá tích lũy từ 6-12 tuần (kiểm tra 40 phiên) với biên độ dao động < 15%
        high_40 = high.iloc[-40:].max()
        low_40 = low.iloc[-40:].min()
        base_range = (high_40 - low_40) / high_40 * 100 if high_40 > 0 else 0.0
        c8 = base_range < 15.0
        points += int(c8)
        details["c8"] = c8
        
        # Tiêu chí 9: Số phiên phân phối trong 25 phiên gần nhất không vượt quá 4 phiên
        dist_days_25 = check_distribution_days(df_hist, period=25)
        c9 = dist_days_25 <= 4
        points += int(c9)
        details["c9"] = c9
        
        # Tiêu chí 10: Doanh nghiệp có tăng trưởng EPS hoặc lợi nhuận sau thuế dương trong 4 quý gần nhất
        c10 = check_fundamental_criteria(ticker)
        points += int(c10)
        details["c10"] = c10
        
        # 3. Phân loại theo điểm
        if points >= 9:
            classification = "Leader mạnh"
        elif points >= 7:
            classification = "Watchlist ưu tiên"
        elif points >= 5:
            classification = "Trung tính"
        else:
            classification = "Loại bỏ"
            
        # 4. Tín hiệu breakout và pullback cho cảnh báo
        is_breakout, breakout_vol_ratio = check_breakout_volume(df_hist)
        is_pullback_ok, pullback_pct = check_pullback_recovery(df_hist)
        
        result = {
            "ticker": ticker,
            "name": ticker_info['name'],
            "exchange": ticker_info['exchange'],
            "sector": ticker_info['sector'] or "Chưa phân loại",
            "industry": ticker_info['industry'] or "Chưa phân loại",
            "score": points,
            "close": c_price,
            "volume": volume.iloc[-1],
            "dist_high": round(pct_from_high, 1),
            "ma20": round(c_ma20, 1),
            "ma50": round(c_ma50, 1),
            "ma200": round(c_ma200, 1),
            "rs_vs_index_3m": round((stock_perf_3m - index_perf_3m) * 100, 2), # % chênh lệch hiệu suất
            "avg_vol_20": round(avg_vol_20, 1),
            "avg_vol_60": round(avg_vol_60, 1),
            "distribution_days": dist_days_25,
            "classification": classification,
            "is_breakout": is_breakout,
            "breakout_vol_ratio": breakout_vol_ratio,
            "is_pullback_ok": is_pullback_ok,
            "pullback_pct": pullback_pct,
            "details": details
        }
        return sanitize_value(result)

    start_time = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        ticker_list_info = df_filtered.to_dict('records')
        future_to_ticker = {executor.submit(process_ticker, t): t['ticker'] for t in ticker_list_info}
        
        for future in concurrent.futures.as_completed(future_to_ticker):
            processed_count += 1
            ticker = future_to_ticker[future]
            try:
                res = future.result()
                if res is not None:
                    results.append(res)
            except Exception as exc:
                print(f"{ticker} generated an exception: {exc}")
                
            if progress_callback and processed_count % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / processed_count
                remaining_time = (total_tickers - processed_count) * avg_time
                
                if remaining_time > 60:
                    time_str = f"{int(remaining_time // 60)} phút {int(remaining_time % 60)} giây"
                else:
                    time_str = f"{int(remaining_time)} giây"
                    
                progress = 0.2 + (processed_count / total_tickers) * 0.75
                msg = f"Đã quét {processed_count}/{total_tickers} mã (Tìm thấy {len(results)} mã). Dự kiến còn: {time_str}"
                progress_callback(msg, round(progress, 2))
                
    if progress_callback:
        progress_callback(f"Hoàn thành! Đã tính điểm cho {len(results)} cổ phiếu.", 1.0)
        
    # Sắp xếp kết quả theo điểm giảm dần, sau đó theo khối lượng giao dịch giảm dần
    results.sort(key=lambda x: (x['score'], x['volume']), reverse=True)
    return results

if __name__ == "__main__":
    # Test run
    print("Testing pipeline...")
    res = run_sepa_screener(lambda m, p: print(f"[{p*100:.0f}%] {m}"))
    print("Screener results count:", len(res))
    if len(res) > 0:
        print("First item:", res[0])
