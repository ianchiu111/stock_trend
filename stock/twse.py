"""
TWSE (Taiwan Stock Exchange)
Open Source: https://www.twse.com.tw/zh/index.html
"""

import os
import gc
import pandas as pd
import aiohttp
import asyncio
import random


class TWSE:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(3)
        self.twse_recent_data = "stock/database/twse/twse_recent_data.csv"
        self.exclude_pattern = (
            r'售|購|牛|熊|展|'          # 權證、展延相關 (最重要)
            r'N$|'                     # 結尾為 N 的通常是 ETN (指數投資證券)
            r'正2|反1|反向|槓桿|'       # 槓桿與反向型工具
            r'債|美債|公司債|投等債|'    # 債券型 ETF (除非你想要債券)
            r'DR$|'                    # 存託憑證 (非台灣本土公司)
            r'上証|滬深|中國|中証|A50|'  # 國外市場 ETF (中國)
            r'恒生|國企|香港|'          # 國外市場 ETF (香港)
            r'越南|印度|歐洲|北美'       # 其他國外市場 ETF
        )

    async def fetch_daily_info(self, session, date: str):
        """
        Asynchronous function to fetch daily stock trading data for a specific date.
        """
        url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALL&response=json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        
        # Use Semaphore to control concurrency and avoid hitting rate limits    
        async with self.semaphore:
            try:
                await asyncio.sleep(random.uniform(2, 5))
                
                async with session.get(url, headers=headers, ssl=False) as response:
                    if response.status != 200:
                        print(f"❌ {date} request failed，status code: {response.status}")
                        return None
                        
                    data = await response.json()                           
                            
                    if data.get('stat') == 'OK':
                        for table in data.get('tables', []):

                            if '每日收盤行情' in table.get('title', ''):

                                df = pd.DataFrame(table['data'], columns=table['fields'])
                                df['Date'] = date
                                df = df.replace(',', '', regex=True)

                                # clean 漲跌(+/-) column
                                is_up = df['漲跌(+/-)'].str.contains('+', regex=False, na=False)
                                is_down = df['漲跌(+/-)'].str.contains('-', regex=False, na=False)
                                
                                df.loc[is_up, '漲跌(+/-)'] = '上漲'
                                df.loc[is_down, '漲跌(+/-)'] = '下跌'                                
                                df.loc[~(is_up | is_down), '漲跌(+/-)'] = '無變動'

                                print(f"✅ Successfully fetched data for {date}, total {len(df)} records")
                                return df

                    else:
                        print(f"⏸️ {date} may not be a trading day (e.g., public holiday), or no data available.")
                        
            except Exception as e:
                print(f"❌ Error occurred while fetching data for {date}: {e}")
                
        return None
    
    # 若之後要做成 API 可以將（fetch_recent_info, fetch_specific_info）整合在一起
    async def fetch_recent_info(self):
        """
        Fetch recent stock trading data for the past 2 years
        - Store every 30 business days in a batch to avoid memory overflow
        """

         # --- First async process: fetch data from twse ---

        two_years_ago = (pd.Timestamp.now() - pd.DateOffset(years=2)).strftime("%Y%m%d")
        now = pd.Timestamp.now().strftime("%Y%m%d")
        date_list = pd.bdate_range(start=two_years_ago, end=now).strftime("%Y%m%d").tolist()
        print(f"🚀 Preparing to fetch data from {date_list[0]} to {date_list[-1]}, total {len(date_list)} business days...")

        os.makedirs("stock/database/twse", exist_ok=True)
        batch_size = 30  
        first_write = True 
       
        async with aiohttp.ClientSession() as session:
            # Batch processing
            for i in range(0, len(date_list), batch_size):
                batch_dates = date_list[i : i + batch_size]
                print(f"📦 Processing Batch：{batch_dates[0]} ~ {batch_dates[-1]} ({i//batch_size + 1} Batch)")

                tasks = [self.fetch_daily_info(session, date) for date in batch_dates]
                results = await asyncio.gather(*tasks)

                batched_df_list = []

                for df in results:
                    if df is not None:
                        batched_df_list.append(df)

                        # clean up memory to avoid OOM error
                        del df
                        gc.collect()

                if batched_df_list:
                    batched_df = pd.concat(batched_df_list, ignore_index=True)
                    
                    # first time to write
                    if first_write:
                        batched_df.to_csv(self.twse_recent_data, index=False, encoding="utf-8-sig", mode='w')
                        first_write = False
                    # after to append
                    else:
                        batched_df.to_csv(self.twse_recent_data, index=False, encoding="utf-8-sig", mode='a', header=False)

                del batched_df_list, results
                gc.collect()

        print(f"✅ 所有資料抓取完成，存檔至：{self.twse_recent_data}")

        #  --- Second async process: separate data by stock symbol and save to individual csv files ---
        print(f"🚀 Separating data by stock symbol...")
        raw_df = pd.read_csv(self.twse_recent_data)
    
        filtered_df = raw_df[
            (raw_df['證券代號'].str.isdigit()) & 
            (~raw_df['證券名稱'].str.contains(self.exclude_pattern, regex=True)) &
            (raw_df['證券代號'].str.len().between(4, 6))
        ].copy()

        print(f"🧹 過濾完成：原始筆數 {len(raw_df)} -> 過濾後筆數 {len(filtered_df)}")

        grouped = filtered_df.groupby('證券代號')
        
        for symbol, group_df in grouped:
            #
            clean_symbol = str(symbol).strip()
            save_path = f"stock/database/twse/{clean_symbol}_twse_recent_data.csv"
            group_df.to_csv(save_path, index=False, encoding="utf-8-sig")
            
        print(f"🎊 拆分完成！共處理 {len(grouped)} 檔個股。")
        
        # 最後清理大表
        del raw_df, filtered_df, grouped
        gc.collect()

    async def fetch_specific_info(self, start_date: str, end_date: str):
        """
        Fetch recent stock trading data for the specific date range
        - Store every 30 business days in a batch to avoid memory overflow

        start_date and end_date should be in "YYYYMMDD" format
        """

        # check date format
        try:
            pd.to_datetime(start_date, format="%Y%m%d")
            pd.to_datetime(end_date, format="%Y%m%d")
        except ValueError:
            print("❌ 日期格式錯誤，請使用 YYYYMMDD 格式")
            return

        date_list = pd.bdate_range(start=start_date, end=end_date).strftime("%Y%m%d").tolist()
        print(f"🚀 Preparing to fetch data from {date_list[0]} to {date_list[-1]}, total {len(date_list)} business days...")

        os.makedirs("stock/database/twse", exist_ok=True)
        batch_size = 30  
       
        async with aiohttp.ClientSession() as session:
            # Batch processing
            for i in range(0, len(date_list), batch_size):
                batch_dates = date_list[i : i + batch_size]
                print(f"📦 Processing Batch：{batch_dates[0]} ~ {batch_dates[-1]} ({i//batch_size + 1} Batch)")

                tasks = [self.fetch_daily_info(session, date) for date in batch_dates]
                results = await asyncio.gather(*tasks)

                batched_df_list = []

                for df in results:
                    if df is not None:
                        batched_df_list.append(df)

                        # clean up memory to avoid OOM error
                        del df
                        gc.collect()

                if batched_df_list:
                    batched_df = pd.concat(batched_df_list, ignore_index=True)
                    batched_df.to_csv(self.twse_recent_data, index=False, encoding="utf-8-sig", mode='a', header=False)

                del batched_df_list, results
                gc.collect()

        print(f"✅ 所有資料抓取完成，存檔至：{self.twse_recent_data}")

        #  --- Second async process: separate data by stock symbol and save to individual csv files ---
        print(f"🚀 Separating data by stock symbol...")
        raw_df = pd.read_csv(self.twse_recent_data)
    
        filtered_df = raw_df[
            (raw_df['證券代號'].str.isdigit()) & 
            (~raw_df['證券名稱'].str.contains(self.exclude_pattern, regex=True)) &
            (raw_df['證券代號'].str.len().between(4, 6))
        ].copy()

        print(f"🧹 過濾完成：原始筆數 {len(raw_df)} -> 過濾後筆數 {len(filtered_df)}")

        grouped = filtered_df.groupby('證券代號')
        
        for symbol, group_df in grouped:
            
            clean_symbol = str(symbol).strip()
            save_path = f"stock/database/twse/{clean_symbol}_twse_recent_data.csv"
            group_df.to_csv(save_path, index=False, encoding="utf-8-sig")
            
        print(f"🎊 拆分完成！共處理 {len(grouped)} 檔個股。")
        
        # 最後清理大表
        del raw_df, filtered_df, grouped
        gc.collect()



if __name__ == "__main__":
    
    twse = TWSE()    

    # fetch recent stock data
    asyncio.run(twse.fetch_recent_info())

    # update stock data for specific date range
    # asyncio.run(twse.update_info(start_date="20260127", end_date="20260127"))

    # separate data by stock symbol
    # twse.seperate_by_symbol()