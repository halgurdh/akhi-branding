# Google Play Console: what to fill in

For the build made by `tools/build_play.py`. Upload the `.aab`, never the APK: Play doesn't accept APKs for new apps.

## Before the first upload

1. **Account type.** A personal developer account created after 13 November 2023 needs a closed test with at least 12
   testers, opted in for 14 days in a row, before it can apply for production. Start this early.
2. **Signing.** Choose Play App Signing. Decide this once, as it can't be undone:
   - Let Google create the signing key, and use your key as the upload key. Simplest, but Android then treats the Play
     build and the GitHub APK as different signers: moving between them means uninstalling, which loses the user's data.
   - Or give Google your own `akhibrowser-release.jks` (the Console's "Export and upload a key from Java keystore"). Both
     builds then share a signer, but Google holds a copy of that key.
3. **Privacy policy.** Commit and push `PRIVACY.md`. Its URL is
   `https://github.com/halgurdh/akhiBrowser/blob/main/PRIVACY.md`.
4. **In-app products**, with exactly these ids, or buying fails (see `AkhiStore.kt`). The prices are the website's:
   - Subscription `akhi_premium` with base plans `monthly` (€3.99) and `yearly` (€39.00)
   - Subscription `akhi_family` with base plan `family` (€59.99, renews every year), with two offers:
     - `trial`: eligibility "New customer acquisition", a 3-day free trial
     - `vip`: eligibility "Developer determined", 10% off (€53.99), recurring for as long as the Console allows. The app
       buys it only for users who installed from a VIP's link (`referrer=ref%3D<code>`)
     - Turn on family sharing for it if the Console offers it, so children with their own Google account get Family too
   - One-time product `akhi_premium_lifetime` (€119)
   - One-time product `akhi_family_year` (€59.99): a year of Family, never offered in the app, only given with promo codes
     (gifts on the license server's `/redeem`, schools' `/school`)
   - One-time product `akhi_family_gift` (€59.99): "Give Family Premium" in the app; the app consumes it once the server
     gave its code
5. **License server access** (keys for Play buyers, gifts, school codes, VIP commission): in Google Cloud, enable the
   "Google Play Android Developer API", create a service account and a JSON key. In Users and permissions, invite its
   email for AkhiBrowser with "View financial data, orders, and cancellation survey responses". It can take up to a day
   to work. Then `npx wrangler secret put PLAY_SERVICE_ACCOUNT` in `akhibrowser-premium/server`, and deploy.
6. **Promo codes**, each quarter (500 one-time codes a quarter, unused ones end with it): Monetize with Play, Promo codes,
   for `akhi_family_year`. Download the CSV and load it: see "Google Play" in `akhibrowser-premium/server/README.md`.

## App access

Say that everything is available without an account. Premium needs a purchase: add the reviewer's account as a license
tester, or the reviewer can't reach it.

## Content rating

Answer the questionnaire as a web browser: it gives access to unrestricted web content. Don't call it safe for children,
as the filters can miss things.

## Target audience

18 and over. Choosing ages under 13 puts the app under the Families policy, which a general browser can't meet.

## Ads

No ads. Advertising ID: **No**. The permission is removed from this build. The Adjust SDK is still linked but never starts
without a token, and the build has none. If you add `.adjust_token`, this answer and the data safety form become false.

## Permissions declaration form

`QUERY_ALL_PACKAGES`, core use "Web browser":

> AkhiBrowser is a web browser. When the user follows a link, it has to find which installed apps can open that link, so it
> can offer to open it there, and which app can handle a downloaded file or a share. Any installed app can declare such
> links, so they can't be listed in advance. The list is used on the device only and is not sent anywhere.

`REQUEST_INSTALL_PACKAGES` is removed from this build, so there is no form. A downloaded APK can't be installed from the
app.

## Foreground services

| Permission | Used for | User sees |
| --- | --- | --- |
| `FOREGROUND_SERVICE_DATA_SYNC` | Downloading files the user started | Download notification with progress |
| `FOREGROUND_SERVICE_MEDIA_PLAYBACK` | Keeping a web video or audio playing, with controls, when the app is in the background | Media notification |
| `FOREGROUND_SERVICE_SPECIAL_USE` | A notification to close private tabs at once; showing the crash report prompt after a crash; a profiler for developers, off unless turned on | Notification |

Google asks for a short video of each: record the download, the media notification and the private tabs notification.

## Data safety

| Data | Collected | Shared | Purpose | Optional |
| --- | --- | --- | --- | --- |
| Web browsing history (site names, to Cloudflare's DNS) | Yes | No, service provider | App functionality, security | Yes, can be turned off |
| Email address (only with Sync, to Mozilla) | Yes | No | Account management | Yes |
| Crash logs, diagnostics (only if turned on, to Mozilla) | Yes | No | Analytics, stability | Yes |

- Encrypted in transit: yes.
- Way to request deletion: there is no AkhiBrowser account or data held by the developer. Sync data is deleted in the
  Mozilla account.
- Camera, microphone and location go only to the site the user allows them for, at the user's request. **Check this
  against Google's current form:** Claude reasoned that this isn't collection by the app, but this isn't legal advice.
- Purchases are handled by Google Play. **Check Google's guidance on the Play Billing library when answering.**

## Listing

Name (30 max): `AkhiBrowser: Halal Web Browser`

Contact details: email `support@akhibrowser.com`, website `https://akhibrowser.com`. Category: Communication (where
Play lists browsers).

Short description (80 max):

> A private browser for Muslims: blocks adult sites, blurs images, removes music.

Full description:

> AkhiBrowser is a web browser that follows your values. Its checks run on your device, and your history and pages stay
> there.
>
> - Blocks ads and trackers, with uBlock Origin in the browser
> - Blocks adult, alcohol, drugs, vaping and gambling sites, and searches for them, and turns on SafeSearch
> - Blurs images until an on-device model has checked them. Nudity is blurred, and by default so are images of women. You
>   choose who is blurred: women, men or both
> - Removes background music from videos and keeps the voices, on your device
> - 12 languages, including Arabic, Persian, Kurdish, Urdu and Turkish
>
> Each protection can be turned off in the menu, under Extensions, AkhiBrowser.
>
> Premium (optional, paid through Google Play, monthly, yearly or lifetime; each feature off until you turn it on):
>
> - Recognize hijab: a woman who is covered is shown instead of blurred
> - Parental PIN: locks the protections so they can't be turned off
> - Block chosen sites
> - Allow only approved sites
> - Time limits, with bedtime and school hours
> - Activity summary of blocked pages, without their addresses
> - Feed limit: hides short video feeds and stops social media websites in AkhiBrowser after a daily time
>
> Parent controls and the feed limit stay on the device. The feed limit works on websites in AkhiBrowser, not in other
> apps.
>
> Filters can miss things, and can't replace a parent's care.
>
> AkhiBrowser is built on Firefox, and is not made or endorsed by Mozilla. To block adult sites, it looks up site names
> through Cloudflare's family DNS.

Rules for this text and the graphics:

- Don't use "Firefox" or Mozilla's logos in the name, the icon or the screenshots, and keep the sentence above saying it
  isn't made by Mozilla.
- Don't name YouTube or other services as sites where ads are blocked, or show their logos.
- The feed limit: say it works on websites in AkhiBrowser, never that it blocks the YouTube, Instagram or TikTok apps.
  It uses no Accessibility service and no usage access, so there is no form for them; keep it that way.
- Don't use words like "best" or "#1", or promise that nothing gets through.
- Screenshots: use plain pages and never show an unblurred image of the kind being filtered. Needed: icon 512x512, feature
  graphic 1024x500, at least 2 phone screenshots.

## After each upload

- Read the pre-launch report for crashes on real devices.
- `versionCode` comes from the build time, so each build is higher. Don't re-upload an old build.
- Set the same new version in `browser/config/akhi_version.txt` and `CURRENT_VERSION` in `lib/updates.js` first.
