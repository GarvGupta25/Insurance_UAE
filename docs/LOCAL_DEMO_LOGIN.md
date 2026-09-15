# Local prototype login

Run the following from the repository root after Docker Desktop says **Engine running**:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-prototype.ps1
```

Open `http://127.0.0.1:5174/login` and sign in with one of these local-only demonstration accounts:

| Use case | Email | Password |
| --- | --- | --- |
| Member assigned to a broker | `member@example` | `password` |
| Broker workspace | `broker@example` | `password` |
| Member without a broker | `regular@example` | `password` |

The launcher creates missing accounts and assigns `member@example` to `broker@example`. It does not reset existing local profiles, applications, policies, or servicing history.
