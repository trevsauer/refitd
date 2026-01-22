# ReFitD Complete Setup Guide

## For Absolute Beginners - No Experience Required

This guide will walk you through every single step needed to get the ReFitD product viewer running on your computer. We assume you have never used a code editor, terminal, or any programming tools before.

**Time Required:** Approximately 30-45 minutes

**What You'll Install:**
- Visual Studio Code (a text/code editor)
- Python (the programming language)
- Git (for downloading the project)
- The ReFitD project itself

---

# Part 1: Determine Your Computer Type

Before we begin, you need to know what type of computer you have.

## For Mac Users:

1. Click the **Apple logo** (🍎) in the top-left corner of your screen
2. Click **"About This Mac"**
3. Look for the **"Chip"** or **"Processor"** information:
   - If it says **"Apple M1"**, **"Apple M2"**, **"Apple M3"**, or **"Apple M4"** → You have an **Apple Silicon Mac**
   - If it says **"Intel"** → You have an **Intel Mac**

Write this down - you'll need it later!

## For Windows Users:

1. Press the **Windows key** on your keyboard
2. Type **"About"** and click **"About your PC"**
3. Look for **"System type"**:
   - If it says **"64-bit operating system, x64-based processor"** → You have a **64-bit Windows PC**
   - If it says **"ARM-based processor"** → You have an **ARM Windows PC**

---

# Part 2: Install Visual Studio Code

Visual Studio Code (VS Code) is a free program where you can view and edit code files.

## For Mac:

1. Open your web browser (Safari, Chrome, etc.)
2. Go to: **https://code.visualstudio.com**
3. Click the big blue **"Download for Mac"** button
4. Wait for the download to complete
5. Open your **Downloads** folder (click the smiley face icon in your dock, then click "Downloads" on the left)
6. Find the file called **"Visual Studio Code"** (it might be in a .zip file)
7. If it's a .zip file, double-click it to unzip
8. Drag the **"Visual Studio Code"** application into your **"Applications"** folder
9. Open your **Applications** folder and double-click **"Visual Studio Code"** to open it
10. If you see a warning saying "Visual Studio Code is an app downloaded from the internet. Are you sure you want to open it?" → Click **"Open"**

## For Windows:

1. Open your web browser (Edge, Chrome, etc.)
2. Go to: **https://code.visualstudio.com**
3. Click the big blue **"Download for Windows"** button
4. Wait for the download to complete
5. Open your **Downloads** folder
6. Double-click the file called **"VSCodeUserSetup-x64-[version].exe"**
7. If Windows asks "Do you want to allow this app to make changes?" → Click **"Yes"**
8. Follow the installation wizard:
   - Click **"I accept the agreement"**
   - Click **"Next"** on each screen
   - ✅ CHECK the box that says **"Add to PATH"** (this is important!)
   - Click **"Install"**
   - Click **"Finish"**

---

# Part 3: Install Python

Python is the programming language that runs the ReFitD viewer.

## For Mac:

1. Open your web browser
2. Go to: **https://www.python.org/downloads/**
3. Click the big yellow button that says **"Download Python 3.x.x"** (the numbers may vary)
4. Wait for the download to complete
5. Open your **Downloads** folder
6. Double-click the file called **"python-3.x.x-macos[...].pkg"**
7. Follow the installation wizard:
   - Click **"Continue"** on each screen
   - Click **"Agree"** to accept the license
   - Click **"Install"**
   - Enter your Mac password if asked
   - Click **"Close"** when done

## For Windows:

1. Open your web browser
2. Go to: **https://www.python.org/downloads/**
3. Click the big yellow button that says **"Download Python 3.x.x"**
4. Wait for the download to complete
5. Open your **Downloads** folder
6. Double-click the file called **"python-3.x.x-amd64.exe"**
7. **⚠️ IMPORTANT:** At the bottom of the first screen, CHECK the box that says:
   **"Add python.exe to PATH"**
8. Click **"Install Now"**
9. Wait for installation to complete
10. Click **"Close"**

---

# Part 4: Install Git

Git is a tool that lets you download code projects from the internet.

## For Mac:

Mac might already have Git installed. Let's check:

