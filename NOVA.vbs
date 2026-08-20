Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("Wscript.Shell")
sh.CurrentDirectory = root
pythonw = root & "\runtime\pythonw.exe"
runpy = root & "\run.py"
bat = root & "\NOVA.bat"
If fso.FileExists(pythonw) Then
  sh.Run """" & pythonw & """ """ & runpy & """", 0, False
Else
  sh.Run "cmd /c """ & bat & """", 1, False
End If
