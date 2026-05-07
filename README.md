
## Website
<img src="images/streamlitUI.png" alt="image" width="400"/>

## Deploy on Fly.io by DockerFile
1. Install **Flyctl** CMD tool with `brew install flyctl`
2. Login in Fly.io with `fly auth login`
3. Establish `startup.sh`, `Dockerfile` and `.dockerignore` in project root
4. **First** init config and deploy with `fly launch`
5. After Fly.io detects Dockerfile, we have to make sure the config and input `y` for Yes
    <img src="images/flyLaunch.png" alt="image" width="400"/>
6. **The following** update and deploy with `fly deploy --no-cache`

## What I learn from the project
1. Use `startup.sh` with `Dockerfile` to run three tasks in one container
    1. Cron service: Daily update data.
    2. Flask API: As backend server.
    3. Streamlit UI: As fronend web.

### 🚀 Fly.io Deploy and Update Command

### 1. Init and Deploy for the first time
> Execute after preparing `Dockerfile`、`startup.sh` and repo files

*   **`fly launch`**：Scan project rool and initialize App。 Generate `fly.toml` config after execution
*   **`fly volumes create stock_storage --region nrt --count 1 --size 1`**
    * `--count 1`： Establish two volumes
    * `--region nrt`: set the region on Tokyo
    * example: `fly volumes create stock_storage --region nrt --count 1 --size 1`

### 2. Update and Re-Deploy for the following time
> Execute after every when modify and codes in the repo

*   **`fly deploy`**：Deploy a new version again based on `fly.toml`
*   **`fly deploy --no-cache`**：Same as above but without past cache

### 3. Monitoring and Logger

*   **`fly logs`**：Check logger in the container
*   **`fly status`**：Check the status of the working machines
*   **`fly open`**：Automatically open the app in browser
*   **`fly machine stop --app <app name>`**: Suspend the app
*   **`fly machine stop --app <app name>`**: Delete the app

### 4. Source Management
*   **`fly m list`** (Virtual Machines List)：List all running virtual machine entities
*   **`fly m restart <ID>`**：Manually restart a specific virtual machine entity

### Key files for deployment
| File Name | Key Point | 目的 |
| :--- | :--- | :--- |
| **`fly.toml`** | 包含 `[mounts]` 與兩組 `[[services]]` | 確保資料持久化並開放 80 (UI) 與 5001 (API) 埠口|
| **`startup.sh`** | 加上 `--server.address=0.0.0.0` | 解決 `refused connection` 警告，讓外網可存取 |
| **`Dockerfile`** | 使用 `FROM python:3.13-slim` | 與你目前的開發環境版本保持一致|
| **`.dockerignore`** | 排除 `.venv` 與 `.git` | 縮小上傳體積，避免過多的無效傳輸|
