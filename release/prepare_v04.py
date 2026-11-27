#!/usr/bin/env python3
"""Prepare AdMob version 0.4.0+4 from the generated 0.3.0+3 Flutter project."""
from pathlib import Path
root = Path(__file__).resolve().parent.parent / "extrait" / "rituel_elegance_site_complet_android"
main = root / "lib/main.dart"
pubspec = root / "pubspec.yaml"
manifest = root / "android/app/src/main/AndroidManifest.xml"

source = main.read_text(encoding="utf-8")
assert "version: 0.3.0+3" in pubspec.read_text(encoding="utf-8")
assert "import 'package:google_mobile_ads/google_mobile_ads.dart';" not in source
source = source.replace("import 'package:flutter/material.dart';", "import 'package:flutter/material.dart';\nimport 'package:google_mobile_ads/google_mobile_ads.dart';", 1)
marker = "const black = Color(0xFF161412);"
assert marker in source
source = source.replace(marker, marker + """

// Real ads are DISABLED in closed testing. Enable only in an approved build
// with --dart-define=RITUEL_LIVE_ADS=true after privacy and payment review.
const bool useLiveAds = bool.fromEnvironment('RITUEL_LIVE_ADS', defaultValue: false);
const String testBannerId = 'ca-app-pub-3940256099942544/9214589741';
const String liveBannerId = 'ca-app-pub-1247287523375640/5461454393';
""", 1)
needle = "  int _checkoutRequestId = 0;"
assert needle in source
source = source.replace(needle, needle + """
  BannerAd? _bannerAd;
  bool _adsInitialized = false;
  bool _privacyOptionsRequired = false;
  bool _sensitivePage = false;
  bool _bannerLoading = false;
""", 1)
needle = "    super.initState();\n    _web = WebViewController()"
assert needle in source
source = source.replace(needle, "    super.initState();\n    _prepareConsentAndAds();\n    _web = WebViewController()", 1)
needle = """        onPageStarted: (_) {
          if (mounted) setState(() => _loadError = false);
        },"""
assert needle in source
source = source.replace(needle, """        onPageStarted: (url) {
          final uri = Uri.tryParse(url);
          if (mounted) setState(() {
            _loadError = false;
            _sensitivePage = uri == null ||
                _isCheckoutUrl(uri) ||
                uri.path.toLowerCase().contains('/cart') ||
                uri.path.toLowerCase().contains('/account') ||
                uri.host != Uri.parse(site).host;
          });
        },""", 1)
needle = "  bool _isOwnStore(Uri uri) {"
assert needle in source
methods = r"""
  void _prepareConsentAndAds() {
    // UMP refresh at every launch. Request ads only when canRequestAds is true.
    ConsentInformation.instance.requestConsentInfoUpdate(
      ConsentRequestParameters(),
      () async {
        try {
          final required = await ConsentInformation.instance
              .getPrivacyOptionsRequirementStatus() ==
              PrivacyOptionsRequirementStatus.required;
          if (mounted) setState(() => _privacyOptionsRequired = required);
          ConsentForm.loadAndShowConsentFormIfRequired((formError) async {
            await _loadAdsIfAllowed();
          });
          await _loadAdsIfAllowed();
        } catch (_) {
          // Keep the store available even if the consent service fails.
        }
      },
      (error) async => _loadAdsIfAllowed(),
    );
  }

  Future<void> _loadAdsIfAllowed() async {
    if (!mounted || _adsInitialized) return;
    try {
      if (!await ConsentInformation.instance.canRequestAds()) return;
      _adsInitialized = true;
      await MobileAds.instance.initialize();
      if (mounted) await _loadBanner();
    } catch (_) {}
  }

  Future<void> _loadBanner() async {
    if (!mounted || _bannerAd != null || _bannerLoading) return;
    _bannerLoading = true;
    try {
      final width = (MediaQuery.sizeOf(context).width - 32).truncate();
      if (width < 200) return;
      final size = await AdSize.getLargeAnchoredAdaptiveBannerAdSize(width);
      if (!mounted || size == null) return;
      final ad = BannerAd(
        adUnitId: useLiveAds ? liveBannerId : testBannerId,
        request: const AdRequest(),
        size: size,
        listener: BannerAdListener(
          onAdLoaded: (ad) {
            if (!mounted) { ad.dispose(); return; }
            setState(() => _bannerAd = ad as BannerAd);
          },
          onAdFailedToLoad: (ad, error) {
            ad.dispose();
            _bannerLoading = false;
          },
        ),
      );
      await ad.load();
    } catch (_) {
      // Optional ads must never block shopping.
    } finally {
      _bannerLoading = false;
    }
  }

  @override
  void dispose() {
    _bannerAd?.dispose();
    super.dispose();
  }

"""
source = source.replace(needle, methods + needle, 1)
needle = """                onSelected: (value) => _web.loadRequest(Uri.parse('$site$value')),
                itemBuilder: (context) => const ["""
assert needle in source
source = source.replace(needle, """                onSelected: (value) {
                  if (value == '__ad_privacy') {
                    ConsentForm.showPrivacyOptionsForm((error) {});
                  } else {
                    _web.loadRequest(Uri.parse('$site$value'));
                  }
                },
                itemBuilder: (context) => [
                  if (_privacyOptionsRequired)
                    const PopupMenuItem(value: '__ad_privacy', child: Text('Choix publicitaires')),""", 1)
needle = """              if (_progress < 100) LinearProgressIndicator(value: _progress / 100),
              Expanded("""
assert needle in source
source = source.replace(needle, """              if (_progress < 100) LinearProgressIndicator(value: _progress / 100),
              // Fixed banner, separate from navigation and checkout controls.
              if (_bannerAd != null && !_sensitivePage && _tab != 2)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 18),
                  decoration: const BoxDecoration(
                    color: Color(0xFFFAFAFA),
                    border: Border(bottom: BorderSide(color: Color(0xFFE5E5E5))),
                  ),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Text('Publicité', style: TextStyle(
                      fontSize: 10, color: Color(0xFF777777))),
                    const SizedBox(height: 6),
                    SizedBox(
                      width: _bannerAd!.size.width.toDouble(),
                      height: _bannerAd!.size.height.toDouble(),
                      child: AdWidget(ad: _bannerAd!),
                    ),
                  ]),
                ),
              Expanded(""", 1)
main.write_text(source, encoding="utf-8")

s = pubspec.read_text(encoding="utf-8")
assert "version: 0.3.0+3" in s and "google_mobile_ads:" not in s
s = s.replace("version: 0.3.0+3", "version: 0.4.0+4", 1)
s = s.replace("  webview_flutter: ^4.13.0", "  google_mobile_ads: ^9.2.0\n  webview_flutter: ^4.13.0", 1)
pubspec.write_text(s, encoding="utf-8")

m = manifest.read_text(encoding="utf-8")
assert "com.google.android.gms.ads.APPLICATION_ID" not in m
idx = m.index(">", m.index("<application")) + 1
m = m[:idx] + """
        <meta-data android:name="com.google.android.gms.ads.APPLICATION_ID"
                   android:value="ca-app-pub-1247287523375640~8275319994"/>
""" + m[idx:]
manifest.write_text(m, encoding="utf-8")
print("0.4.0+4: AdMob + UMP installed. Test ads enabled; live ads disabled.")
