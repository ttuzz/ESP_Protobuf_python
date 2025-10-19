@echo off
REM Generate Python and (optionally) nanopb C files from .proto definitions

REM Resolve script directory
set SCRIPT_DIR=%~dp0

REM Compute absolute path of the script directory and print it for debugging
pushd "%SCRIPT_DIR%" >nul 2>&1
set SCRIPT_ABS=%CD%
popd >nul 2>&1
REM Use Windows 'color' to highlight important lines in yellow (foreground E) briefly.
REM Note: this changes the whole console color while the highlighted lines print.
color 0E >nul 2>&1
echo Batch script directory (%%~dp0): %SCRIPT_DIR%
echo Batch script absolute path: %SCRIPT_ABS%
color 07 >nul 2>&1

REM Compute repository root (absolute) by moving up one directory from script dir
pushd "%SCRIPT_DIR%.." >nul 2>&1
set REPO_ROOT=%CD%
popd >nul 2>&1

set PROTO_FILE=%REPO_ROOT%\proto\message.proto
set OUTPUT_DIR=%REPO_ROOT%\py_scripts
set OUTPUT_C_DIR=%REPO_ROOT%\src
set OPTIONS_FILE=%REPO_ROOT%\proto\message.options

echo Using proto directory: %REPO_ROOT%\proto
color 0E >nul 2>&1
echo Proto file: "%PROTO_FILE%"
color 07 >nul 2>&1
if exist "%PROTO_FILE%" (
    echo   - proto found
) else (
    echo ERROR: proto file not found at "%PROTO_FILE%"
    exit /b 1
)
echo Options file: "%OPTIONS_FILE%"
if exist "%OPTIONS_FILE%" (
    echo   - options file found
) else (
    echo   - options file missing (nanopb generation may still work but fixed-array options will be absent)
)
echo Python output dir: "%OUTPUT_DIR%"
echo C output dir: "%OUTPUT_C_DIR%"

REM Locate protoc: prefer the copy under %SCRIPT_DIR%\protoc\bin\protoc.exe, then a protoc.exe next to the script, then any on PATH, then a common fallback
set LOCAL_PROTOC=%SCRIPT_DIR%protoc\bin\protoc.exe
set LOCAL_PROTOC2=%SCRIPT_DIR%protoc.exe
set PROTOC_PATH=
if exist "%LOCAL_PROTOC%" (
    set PROTOC_PATH=%LOCAL_PROTOC%
) else (
    if exist "%LOCAL_PROTOC2%" (
        set PROTOC_PATH=%LOCAL_PROTOC2%
    )
)
if not defined PROTOC_PATH (
    for /f "delims=" %%i in ('where protoc 2^>nul') do (
        set PROTOC_PATH=%%i
        goto :protoc_found
    )
)
if not defined PROTOC_PATH (
    set PROTOC_PATH=C:\protoc\bin\protoc.exe
)
:protoc_found

if not exist "%PROTOC_PATH%" (
    echo ERROR: protoc not found. Put protoc.exe under "%SCRIPT_DIR%\protoc\\bin\protoc.exe" or next to this script, or install protoc and add it to PATH.
    echo Tried: %LOCAL_PROTOC% , %LOCAL_PROTOC2% , PATH and fallback C:\protoc\bin\protoc.exe
    exit /b 1
)

echo Using protoc: %PROTOC_PATH%

REM Run the python generation step
"%PROTOC_PATH%" --python_out="%OUTPUT_DIR%" --proto_path="%REPO_ROOT%\proto" "%PROTO_FILE%"
if %errorlevel% neq 0 (
    echo Protobuf ^(Python^) generation failed.
    exit /b %errorlevel%
)
color 0E >nul 2>&1
echo Protobuf (Python) generation succeeded.
color 07 >nul 2>&1

REM Attempt to locate protoc-gen-nanopb plugin: prefer local copy, then PATH
set LOCAL_NANOPB=%SCRIPT_DIR%protoc-gen-nanopb.exe
set NANOPB_PLUGIN=
if exist "%LOCAL_NANOPB%" (
    set NANOPB_PLUGIN=%LOCAL_NANOPB%
)
if not defined NANOPB_PLUGIN (
    for /f "delims=" %%p in ('where protoc-gen-nanopb.exe 2^>nul') do (
        set NANOPB_PLUGIN=%%p
        goto :nanopb_found
    )
)

:nanopb_found
if not defined NANOPB_PLUGIN (
    call :download_nanopb
)
if not defined NANOPB_PLUGIN (
    echo WARNING: protoc-gen-nanopb plugin not found locally or on PATH and automatic download failed. Skipping nanopb C generation.
    echo To enable C generation manually: download protoc-gen-nanopb.exe and place it in "%SCRIPT_DIR%" or add it to PATH.
    exit /b 0
)

echo Using nanopb plugin: %NANOPB_PLUGIN%

REM Run nanopb generation
"%PROTOC_PATH%" --plugin=protoc-gen-nanopb="%NANOPB_PLUGIN%" --nanopb_out="%OUTPUT_C_DIR%" --proto_path="%REPO_ROOT%\proto" "%PROTO_FILE%"
if %errorlevel% neq 0 (
    echo Nanopb C generation failed ^(plugin error^). Check the plugin and protoc versions.
    exit /b %errorlevel%
)
echo Nanopb C generation succeeded; files written to %OUTPUT_C_DIR%.

:download_nanopb
echo WARNING: protoc-gen-nanopb plugin not found locally or on PATH.
echo Attempting to download protoc-gen-nanopb.exe from nanopb releases into "%SCRIPT_DIR%" ...
set DOWNLOAD_URL=https://github.com/nanopb/nanopb/releases/latest/download/protoc-gen-nanopb.exe
echo Download URL: %DOWNLOAD_URL%
echo Using PowerShell Invoke-WebRequest to download (requires internet access).
powershell -Command "Try { Invoke-WebRequest -Uri '%DOWNLOAD_URL%' -OutFile '%SCRIPT_DIR%protoc-gen-nanopb.exe' -UseBasicParsing; exit 0 } Catch { exit 1 }"
if exist "%SCRIPT_DIR%protoc-gen-nanopb.exe" (
    echo Download succeeded; using downloaded plugin.
    set NANOPB_PLUGIN=%SCRIPT_DIR%protoc-gen-nanopb.exe
) else (
    echo Automatic download failed or is blocked.
)
goto :eof