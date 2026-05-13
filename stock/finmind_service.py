"""
提供股票狀態的即時查訊功能，查詢的重點為：
(技術面)
1. K 線圖分析

(基本面)
1. 財報分析

(籌碼面)
1. 三大法人買賣超分析: **三大法人今天到底是買多還是賣多**
    1. 外資 (Foreign Investors): For Long Term Investment
    2. 投信 (Investment Trusts): 
    3. 自營商 (Dealers)

(大環境/消息面)(待開發)
1. 產業分析
2. 時事分析

Source: FinMind (https://finmindtrade.com/analysis/#/data/api)
"""
import os
import gc
import requests
import pandas as pd
import concurrent.futures
from functools import reduce

from dotenv import load_dotenv
load_dotenv(".env")


class FinMind:
    def __init__(self):
        # FinMind 通用 API
        self.base_url = "https://api.finmindtrade.com/api/v4/data"
        self.base_parameter = {
            "dataset": "",
            "data_id": "",
            "start_date": "",
            "end_date": "",
        }

        # dataset path
        self.diagonosis_dataset = "stock/database/finmind"
        os.makedirs(self.diagonosis_dataset, exist_ok=True)

    def getMarginPurchaseShortSale(self, stock_id: str = None, start_date: str = None, end_date: str = None):
        """
        抓取「個股融資融劵表」for 散戶投資人

        parameter = {
            "dataset": dataset in string,
            "data_id": stock_id in string,
            "start_date": yyyy-mm-dd in string,
            "end_date": yyyy-mm-dd in string,
        }

        Data Schema:
        - date: 日期
        - stock_id: 股票代號

        - MarginPurchaseBuy: 融資買進股數
        - MarginPurchaseCashRepayment: 融資現金償還股數
        - MarginPurchaseLimit: 融資限額股數
        - MarginPurchaseSell: 融資賣出股數
        - MarginPurchaseTodayBalance: 融資今日餘額股數
        - MarginPurchaseYesterdayBalance: 融資昨日餘額股數
        - Note: 融資註記
        - OffsetLoanAndShort: 融券借券賣出股數
        - ShortSaleBuy: 融券買進股數
        - ShortSaleCashRepayment: 融券現金償還股數
        - ShortSaleLimit: 融券限額股數
        - ShortSaleSell: 融券賣出股數
        - ShortSaleTodayBalance: 融券今日餘額股數
        - ShortSaleYesterdayBalance: 融券昨日餘額股數   
        
        """
        if stock_id is not None:
            parameter = self.base_parameter.copy()
            parameter["dataset"] = "TaiwanStockMarginPurchaseShortSale"
            parameter["data_id"] = stock_id

            # default as the past 1 years if start_date or end_date is not provided
            parameter["start_date"] = start_date or (pd.Timestamp.today() - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
            parameter["end_date"] = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")

            headers = {
                "Authorization": os.getenv("FINMIND_API_KEY") 
            }

            response = requests.get(self.base_url, params=parameter, headers=headers)
            data = response.json()

            ## save from dict to dataframe
            if data.get('status') == 200 and data.get('data') != []:

                out = pd.DataFrame(data['data'])            
                out['date'] = pd.to_datetime(out['date'])

                return out
                
            else:
                print(f"Error fetching data on margin purchase and short sale: {data.get('msg')}")
                return pd.DataFrame()
        
        else:
            raise ValueError("stock_id is required to fetch margin purchase and short sale data.")
    

    def getTaiwanStockInstitutionalInvestorsBuySell(self, stock_id: str = None, start_date: str = None, end_date: str = None):
        """
        抓取「個股三大法人買賣超」for 三大投資法人

        parameter = {
            "dataset": dataset in string,
            "data_id": stock_id in string,
            "start_date": yyyy-mm-dd in string,
            "end_date": yyyy-mm-dd in string,
        }

        Data Schema:
        - date: 日期
        - stock_id: 股票代號
        
        - Dealer_Hedging_buy: 自營商避險買進股數
        - Dealer_self_buy: 自營商自營買進股數
        - Foreign_Dealer_Self_buy: 外資自營買進股數
        - Foreign_Investor_buy: 外資買進股數
        - Investment_Trust_buy: 投信買進股數

        -  Dealer_Hedging_sell: 自營商避險賣出股數
        - Dealer_self_sell: 自營商自營賣出股數
        - Foreign_Dealer_Self_sell: 外資自營賣出股數
        - Foreign_Investor_sell: 外資賣出股數
        - Investment_Trust_sell: 投信賣出股數

        - Dealer_Hedging_net_buy: 自營商避險買賣超股數
        - Dealer_self_net_buy: 自營商自營買賣超股數
        - Foreign_Dealer_Self_net_buy: 外資自營買賣超股數
        - Foreign_Investor_net_buy: 外資買賣超股數
        - Investment_Trust_net_buy: 投信買賣超股數
        
        """
        if stock_id is not None:
            parameter = self.base_parameter.copy()
            parameter["dataset"] = "TaiwanStockInstitutionalInvestorsBuySell"
            parameter["data_id"] = stock_id

            # default as the past 1 years if start_date or end_date is not provided
            parameter["start_date"] = start_date or (pd.Timestamp.today() - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
            parameter["end_date"] = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")

            headers = {
                "Authorization": os.getenv("FINMIND_API_KEY") 
            }

            response = requests.get(self.base_url, params=parameter, headers=headers)
            data = response.json()

            ## save from dict to dataframe
            if data.get('status') == 200 and data.get('data') != []:

                out = pd.DataFrame(data['data'])            
                out['date'] = pd.to_datetime(out['date'])

                # add new column net_buy = buy - sell
                out['net_buy'] = out['buy'] - out['sell']
                out_pivoted = out.pivot_table(
                    index=['date', 'stock_id'], 
                    columns='name', 
                    values=['buy', 'sell', 'net_buy'], 
                    aggfunc='first'
                )
                
                out_pivoted.columns = [f"{col[1]}_{col[0]}" for col in out_pivoted.columns]
                out_pivoted = out_pivoted.reset_index()   

                return out_pivoted
                
            else:
                print(f"Error fetching data on institutional investors buy/sell: {data.get('msg')}")
                return pd.DataFrame()
        
        else:
            raise ValueError("stock_id is required to fetch institutional investors buy/sell data.")


    def getTaiwanStockPER(self, stock_id: str = None, start_date: str = None, end_date: str = None):
        """
        抓取「個股 PER、PBR 資料表」for 散戶投資人

        parameter = {
            "dataset": dataset in string,
            "data_id": stock_id in string,
            "start_date": yyyy-mm-dd in string,
            "end_date": yyyy-mm-dd in string,
        }

        Data Schema:
        - date: 日期
        - stock_id: 股票代號
        - dividend_yield: 股息殖利率
        - PER: 本益比
        - PBR: 股價淨值比
        """
        if stock_id is not None:
            parameter = self.base_parameter.copy()
            parameter["dataset"] = "TaiwanStockPER"
            parameter["data_id"] = stock_id

            # default as the past 1 years if start_date or end_date is not provided
            parameter["start_date"] = start_date or (pd.Timestamp.today() - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
            parameter["end_date"] = end_date or pd.Timestamp.today().strftime("%Y-%m-%d")

            headers = {
                "Authorization": os.getenv("FINMIND_API_KEY") 
            }

            response = requests.get(self.base_url, params=parameter, headers=headers)
            data = response.json()


            ## save from dict to dataframe
            if data.get('status') == 200 and data.get('data') != []:

                out = pd.DataFrame(data['data'])            
                out['date'] = pd.to_datetime(out['date'])

                return out
                
            else:
                print(f"Error fetching data on PER and PBR: {data.get('msg')}")
                return pd.DataFrame()
        
        else:
            raise ValueError("stock_id is required to fetch PER and PBR data.")


    def getFinMindData(self, stock_id: str = None, start_date: str = None, end_date: str = None):

        if stock_id is not None:

            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 將任務映射到函數，方便未來擴充 (如：加入基本面、技術面)
                tasks = {
                    "margin": executor.submit(self.getMarginPurchaseShortSale, stock_id, start_date, end_date),
                    "institutional": executor.submit(self.getTaiwanStockInstitutionalInvestorsBuySell, stock_id, start_date, end_date),
                    "per": executor.submit(self.getTaiwanStockPER, stock_id, start_date, end_date)
                }
            
                # 收集結果
                results = []
                for name, future in tasks.items():
                    try:
                        df = future.result()
                        if not df.empty and 'date' in df.columns:
                            results.append(df)
                        else:
                            print(f"Warning: Data source '{name}' returned empty or invalid data. Skipping...")
                    except Exception as e:
                        print(f"Error fetching {name}: {e}")


            if not results:
                print("No data collected from any source.")
                return

            # 彈性合併：使用 reduce 自動處理 N 個 DataFrame
            # how='outer' 確保就算日期不完全對齊也能保留資料
            out = reduce(lambda left, right: pd.merge(left, right, on=['date', 'stock_id'], how='outer'), results)

            # 後續處理
            out.set_index('date', inplace=True)
            out.to_csv(f"{self.diagonosis_dataset}/{stock_id}_stock_diagnosis.csv")

            # # Processing Stock Diagnosis Tasks in Parallel using ThreadPoolExecutor
            # with concurrent.futures.ThreadPoolExecutor() as executor:
            #     # Tasks for executor
            #     future_margin = executor.submit(self.getMarginPurchaseShortSale, stock_id, start_date, end_date)
            #     future_institutional = executor.submit(self.getTaiwanStockInstitutionalInvestorsBuySell, stock_id, start_date, end_date)
            #     future_per = executor.submit(self.getTaiwanStockPER, stock_id, start_date, end_date)

            #     # Wait for all tasks to complete and get results
            #     margin_short_data = future_margin.result()
            #     institutional_data = future_institutional.result()
            #     per_data = future_per.result()

            #     # testing 
            #     print("aaaaaa", margin_short_data)
            #     print("bbbbb", institutional_data)
            #     print("ccccc", per_data)

            # # flexible merging if some of the data is missing
            # out = pd.merge(margin_short_data, institutional_data, on=['date', 'stock_id'], how='outer')
            # out = pd.merge(out, per_data, on=['date', 'stock_id'], how='outer')
            # out.set_index('date', inplace=True)
            # out.to_csv(f"{self.diagonosis_dataset}/{stock_id}_stock_diagnosis.csv")

            results.clear() 

            del out
            gc.collect()

        else:
            raise ValueError("stock_id is required to perform stock diagnosis.")


if __name__ == "__main__":

    finmind = FinMind()
    # df = finmind.getTaiwanStockPER(stock_id="2355", start_date="2026-05-08")  

    start_time = pd.Timestamp.now()

    # main entry point
    finmind.getFinMindData(stock_id = "0050")

    end_time = pd.Timestamp.now()
    print(f"Processing time: {end_time - start_time}")