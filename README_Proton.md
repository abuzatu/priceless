# Intro

Reading the Proton email for the Priceless program.

# Seed session for a new email

Each Proton address has its own saved browser session. When you change the email in `.env`, the notebook looks for a matching file under `data/proton_email/sessions/` and skips login if it exists.

You need to seed a session when:

- You switch to a **new** `PROTON_EMAIL_ADDRESS_01` in `.env`
- Proton shows **Human Verification** (CAPTCHA) and login times out
- The session file for that email is missing or expired

The notebook runs **inside Docker**, so `headless=False` does **not** open a browser on your Mac. Seed the session once from Chrome on your Mac, then the notebook reuses it.

## 1. Set credentials in `.env`

```bash
PROTON_EMAIL_ADDRESS_01="new.account@proton.me"
PROTON_EMAIL_PASSWORD_01="your-password"
```

Restart the Jupyter kernel after changing `.env`.

## 2. Start Chrome with remote debugging (Mac terminal)

**Quit Chrome completely first** (Cmd+Q — not just close the window). Your normal Chrome window does not open port 9222.

In a **separate Mac terminal** (not inside Docker):

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.proton-chrome-seed" \
  https://account.proton.me/login
```

## 3. Log in and complete Human Verification

In that Chrome window:

- Sign in as the **same email** you set in `.env`
- Complete the Human Verification puzzle if Proton shows it
- Wait until you see the Proton Mail inbox or the apps page

## 4. Save the session for Docker

From the project folder (Docker container must be running: `make start`):

```bash
make proton-seed-session
```

The script checks that Chrome is listening on port 9222, then asks you to press Enter. It writes a session file named from the email, for example:

```text
data/proton_email/sessions/stefan.buzatu21_at_proton.me.json
data/proton_email/sessions/adrian.buzatu.ds_at_proton.me.json
```

(`@` becomes `_at_`, `+` becomes `_plus_`.)

## 5. Run the notebook

Use the default login cell — do **not** pass `headless=False`:

```python
proton = ProtonEmailLogin(debug=True, debug_version=proton_debug_version)
try:
    details = await proton.get_libra_voucher_details(since=since)
finally:
    await proton.close()
