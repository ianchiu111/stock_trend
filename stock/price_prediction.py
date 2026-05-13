import os
import joblib
import glob
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from torch.utils.data import DataLoader, TensorDataset

# # Build model
# #####################
# input_dim = 1
# hidden_dim = 32
# num_layers = 2 
# output_dim = 1
class LSTM(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_layers, output_dim):
        super(LSTM, self).__init__()
        # Hidden dimensions
        self.hidden_dim = hidden_dim

        # Number of hidden layers
        self.num_layers = num_layers

        # batch_first=True causes input/output tensors to be of shape
        # (batch_dim, seq_dim, feature_dim)
        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True)

        # Readout layer
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # Initialize hidden state with zeros
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).requires_grad_()

        # Initialize cell state
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_dim).requires_grad_()

        # We need to detach as we are doing truncated backpropagation through time (BPTT)
        # If we don't, we'll backprop all the way to the start even after going through another batch
        out, (hn, cn) = self.lstm(x, (h0.detach(), c0.detach()))

        # Index hidden state of last time step
        # out.size() --> 100, 32, 100
        # out[:, -1, :] --> 100, 100 --> just want last time step hidden states! 
        out = self.fc(out[:, -1, :]) 
        # out.size() --> 100, 10
        return out

class StockPriceLSTM:
    def __init__(self, sequence_length=30):
        self.seq_len = sequence_length
        self.scaler = MinMaxScaler()
        self.label_encoder = LabelEncoder()
        self.device = torch.device('mps' if torch.backends.mps.is_available() 
                           else 'cuda' if torch.cuda.is_available() 
                           else 'cpu')
        self.model = None

    def preprocess_data(self, file_list, target_col='最高價'):
        all_df = []
        for f in file_list:
            df = pd.read_csv(f)
            df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
            df = df.sort_values('Date')
            # 轉換數值
            for col in ['開盤價', '最高價', '最低價', '收盤價', '成交股數']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            all_df.append(df.dropna())

        full_data = pd.concat(all_df)
        
        # 處理股票代號為數值特徵
        full_data['stock_id'] = self.label_encoder.fit_transform(full_data['證券代號'])
        
        # 選取特徵：代號, 開盤, 最高, 最低, 收盤, 成交量
        feature_cols = ['stock_id', '開盤價', '最高價', '最低價', '收盤價', '成交股數']
        scaled_data = self.scaler.fit_transform(full_data[feature_cols])
        
        # 建立滑動視窗資料
        X, y = [], []
        target_idx = feature_cols.index(target_col)
        
        for i in range(len(scaled_data) - self.seq_len):
            X.append(scaled_data[i : i + self.seq_len])
            y.append(scaled_data[i + self.seq_len, target_idx])
            
        return torch.FloatTensor(np.array(X)), torch.FloatTensor(np.array(y)).view(-1, 1)

    def train(self, X, y, epochs=50, batch_size=32, lr=0.001):
        dataset = TensorDataset(X, y)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        input_dim = X.shape[2]
        self.model = PricePredictionLSTM(input_dim, 64, 2, 1).to(self.device)
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        
        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            for batch_X, batch_y in loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                
                outputs = self.model(batch_X)
                loss = criterion(outputs, batch_y)
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if (epoch+1) % 10 == 0:
                print(f'Epoch [{epoch+1}/{epochs}], Loss: {total_loss/len(loader):.6f}')
        
        # save model and scalers
        torch.save(self.model.state_dict(), 'stock/models/price_prediction_model.pth')
        self.save_scalers()


    def save_scalers(self, scaler_path='stock/models/scaler.pkl', encoder_path='stock/models/encoder.pkl'):
        """儲存 Scaler 與 Encoder，這對未來預測至關重要"""
        os.makedirs(os.path.dirname(scaler_path), exist_ok=True)
        joblib.dump(self.scaler, scaler_path)
        joblib.dump(self.label_encoder, encoder_path)
        print("Scalers 已儲存！")

    def load_model_and_scalers(self, model_path, scaler_path, encoder_path, input_dim=6):
        """載入模型與轉換器"""
        # 1. 載入 Scaler & Encoder
        self.scaler = joblib.load(scaler_path)
        self.label_encoder = joblib.load(encoder_path)
        
        # 2. 載入模型結構與權重
        self.model = PricePredictionLSTM(input_dim, 64, 2, 1).to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        
        # 3. 切換至評估模式 (這很重要！會關閉 Dropout 等訓練專用機制)
        self.model.eval() 
        print("模型與 Scalers 載入成功！")

    def predict_next_day(self, recent_30_days_df, target_col='最高價'):
        """
        傳入某檔股票「最近 30 天」的歷史資料 DataFrame，預測第 31 天的股價
        """
        # 1. 確保資料經過正確的轉換
        df = recent_30_days_df.copy()
        for col in ['開盤價', '最高價', '最低價', '收盤價', '成交股數']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna()
        
        if len(df) < self.seq_len:
            raise ValueError(f"資料筆數不足！需要 {self.seq_len} 天，但只提供了 {len(df)} 天。")
            
        # 只取最後 30 天
        df = df.tail(self.seq_len)
        
        # 2. 特徵工程 (使用已經訓練好的 encoder 和 scaler)
        df['stock_id'] = self.label_encoder.transform(df['證券代號'])
        feature_cols = ['stock_id', '開盤價', '最高價', '最低價', '收盤價', '成交股數']
        
        # 縮放特徵
        scaled_data = self.scaler.transform(df[feature_cols])
        
        # 3. 轉換為 Tensor。形狀必須是 (Batch=1, Seq_len=30, Features=6)
        X_tensor = torch.FloatTensor(scaled_data).unsqueeze(0).to(self.device)
        
        # 4. 進行預測
        with torch.no_grad(): # 預測時不計算梯度，節省記憶體並加快速度
            pred_scaled = self.model(X_tensor)
            pred_scaled = pred_scaled.cpu().numpy() # 轉回 numpy array
            
        # 5. 反向轉換 (Inverse Transform) 將縮放值還原成真實股價
        # 因為你的 scaler 當初是 fit 6 個特徵，所以反向轉換時也要塞 6 個特徵的陣列給它
        dummy_array = np.zeros((1, len(feature_cols)))
        target_idx = feature_cols.index(target_col)
        dummy_array[0, target_idx] = pred_scaled[0, 0] # 將預測值放入對應的目標欄位位置
        
        # 反向轉換並取出真實價格
        real_price = self.scaler.inverse_transform(dummy_array)[0, target_idx]
        
        return real_price

