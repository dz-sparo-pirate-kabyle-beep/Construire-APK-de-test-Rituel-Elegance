#!/usr/bin/env python3
"""Prépare le projet Flutter fourni pour la mise à jour Alpha 0.3.0+3.

Paiements Shopify : biens physiques uniquement, après vérification du panier.
Achats de livres numériques : NON activés avant intégration Play Billing.
Ne contient ni clé de signature ni secret Shopify.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent / "extrait" / "rituel_elegance_site_complet_android"
p = root / "lib/main.dart"
text = p.read_text(encoding="utf-8")
text = text.replace("import 'package:flutter/material.dart';",
                    "import 'dart:convert';\n\nimport 'package:flutter/material.dart';", 1)
text = text.replace("if (error.isForMainFrame && mounted)",
                    "if ((error.isForMainFrame ?? false) && mounted)")
text = text.replace("  bool _loadError = false;",
"""  bool _loadError = false;
  bool _checkoutApproved = false;
  bool _checkingCheckout = false;
  Uri? _pendingCheckout;
  int _checkoutRequestId = 0;""", 1)
text = text.replace("    _web = WebViewController()\n      ..setJavaScriptMode",
"""    _web = WebViewController()
      ..addJavaScriptChannel('RituelCheckout', onMessageReceived: _handleCartVerification)
      ..setJavaScriptMode""", 1)
text = text.replace("""        onPageStarted: (_) {
          if (mounted) setState(() => _loadError = false);
        },""",
"""        onPageStarted: (_) {
          if (mounted) setState(() => _loadError = false);
        },
        onPageFinished: (_) => _limitDigitalProductPurchase(),""", 1)

start = text.index("  bool _isPaymentUrl(Uri url) {")
end = text.index("\n  Future<void> _launchExternal", start)
methods = r"""
  bool _isOwnStore(Uri uri) {
    final host = uri.host.toLowerCase();
    return host == 'rituel-elegance.fr' ||
        host == 'www.rituel-elegance.fr' ||
        host == 'rituel-elegance.myshopify.com';
  }

  bool _isCheckoutUrl(Uri uri) {
    final host = uri.host.toLowerCase();
    final path = uri.path.toLowerCase();
    return path.contains('/checkout') || path.contains('/checkouts') ||
        host == 'checkout.shopify.com' || host == 'pay.shopify.com' ||
        host == 'shop.app' || path.contains('/payments/') ||
        path.contains('/payment/');
  }

  bool _isDigitalItem(Map<String, dynamic> item) {
    if (item['requires_shipping'] != true) return true;
    final description = [
      item['title'], item['product_title'], item['product_type'],
      item['handle'], item['product_description'],
    ].whereType<String>().join(' ').toLowerCase();
    return RegExp(r'(ebook|e-book|pdf|numérique|numerique|digital|téléchargeable|telechargeable|livre numérique|guide numérique)')
        .hasMatch(description);
  }

  NavigationDecision _navigationRequest(NavigationRequest request) {
    final uri = Uri.tryParse(request.url);
    if (uri == null) return NavigationDecision.prevent;
    if (uri.scheme == 'mailto' || uri.scheme == 'tel' ||
        uri.scheme == 'whatsapp') {
      _launchExternal(uri);
      return NavigationDecision.prevent;
    }
    if (uri.scheme != 'https') return NavigationDecision.prevent;

    if (_isCheckoutUrl(uri)) {
      if (_checkoutApproved) return NavigationDecision.navigate;
      _verifyCartBeforeCheckout(uri);
      return NavigationDecision.prevent;
    }

    if (_isOwnStore(uri)) {
      if (!uri.path.toLowerCase().contains('/account')) {
        _checkoutApproved = false;
      }
      return NavigationDecision.navigate;
    }

    if (uri.host == 'shopify.com' || uri.host.endsWith('.shopify.com')) {
      return NavigationDecision.navigate;
    }

    if (_checkoutApproved) return NavigationDecision.navigate;
    _launchExternal(uri);
    return NavigationDecision.prevent;
  }

  Future<void> _verifyCartBeforeCheckout(Uri target) async {
    if (_checkingCheckout) return;
    _checkingCheckout = true;
    _pendingCheckout = target;
    final requestId = ++_checkoutRequestId;
    try {
      await _web.runJavaScript(r'''
        (function() {
          const id = REQUEST_ID;
          fetch('/cart.js', {credentials: 'same-origin', cache: 'no-store'})
            .then(function(r) { if (!r.ok) throw Error('cart'); return r.json(); })
            .then(function(cart) { RituelCheckout.postMessage(JSON.stringify({id:id, cart:cart})); })
            .catch(function() { RituelCheckout.postMessage(JSON.stringify({id:id, error:'cart'})); });
        })();
      '''.replaceAll('REQUEST_ID', '$requestId'));
    } catch (_) {
      _checkingCheckout = false;
      _pendingCheckout = null;
      _message('Impossible de vérifier le panier. Réessayez depuis votre panier.');
    }
  }

  Future<void> _handleCartVerification(JavaScriptMessage message) async {
    if (!_checkingCheckout || !mounted) return;
    try {
      final response = jsonDecode(message.message) as Map<String, dynamic>;
      if (response['id'] != _checkoutRequestId) return;
      final cart = response['cart'] as Map<String, dynamic>?;
      final items = cart?['items'] as List<dynamic>? ?? [];
      final allowed = cart != null && items.isNotEmpty &&
          items.every((item) => item is Map<String, dynamic> && !_isDigitalItem(item));
      final target = _pendingCheckout;
      _checkingCheckout = false;
      _pendingCheckout = null;
      if (!allowed || target == null) {
        _message('Paiement réservé aux articles physiques. Retirez les livres numériques du panier.');
        return;
      }
      _checkoutApproved = true;
      await _web.loadRequest(target);
    } catch (_) {
      _checkingCheckout = false;
      _pendingCheckout = null;
      _message('Panier non vérifiable : paiement indisponible pour cette commande.');
    }
  }

  Future<void> _limitDigitalProductPurchase() async {
    try {
      await _web.runJavaScript(r'''
        (function () {
          if (!location.hostname.endsWith('rituel-elegance.fr')) return;
          const match = location.pathname.match(/\/products\/([^/?#]+)/);
          if (!match) return;
          fetch('/products/' + encodeURIComponent(match[1]) + '.js', {credentials:'same-origin'})
            .then(r => r.ok ? r.json() : Promise.reject())
            .then(product => {
              const variants = product.variants || [];
              const tags = (product.tags || []).toString().toLowerCase();
              const title = (product.title || '').toLowerCase();
              const digital = variants.some(v => v.requires_shipping === false) ||
                /ebook|e-book|pdf|numérique|numerique|digital|téléchargeable|telechargeable/.test(title + ' ' + tags);
              if (!digital) return;
              const hide = () => {
                document.querySelectorAll('form[action*="/cart/add"], .shopify-payment-button, button[name="add"], button[name="checkout"]').forEach(el => { el.style.display = 'none'; });
                if (!document.getElementById('rituel-digital-notice')) {
                  const note = document.createElement('p');
                  note.id = 'rituel-digital-notice';
                  note.textContent = 'Livre numérique : achat indisponible dans l’application Android pour le moment.';
                  note.style.cssText = 'padding:12px;background:#fff3da;color:#222;border-radius:6px;margin:12px 0';
                  const h = document.querySelector('main h1') || document.querySelector('h1');
                  if (h) h.insertAdjacentElement('afterend', note);
                }
              };
              hide();
              const observer = new MutationObserver(() => {
                observer.disconnect();
                hide();
                observer.observe(document.body, {childList:true,subtree:true});
              });
              observer.observe(document.body, {childList:true,subtree:true});
            }).catch(() => {});
        })();
      ''');
    } catch (_) {}
  }
