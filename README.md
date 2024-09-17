# Validator Node Monitor Telegram Bot

## 🛠 Features

- **Fetch Block Data:** Retrieve the status of the last 100, 500, 1k, 2k, 5k, 10k, 25k, 50k, and 100k blocks.
- **Real-Time Alerts:** Receive instant notifications via Telegram when your validator misses a block.
- **Asynchronous Operations:** Efficiently handles large block ranges without performance degradation.
- **Multiple Alert Recipients:** Register multiple Telegram chats to receive alerts.
- **Systemd Integration:** Ensure the bot runs continuously in the background and restarts automatically on failure.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Set Up Environment Variables](#2-set-up-environment-variables)
  - [3. Install Dependencies](#3-install-dependencies)
  - [4. Configure the Bot](#4-configure-the-bot)
- [Setting Up systemd Service](#setting-up-systemd-service)
  - [1. Create the systemd Service File](#1-create-the-systemd-service-file)
  - [2. Reload systemd and Enable the Service](#2-reload-systemd-and-enable-the-service)
  - [3. Start and Manage the Service](#3-start-and-manage-the-service)
- [Usage](#usage)
  - [Available Commands](#available-commands)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Prerequisites

Before setting up the **Validator Node Monitor Telegram Bot**, ensure you have the following:

- **Python 3.7+** installed on your system.
- **Telegram Bot Token:** Obtainable by creating a bot via [BotFather](https://core.telegram.org/bots#6-botfather).
- **Access to Your Validator Node's REST API Endpoints.**
- **Systemd** installed (common on most Linux distributions).

## Installation

### 1. Clone the Repository

First, clone the repository to your local machine:

```
git clone (https://github.com/MavNode/nodescan/tree/main)
cd nodescan
```

### 2. Set Up Environment Variables

Create a `.env` file in the project directory to securely store your Telegram bot token and other sensitive information.

#### **a. Using a Text Editor**

1. Open your preferred text editor and create a new file named `.env`.
2. Add the following line, replacing `your_telegram_bot_token_here` with your actual Telegram bot token:

    ```dotenv
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
    ```

3. Save the file in the project root directory.

#### **b. Using Command Line**

You can also create the `.env` file directly from the terminal:

```bash
echo "TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here" > .env
```

*Ensure to replace `your_telegram_bot_token_here` with the token provided by BotFather.*

**⚠️ Important:** Do **NOT** share your `.env` file publicly as it contains sensitive information.

### 3. Install Dependencies

Ensure you have `pip` installed. Then, install the required Python packages using the provided `requirements.txt` file:

```bash
pip3 install -r requirements.txt
```

*If you're using a virtual environment (recommended), activate it before running the above command.*

### 4. Configure the Bot

Open the `nodescan.py` script and replace the placeholder values with your specific configurations.

#### **a. Define Your Node's REST API URLs and Validator Address**

Locate the following section in `nodescan.py`:

```python
# Define your node's REST API base URLs and the base64 encoded validator address
BASE_URLS = [
    "https://REPLACE_WITH_YOUR_REST_API",  # Primary node's REST API endpoint
    "https://REPLACE_WITH_YOUR_REST_API"   # Secondary node's REST API endpoint
]
VALIDATOR_ADDRESS_BASE64 = "REPLACE_WITH_YOUR_BASE64_ADDRESS"
```

**Replace the placeholders:**

- **`https://REPLACE_WITH_YOUR_REST_API`**: Insert your validator node's primary and secondary REST API endpoints.
- **`REPLACE_WITH_YOUR_BASE64_ADDRESS`**: Insert your validator's base64-encoded address.

**Example:**

```python
BASE_URLS = [
    "https://api-primary.yournode.com",  # Primary node's REST API endpoint
    "https://api-secondary.yournode.com" # Secondary node's REST API endpoint
]
VALIDATOR_ADDRESS_BASE64 = "5dq1B/Z03lNqehSRAZ69RuyDbYA="
```

## Setting Up systemd Service

To ensure that the bot runs continuously in the background and starts automatically on system boot, set it up as a systemd service.

### 1. Create the systemd Service File

Create a service file named `nodescan.service` in the `/etc/systemd/system/` directory.

```bash
sudo nano /etc/systemd/system/nodescan.service
```

**Paste the following configuration:**

```ini
[Unit]
Description=Nodescan Telegram Bot Service
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/nodescan/

# Load the environment variables from the .env file
EnvironmentFile=/root/nodescan/.env

# Command to run the Python script
ExecStart=/usr/bin/python3 /root/nodescan/nodescan.py

# Restart the service if it fails
Restart=always
RestartSec=5

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**⚠️ Important:**

- **`User=root` and `Group=root`**: The service runs as the root user. Ensure this is acceptable for your security requirements. For enhanced security, consider creating a dedicated non-root user.
- **`WorkingDirectory`**: Ensure the path `/root/nodescan/` correctly points to your project's directory.
- **`EnvironmentFile`**: Points to the `.env` file containing your Telegram bot token and other environment variables.
- **`ExecStart`**: Specifies the command to run your Python script.

### 2. Reload systemd and Enable the Service

After creating the service file, reload systemd to recognize the new service and enable it to start on boot.

```bash
sudo systemctl daemon-reload
sudo systemctl enable nodescan.service
```

### 3. Start and Manage the Service

Start the service using the following command:

```bash
sudo systemctl start nodescan.service
```

**Check the Service Status:**

```bash
sudo systemctl status nodescan.service
```

You should see an output indicating that the service is active and running. For example:

```
● nodescan.service - Nodescan Telegram Bot Service
     Loaded: loaded (/etc/systemd/system/nodescan.service; enabled; vendor preset: enabled)
     Active: active (running) since Tue 2024-09-17 00:10:34 UTC; 1min ago
   Main PID: 211225 (python3)
      Tasks: 2 (limit: 1152)
     Memory: 50.0M
     CGroup: /system.slice/nodescan.service
             └─211225 /usr/bin/python3 /root/nodescan/nodescan.py
```

**View Logs:**

To monitor the service logs in real-time, use:

```bash
journalctl -u nodescan.service -f
```

## Usage

Once the bot is up and running, interact with it via Telegram using the available commands.

### Available Commands

- **`/start` or `/help`**: Display a welcome message with available commands.
- **`/last100`**: Fetch the status of the last 100 blocks.
- **`/last500`**: Fetch the status of the last 500 blocks.
- **`/last1000`**: Fetch the status of the last 1,000 blocks.
- **`/last2000`**: Fetch the status of the last 2,000 blocks.
- **`/last5000`**: Fetch the status of the last 5,000 blocks.
- **`/last10000`**: Fetch the status of the last 10,000 blocks.
- **`/last25000`**: Fetch the status of the last 25,000 blocks.
- **`/last50000`**: Fetch the status of the last 50,000 blocks.
- **`/last100000`**: Fetch the status of the last 100,000 blocks.
- **`/status`**: Check the current status of your validator node.
- **`/set_alert`**: Register the current chat to receive missed block alerts.
- **`/unset_alert`**: Unregister the current chat from receiving alerts.

**Example Interaction:**

1. **Start the Bot:**

    ```text
    /start
    ```

    **Bot Response:**

    ```
    👋 Hello! I'm your Validator Node Monitor Bot.

    📋 **Available Commands:**
    /last100 - Fetch the last 100 blocks
    /last500 - Fetch the last 500 blocks
    /last1000 - Fetch the last 1,000 blocks
    /last2000 - Fetch the last 2,000 blocks
    /last5000 - Fetch the last 5,000 blocks
    /last10000 - Fetch the last 10,000 blocks
    /last25000 - Fetch the last 25,000 blocks
    /last50000 - Fetch the last 50,000 blocks
    /last100000 - Fetch the last 100,000 blocks
    /status - Check the current status of your validator node
    /set_alert - Register this chat to receive missed block alerts
    /unset_alert - Unregister this chat from receiving alerts
    ```

2. **Set Up Alerts:**

    ```text
    /set_alert
    ```

    **Bot Response:**

    ```
    ✅ This chat will now receive alerts for missed blocks.
    ```

3. **Fetch Last 1000 Blocks:**

    ```text
    /last1000
    ```

    **Bot Response:**

    ```
    🔍 Fetching the last 1,000 blocks. Please wait...
    ```

    *(After processing)*

    ```
    📊 **Last 1000 Blocks Status:**
    🆙 Latest Block: 123456
    🟢 Signed Blocks: 995
    🔴 Missed Blocks: 5

    **Missed Blocks (Showing up to 100):**
    Block 123450
    Block 123452
    Block 123455
    Block 123460
    Block 123465
    ```

## Troubleshooting

If you encounter issues while setting up or running the bot, follow these steps:

### 1. **Check Service Status and Logs**

- **View Service Status:**

    ```bash
    sudo systemctl status nodescan.service
    ```

- **View Real-Time Logs:**

    ```bash
    journalctl -u nodescan.service -f
    ```

### 2. **Common Issues and Solutions**

- **Import Errors:**

    ```text
    ImportError: cannot import name 'executor' from 'aiogram.utils'
    ```

    **Solution:** Ensure you're using the compatible version of `aiogram`. Install version `2.25.1`:

    ```bash
    pip install aiogram==2.25.1
    ```

- **Environment Variables Not Loaded:**

    Ensure the `.env` file is correctly placed in `/root/nodescan/` and has the necessary variables.

- **Permission Issues:**

    Since the service runs as `root`, ensure that all files in `/root/nodescan/` have the appropriate permissions.

- **Service Failing to Start:**

    Review the service logs for specific error messages and address them accordingly.

### 3. **Run the Script Manually for Debugging**

To identify script-specific issues, run it manually:

```bash
python3 /root/nodescan/nodescan.py
```

Monitor for any error messages and resolve them as needed.

## Contributing

Contributions are welcome! If you find bugs or have feature requests, please open an issue or submit a pull request.

### **Steps to Contribute:**

1. **Fork the Repository**
2. **Create a New Branch:**

    ```bash
    git checkout -b feature/YourFeatureName
    ```

3. **Make Your Changes**
4. **Commit Your Changes:**

    ```bash
    git commit -m "Add Your Feature"
    ```

5. **Push to Your Fork:**

    ```bash
    git push origin feature/YourFeatureName
    ```

6. **Open a Pull Request**

## License

This project is licensed under the [MIT License](LICENSE).

---

**Disclaimer:** Use this bot at your own risk. Ensure you understand the security implications of running scripts as the root user. It's recommended to create a dedicated user for running such services to enhance security.

```