if __name__ == "__main__":
    os.makedirs('stock/models', exist_ok=True) # 確保資料夾存在

    folder_path = 'stock/database/twse/*_twse_recent_data.csv'
    file_paths = glob.glob(folder_path)
    # print(f"成功找到 {len(file_paths)} 個檔案，準備開始處理...")
    # print(file_paths)


    # 初始化同一個類別
    trainer = StockPriceLSTM(sequence_length=30)

    # --- 訓練 High 模型 ---
    X_high, y_high = trainer.preprocess_data(file_list, target_col='最高價')
    trainer.train(X_high, y_high) 
    # 注意：你的 train 內建儲存檔名是 'price_prediction_model.pth'
    # 你可能需要修改 train 方法，讓它接受不同的 model_name 參數
    # 例如：torch.save(self.model.state_dict(), f'stock/models/{model_name}.pth')

    # --- 訓練 Low 模型 ---
    X_low, y_low = trainer.preprocess_data(file_list, target_col='最低價')
    trainer.train(X_low, y_low)








------
    # Training 
    X_train, y_train = manager.preprocess_data(file_paths[: 50], target_col='最高價')
    manager.train(X_train, y_train)
    manager.save_scalers() # <--- 訓練完記得儲存 scalers

    # ==========================================
    # 2. 預測流程 (以剛剛訓練的其中一檔股票為例)
    # ==========================================
    
    stock_symbol = "6887"
    
    # 尋找檔名中包含特定 stock symbol 的檔案
    target_file = next((f for f in file_paths if stock_symbol in f), None)

    if target_file:
        print(f"找到目標股票檔案: {target_file}")
        df = pd.read_csv(target_file) # 這裡傳入單一字串，就不會報錯了

        df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d')
        target_stock_df = df[df['證券代號'].astype(str) == stock_symbol].copy()
        target_stock_df = target_stock_df.sort_values('Date')
        
        if len(target_stock_df) >= 30:
            # 抓取該股票最近的 30 天資料
            recent_30_days = target_stock_df.tail(30)
            
            # 進行預測
            predicted_high_price = manager.predict_next_day(recent_30_days, target_col='最高價')
            
            print(f"\n--- 預測結果 ---")
            print(f"股票代號: {stock_symbol}")
            print(f"參考最後交易日: {recent_30_days['Date'].iloc[-1].strftime('%Y-%m-%d')}")
            print(f"預測下個交易日的最高價為: {predicted_high_price:.2f}")
        else:
            print(f"錯誤：{stock_symbol} 的歷史資料不足 30 天，無法預測。")
    else:
        print(f"錯誤：在資料庫中找不到股票代號 {stock_symbol} 的檔案。")