# Google Play organization account, with a ZZP

An organization account skips the closed test with 12 testers for 14 days that new personal accounts need. Check this
in the Play Console help when you sign up, as Google changes its rules. Work through the steps in order: every later
step must match the details of the earlier ones exactly.

## 1. Gather your details

Write them down once and copy them everywhere, spelled the same, with the same address format:

| Detail | Where it comes from | Yours |
| --- | --- | --- |
| Legal name (as at the KvK) | KvK extract | |
| Trade name (handelsnaam) | KvK extract | |
| KvK number | KvK extract | |
| Business address | KvK extract | |
| Business phone number | Yours, Google calls or texts it | |
| VAT number (btw-id) | Belastingdienst | |
| Website | | `https://akhibrowser.com` |
| Contact email | | `support@akhibrowser.com` |
| D-U-N-S number | Step 2 | |

Have ready: a recent KvK extract (uittreksel) as a PDF, your passport or ID card, and the bank account of the business.

**Privacy:** the business address and phone number are shown publicly on the Play listing. If your KvK address is your
home, think about a business address (a virtual office) before step 2, and change it at the KvK first.

## 2. D-U-N-S number (free)

Dun & Bradstreet copies KvK records, so your ZZP may already have a D-U-N-S number.

1. Look it up with Apple's free tool, https://developer.apple.com/enroll/duns-lookup/ , or D&B's lookup at
   https://www.dnb.com/duns-number/lookup.html . Search with the legal name and address of the KvK.
2. Found: check that the name and address are exactly the ones in step 1. If they differ, ask D&B to correct them, and
   wait for the change before going on.
3. Not found: request one for free through the same lookup. It takes about 5 working days, sometimes up to 30. Don't
   pay for a faster one.

## 3. Play Console account

1. Use a Google account you'll keep for the business (it can't be moved later). It can be a new Gmail account, or a
   Google account for support@akhibrowser.com.
2. Go to https://play.google.com/console/signup and choose **An organization or business**.
3. Fill in the details of step 1 and the D-U-N-S number. The payments profile has to be an organization profile with the
   same name and address.
4. Developer name (shown under the app on Play): `AkhiBrowser`. It can differ from the legal name.
5. Pay the one-time fee of 25 US dollars.

## 4. Verification

Google checks:

- your identity (passport or ID card)
- the organization: the D-U-N-S record, sometimes the KvK extract
- the phone number and the contact email, with codes
- sometimes the website: verify `akhibrowser.com` in Google Search Console with the same Google account if asked. A
  DNS TXT record at STRATO works for that.

This usually takes a few days. Answer any email from Google quickly, the reviewer may close the request otherwise.

## 5. Payments, for Premium

In the Play Console: **Setup, Payments profile**. Add the business bank account and the VAT number, and fill in the tax
forms (for a Dutch business, no US tax is withheld from sales outside the US). Google collects and pays the VAT on sales to
consumers in the EU. Ask your accountant how this works with the kleineondernemersregeling (KOR) if you use it.

Then create the in-app products listed in `CONSOLE.md`.

## 6. After that

Follow `CONSOLE.md` from **App access** on. Without the closed test you can send the first release straight to
production; an internal test with yourself first is still worth it.

## Checklist

- [ ] Details of step 1 written down, the same everywhere
- [ ] Business address decided (home or a business address)
- [ ] D-U-N-S number found or requested, details match the KvK
- [ ] Play Console organization account created, fee paid
- [ ] Identity, organization, phone and email verified
- [ ] Website verified, if asked
- [ ] Payments profile: bank account, VAT number, tax forms
- [ ] In-app products created (see `CONSOLE.md`)
