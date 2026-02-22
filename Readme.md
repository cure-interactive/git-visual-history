# Interactive Commit History Visualization with Gource

This script provides an interactive visualization of the commit history of a project using [Gource](https://github.com/acaudwell/Gource), a software version control visualization tool. It allows you to explore the evolution of the project's files and directories over time, and see who made changes to the codebase.

---

## Introduction

Have you ever wanted to explore the history of your project's codebase in an interactive and visual way? This script provides an easy way to create a Gource visualization of your project's commit history. With Gource, you can see how files and directories have evolved over time, and who made changes to them. This can be a great tool for understanding the evolution of your codebase, identifying patterns in development, and even creating videos to showcase your project's progress.

---

## Getting Started
My apologies for the confusion in my previous response. Here's an updated Prerequisites section that includes instructions for installing Python:

### Prerequisites

#### Python

To use this script, you need to have Python installed on your system. Here's how to install it:

1. Go to the [official Python website](https://www.python.org/downloads/) and download the appropriate installer for your operating system.
2. Follow the installation instructions provided in the installer.

Once Python is installed, you should be able to run it from the command line. You can verify that Python is installed correctly by running the command `python --version` in your terminal or command prompt. If Python is installed correctly, you should see the version number printed in the output.

#### Gource

You also need to have Gource installed on your system. Here's how to install it:

1. Go to the official [Gource repository](https://github.com/acaudwell/Gource) on GitHub.
2. Download the appropriate installer for your operating system (Windows, macOS, or Linux).
3. Follow the installation instructions provided in the installer.

Once Gource is installed, you should be able to run it from the command line. You can verify that Gource is installed correctly by running the command `gource --version` in your terminal or command prompt. If Gource is installed correctly, you should see the version number printed in the output.

### Setup

1. Navigate to the directory containing the script.
2. Modify the script with your desired parameters (e.g., working directory, Gource options).
3. Run the script in your terminal or command prompt.

---

## Usage

To run the script, open your terminal or command prompt and navigate to the directory containing the script. Then, run the script with the command:

```python
python visualize_history.py
```

When you run the script, you will be prompted to enter the working directory for the subprocess. This is the directory where the Gource visualization will be created. You can enter a relative or absolute path.

The script will then automatically detect the project name, set Gource parameters, and attempt to run Gource using the available executables (`gource` and `gource.cmd`). You can modify the Gource options in the script to customize the visualization.

Once the Gource visualization is created, you can use the keyboard controls to interact with it. See the Gource Controls section in the script for a list of available controls.

---

## Contributing

If you find any issues or have suggestions for improving the script, please open an issue or submit a pull request on GitHub.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
