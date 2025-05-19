📦 Installation Instructions
🖥 macOS
bash
Copy
Edit
# Install Python (if not installed)
brew install python

# Clone the project and install requirements
git clone <repo-url>
cd <repo-folder>
pip install -r requirements.txt

# Run
python3 system_monitor.py &
🪟 Windows
Install Python

Open PowerShell as Administrator:

powershell
Copy
Edit
git clone <repo-url>
cd <repo-folder>
python -m pip install -r requirements.txt
python system_monitor.py
To run it in background:

Use pythonw.exe or create a scheduled task.

🐧 Linux
bash
Copy
Edit
sudo apt install python3 python3-pip -y
git clone <repo-url>
cd <repo-folder>
pip3 install -r requirements.txt
python3 system_monitor.py &
(Optional: Create a systemd service for startup)

✅ requirements.txt
txt
Copy
Edit
requests