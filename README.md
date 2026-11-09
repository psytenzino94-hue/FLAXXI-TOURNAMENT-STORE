# FLAXXI ESPORTS

Premium esports tournament platform for Free Fire and PUBG Mobile.

## Included
- Player registration and login
- Free tournament registration (Solo / Duo / Squad)
- Admin approval/rejection workflow
- Admin creates tournaments and sets match room details
- Room ID/password shown only to approved participants
- Winner/leaderboard management
- PostgreSQL on Render, SQLite for local development
- Responsive neon esports UI

## Run locally
1. Install Python 3.10+
2. `pip install -r requirements.txt`
3. Set environment variables:
   - `SECRET_KEY` to a long random value
   - `ADMIN_USERNAME` (default: `flaxxiadmin`)
   - `ADMIN_PASSWORD` (required for admin login)
4. `python app.py`
5. Open `http://127.0.0.1:5000`

## Deploy on Render
1. Upload this folder to a GitHub repository.
2. In Render choose **New + → Blueprint** and connect the repository.
3. Render reads `render.yaml`. Enter a strong value for `ADMIN_PASSWORD` when prompted.
4. Deploy. Open `/admin/login` and sign in using `ADMIN_USERNAME` and the password you set.
5. Change the admin username in Render environment variables if desired.

## Important production notes
- Keep `SECRET_KEY` and `ADMIN_PASSWORD` private. Never commit real credentials.
- Use Render PostgreSQL so tournament data persists across deploys.
- The included demo tournaments are inserted only when the database is empty.
- This starter does not process payments or guarantee prizes. Add only lawful, clearly explained community rewards and publish tournament rules before accepting registrations.
- For a public launch, add email verification, rate limiting, CSRF protection, backups, privacy policy, and terms before collecting real player data.
