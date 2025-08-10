# 📥 Telegram Media Downloader (Paged + Multi-Select + Progress UI)

> **Advanced Telegram downloader** for **user accounts** (not bots) with **paging**, **multi-select**, and a beautiful **progress bar** using [Rich](https://github.com/Textualize/rich).

---

## ✨ Features

- 🔑 **Login as a Telegram user** (not bot) using **API ID** & **API Hash**.
- 📋 **TUI (Terminal User Interface)** to:
  - Select **chat / group / channel** to scan.
  - Media **paging** per batch (default 50 media per page).
  - Navigate between pages without scanning the entire chat (saves time!).
  - **Multi-select** files to download.
- 📊 **Per-file progress bar** powered by **Rich**.
- 💾 Files saved **neatly by type** (`document/`, `video/`, `audio/`, `photo/`).
- 🚀 Downloads run on your VPS → **100% bandwidth from VPS**.

---

## 📦 Requirements

- Python **3.8+**
- Telegram account already **joined** to the target group/channel.
- **API ID** and **API Hash** from [my.telegram.org](https://my.telegram.org).

---

## 🔧 Installation

1. **Clone the repo** (or save the script):
   ```bash
   git clone https://github.com/x666dbg/Telegram-Media-Downloader.git
   cd Telegram-Media-Downloader
   ```

2. **Install dependencies**:
   ```bash
   pip install telethon tqdm
   pip install rich
   # Windows (extra requirement)
   pip install windows-curses
   ```

3. **Edit configuration** inside the script:
   ```python
   API_ID = 666       # Replace with your API ID
   API_HASH = "YOUR_API_HASH_HERE" # Replace with your API Hash
   ```

---

## ▶️ Usage

Run the script:
```bash
python v.py
```

### 1️⃣ Select Chat
- Use **↑/↓** to navigate.
- Press **Enter** to choose a target chat.
- Press **Q** to cancel.

### 2️⃣ Media Picker (Paging)
- **W/S** → Move cursor within the page.
- **→ Right** → Select highlighted file.
- **← Left** → Deselect highlighted file.
- **↑ Up** → Go to previous page.
- **↓ Down** → Go to next page (scans a new batch).
- **Enter** → Start downloading selected files.
- **Q** → Exit without downloading.

> 📌 **Tip:** Initially only the first 50 media are scanned.  
> Moving to the next page scans another 50 media, making it faster & more resource-friendly.

### 3️⃣ Progress Bar
- While downloading, each file shows:
  - File name
  - Progress bar
  - Downloaded size
  - Speed
  - Estimated time remaining

---

## 📂 Output Structure

The output folder will contain subfolders by file type:
```
result/date-month-year
├── document/
├── video/
├── audio/
└── photo/
```
Files are prefixed with `msg_id_` for uniqueness.

---

## ⚠️ Important Notes

- **Only** for user accounts. **Bot API** cannot read history before the bot joins.
- Do not share the `tg_session.session` file — it is your login credential.
- Use this script legally and **respect copyrights**.

---

## 📝 License

This script is free to use and modify, but use it at your own risk.  
No warranty is provided regarding security, legality, or results.