"""
text = text[:start] + methods + text[end:]
text = text.replace("""    setState(() => _tab = next);
    final target""", """    setState(() => _tab = next);
    _checkoutApproved = false;
    final target""", 1)
old_banner = """              // Visible reminder: this is a development/closed-test build.
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                color: const Color(0xFFFFF3DA),
                child: const Text(
                  'VERSION DE TEST — paiement désactivé avant validation Google Play',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                ),
              ),"""
new_banner = """              if (_tab == 1)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
                  color: const Color(0xFFFFF3DA),
                  child: const Text(
                    'Livres numériques : catalogue uniquement. Achat indisponible dans l’application.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600),
                  ),
                ),"""
if old_banner not in text:
    raise SystemExit("Le bandeau initial est introuvable")
text = text.replace(old_banner, new_banner, 1)
if "VERSION DE TEST — paiement désactivé" in text:
    raise SystemExit("Le blocage de test n'a pas disparu")
p.write_text(text, encoding="utf-8")
pubspec = root / "pubspec.yaml"
version = pubspec.read_text(encoding="utf-8")
if "version: 0.2.0+2" not in version:
    raise SystemExit("Version initiale inattendue")
pubspec.write_text(version.replace("version: 0.2.0+2", "version: 0.3.0+3"), encoding="utf-8")
print("Mise à jour 0.3.0+3 créée pour", root)
