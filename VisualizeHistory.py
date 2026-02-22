import os
import subprocess

# specify the working directory for the subprocess
working_directory = "./../../"
gource_executables = ["gource", "gource.cmd"]
gource_exceptions = []
gource_found = False

# change the working directory to a different directory
os.chdir(working_directory)

# Get project name
project_name = os.path.basename(os.getcwd())

# Print controls
if project_name:
    print(f'History Visualization for project: "{project_name}"')
else:
    print("History Visualization")
print("""
Gource Controls:

  (SPACE) Pause/resume                   (LEFT-MOUSE) Manually control camera
  (RIGHT-MOUSE) Rotate camera            (V or MIDDLE-MOUSE) Toggle camera mode
  (C)   Displays Gource logo             (K)   Toggle file extension key
  (M)   Toggle mouse visibility          (N)   Jump to next log entry
  (S)   Randomize colours                (D)   Cycle directory name mode
  (F)   Cycle file name mode             (U)   Cycle user name mode
  (G)   Toggle users display             (T)   Toggle directory tree edges
  (R)   Toggle root directory edges      (+ -) Adjust simulation speed
  (< >) Adjust time scale                (TAB) Cycle visible users
  (F12) Screenshot                       (Alt+Enter) Fullscreen toggle
  (ESC) Quit

 * Camera modes: Track activity / show entire tree

 * While paused you may use the mouse to inspect the detail of individual files
   and users.\n""")
input("Press Enter to continue...\n")

# Set Gource parameters
cam_mode = "overview"
background = "111111"
seconds_per_day = "24"
auto_skip_seconds = "1"
file_idle_time = "0"
max_file_lag = "1"
bloom_multiplier = "0.5"
bloom_intensity = "0.5"
branch_elasticity = "0.0001"

title = f"Interactive Commit History: {project_name}"
logo_path = "Scripts/VisualizeHistory/Graphic.png"

# Try running gource and gource.cmd
for gource_executable in gource_executables:
    parameters = [
        gource_executable,
        "-f",
        "--title", title,
        "--camera-mode", cam_mode,
        "--background", background,
        "--seconds-per-day", seconds_per_day,
        "--auto-skip-seconds", auto_skip_seconds,
        "--file-idle-time", file_idle_time,
        "--max-file-lag", max_file_lag,
        "--key",
        "--bloom-multiplier", bloom_multiplier,
        "--bloom-intensity", bloom_intensity,
        "-e", branch_elasticity,
        "--highlight-users"
    ]

    if os.path.exists(logo_path):
        parameters.extend(["--logo", logo_path])

    try:
        # run the command and capture the output
        process = subprocess.Popen(parameters, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # print the output to the console
        for line in process.stdout:
            print(line.decode().strip())

        # check if there were any errors
        error = process.stderr.read().decode().strip()
        if error:
            print("Error running Gource:", error)

        # Exit the loop if the command executed successfully
        print(f"Gource executable found: {gource_executable}\n")
        gource_found = True
        break

    except Exception as e:
        gource_exceptions.append(gource_executable)

if not gource_found:
    print(f"No suitable Gource executable found. Tried: {gource_executables}")
    print(f"Gource executables that raised an exception: {gource_exceptions}\n")

input("Press Enter to close...")
