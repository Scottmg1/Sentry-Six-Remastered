# SentrySix Remastered

SentrySix-Remastered is a multi-camera TeslaCam viewer built with Python and PyQt6 with the help of Google AIStudio's Gemini 2.5 Pro Model and original SentrySix by ChadR23 (https://github.com/ChadR23/Sentry-Six)

---

## 🚗 Features

-  **6-Camera Playback** — View front, back, repeater, and pillar footage in a synchronized grid
-  **Zoom & Pan** - Zoom in to a camera view by hovering over the camera you want to zoom and using your scroll wheel.
-  **Adjustable Playback Speed** - Adjust your playback speed of your clips from 0.5x all the way to 4x
-  **Frame Forward/Backward & 15 Second Skip Forward/Backward** You can click the FR to adjust the frame displayed to capture the perfect moment of a shot you need. (Like a license plate.) Or skip at 15 second intervals.
-  **Real-Time Timestamps** — Time synced from Tesla’s clip names
-  **Toggle Cameras Shown** - Toggle between having 1-6 Camera Views shown at a time. With an option to reset the layout to the original 6 Camera Layout
-  **Go to Timestamp with Preview** - Enter a 24 hour time you wish to go to and press OK. Before confirming the time you would like to go to you'll get a preview of the front camera at that set timestamp.

---

## 📸 Layout & Photos

- **All Cameras (3x2)**
  > Front / Back / Repeaters / Pillars in a grid layout
  ![Camera Overview](https://github.com/user-attachments/assets/3b73e2cc-c788-4ef0-aa20-1c4b183a0cb7)

- **Single Camera View**
  ![Single Camera](https://github.com/user-attachments/assets/727c7a3c-e5e7-4734-b6e6-66ae355e435d)

- **Timestamp & Preview**
  > Enter a timestamp and see a preview
  ![Timestamp Preview](https://github.com/user-attachments/assets/00c88db2-dc54-4dbc-9787-c7a2e06b8c4c)

- **Playback Speed Adjustment**
  > Adjust your playback speed.
  ![Playback Options](https://github.com/user-attachments/assets/78b513bb-b064-4e4d-8099-d87876778ff0)


---

## 🛠 Requirements

- Python 3.10+
- PyQt6
- FFmpeg (must be in system PATH)

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 🧪 Usage

1. Launch **main.py**
2. Click **“Select RecentClips Folder”** 
3. Click the **Date** dropdown and select the date you want to view.

---

## 🔒 License

MIT License — See [LICENSE](LICENSE) file

---

## 🙌 Credits

Built with ❤️ by Chad — Inspired by TeslaCam’s incredible capture system
Remastered with Google AIStudio and Gemini 2.5 Pro by Scott