details
```

You should see a log line like `Loading saved Proton session from data/proton_email/sessions/...`.

## Switching between emails

| Step | Action |
|------|--------|
| 1 | Change `PROTON_EMAIL_ADDRESS_01` and `PROTON_EMAIL_PASSWORD_01` in `.env` |
| 2 | Restart the notebook kernel |
| 3 | If that email has no session file yet, repeat steps 2–4 above |
| 4 | Run the notebook as usual |

Each email keeps its own session file; you only seed once per account (until Proton expires the session or you delete the file).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `make proton-seed-session` says Chrome is not on port 9222 | Quit Chrome (Cmd+Q), run the Step 2 command again — not your regular Chrome |
| Could not connect to Chrome from Docker | Keep the Step 2 Chrome window open, then re-run `make proton-seed-session` |
| Login timeout / CAPTCHA in the notebook | Seed the session for that email; do not use `headless=False` in the notebook |
| Wrong inbox after switching emails | Confirm `.env` matches the account you seeded; check the session filename matches that email |

# The one time code looks like this

Launching browser (headless=True, debug=True)...
Screenshots -> /opt/priceless/data/debug/proton_email
Signing in to Proton...
Screenshot: /opt/priceless/data/debug/proton_email/v03_01_login_page.png
Login page loaded.
Submitting password...
Screenshot: /opt/priceless/data/debug/proton_email/v03_02_authenticated.png
Authenticated at https://account.proton.me/apps
Opening inbox...
On Proton apps page, opening Mail...
Dismissing welcome modal (step 1)...
Dismissing welcome modal (step 2)...
Dismissing welcome modal (step 3)...
Dismissing welcome modal (step 4)...
Inbox URL: https://mail.proton.me/u/0/inbox
Screenshot: /opt/priceless/data/debug/proton_email/v03_03_inbox.png
Looking for "One-time code for Libra X Priceless"...
Waiting for message list...
Message list ready via .item-container:not(.item-is-loading)
Scanning 10 inbox rows for subject match...
Matched email: One-time code for Libra X Priceless
Email body preview: Proton requires Javascript. Enable Javascript and reload this page to continue.
Your one-time code for Libra X Priceless...
Screenshot: /opt/priceless/data/debug/proton_email/v03_04_libra_one_time_code.png
Found code: 974143
LibraOneTimeCode(code='974143', subject='One-time code for Libra X Priceless', received_at='Sunday, 21 June 2026 at 9:27 PM')

# The voucher url and password

Launching browser (headless=True, debug=True)...
Screenshots -> /opt/priceless/data/debug/proton_email
Signing in to Proton...
Screenshot: /opt/priceless/data/debug/proton_email/v15_01_login_page.png
Login page loaded.
Submitting password...
Screenshot: /opt/priceless/data/debug/proton_email/v15_02_authenticated.png
Authenticated at https://account.proton.me/apps
Opening inbox...
On Proton apps page, opening Mail...
Dismissing welcome modal (step 1)...
Dismissing welcome modal (step 2)...
Dismissing welcome modal (step 3)...
Dismissing welcome modal (step 4)...
Inbox URL: https://mail.proton.me/u/1/inbox
Screenshot: /opt/priceless/data/debug/proton_email/v15_03_inbox.png
Looking for "Detalii comand* e-voucher" thread...
Waiting for message list...
Message list ready via .item-container:not(.item-is-loading)
Scanning 10 inbox rows for subject match...
Matched email: Detalii comandă e-voucher
Opened voucher thread: Detalii comandă e-voucher
Reading 3 message(s) one by one...
Expanding all messages in thread...
Found 5 message iframe(s).
Screenshot: /opt/priceless/data/debug/proton_email/v15_04_voucher_msg_01.png
  extracted comanda#=979182 redemption_id=1008541841 code=7714061d-cf10-4303-b6b2-516c1b831204
Skipping duplicate pair in message 1
Screenshot: /opt/priceless/data/debug/proton_email/v15_05_voucher_msg_02.png
  extracted comanda#=979627 redemption_id=1008606220 code=0109a567-298b-4e9e-aa60-1557050ecf87
Skipping duplicate pair in message 2
Screenshot: /opt/priceless/data/debug/proton_email/v15_06_voucher_msg_03.png
  extracted comanda#=979629 redemption_id=1008606250 code=a6b892b7-2570-45c1-9792-6a483e6088fa
Skipping duplicate pair in message 3
Screenshot: /opt/priceless/data/debug/proton_email/v15_07_libra_voucher_details.png
Found 3 voucher message(s).
  1. comanda#=979182 redemption_id=1008541841 comanda_id=979182-1 cantitate=3 puncte=1.290 subtotal=3.870 total=3.870 code=7714061d-cf10-4303-b6b2-516c1b831204
  2. comanda#=979627 redemption_id=1008606220 comanda_id=979627-1 cantitate=3 puncte=1.290 subtotal=3.870 total=3.870 code=0109a567-298b-4e9e-aa60-1557050ecf87
  3. comanda#=979629 redemption_id=1008606250 comanda_id=979629-1 cantitate=1 puncte=221 subtotal=221 total=221 code=a6b892b7-2570-45c1-9792-6a483e6088fa
[LibraVoucherDetail(url='https://rl.rewardcloud.io/index/676c450d-f1d5-4a33-9ff3-302dc6356c90', code='7714061d-cf10-4303-b6b2-516c1b831204', received_at='Sunday, 21 June 2026 at 4:49 AM', comanda_nr='979182', redemption_id='1008541841', comanda_id='979182-1', cantitate='3', puncte='1.290', subtotal='3.870', total='3.870', received_at_dt=datetime.datetime(2026, 6, 21, 4, 49)),
 LibraVoucherDetail(url='https://rl.rewardcloud.io/index/fcd8c15c-30ae-4667-b08c-e33842c65be5', code='0109a567-298b-4e9e-aa60-1557050ecf87', received_at='Sunday, 21 June 2026 at 9:30 PM', comanda_nr='979627', redemption_id='1008606220', comanda_id='979627-1', cantitate='3', puncte='1.290', subtotal='3.870', total='3.870', received_at_dt=datetime.datetime(2026, 6, 21, 21, 30)),
 LibraVoucherDetail(url='https://rl.rewardcloud.io/index/7c85623f-b610-475d-ac35-dd9a8bf64709', code='a6b892b7-2570-45c1-9792-6a483e6088fa', received_at='Sunday, 21 June 2026 at 9:31 PM', comanda_nr='979629', redemption_id='1008606250', comanda_id='979629-1', cantitate='1', puncte='221', subtotal='221', total='221', received_at_dt=datetime.datetime(2026, 6, 21, 21, 31))]