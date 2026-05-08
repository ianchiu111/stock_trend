
import glob
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler, LabelEncoder
from torch.utils.data import DataLoader, TensorDataset

class PricePredictionLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size=1):
        super(PricePredictionLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :]) # 取最後一個時間步的輸出
        return out

class PriceModelManager:
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
        
        input_size = X.shape[2]
        self.model = PricePredictionLSTM(input_size, 64, 2, 1).to(self.device)
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
        
        # save model
        torch.save(self.model.state_dict(), 'stock/models/price_prediction_model.pth')
    

if __name__ == "__main__":

    folder_path = 'stock/database/twse/*_twse_recent_data.csv'
    file_paths = glob.glob(folder_path)
    print(f"成功找到 {len(file_paths)} 個檔案，準備開始處理...")

    manager = PriceModelManager(sequence_length=30)

    X_train, y_train = manager.preprocess_data(file_paths, target_col='最高價')
    manager.train(X_train, y_train)
