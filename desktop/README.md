# LoanHub Desktop — Phase 2

C# / .NET 10 / WPF standalone Windows shell. This is a foundation module, not a production offline loan system.

Implemented: overview, device identity encrypted using Windows DPAPI CurrentUser, local HTTPS endpoint setting and safe network probe. The account sign-in action is deliberately disabled.

NOT implemented: authenticated login, server enrollment and revocation, employee authorization, offline database, CRUD, transaction outbox, synchronization, real repayment processing or MSI signing. Never enter live customer data.

## Windows build

Install [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0), open PowerShell from the repository root, and run:

```powershell
cd desktop
.\packaging\build-windows.ps1
.\artifacts\publish\LoanHub.Desktop.exe
```

Portable package: `desktop/artifacts/LoanHub-Desktop-win-x64.zip`. No MSI installer is yet provided. GitHub Actions also publishes this ZIP as a run artifact. Because authentication is disabled, HTTPS connectivity alone never grants application access.
