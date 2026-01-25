# ONYX: The Offline Desktop Agent

> **"It's not just a chatbot. It's an Operating System Overlay."**

Onyx is a Python-based AI Agent that lives on your desktop. It listens to your voice, thinks on your GPU, and controls your computer actions—all without sending a single byte of data to the cloud.

Inspired by the personality of TARS (Interstellar) and the utility of JARVIS.

![UI Screenshot](link_to_your_screenshot_here.png)

## Features (v1.0)
*   **100% Offline:** Runs locally using `Ollama` (Llama-3) and `Faster-Whisper`.
*   **Voice Control:** Wake-word detection ("Hey Onyx") with natural voice interactions.
*   **Agentic Capabilities:**
    *   Open/Close Applications.
    *   Perform Google Searches.
    *   Control System Volume / Screenshots.
*   **Personality Engine:** Sarcastic, dry, and efficient responses.
*   **Privacy First:** No data harvesting. Your microphone stream never leaves localhost.

## Tech Stack
*   **Brain:** Llama-3 8B (via Ollama)
*   **Ears:** Faster-Whisper (CUDA accelerated)
*   **Voice:** Pyttsx3 (Local Neural TTS)
*   **GUI:** Tkinter (Glass-morphism Overlay)

## Hardware Requirements
*   **GPU:** NVIDIA RTX 3060/4060/5050 (Minimum 6GB VRAM recommended).
*   **RAM:** 16GB System RAM.
*   **OS:** Windows 10/11.

## Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/YourUsername/NEURAL-SHELL.git
    cd NeuralShell
    ```

2.  **Initialize the Environment**
    Open a command terminal in this folder and run:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Install the Brain (Ollama)**
    1. Download and install [Ollama for Windows](https://ollama.com/).
    2. Open a new terminal and run:
    ```bash
    ollama run llama3
    ```
    *(This will download the 4.7GB model weights to your local machine).*

4.  **Run Neural-Shell**
    You can simply double-click the **`Run_NeuralShell.bat`** file, or run via terminal:
    ```bash
    python main.py
    ```

## 📜Roadmap
*   [x] v1.0: Core Loop (Voice -> Logic -> Action).
*   [ ] v1.5: Long-term Memory Vector DB.
*   [ ] v2.0: Computer Vision (LLaVA Integration).

⚙️ Usage Guide
Wake Words:
The system listens passively but only engages when addressed.

"Seven..." (Default persona name)
"Computer..."
"System..."
Command Examples:

"Seven, open Visual Studio Code."
"Search for documentation on Python threading."
"Take a screenshot."
"Close Chrome."
"Go to sleep." (Terminates the program).

## License
Distributed under the GPL-3.0 License. See `LICENSE` for more information.