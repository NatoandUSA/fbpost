"""Stealth Evasion & CDP Artifact Neutralizer.

Injects client-side evasion scripts into Playwright browser contexts
to defeat automated browser fingerprinting (Meta Behavioral Radar, Akamai, Cloudflare, DataDome).
"""

from typing import Any

STEALTH_INJECTION_SCRIPT = """
(() => {
    // 1. Defeat navigator.webdriver detection
    try {
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        delete Object.getPrototypeOf(navigator).webdriver;
    } catch (e) {}

    // 2. Mock realistic window.chrome properties
    try {
        if (!window.chrome) {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {
                connect: () => {},
                sendMessage: () => {},
                onMessage: { addListener: () => {} }
            };
        }
        if (!window.chrome.loadTimes) {
            window.chrome.loadTimes = () => ({
                requestTime: performance.now() / 1000,
                startLoadTime: performance.now() / 1000,
                commitLoadTime: performance.now() / 1000,
                finishDocumentLoadTime: performance.now() / 1000,
                firstPaintTime: performance.now() / 1000,
                firstPaintAfterLoadTime: 0,
                navigationType: 'Other',
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true,
                npnNegotiatedProtocol: 'h2',
                wasAlternateProtocolAvailable: false,
                connectionInfo: 'h2'
            });
        }
        if (!window.chrome.csi) {
            window.chrome.csi = () => ({
                startE: Date.now(),
                onloadT: Date.now(),
                pageT: performance.now(),
                tran: 15
            });
        }
    } catch (e) {}

    // 3. Normalize navigator.plugins and mimeTypes
    try {
        const fakePlugins = [
            { name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }
        ];
        Object.defineProperty(navigator, 'plugins', {
            get: () => fakePlugins,
            configurable: true
        });
    } catch (e) {}

    // 4. Normalize Notification and Permissions query
    try {
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    } catch (e) {}

    // 5. Mask WebGL vendor / renderer from SwiftShader
    try {
        const getParameterProto = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            // UNMASKED_VENDOR_WEBGL
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            // UNMASKED_RENDERER_WEBGL
            if (parameter === 37446) {
                return 'Intel(R) Iris(R) Xe Graphics Direct3D11 VS_5_0 PS_5_0';
            }
            return getParameterProto.apply(this, arguments);
        };
    } catch (e) {}
})();
"""


def apply_stealth_scripts(context_or_page: Any) -> bool:
    """
    Apply stealth evasion scripts to a Playwright BrowserContext or Page.
    """
    if not context_or_page:
        return False
    try:
        if hasattr(context_or_page, "add_init_script"):
            context_or_page.add_init_script(STEALTH_INJECTION_SCRIPT)
            return True
        if hasattr(context_or_page, "evaluate"):
            context_or_page.evaluate(STEALTH_INJECTION_SCRIPT)
            return True
        return False
    except Exception:
        return False
