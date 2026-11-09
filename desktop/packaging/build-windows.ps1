$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$publish = Join-Path $root 'artifacts\publish'
if (!(Get-Command dotnet -ErrorAction SilentlyContinue)) { throw 'Install .NET 10 SDK before building.' }
dotnet restore (Join-Path $root 'LoanHub.Desktop\LoanHub.Desktop.csproj')
if ($LASTEXITCODE -ne 0) { throw 'Restore failed.' }
dotnet publish (Join-Path $root 'LoanHub.Desktop\LoanHub.Desktop.csproj') -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o $publish
if ($LASTEXITCODE -ne 0) { throw 'Publish failed.' }
New-Item -ItemType Directory -Force (Join-Path $root 'artifacts') | Out-Null
Compress-Archive -Path (Join-Path $publish '*') -DestinationPath (Join-Path $root 'artifacts\LoanHub-Desktop-win-x64.zip') -Force
Write-Host "Executable: $(Join-Path $publish 'LoanHub.Desktop.exe')"