1. Open **Terminal**:
   - Press **Command (⌘) + Spacebar** on your keyboard
   - Type **"Terminal"**
   - Press **Enter** or click on the Terminal app

2. In the Terminal window, type exactly:
   ```
   git --version
   ```
3. Press **Enter**

4. **If you see a version number** (like "git version 2.39.0") → Git is already installed! Skip to Part 5.

5. **If you see a popup asking to install developer tools** → Click **"Install"** and wait for it to complete.

6. **If you see an error** → Continue with manual installation:
   - Go to: **https://git-scm.com/download/mac**
   - Download and install Git following the on-screen instructions

## For Windows:

1. Open your web browser
2. Go to: **https://git-scm.com/download/win**
3. The download should start automatically. If not, click **"Click here to download manually"**
4. Open your **Downloads** folder
5. Double-click the file called **"Git-[version]-64-bit.exe"**
6. If Windows asks permission, click **"Yes"**
7. Follow the installation wizard:
   - Click **"Next"** on each screen (the default options are fine)
   - Click **"Install"**
   - Click **"Finish"**

---

# Part 5: Opening the Terminal

The Terminal (also called Command Prompt on Windows) is where you type commands to control your computer.

## For Mac:

1. Press **Command (⌘) + Spacebar**
2. Type **"Terminal"**
3. Press **Enter**

A window will open with a blank line and a blinking cursor. This is where you'll type commands.

## For Windows:

1. Press the **Windows key** on your keyboard
2. Type **"cmd"**
3. Click on **"Command Prompt"**

A black window will open with a blinking cursor. This is where you'll type commands.

---

# Part 6: Create a Folder for Projects

Let's create a dedicated folder on your Desktop to store the project.

## For Mac:

In your Terminal window, type these commands ONE AT A TIME. Press **Enter** after each one:

```
cd ~/Desktop
```

```
mkdir projects
```

```
cd projects
```

**What these commands do:**
- `cd ~/Desktop` → Navigates to your Desktop folder
- `mkdir projects` → Creates a new folder called "projects"
- `cd projects` → Goes inside that folder

## For Windows:

In your Command Prompt window, type these commands ONE AT A TIME. Press **Enter** after each one:

```
cd %USERPROFILE%\Desktop
```

```
mkdir projects
```

```
cd projects
```

---

# Part 7: Download the ReFitD Project

Now we'll download the actual project files from GitHub.

## For Mac & Windows:

In your Terminal/Command Prompt, type:

```
git clone https://github.com/trevsauer/refitd.git
```

Press **Enter** and wait. You'll see text appearing showing the download progress.

When it's done, type:

```
cd refitd
```

Press **Enter**. You are now inside the project folder.

---

# Part 8: Install Project Requirements

The project needs additional Python packages to run. Let's install them.

## For Mac:

In your Terminal, type:

```
pip3 install -r requirements.txt
```

Press **Enter** and wait. You'll see lots of text scrolling by as packages are installed. This might take 2-5 minutes.

**If you see an error about "pip3 not found"**, try:
```
python3 -m pip install -r requirements.txt
```

## For Windows:

In your Command Prompt, type:

```
pip install -r requirements.txt
```

Press **Enter** and wait. This might take 2-5 minutes.

**If you see an error about "pip not found"**, try:
```
python -m pip install -r requirements.txt
```

---

# Part 9: Run the Product Viewer

Now you're ready to run the viewer!

## For Mac:

In your Terminal, type:

```
python3 viewer.py --supabase
```

Press **Enter**.

## For Windows:

In your Command Prompt, type:

```
python viewer.py --supabase
```

Press **Enter**.

---

# Part 10: View the Application

After running the command above, you should see output that includes something like:

```
 * Running on http://127.0.0.1:5001
```

or

```
 * Running on http://localhost:5001
```

## To view the application:

1. Open your web browser (Chrome, Safari, Firefox, etc.)
2. In the address bar at the top, type: **http://localhost:5001**
3. Press **Enter**

🎉 **You should now see the ReFitD Product Viewer!**

---

# Part 11: Stopping the Application

When you're done using the viewer:

1. Go back to your Terminal/Command Prompt window
2. Press **Control + C** on your keyboard (hold Control and press C)
3. The application will stop

