Set Shell = CreateObject("WScript.Shell")
Set Shortcut = Shell.CreateShortcut(Shell.SpecialFolders("Desktop") & "\视频镜头分析.lnk")
Shortcut.TargetPath = "C:\Users\雨下雨停\Desktop\VideoPromptAnalyzer\启动.bat"
Shortcut.WorkingDirectory = "C:\Users\雨下雨停\Desktop\VideoPromptAnalyzer"
Shortcut.IconLocation = "C:\Users\雨下雨停\Desktop\VideoPromptAnalyzer\icon.ico"
Shortcut.Description = "视频镜头分析 & 提示词反推工具"
Shortcut.Save
