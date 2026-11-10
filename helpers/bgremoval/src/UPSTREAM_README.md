# Apple Vision Mask for TouchDesigner

A high-performance C++ TOP plugin for TouchDesigner that utilizes Apple's native Vision framework (`VNGeneratePersonSegmentationRequest`) to perform real-time person segmentation and background removal. This plugin is designed for macOS, specifically leveraging Apple Silicon for hardware-accelerated inference.

## Features

*   **Asynchronous Inference (60 FPS Ready):** Optimized processing runs on a background queue. The plugin reuses model requests to maintain maximum performance.
*   **Frame-Perfect Synchronization:** The plugin maintains a queue of input frames and outputs a **delayed original image** that perfectly matches the latency of the asynchronous mask.
*   **Steady Framerate:** Even when the mask is processing, the node continues to output at the full TouchDesigner frame rate (e.g., 60fps), avoiding stuttering.
*   **High-Quality Resizing:** Uses bilinear interpolation to upscale the segmentation mask to match the input resolution for smoother edges.
*   **Adjustable Quality:** Choose between 'Accurate', 'Balanced', or 'Fast' modes.
*   **Diagnostic Info:** Includes Info CHOP channels to monitor processing latency and internal queue state.

## Requirements

*   **Operating System:** macOS (optimized for Apple Silicon / arm64).
*   **Software:** TouchDesigner (Commercial or Pro).
*   **Hardware:** Apple Silicon (M1/M2/M3) recommended.

## Building the Plugin

1.  Open a terminal and navigate to the project root directory.
2.  Create a build directory:
    ```bash
    mkdir build
    cd build
    ```
3.  Generate the build files using CMake:
    ```bash
    cmake ..
    ```
4.  Compile the plugin:
    ```bash
    make
    ```

## Usage in TouchDesigner

The plugin provides two synchronized output buffers:
1.  **Output 0 (Main):** The Alpha Mask or Composited image (based on "Output Mode").
2.  **Output 1:** The **Delayed Original Image** (synchronized to the mask's latency).

### How to access the Second Output:
1.  Create your **CPlusPlus TOP** and load the plugin.
2.  Create a **Render Select TOP**.
3.  In the "TOP" parameter of the Render Select, point it to your CPlusPlus TOP.
4.  Set the **Color Buffer Index** parameter to `1`.

### Monitoring Performance:
Connect an **Info CHOP** to the CPlusPlus TOP to see:
*   `latency_frames`: How many frames behind the current input the output is (typically 2-4 frames depending on quality).
*   `queue_size`: The number of frames currently stored in the internal delay line.

## Parameters

*   **Opacity:** Controls the alpha transparency of the output.
*   **Output Mode:** *Composited* or *Mask Only*.
*   **Vision Quality:** *Accurate*, *Balanced*, or *Fast*. Use **Fast** for the lowest latency at 60fps.
*   **Process Every N Frames:** Skips segmentation updates to save resources.

## License

MIT License
