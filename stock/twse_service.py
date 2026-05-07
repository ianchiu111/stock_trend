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
        self.base_dir = "stock/database/twse"
        os.makedirs(self.base_dir, exist_ok=True)
        
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

    def _save_to_individual_files(self, df):
        """ 將 DataFrame 拆分並追加到各別股票的 CSV """
        filtered_df = df[
            (df['證券代號'].str.isdigit()) & 
            (~df['證券名稱'].str.contains(self.exclude_pattern, regex=True)) &
            (df['證券代號'].str.len().between(4, 6))
        ].copy()

        grouped = filtered_df.groupby('證券代號')
        for symbol, group_df in grouped:
            clean_symbol = str(symbol).strip()
            save_path = f"{self.base_dir}/{clean_symbol}_twse_recent_data.csv"
            
            # 如果檔案已存在，則追加且不寫入 Header
            file_exists = os.path.isfile(save_path)
            group_df.to_csv(save_path, index=False, encoding="utf-8-sig", 
                           mode='a' if file_exists else 'w', 
                           header=not file_exists)

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
    
    async def process_range(self, start_date: str, end_date: str, for_update: bool = False):
        """
        整合後的抓取邏輯
        for_update=True: 追加模式
        for_update=False: 覆蓋模式
        """
        date_list = pd.bdate_range(start=start_date, end=end_date).strftime("%Y%m%d").tolist()
        if not date_list:
            return "No business days in range"

        batch_size = 30
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(date_list), batch_size):
                batch_dates = date_list[i : i + batch_size]
                tasks = [self.fetch_daily_info(session, date) for date in batch_dates]
                results = await asyncio.gather(*tasks)

                batched_df_list = [df for df in results if df is not None]

                if batched_df_list:
                    batched_df = pd.concat(batched_df_list, ignore_index=True)
                    
                    # 1. 存入/更新大表 (Master CSV)
                    mode = 'a' if (for_update or i > 0) else 'w'
                    header = False if mode == 'a' else True
                    batched_df.to_csv(self.twse_recent_data, index=False, encoding="utf-8-sig", mode=mode, header=header)

                    # 2. 拆分並更新個股 CSV
                    self._save_to_individual_files(batched_df)

                del batched_df_list, results
                gc.collect()
        
        return f"Successfully processed {len(date_list)} days"


# if __name__ == "__main__":
    
#     twse = TWSE()    
#     asyncio.run(twse.process_range(start_date="20260507", end_date="20260507", for_update=True))
    
    # fetch recent stock data
    # asyncio.run(twse.process_range(start_date="20240101", end_date="20240626", for_update=False))
