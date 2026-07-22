Set sh = CreateObject("WScript.Shell")
root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
appDir = root & "\my-project"
uvicorn = root & "\.venv\Scripts\uvicorn.exe"
port = 8006
url = "http://127.0.0.1:" & port & "/login"

On Error Resume Next
Set http = CreateObject("MSXML2.XMLHTTP")
http.Open "GET", "http://127.0.0.1:" & port & "/health", False
http.Send
If http.Status = 200 Then
  sh.Run "cmd /c start """" """ & url & """", 0, False
  WScript.Quit 0
End If
On Error GoTo 0

sh.Run """" & uvicorn & """ main:app --host 127.0.0.1 --port " & port, 0, False
WScript.Sleep 3000
sh.Run "cmd /c start """" """ & url & """", 0, False
