# 🎨 Virtual Painter

This project is a professional-grade virtual painting application that transforms your webcam into an interactive canvas, enabling you to create digital art using hand gestures or mouse controls. If you find this repository helpful or interesting, please consider giving it a star! ⭐

## Why Star This Repository?

- It helps others discover the project.
- It motivates continued maintenance and improvement.
- It supports open-source development!

## How to Contribute

If you want to contribute, feel free to fork the repository and submit a pull request. Also, don’t forget to star the repo!

Thanks for your support! ❤

[Star the project](https://github.com/sayyedrabeeh/virtual-painter)

### 🖼️ Demo Videos

<a href="https://youtu.be/AXkNGLHpuh4" target="_blank">
  <img src="/screenshots/vp1.jpg" alt="Virtual Painter Demo 1" />
</a>

<a href="https://youtu.be/AXkNGLHpuh4" target="_blank">
  <img src="/screenshots/vp2.jpg" alt="Virtual Painter Demo 2" />
</a>

## ✨ Features

- **Intuitive Controls** - Paint using either hand gestures (via webcam) or traditional mouse input.
- **Multiple Tools** - Brush, Eraser, Rectangle (outline & filled), Circle (outline & filled), and Line tools.
- **Color Palette** - Choose from 12 vibrant colors.
- **Adjustable Brush Sizes** - Customize brush thickness for precise control.
- **Gesture Recognition** - Uses MediaPipe hand tracking for gesture and drawing detection.
- **Canvas Manipulation** - Clear canvas option to start fresh.
- **Smooth Drawing** - Point averaging for smoother lines and reduced jitter.
- **Professional UI** - Clean, intuitive interface with visual feedback.

## 🚀 Run Without Installing Python

If you don’t want to install Python or dependencies manually, use the pre-built `.exe`:

1. Download the `.exe` file from the [Releases Section](https://github.com/sayyedrabeeh/virtual-painter/releases).
2. Ensure your system has a working webcam connected.
3. Double-click the `.exe` file to launch the app.
4. Start drawing using your mouse or hand gestures.

> ⚠️ **Note:** Windows SmartScreen may block the file. Click **“More Info” → “Run Anyway”** to continue.

## 🖥️ Requirements

- Python 3.6+
- OpenCV (`opencv-python`)
- NumPy
- MediaPipe
- Webcam (for hand gesture functionality)

## 📋 Installation

1. Clone this repository:
   ```bash
   git clone [https://github.com/sayyedrabeeh/virtual-painter.git](https://github.com/sayyedrabeeh/virtual-painter.git)
   cd virtual-painter
   ```

2. Install the required packages:
   ```bash
   pip install opencv-python numpy mediapipe pytesseract textblob reportlab
   ```

3. Run the application:
   ```bash
   python virtual_painter.py
   ```

## 🎮 How to Use

### Mouse Controls
- **Select Colors/Tools**: Click on the buttons at the top of the screen.
- **Draw**: Click and drag on the canvas area.
- **Create Shapes**: Click to set the starting point, drag to adjust size/position, and release.

### Hand Gesture Controls
- **UI Interaction**: Move your index finger to the top of the screen to select tools and colors.
- **Drawing**:
  - Keep your index finger up (middle finger down) to draw.
  - Index and middle fingers together enter selection mode.
  - Three fingers up forces idle mode.
  - For shapes, start drawing at the initial position and release to place.

## 💫 Support This Project

If you find Virtual Painter fun, helpful, or inspiring, please consider giving it a ⭐️ on GitHub!

![GitHub Repo stars](https://img.shields.io/github/stars/sayyedrabeeh/virtual-painter?style=social)

## 🙏 Acknowledgements

- [OpenCV](https://opencv.org/) - Computer vision functionality.
- [MediaPipe](https://mediapipe.dev/) - Hand tracking capabilities.
- [NumPy](https://numpy.org/) - Numerical operations.
