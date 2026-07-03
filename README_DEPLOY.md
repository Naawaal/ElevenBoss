# Deploying ElevenBoss Bot to Render & UptimeRobot

This guide outlines how to deploy your ElevenBoss Discord bot to the Render platform as a Web Service and keep it running continuously using UptimeRobot.

---

## 1. Render Deployment Blueprint

Because Render's free tier automatically sleeps Web Services after 15 minutes of inactivity, we added a lightweight, built-in HTTP server that binds to the Render-allocated port (listening on `/health` and `/`). 

This allows Render to successfully build the app, execute its health checks, and enables external ping utilities (like UptimeRobot) to keep it awake.

### Option A: Automatic Import (Blueprint)
1. Push your code to your GitHub/GitLab repository.
2. In the Render Dashboard, click **New +** -> **Blueprint**.
3. Select your repository. Render will automatically parse the [render.yaml](file:///d:/Python/Discord%20Bots/ElevenBoss/render.yaml) file.
4. Input the environment variables (e.g. `DATABASE_URL`, `DISCORD_TOKEN`) and deploy.

### Option B: Manual Setup
If you prefer setting up the Web Service manually:
1. Click **New +** -> **Web Service**.
2. Select **Build and deploy from a Git repository**.
3. Configure the following:
   * **Name**: `elevenboss-bot`
   * **Runtime**: `Python`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `python main.py`
4. Add the following **Environment Variables**:
   * `ENVIRONMENT`: `production`
   * `PORT`: `10000` (or any port of your choice; the bot reads this to start the health-check web server)
   * `DATABASE_URL`: `postgresql+asyncpg://...` (your PostgreSQL connection string)
   * `DISCORD_TOKEN`: `YOUR_DISCORD_BOT_TOKEN`

---

## 2. UptimeRobot Configuration

Render Web Services sleep if they do not receive HTTP requests for 15 minutes. To keep the bot running 24/7:

1. Log in to [UptimeRobot](https://uptimerobot.com/).
2. Click **Add New Monitor**.
3. Configure the monitor details:
   * **Monitor Type**: `HTTP(s)`
   * **Friendly Name**: `ElevenBoss Bot Health`
   * **URL (or IP)**: `https://your-app-subdomain.onrender.com/health` (replace with your actual Render Web Service URL)
   * **Monitoring Interval**: Every `5 minutes` (this keeps the service active and prevents it from sleeping)
4. Click **Create Monitor**.

---

## 3. Verify Deployment

Once deployed:
1. Verify in the Render Logs that you see:
   ```text
   Web server started on port 10000 for Render health checks.
   Starting ElevenBoss Discord bot...
   ```
2. Open a browser and visit `https://your-app-subdomain.onrender.com/health`. It should return:
   ```json
   {"status": "ok", "bot": "ElevenBoss"}
   ```