---

# Part 12: Running the Viewer Again Later

If you close everything and want to run the viewer again another day:

## For Mac:

1. Open **Terminal** (Command + Spacebar, type "Terminal", press Enter)
2. Type these commands:
   ```
   cd ~/Desktop/projects/refitd
   ```
   Press Enter, then:
   ```
   python3 viewer.py --supabase
   ```
   Press Enter.
3. Open your browser and go to **http://localhost:5001**

## For Windows:

1. Open **Command Prompt** (Windows key, type "cmd", press Enter)
2. Type these commands:
   ```
   cd %USERPROFILE%\Desktop\projects\refitd
   ```
   Press Enter, then:
   ```
   python viewer.py --supabase
   ```
   Press Enter.
3. Open your browser and go to **http://localhost:5001**

---

# Troubleshooting Common Problems

## "python is not recognized" or "python3 not found"

**Cause:** Python wasn't added to your system PATH during installation.

**Solution for Mac:**
1. Reinstall Python from python.org
2. Or try using `python3` instead of `python`

**Solution for Windows:**
1. Reinstall Python from python.org
2. Make sure to CHECK the box "Add python.exe to PATH" during installation

---

## "pip is not recognized"

**Cause:** pip (Python's package installer) isn't accessible.

**Solution for Mac:**
Try: `python3 -m pip install -r requirements.txt`

**Solution for Windows:**
Try: `python -m pip install -r requirements.txt`

---

## "git is not recognized" or "git not found"

**Cause:** Git wasn't installed properly.

**Solution:** Reinstall Git from https://git-scm.com and restart your Terminal/Command Prompt.

---

## "No module named 'flask'" or similar errors

**Cause:** The required packages weren't installed correctly.

**Solution:** Run the pip install command again:

Mac: `pip3 install -r requirements.txt`

Windows: `pip install -r requirements.txt`

---

## "Address already in use" error

**Cause:** The viewer is already running in another window, or another program is using port 5001.

**Solution:**
1. Check if you have another Terminal/Command Prompt window with the viewer running
2. Close it by pressing **Control + C**
3. Try running the viewer again

---

## The webpage shows "This site can't be reached"

**Cause:** The viewer application isn't running.

**Solution:**
1. Make sure your Terminal/Command Prompt window is still open
2. Make sure you see "Running on http://127.0.0.1:5001" in the terminal
3. If not, run the viewer command again

---

## Nothing happens when I type a command

**Cause:** You might have forgotten to press Enter, or there's invisible characters in your command.

**Solution:**
1. Make sure you press **Enter** after typing each command
2. Try typing the command manually instead of copy-pasting

---

# Opening the Project in VS Code (Optional)

If you want to view or edit the code files:

1. Open **Visual Studio Code**
2. Click **File** → **Open Folder** (Mac: **File** → **Open**)
3. Navigate to: Desktop → projects → refitd
4. Click **Open** or **Select Folder**

You'll now see all the project files in the left sidebar!

---

# Glossary of Terms

| Term | Definition |
|------|------------|
| Terminal | A program where you type commands to control your computer (Mac) |
| Command Prompt | A program where you type commands to control your computer (Windows) |
| Python | A programming language used to build the viewer |
| Git | A tool for downloading and managing code projects |
| Repository (Repo) | A project folder stored on GitHub |
| Clone | To download a copy of a repository |
| pip | Python's tool for installing additional packages |
| localhost | Your own computer acting as a web server |
| Port | A number that identifies a specific program (we use 5001) |

---

# Quick Reference Card

## Start the Viewer

**Mac:**
```
cd ~/Desktop/projects/refitd
python3 viewer.py --supabase
```

**Windows:**
```
cd %USERPROFILE%\Desktop\projects\refitd
python viewer.py --supabase
```

## Stop the Viewer
Press **Control + C** in the Terminal/Command Prompt

## View the Application
Open browser → Go to **http://localhost:5001**

---

# Getting Help

If you encounter any issues not covered in this guide:

1. Take a screenshot of any error messages you see
2. Note which step you were on when the problem occurred
3. Contact the project maintainer with this information

---

*Document Version: 1.0*
*Last Updated: January 2025*
