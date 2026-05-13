"""
因為 API 數據的限制，無法直接從 API 取得完整的診斷報告所需的所有數據
這部分要再調整一下，改用 LLM 來分析數據並產出診斷報告 --> 思考 Prompting 的設計
"""
import os
import base64
import pandas as pd
import numpy as np
from openai import OpenAI
from .prompt.prompts import get_financial_analysis_prompt

from dotenv import load_dotenv
load_dotenv(".env")


class StockDiagnosis:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.df['date'] = pd.to_datetime(self.df['date'])
        self.df = self.df.sort_values('date')

        self.stock_id = self.df['stock_id'].iloc[0]
        self.start_date = self.df['date'].iloc[0].strftime('%Y-%m-%d')
        self.end_date = self.df['date'].iloc[-1].strftime('%Y-%m-%d')
        self.days_count = len(self.df)

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def get_diagnosis_report(self) -> str:

        df = self.df.copy()
        if df.empty:
            return "資料集為空，無法產出報告。"
        
        if self.days_count < 20:
            return f"資料筆數不足（僅 {self.days_count} 筆），請選擇至少 20 天以上以進行更全面的診斷分析。"
    
        report = ""
        

        # === 指標 1. 趨勢與估值分析 (Valuation) ===
        # 本益比 / 股價淨值比 / 殖利率
        try: 
            current_per = df['PER'].iloc[-1]
            avg_per = df['PER'].mean()
            current_pbr = df['PBR'].iloc[-1]
            avg_pbr = df['PBR'].mean()
            current_yield = df['dividend_yield'].iloc[-1]
            avg_yield = df['dividend_yield'].mean()
            
            valuation_status = "偏高" if current_per > avg_per else "偏低"

            report += "#### 估值與趨勢狀態 (Trend & Valuation)\n"
            report += f"- 目前本益比 (PER): {current_per:.2f} (總平均: {avg_per:.2f})\n"
            report += f"- 目前股價淨值比 (PBR): {current_pbr:.2f} (總平均: {avg_pbr:.2f})\n"
            report += f"- 目前殖利率: {current_yield:.2f}% (總平均: {avg_yield:.2f}%)\n"
            report += f"##### 診斷:\n"            
            report += f"- 目前本益比相較於過去一年平均來得`{valuation_status}`\n"
            report += f"- 從歷史估值區間來看，目前的股價處於相對`{'昂貴' if valuation_status=='偏高' else '便宜'}`的位置\n"
        
        except KeyError as e:
            print(f"無法分析 {self.stock_id} 的本益比 / 股價淨值比 / 殖利率")

        # === 指標 2. 三大法人分析 (Institutional) ===
        # 外資 / 投信 / 自營商 近五日、近二十日的買賣超趨勢
        try: 
            last_5 = df.tail(5)
            last_20 = df.tail(20)
            
            # 外資
            foreign_5d = last_5['Foreign_Investor_net_buy'].sum()
            foreign_20d = last_20['Foreign_Investor_net_buy'].sum()
            
            # 投信
            trust_5d = last_5['Investment_Trust_net_buy'].sum()
            trust_20d = last_20['Investment_Trust_net_buy'].sum()
            
            # 自營商
            dealer_5d = last_5['Dealer_self_net_buy'].sum() + last_5['Dealer_Hedging_net_buy'].sum()
            dealer_20d = last_20['Dealer_self_net_buy'].sum() + last_20['Dealer_Hedging_net_buy'].sum()
            
            inst_total_5d = foreign_5d + trust_5d + dealer_5d
            inst_total_20d = foreign_20d + trust_20d + dealer_20d

            # 三大法人近五日分析
            if inst_total_5d > 0:
                inst_action_5d = "買超"
            else:
                inst_action_5d = "賣超"

            driver_val_5d = max(abs(foreign_5d), abs(trust_5d), abs(dealer_5d))
            if driver_val_5d == abs(foreign_5d):
                driver_5d = "外資主導"
            elif driver_val_5d == abs(trust_5d):
                driver_5d = "投信主導"
            elif driver_val_5d == abs(dealer_5d):
                driver_5d = "自營商主導"

            # 三大法人近二十日分析
            if inst_total_20d > 0:
                inst_action_20d = "買超"
            else:
                inst_action_20d = "賣超"

            driver_val_20d = max(abs(foreign_20d), abs(trust_20d), abs(dealer_20d))
            if driver_val_20d == abs(foreign_20d):
                driver_20d = "外資主導"
            elif driver_val_20d == abs(trust_20d):
                driver_20d = "投信主導"
            elif driver_val_20d == abs(dealer_20d):
                driver_20d = "自營商主導"

            report += "#### 三大法人動作與策略狀態\n"
            report += f"##### 外資:\n"            
            report += f"- 近 5 日累積買賣超: {foreign_5d:,} 股\n"
            report += f"- 近 20 日累積買賣超: {foreign_20d:,} 股\n"
            report += f"##### 投信:\n"            
            report += f"- 近 5 日累積買賣超: {trust_5d:,} 股\n"
            report += f"- 近 20 日累積買賣超: {trust_20d:,} 股\n"
            report += f"##### 自營商:\n"            
            report += f"- 近 5 日累積買賣超: {dealer_5d:,} 股\n"
            report += f"- 近 20 日累積買賣超: {dealer_20d:,} 股\n"
            report += f"##### 診斷:\n"            
            report += f"- 近 5 日以來，三大法人整體呈現`{inst_action_5d}`。多為`{driver_5d}`。\n"
            report += f"- 近 20 日以來，三大法人整體呈現`{inst_action_20d}`。多為`{driver_20d}`。\n"

        except KeyError as e:
            print(f"無法分析 {self.stock_id} 的三大法人買賣超數據")

        # === 指標 3. 散戶動向 (Retail) ===
        try: 
            current_margin = df['MarginPurchaseTodayBalance'].iloc[-1]
            margin_20d_ago = df['MarginPurchaseTodayBalance'].iloc[-21] if len(df) > 20 else df['MarginPurchaseTodayBalance'].iloc[0]
            margin_change = current_margin - margin_20d_ago
            retail_mood = "偏多 (槓桿增加)" if margin_change > 0 else "退場或偏空 (槓桿減少)"
            
            current_short = df['ShortSaleTodayBalance'].iloc[-1]
            short_20d_ago = df['ShortSaleTodayBalance'].iloc[-21] if len(df) > 20 else df['ShortSaleTodayBalance'].iloc[0]
            short_change = current_short - short_20d_ago

            report += "#### 散戶動向\n"
            report += f"- 目前融資餘額: {current_margin:,} 股 (近 20 日變化: {'+' if margin_change > 0 else ''}{margin_change:,} 股)\n"
            report += f"- 目前融券餘額: {current_short:,} 股 (近 20 日變化: {'+' if short_change > 0 else ''}{short_change:,} 股)\n"
            report += f"##### 診斷:\n"            
            report += f"- 近一個月融資餘額呈現`{'增加' if margin_change > 0 else '減少'}`。\n"       
            report += f"- 散戶情緒目前`{retail_mood}`。\n"       

        except KeyError as e:
            print(f"無法分析 {self.stock_id} 的散戶動向數據")
            current_margin = margin_change = current_short = short_change = 0

        return report


    def get_AI_suggestion(self, report: str, query: str, uploaded_file: object = None) -> str:
        """
        LLM 根據 report 的內容以及 query 的問題，給出進一步的分析建議
        """
        system_prompt = get_financial_analysis_prompt(report = report, query = query)

        user_content = [
            {
                "type": "text",
                "text": query
            }
        ]

        # photo processing
        if uploaded_file is not None:
            try:
                img_bytes = uploaded_file.getvalue()
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}"
                    }
                })
            except Exception as e:
                print(f"圖片處理失敗: {e}")

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {
                        "role": "system", 
                        "content": system_prompt
                    },
                    {
                        "role": "user", 
                        "content": user_content 
                    }
                ],
                temperature=0.0, 
            )
            
            return response.choices[0].message.content
                
        except Exception as e:
            return f"呼叫 API 時發生錯誤: {str(e)}"

if __name__ == "__main__":

    from finmind_service import FinMind

    finmind = FinMind()
    stock_id = "0050"
    start_date = "2026-01-10"
    end_date = "2026-05-12"

    finmind.getFinMindData(stock_id = stock_id, start_date = start_date, end_date = end_date)
    df = pd.read_csv(f'stock/database/finmind/{stock_id}_stock_diagnosis.csv', dtype={'stock_id': str})
    analyzer = StockDiagnosis(df)
    report = analyzer.get_diagnosis_report()
    print(analyzer.get_AI_suggestion(report, "這隻股票適合現在進場購買嗎？"))