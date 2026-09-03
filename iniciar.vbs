' ============================================================
'  CANELS - Lanzador silencioso
'  Ejecuta el servidor sin mostrar consola negra
'  y abre el navegador automáticamente
' ============================================================

Dim oShell, oFSO, strBase, strPython, strApp

Set oShell = CreateObject("WScript.Shell")
Set oFSO   = CreateObject("Scripting.FileSystemObject")

' Directorio base: donde está este .vbs
strBase   = oFSO.GetParentFolderName(WScript.ScriptFullName)
strPython = strBase & "\venv\Scripts\pythonw.exe"
strApp    = strBase & "\app.py"

' Verificar que el entorno virtual existe
If Not oFSO.FileExists(strPython) Then
    MsgBox "No se encontró el entorno virtual." & vbCrLf & _
           "Ejecuta primero: python setup.py", _
           vbCritical, "CANELS - Error"
    WScript.Quit 1
End If

' Verificar que .env existe
If Not oFSO.FileExists(strBase & "\.env") Then
    MsgBox "No se encontró el archivo .env" & vbCrLf & _
           "Ejecuta primero: python setup.py", _
           vbCritical, "CANELS - Error"
    WScript.Quit 1
End If

' Lanzar el servidor con pythonw (sin ventana de consola)
' 0 = ventana oculta, False = no esperar a que termine
oShell.Run """" & strPython & """ """ & strApp & """", 0, False

' Esperar unos segundos a que Flask arranque
WScript.Sleep 3000

' Abrir el navegador predeterminado en la app
oShell.Run "http://localhost:5000", 1, False

Set oShell = Nothing
Set oFSO   = Nothing