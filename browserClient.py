"""
browserClient.py — Browser automation client for the Toingg personal AI assistant.

Connects to the backend WebSocket, receives Playwright-compatible commands from the LLM,
executes them in a real browser, and returns results.

Usage:
    python claudeBot.py --url ws://localhost:8002/api/v3/media/browser/default

Requirements:
    pip install websocket-client playwright playwright-stealth
    playwright install chromium
"""

import argparse
import json
import logging
import os
import random
import sys
import threading
import time
import base64

import websocket
from playwright.sync_api import sync_playwright, Page, Playwright
from upload_store import UploadStore, attach_uploaded_files

# playwright-stealth >= 2.x uses `Stealth`; older 1.x used `stealth_sync`.
try:
    from playwright_stealth import Stealth

    def _apply_stealth(page):
        Stealth().apply_stealth_sync(page)
except ImportError:
    try:
        from playwright_stealth import stealth_sync

        def _apply_stealth(page):
            stealth_sync(page)
    except ImportError:

        def _apply_stealth(page):
            log.warning("playwright-stealth is not installed; continuing without stealth patches")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [BROWSER] %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stealth init script — patches common fingerprint leaks that trigger Google
# ---------------------------------------------------------------------------
STEALTH_INIT_SCRIPT = """
    // Remove webdriver flag
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

    // Spoof plugins (empty in headless = bot signal)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin' },
            { name: 'Chrome PDF Viewer' },
            { name: 'Native Client' }
        ]
    });

    // Realistic language list
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});

    // Chrome object is missing in raw headless
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // Permissions API — headless returns 'denied' for notifications by default
    const _origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
        params.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : _origQuery(params);

    // WebGL vendor/renderer — real values instead of Mesa/llvmpipe
    const getParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return getParam.call(this, param);
    };

    // Hide automation-related properties
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
"""


class BrowserClient:
    def __init__(self, ws_url: str, headless: bool = False, user_data_dir: str | None = None):
        self.ws_url = ws_url
        self.headless = headless
        self.user_data_dir = os.path.expanduser(user_data_dir or ".browser-profile")
        self.ws: websocket.WebSocketApp | None = None
        self.page: Page | None = None
        self.playwright: Playwright | None = None
        self._stop = threading.Event()
        self.upload_store = UploadStore()

    def _select_active_page(self) -> Page | None:
        """Prefer the useful app tab over the initial about:blank page."""
        if self.page is None:
            return None

        try:
            pages = [page for page in self.page.context.pages if not page.is_closed()]
        except Exception:
            return self.page

        if not pages:
            return self.page

        def is_blank(page: Page) -> bool:
            return page.url in ("about:blank", "") or page.url.startswith("chrome://")

        for page in reversed(pages):
            if "elevenlabs" in page.url.lower():
                self.page = page
                return page

        for page in reversed(pages):
            if not is_blank(page):
                self.page = page
                return page

        self.page = pages[-1]
        return self.page

    # ------------------------------------------------------------------
    # Human-like helpers
    # ------------------------------------------------------------------

    def _human_delay(self, min_ms: int = 150, max_ms: int = 600):
        """Sleep for a random duration to mimic human reaction time."""
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def _human_type(self, selector: str, text: str, timeout: int = 10000):
        """Type text character-by-character with randomised delays."""
        page = self.page
        if page is None:
            raise RuntimeError("Browser page not initialised")

        log.info(
            "Human type target: selector=%r page=%s new_len=%s new_preview=%r",
            selector,
            page.url,
            len(text),
            self._preview_text(text),
        )
        page.click(selector, timeout=timeout)
        for char in text:
            page.keyboard.type(char)
            time.sleep(random.uniform(30, 150) / 1000)
        log.info("Human type completed: selector=%r page=%s", selector, page.url)

    # ------------------------------------------------------------------
    # Playwright action dispatch
    # ------------------------------------------------------------------

    @staticmethod
    def _repair_selector(selector: str) -> str:
        """Repair unescaped Tailwind class selectors like button.p-2.5 or button.p-2.5.flex.

        CSS parsers treat 'button.p-2.5' as two classes ('p-2' and '5'), but the Tailwind
        class is a single token 'p-2.5'. This converts each class to [class~="token"] so
        multi-class selectors like 'button.p-2.5.flex' become
        'button[class~="p-2.5"][class~="flex"]' and still match correctly.
        """
        if "," in selector or " " in selector or "[" in selector or "#" in selector:
            return selector
        parts = selector.split(".")
        if len(parts) <= 2:
            return selector
        tag = parts[0]
        if not tag:
            return selector

        # Re-merge decimal suffixes: ["p-2", "5"] → "p-2.5"
        classes: list[str] = []
        for part in parts[1:]:
            if not part:
                continue
            if classes and part.isdigit():
                classes[-1] += "." + part
            else:
                classes.append(part)

        if not classes:
            return selector

        escaped = [c.replace("\\", "\\\\").replace('"', '\\"') for c in classes]
        return tag + "".join(f'[class~="{c}"]' for c in escaped)

    @staticmethod
    def _preview_text(value: str | None, limit: int = 120) -> str:
        """Keep debug logs readable when values or labels are long."""
        if value is None:
            return ""
        normalized = " ".join(str(value).split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 3] + "..."

    def _click_element(self, selector: str, timeout: int, force: bool = False) -> str:
        page = self.page
        if page is None:
            raise RuntimeError("Browser page not initialised")

        target = page.evaluate(
            """selector => {
                const textNeedles = value => {
                    const pattern = /:contains\\((["']?)(.*?)\\1\\)/g;
                    const needles = [];
                    let match;
                    while ((match = pattern.exec(value)) !== null) {
                        needles.push(match[2].toLowerCase());
                    }
                    const hasTextPattern = /:has-text\\((["']?)(.*?)\\1\\)/g;
                    while ((match = hasTextPattern.exec(value)) !== null) {
                        needles.push(match[2].toLowerCase());
                    }
                    const textSelector = value.match(/^text=(.*)$/i);
                    if (textSelector) {
                        needles.push(textSelector[1].replace(/^["']|["']$/g, '').toLowerCase());
                    }
                    const roleName = value.match(/^role=button\\[name=(["']?)(.*?)\\1\\]$/i);
                    if (roleName) {
                        needles.push(roleName[2].toLowerCase());
                    }
                    if (!/[#.[>:,=]/.test(value)) {
                        needles.push(value.replace(/^["']|["']$/g, '').toLowerCase());
                    }
                    return needles;
                };
                const splitSelectorGroup = value => {
                    const parts = [];
                    let current = '';
                    let quote = null;
                    let parenDepth = 0;
                    let bracketDepth = 0;
                    for (const ch of value) {
                        if (quote) {
                            current += ch;
                            if (ch === quote) quote = null;
                            continue;
                        }
                        if (ch === '"' || ch === "'") {
                            quote = ch;
                            current += ch;
                            continue;
                        }
                        if (ch === '(') parenDepth += 1;
                        if (ch === ')') parenDepth = Math.max(0, parenDepth - 1);
                        if (ch === '[') bracketDepth += 1;
                        if (ch === ']') bracketDepth = Math.max(0, bracketDepth - 1);
                        if (ch === ',' && parenDepth === 0 && bracketDepth === 0) {
                            if (current.trim()) parts.push(current.trim());
                            current = '';
                            continue;
                        }
                        current += ch;
                    }
                    if (current.trim()) parts.push(current.trim());
                    return parts;
                };
                const selectorMatches = value => {
                    const textPattern = /:(?:contains|has-text)\\((["']?)(.*?)\\1\\)/;
                    const searchableText = el => [
                        el.innerText,
                        el.textContent,
                        el.value,
                        el.getAttribute('aria-label'),
                        el.getAttribute('data-agent-tooltip'),
                        el.getAttribute('title'),
                        el.getAttribute('data-testid')
                    ].filter(Boolean).join(' ').toLowerCase();
                    const actionable = 'button,[role="button"],a,input[type=button],input[type=submit],[aria-label],[data-agent-tooltip],[data-testid]';
                    const textMatches = needle => Array.from(document.querySelectorAll(actionable))
                        .filter(el => searchableText(el).includes(needle));
                    const visible = el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    };
                    const enabled = el =>
                        !el.disabled &&
                        el.getAttribute('aria-disabled') !== 'true' &&
                        !el.closest('[inert],[aria-hidden="true"]');
                    const promptActionButtons = () => {
                        const active = document.activeElement;
                        const prompt = document.querySelector(
                            '#image-video-prompt-box,[data-placeholder*="prompt" i],textarea,'
                            + '[contenteditable="true"],[role="textbox"],.ProseMirror'
                        );
                        const input = prompt || (active && active !== document.body ? active : null);
                        if (!input) return [];
                        const inputRect = input.getBoundingClientRect();
                        const ancestors = [];
                        let node = input;
                        while (node && node !== document.body && ancestors.length < 8) {
                            ancestors.push(node);
                            node = node.parentElement;
                        }
                        const buttons = Array.from(document.querySelectorAll('button,[role="button"],input[type=button],input[type=submit]'));
                        return buttons.filter(button => {
                            if (!visible(button) || !enabled(button)) return false;
                            const rect = button.getBoundingClientRect();
                            const nearSameRow = rect.left >= inputRect.left - 12 &&
                                rect.left <= inputRect.right + 180 &&
                                rect.top < inputRect.bottom + 40 &&
                                rect.bottom > inputRect.top - 40;
                            const inPromptContainer = ancestors.some(parent => parent !== input && parent.contains(button));
                            return nearSameRow || inPromptContainer;
                        });
                    };
                    const matches = [];
                    for (const part of splitSelectorGroup(value)) {
                        const textSelector = part.match(/^text=(.*)$/i);
                        if (textSelector) {
                            const needle = textSelector[1].replace(/^["']|["']$/g, '').toLowerCase();
                            matches.push(...textMatches(needle));
                            continue;
                        }
                        const roleName = part.match(/^role=button\\[name=(["']?)(.*?)\\1\\]$/i);
                        if (roleName) {
                            matches.push(...textMatches(roleName[2].toLowerCase()));
                            continue;
                        }
                        const contains = part.match(textPattern);
                        const css = contains ? part.replace(textPattern, '') || '*' : part;
                        try {
                            const nodes = Array.from(document.querySelectorAll(css));
                            if (contains) {
                                const needle = contains[2].toLowerCase();
                                matches.push(...nodes.filter(el => searchableText(el).includes(needle)));
                            } else {
                                matches.push(...nodes);
                            }
                        } catch (error) {
                            const fallbackNeedles = textNeedles(part);
                            if (contains || fallbackNeedles.length) {
                                const needles = contains ? [contains[2].toLowerCase()] : fallbackNeedles;
                                for (const needle of needles) matches.push(...textMatches(needle));
                            } else {
                                throw error;
                            }
                        }
                    }
                    if (!matches.length) {
                        for (const needle of textNeedles(value)) matches.push(...textMatches(needle));
                    }
                    if (!matches.length && textNeedles(value).some(needle => /generate|process|submit|create/.test(needle))) {
                        matches.push(...promptActionButtons());
                    }
                    return [...new Set(matches)];
                };
                const needles = textNeedles(selector);
                const visible = el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden' &&
                        style.display !== 'none' &&
                        rect.width > 0 &&
                        rect.height > 0;
                };
                const enabled = el =>
                    !el.disabled &&
                    el.getAttribute('aria-disabled') !== 'true' &&
                    !el.closest('[inert],[aria-hidden="true"]');
                const matches = selectorMatches(selector);
                const labelText = el => [
                    el.innerText,
                    el.textContent,
                    el.value,
                    el.getAttribute('aria-label'),
                    el.getAttribute('data-agent-tooltip'),
                    el.getAttribute('title'),
                    el.getAttribute('data-testid')
                ].filter(Boolean).join(' ').replace(/\\s+/g, ' ').trim().toLowerCase();
                const textScore = el => {
                    const text = labelText(el);
                    if (!needles.length) return 0;
                    if (needles.some(needle => text === needle)) return 40;
                    if (needles.some(needle => text.startsWith(needle))) return 30;
                    if (needles.some(needle => text.includes(needle))) return 20;
                    return 0;
                };
                const activeProximityScore = el => {
                    const active = document.activeElement;
                    const prompt = document.querySelector(
                        '#image-video-prompt-box,[data-placeholder*="prompt" i],textarea,'
                        + '[contenteditable="true"],[role="textbox"],.ProseMirror'
                    );
                    const input = prompt || (active && active !== document.body ? active : null);
                    if (!input) return 0;
                    const activeRect = input.getBoundingClientRect();
                    const rect = el.getBoundingClientRect();
                    const rowOverlap = rect.top < activeRect.bottom + 40 && rect.bottom > activeRect.top - 40;
                    const rightSide = rect.left >= activeRect.left - 12 && rect.left <= activeRect.right + 180;
                    return rowOverlap && rightSide ? 25 : 0;
                };
                const score = el =>
                    (visible(el) ? 100 : 0) +
                    (enabled(el) ? 50 : 0) +
                    textScore(el) +
                    activeProximityScore(el) +
                    (el.type === 'submit' ? 5 : 0);
                const ranked = matches
                    .map((el, index) => ({el, index, score: score(el)}))
                    .sort((a, b) => b.score - a.score || a.index - b.index);
                const el = ranked[0] && ranked[0].el;
                if (!el) return {ok: false, count: 0};
                const markerAttr = 'data-browser-client-click-target';
                const markerValue = String(Date.now()) + '-' + Math.random().toString(36).slice(2);
                document.querySelectorAll(`[${markerAttr}]`).forEach(item => item.removeAttribute(markerAttr));
                el.setAttribute(markerAttr, markerValue);
                const rect = el.getBoundingClientRect();
                return {
                    ok: true,
                    count: matches.length,
                    markerAttr,
                    markerValue,
                    visible: visible(el),
                    enabled: enabled(el),
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    type: el.getAttribute('type') || '',
                    id: el.id || '',
                    className: typeof el.className === 'string' ? el.className : (el.className && el.className.baseVal) || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    testId: el.getAttribute('data-testid') || '',
                    text: labelText(el),
                    rect: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            }""",
            selector,
        )
        if not target.get("ok"):
            raise RuntimeError(f"No element found for {selector}")

        click_selector = f'[{target["markerAttr"]}="{target["markerValue"]}"]'
        locator = page.locator(click_selector).first
        locator.scroll_into_view_if_needed(timeout=timeout)
        box = locator.bounding_box(timeout=timeout)
        log.info(
            "Click target: selector=%r page=%s matches=%s tag=%s role=%s type=%s "
            "visible=%s enabled=%s text=%r aria-label=%r data-testid=%r id=%r class=%r rect=%s",
            selector,
            page.url,
            target.get("count"),
            target.get("tag"),
            target.get("role"),
            target.get("type"),
            target.get("visible"),
            target.get("enabled"),
            self._preview_text(target.get("text")),
            self._preview_text(target.get("ariaLabel")),
            target.get("testId"),
            target.get("id"),
            self._preview_text(target.get("className")),
            target.get("rect"),
        )
        if box and target.get("visible"):
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        else:
            locator.click(timeout=timeout, force=force)
        log.info("Click completed: selector=%r page=%s", selector, page.url)
        detail = f" ({target['count']} matches, selected visible={target['visible']}, text={target.get('text', '')})"
        return f"Clicked '{selector}'{detail}"

    def _fill_field(self, selector: str, value: str, timeout: int) -> str:
        """Fill a field, falling back for hidden proxy inputs used by rich UIs."""
        page = self.page
        if page is None:
            raise RuntimeError("Browser page not initialised")

        page.wait_for_function(
            """selector => {
                const visible = el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden' &&
                        style.display !== 'none' &&
                        rect.width > 0 &&
                        rect.height > 0;
                };
                const hasRequestedTarget = document.querySelector(selector) !== null;
                const hasRichEditor = Array.from(document.querySelectorAll(
                    '[contenteditable],[role="textbox"],.ProseMirror,[data-placeholder],textarea,input:not([type=hidden]),select'
                )).some(visible);
                return hasRequestedTarget || hasRichEditor;
            }""",
            arg=selector,
            timeout=timeout,
        )
        marker_attr = "data-browser-client-fill-target"
        marker_value = str(time.time_ns())
        target = page.evaluate(
            """([selector, markerAttr, markerValue]) => {
                const root = document;
                const matches = Array.from(root.querySelectorAll(selector));
                const isEditable = el =>
                    el instanceof HTMLInputElement ||
                    el instanceof HTMLTextAreaElement ||
                    el instanceof HTMLSelectElement ||
                    (el.hasAttribute('contenteditable') && el.getAttribute('contenteditable') !== 'false') ||
                    el.getAttribute('role') === 'textbox' ||
                    el.classList.contains('ProseMirror') ||
                    el.hasAttribute('data-placeholder');
                const enabled = el =>
                    !el.disabled &&
                    el.getAttribute('readonly') === null &&
                    el.getAttribute('aria-readonly') !== 'true';
                const visible = el => {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    return style.visibility !== 'hidden' &&
                        style.display !== 'none' &&
                        rect.width > 0 &&
                        rect.height > 0;
                };
                const visibleEditors = Array.from(root.querySelectorAll(
                    '[contenteditable],[role="textbox"],.ProseMirror,[data-placeholder],textarea,input:not([type=hidden]),select'
                )).filter(el => isEditable(el) && enabled(el) && visible(el));
                const candidates = [
                    ...matches.filter(el => isEditable(el) && enabled(el) && visible(el)),
                    ...matches.map(el => el.closest('[contenteditable],[role="textbox"],.ProseMirror')).filter(Boolean),
                    ...visibleEditors,
                    ...matches.filter(el => isEditable(el) && enabled(el))
                ].filter(el => enabled(el) && visible(el));
                const el = candidates[0];
                if (!el) return {ok: false};
                root.querySelectorAll(`[${markerAttr}]`).forEach(item => item.removeAttribute(markerAttr));
                el.setAttribute(markerAttr, markerValue);
                const rect = el.getBoundingClientRect();
                const className = typeof el.className === 'string' ? el.className : (el.className && el.className.baseVal) || '';
                const currentValue = el.value || el.innerText || el.textContent || '';
                return {
                    ok: true,
                    target: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    type: el.getAttribute('type') || '',
                    placeholder: el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    id: el.id || '',
                    className,
                    visible: visible(el),
                    currentLength: currentValue.length,
                    currentPreview: currentValue.replace(/\\s+/g, ' ').trim().slice(0, 120),
                    rect: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            }""",
            [selector, marker_attr, marker_value],
        )
        if not target.get("ok"):
            raise RuntimeError(f"No editable element found for {selector}")

        locator = page.locator(f'[{marker_attr}="{marker_value}"]').first
        log.info(
            "Input target: selector=%r page=%s tag=%s role=%s type=%s placeholder=%r "
            "aria-label=%r id=%r class=%r visible=%s rect=%s current_len=%s current_preview=%r new_len=%s new_preview=%r",
            selector,
            page.url,
            target.get("target"),
            target.get("role"),
            target.get("type"),
            self._preview_text(target.get("placeholder")),
            self._preview_text(target.get("ariaLabel")),
            target.get("id"),
            self._preview_text(target.get("className")),
            target.get("visible"),
            target.get("rect"),
            target.get("currentLength"),
            self._preview_text(target.get("currentPreview")),
            len(value),
            self._preview_text(value),
        )

        try:
            locator.fill(value, timeout=timeout)
            log.info("Input completed with locator.fill: selector=%r page=%s", selector, page.url)
            return f"Filled {target['target']} with value"
        except Exception as fill_error:
            log.info("locator.fill failed for selector=%r: %s", selector, fill_error)
            try:
                locator.click(timeout=timeout)
                page.keyboard.press("ControlOrMeta+A")
                page.keyboard.insert_text(value)
                log.info("Input completed with keyboard fallback: selector=%r page=%s", selector, page.url)
                return f"Typed into {target['target']} with keyboard fallback"
            except Exception as keyboard_error:
                log.info(f"Keyboard fill fallback failed: {keyboard_error}")

            fallback = page.evaluate(
                """([selector, value]) => {
                    const root = document;
                    const matches = Array.from(root.querySelectorAll(selector));
                    const isEditable = el =>
                        el instanceof HTMLInputElement ||
                    el instanceof HTMLTextAreaElement ||
                    el instanceof HTMLSelectElement ||
                    (el.hasAttribute('contenteditable') && el.getAttribute('contenteditable') !== 'false') ||
                    el.getAttribute('role') === 'textbox' ||
                    el.classList.contains('ProseMirror') ||
                    el.hasAttribute('data-placeholder');
                    const enabled = el =>
                        !el.disabled &&
                        el.getAttribute('readonly') === null &&
                        el.getAttribute('aria-readonly') !== 'true';
                    const visible = el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    };
                    const visibleEditors = Array.from(root.querySelectorAll(
                        '[contenteditable],[role="textbox"],.ProseMirror,[data-placeholder],textarea,input:not([type=hidden]),select'
                    )).filter(el => isEditable(el) && enabled(el) && visible(el));
                    const candidates = [
                        ...matches.filter(el => isEditable(el) && enabled(el) && visible(el)),
                        ...matches.map(el => el.closest('[contenteditable],[role="textbox"],.ProseMirror')).filter(Boolean),
                        ...visibleEditors,
                        ...matches.filter(el => isEditable(el) && enabled(el))
                    ].filter(el => enabled(el) && visible(el));
                    const el = candidates[0];
                    if (!el) {
                        return {ok: false, error: `No editable element found for ${selector}`};
                    }

                    el.focus();
                    if (
                        el.isContentEditable ||
                        el.hasAttribute('contenteditable') ||
                        el.getAttribute('role') === 'textbox' ||
                        el.classList.contains('ProseMirror') ||
                        el.hasAttribute('data-placeholder')
                    ) {
                        el.textContent = value;
                    } else {
                        const proto = Object.getPrototypeOf(el);
                        const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                        if (descriptor && descriptor.set) {
                            descriptor.set.call(el, value);
                        } else {
                            el.value = value;
                        }
                    }
                    el.dispatchEvent(new InputEvent('input', {
                        bubbles: true,
                        cancelable: true,
                        data: value,
                        inputType: 'insertText'
                    }));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return {ok: true, target: el.tagName.toLowerCase()};
                }""",
                [selector, value],
            )
            if fallback.get("ok"):
                log.info("Input completed with DOM fallback: selector=%r page=%s", selector, page.url)
                return f"Filled '{selector}' with value via {fallback['target']} fallback"
            raise RuntimeError(f"{fill_error}; fallback failed: {fallback.get('error')}")

    def _execute(self, action: str, params: dict) -> dict:
        """Execute a single Playwright action and return a result dict."""
        page = self._select_active_page()
        if page is None:
            return {"success": False, "error": "Browser page not initialised"}

        try:
            if action == "navigate":
                url = params["url"]
                page.goto(url, timeout=params.get("timeout", 30000))
                return {"success": True, "result": f"Navigated to {url}"}

            elif action == "click":
                selector = params["selector"]
                self._human_delay()
                try:
                    result = self._click_element(
                        selector,
                        params.get("timeout", 10000),
                        params.get("force", False),
                    )
                    return {"success": True, "result": result}
                except Exception:
                    repaired = self._repair_selector(selector)
                    if repaired == selector:
                        raise
                    result = self._click_element(
                        repaired,
                        params.get("timeout", 10000),
                        params.get("force", False),
                    )
                    return {"success": True, "result": result}

            elif action == "fill":
                selector = params["selector"]
                value = params["value"]
                if params.get("human_type", False):
                    self._human_type(selector, value, params.get("timeout", 10000))
                    result = f"Typed into '{selector}' with human-like delays"
                else:
                    self._human_delay(100, 400)
                    result = self._fill_field(selector, value, params.get("timeout", 10000))
                return {"success": True, "result": result}

            elif action == "type":
                value = params.get("value", params.get("text", ""))
                selector = params.get("selector")
                log.info(
                    "Type action: selector=%r page=%s clear=%s human_type=%s new_len=%s new_preview=%r",
                    selector,
                    page.url,
                    params.get("clear", False),
                    params.get("human_type", False),
                    len(value),
                    self._preview_text(value),
                )
                if selector:
                    page.click(selector, timeout=params.get("timeout", 10000))
                if params.get("clear", False):
                    page.keyboard.press("ControlOrMeta+A")
                if params.get("human_type", False):
                    for char in value:
                        page.keyboard.type(char)
                        time.sleep(random.uniform(30, 150) / 1000)
                else:
                    page.keyboard.insert_text(value)
                target = f"'{selector}'" if selector else "focused element"
                log.info("Type action completed: target=%s page=%s", target, page.url)
                return {"success": True, "result": f"Typed into {target}"}

            elif action == "get_text":
                selector = params.get("selector")
                max_chars = params.get("max_chars", 3000)
                if selector:
                    text = page.evaluate("""selector => {
                        const el = document.querySelector(selector);
                        return el ? el.innerText || el.textContent || '' : null;
                    }""", selector)
                    if text is None:
                        return {"success": False, "error": f"Selector '{selector}' not found"}
                else:
                    text = page.evaluate("""() => {
                        const clone = document.body.cloneNode(true);
                        clone.querySelectorAll('script,style,noscript,svg').forEach(e => e.remove());
                        return clone.innerText;
                    }""")
                text = " ".join(text.split())[:max_chars]
                return {"success": True, "result": text}

            elif action == "get_input_boxes":
                limit = params.get("limit", 80)
                inputs = page.evaluate("""limit => {
                    const trim = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
                    const className = el => {
                        if (!el.className) return '';
                        if (typeof el.className === 'string') return el.className;
                        return el.className.baseVal || '';
                    };
                    const cssString = value => {
                        if (window.CSS && CSS.escape) return CSS.escape(value);
                        return String(value).replace(/["\\\\]/g, '\\\\$&');
                    };
                    const attrString = value => String(value || '').replace(/["\\\\]/g, '\\\\$&');
                    const classSelector = (tag, token) => {
                        if (/^[A-Za-z_][A-Za-z0-9_-]*$/.test(token)) return tag + '.' + token;
                        return `${tag}[class~="${attrString(token)}"]`;
                    };
                    const visible = el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    };
                    const selectorFor = el => {
                        if (el.getAttribute('aria-label')) return `[aria-label="${cssString(el.getAttribute('aria-label'))}"]`;
                        if (el.id) return '#' + cssString(el.id);
                        if (el.getAttribute('data-agent-id')) return `[data-agent-id="${cssString(el.getAttribute('data-agent-id'))}"]`;
                        if (el.getAttribute('data-agent-role')) return `[data-agent-role="${cssString(el.getAttribute('data-agent-role'))}"]`;
                        if (el.getAttribute('data-testid')) return `[data-testid="${cssString(el.getAttribute('data-testid'))}"]`;
                        if (el.name) return `[name="${cssString(el.name)}"]`;
                        if (el.getAttribute('placeholder')) return `[placeholder="${cssString(el.getAttribute('placeholder'))}"]`;
                        if (el.getAttribute('data-placeholder')) return `[data-placeholder="${cssString(el.getAttribute('data-placeholder'))}"]`;
                        const cls = className(el).trim();
                        if (cls) return classSelector(el.tagName.toLowerCase(), cls.split(/\\s+/)[0]);
                        return el.tagName.toLowerCase();
                    };
                    const rawNodes = [...document.querySelectorAll(
                        'input:not([type=hidden]),textarea,select,[contenteditable],[role="textbox"],.ProseMirror,[data-placeholder]'
                    )];
                    const nodes = rawNodes
                        .map(el => {
                            try {
                                return el.closest('[contenteditable],[role="textbox"],.ProseMirror') || el;
                            } catch (error) {
                                return el;
                            }
                        })
                        .filter((el, index, list) => list.indexOf(el) === index);
                    const results = [];
                    let skipped = 0;
                    for (const el of nodes) {
                        try {
                            if (!visible(el) && !el.getAttribute('data-placeholder') && !el.getAttribute('placeholder')) continue;
                            results.push({
                                selector: selectorFor(el),
                                tag: el.tagName.toLowerCase(),
                                type: el.type || el.getAttribute('role') || (el.isContentEditable ? 'contenteditable' : el.tagName.toLowerCase()),
                                placeholder: trim(el.placeholder || el.getAttribute('data-placeholder')),
                                label: trim(el.getAttribute('aria-label') || el.getAttribute('data-agent-tooltip') || el.getAttribute('title')),
                                value: trim(el.value || el.innerText),
                                visible: visible(el),
                                disabled: Boolean(el.disabled) || el.getAttribute('aria-disabled') === 'true',
                                readonly: el.getAttribute('readonly') !== null || el.getAttribute('aria-readonly') === 'true'
                            });
                            if (results.length >= limit) break;
                        } catch (error) {
                            skipped += 1;
                        }
                    }
                    return {items: results, skipped};
                }""", limit)
                input_items = inputs.get("items", [])
                content = f"INPUT BOXES ({len(input_items)}, skipped={inputs.get('skipped', 0)}):\n"
                for el in input_items:
                    content += (
                        f"  {el['selector']} | tag={el['tag']} | type={el['type']} | "
                        f"placeholder={el['placeholder']} | label={el['label']} | "
                        f"visible={el['visible']} | disabled={el['disabled']} | readonly={el['readonly']}\n"
                    )
                return {"success": True, "result": content}

            elif action == "get_clickable_elements":
                limit = params.get("limit", 150)
                elements = page.evaluate("""limit => {
                    const trim = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
                    const className = el => {
                        if (!el.className) return '';
                        if (typeof el.className === 'string') return el.className;
                        return el.className.baseVal || '';
                    };
                    const cssString = value => {
                        if (window.CSS && CSS.escape) return CSS.escape(value);
                        return String(value).replace(/["\\\\]/g, '\\\\$&');
                    };
                    const attrString = value => String(value || '').replace(/["\\\\]/g, '\\\\$&');
                    const classSelector = (tag, token) => {
                        if (/^[A-Za-z_][A-Za-z0-9_-]*$/.test(token)) return tag + '.' + token;
                        return `${tag}[class~="${attrString(token)}"]`;
                    };
                    const nthPath = el => {
                        const parts = [];
                        let node = el;
                        while (node && node.nodeType === Node.ELEMENT_NODE && node !== document.body && parts.length < 5) {
                            const tag = node.tagName.toLowerCase();
                            if (node.id) {
                                parts.unshift(`#${cssString(node.id)}`);
                                break;
                            }
                            const siblings = Array.from(node.parentElement ? node.parentElement.children : [])
                                .filter(item => item.tagName === node.tagName);
                            const nth = siblings.length > 1 ? `:nth-of-type(${siblings.indexOf(node) + 1})` : '';
                            parts.unshift(`${tag}${nth}`);
                            node = node.parentElement;
                        }
                        return parts.join(' > ') || el.tagName.toLowerCase();
                    };
                    const visible = el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    };
                    const enabled = el =>
                        !el.disabled &&
                        el.getAttribute('aria-disabled') !== 'true' &&
                        !el.closest('[inert],[aria-hidden="true"]');
                    const label = el => trim(
                        el.innerText ||
                        el.value ||
                        el.getAttribute('aria-label') ||
                        el.getAttribute('data-agent-tooltip') ||
                        el.getAttribute('title') ||
                        el.getAttribute('data-testid') ||
                        el.getAttribute('alt') ||
                        (el.querySelector && el.querySelector('svg title') && el.querySelector('svg title').textContent)
                    );
                    const prompt = document.querySelector('#image-video-prompt-box,[data-placeholder*="prompt" i],textarea,[contenteditable="true"],[role="textbox"],.ProseMirror');
                    const active = prompt || (document.activeElement && document.activeElement !== document.body
                        ? document.activeElement
                        : null);
                    const activeRect = active ? active.getBoundingClientRect() : null;
                    const proximity = el => {
                        if (!activeRect) return {nearInput: false, distance: 999999, relation: ''};
                        const rect = el.getBoundingClientRect();
                        const centerX = rect.left + rect.width / 2;
                        const centerY = rect.top + rect.height / 2;
                        const inputCenterX = activeRect.left + activeRect.width / 2;
                        const inputCenterY = activeRect.top + activeRect.height / 2;
                        const distance = Math.round(Math.hypot(centerX - inputCenterX, centerY - inputCenterY));
                        const sameRow = rect.top < activeRect.bottom + 40 && rect.bottom > activeRect.top - 40;
                        const rightSide = rect.left >= activeRect.left - 12 && rect.left <= activeRect.right + 220;
                        const nearInput = (sameRow && rightSide) || distance < 320;
                        const relation = nearInput ? 'near-active-input' : '';
                        return {nearInput, distance, relation};
                    };
                    const surroundingText = el => {
                        const parent = el.closest('form,[role="form"],section,main,div') || el.parentElement;
                        if (!parent) return '';
                        const clone = parent.cloneNode(true);
                        clone.querySelectorAll('script,style,noscript,svg').forEach(item => item.remove());
                        return trim(clone.innerText || clone.textContent || '');
                    };
                    const selectorFor = el => {
                        const text = label(el);
                        const tag = el.tagName.toLowerCase();
                        const role = el.getAttribute('role');
                        if (text && (tag === 'button' || tag === 'input' || role === 'button')) {
                            if (role === 'button' && tag !== 'button') return `[role="button"]:contains("${attrString(text)}")`;
                            return `${tag === 'input' ? 'input' : tag}:contains("${attrString(text)}")`;
                        }
                        if (el.getAttribute('aria-label')) return `[aria-label="${cssString(el.getAttribute('aria-label'))}"]`;
                        if (el.id) return '#' + cssString(el.id);
                        if (el.getAttribute('data-agent-id')) return `[data-agent-id="${cssString(el.getAttribute('data-agent-id'))}"]`;
                        if (el.getAttribute('data-agent-tooltip')) return `[data-agent-tooltip="${cssString(el.getAttribute('data-agent-tooltip'))}"]`;
                        if (el.getAttribute('data-testid')) return `[data-testid="${cssString(el.getAttribute('data-testid'))}"]`;
                        if (el.name) return `[name="${cssString(el.name)}"]`;
                        const cls = className(el).trim();
                        if (cls) return classSelector(el.tagName.toLowerCase(), cls.split(/\\s+/)[0]);
                        return nthPath(el);
                    };
                    const isClickable = el => {
                        const tag = el.tagName.toLowerCase();
                        const role = el.getAttribute('role');
                        return tag === 'button' ||
                            tag === 'a' ||
                            tag === 'summary' ||
                            tag === 'label' ||
                            role === 'button' ||
                            role === 'link' ||
                            role === 'menuitem' ||
                            role === 'tab' ||
                            role === 'radio' ||
                            role === 'checkbox' ||
                            role === 'combobox' ||
                            el.onclick ||
                            el.getAttribute('aria-haspopup') ||
                            el.getAttribute('data-agent-id') ||
                            el.getAttribute('data-agent-tooltip');
                    };
                    const nodes = [...document.querySelectorAll(
                        'button,a[href],summary,label,[role],[aria-label],[aria-haspopup],[data-agent-id],[data-agent-tooltip],[data-testid],[onclick],input[type=button],input[type=submit],input[type=radio],input[type=checkbox]'
                    )].filter((el, index, list) => list.indexOf(el) === index && isClickable(el));
                    return nodes
                        .filter(el => visible(el) || label(el) || proximity(el).nearInput)
                        .sort((a, b) => Number(proximity(b).nearInput) - Number(proximity(a).nearInput) ||
                            Number(visible(b)) - Number(visible(a)) ||
                            proximity(a).distance - proximity(b).distance)
                        .slice(0, limit)
                        .map(el => {
                            const rect = el.getBoundingClientRect();
                            const near = proximity(el);
                            return {
                                selector: selectorFor(el),
                                tag: el.tagName.toLowerCase(),
                                role: el.getAttribute('role') || '',
                                type: el.getAttribute('type') || '',
                                text: label(el),
                                context: surroundingText(el),
                                href: el.href || '',
                                visible: visible(el),
                                disabled: !enabled(el),
                                expanded: el.getAttribute('aria-expanded') || '',
                                checked: el.getAttribute('aria-checked') || '',
                                nearInput: near.nearInput,
                                relation: near.relation,
                                distance: near.distance,
                                rect: `${Math.round(rect.x)},${Math.round(rect.y)},${Math.round(rect.width)}x${Math.round(rect.height)}`
                            };
                        });
                }""", limit)
                content = f"CLICKABLE ELEMENTS ({len(elements)}):\n"
                for el in elements:
                    content += (
                        f"  {el['selector']} | tag={el['tag']} | role={el['role']} | "
                        f"type={el['type']} | text={el['text']} | visible={el['visible']} | "
                        f"disabled={el['disabled']} | rect={el['rect']}"
                    )
                    if el["relation"]:
                        content += f" | relation={el['relation']} | distance={el['distance']}"
                    if el["context"] and el["context"] != el["text"]:
                        content += f" | context={el['context']}"
                    if el["href"]:
                        content += f" | href={el['href']}"
                    if el["expanded"]:
                        content += f" | expanded={el['expanded']}"
                    if el["checked"]:
                        content += f" | checked={el['checked']}"
                    content += "\n"
                log.info("Clickable elements on %s:\n%s", page.url, content.rstrip())
                return {"success": True, "result": content}

            elif action == "screenshot":
                path = params.get("path")
                if path:
                    page.screenshot(path=path, full_page=params.get("full_page", False))
                    return {"success": True, "result": f"Screenshot saved to {path}"}
                else:
                    img_bytes = page.screenshot(full_page=params.get("full_page", False))
                    encoded = base64.b64encode(img_bytes).decode()
                    return {"success": True, "result": f"data:image/png;base64,{encoded[:100]}... (truncated)"}

            elif action == "evaluate":
                expression = params["expression"]
                result = page.evaluate(expression)
                return {"success": True, "result": str(result)}

            elif action == "wait_for_selector":
                selector = params["selector"]
                state = params.get("state", "visible")
                page.wait_for_selector(selector, state=state, timeout=params.get("timeout", 30000))
                return {"success": True, "result": f"Selector '{selector}' is {state}"}

            elif action == "press":
                selector = params["selector"]
                key = params["key"]
                self._human_delay(80, 250)
                page.press(selector, key)
                return {"success": True, "result": f"Pressed '{key}' on '{selector}'"}

            elif action == "select":
                selector = params["selector"]
                value = params["value"]
                self._human_delay()
                page.select_option(selector, value)
                return {"success": True, "result": f"Selected '{value}' in '{selector}'"}

            elif action in ("input_file", "set_input_files"):
                selector = params["selector"]
                tokens = params.get("tokens")
                if tokens is None:
                    token = params.get("token")
                    tokens = [token] if token else []
                count = attach_uploaded_files(
                    page,
                    self.upload_store,
                    selector,
                    tokens,
                    params.get("timeout", 10000),
                )
                return {
                    "success": True,
                    "result": f"Attached {count} uploaded file(s) to '{selector}'",
                }

            elif action == "scroll":
                x = params.get("x", 0)
                y = params.get("y", 0)
                self._human_delay(80, 300)
                page.evaluate(f"window.scrollBy({x}, {y})")
                return {"success": True, "result": f"Scrolled by ({x}, {y})"}

            elif action == "hover":
                selector = params["selector"]
                self._human_delay()
                page.hover(selector, timeout=params.get("timeout", 10000))
                return {"success": True, "result": f"Hovered over '{selector}'"}

            elif action == "get_url":
                return {"success": True, "result": page.url}

            elif action == "go_back":
                page.go_back(timeout=params.get("timeout", 10000))
                return {"success": True, "result": "Navigated back"}

            elif action == "go_forward":
                page.go_forward(timeout=params.get("timeout", 10000))
                return {"success": True, "result": "Navigated forward"}

            elif action == "reload":
                page.reload(timeout=params.get("timeout", 30000))
                return {"success": True, "result": "Page reloaded"}

            elif action == "get_page_content":
                title = page.title()
                url = page.url
                elements = page.evaluate("""() => {
                    const trim = s => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 120);
                    const className = el => {
                        if (!el.className) return '';
                        if (typeof el.className === 'string') return el.className;
                        return el.className.baseVal || '';
                    };
                    const cssString = value => {
                        if (window.CSS && CSS.escape) return CSS.escape(value);
                        return String(value).replace(/["\\\\]/g, '\\\\$&');
                    };
                    const attrString = value => String(value || '').replace(/["\\\\]/g, '\\\\$&');
                    const classSelector = (tag, token) => {
                        if (/^[A-Za-z_][A-Za-z0-9_-]*$/.test(token)) return tag + '.' + token;
                        return `${tag}[class~="${attrString(token)}"]`;
                    };
                    const visible = el => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            rect.width > 0 &&
                            rect.height > 0;
                    };
                    const label = el => trim(
                        el.innerText ||
                        el.value ||
                        el.getAttribute('aria-label') ||
                        el.getAttribute('data-agent-tooltip') ||
                        el.getAttribute('title')
                    );
                    const sel = el => {
                        const text = label(el);
                        const tag = el.tagName.toLowerCase();
                        const role = el.getAttribute('role');
                        if (text && (tag === 'button' || tag === 'input' || role === 'button')) {
                            if (role === 'button' && tag !== 'button') return `[role="button"]:contains("${attrString(text)}")`;
                            return `${tag === 'input' ? 'input' : tag}:contains("${attrString(text)}")`;
                        }
                        if (el.getAttribute('aria-label')) return `[aria-label="${cssString(el.getAttribute('aria-label'))}"]`;
                        if (el.getAttribute('data-agent-id')) return `[data-agent-id="${cssString(el.getAttribute('data-agent-id'))}"]`;
                        if (el.getAttribute('data-agent-tooltip')) return `[data-agent-tooltip="${cssString(el.getAttribute('data-agent-tooltip'))}"]`;
                        if (el.id) return '#' + cssString(el.id);
                        if (el.getAttribute('data-testid')) return `[data-testid="${cssString(el.getAttribute('data-testid'))}"]`;
                        if (el.name) return `[name="${cssString(el.name)}"]`;
                        if (el.getAttribute('placeholder')) return `[placeholder="${cssString(el.getAttribute('placeholder'))}"]`;
                        if (el.getAttribute('data-placeholder')) return `[data-placeholder="${cssString(el.getAttribute('data-placeholder'))}"]`;
                        const cls = className(el).trim();
                        if (cls) return classSelector(el.tagName.toLowerCase(), cls.split(/\\s+/)[0]);
                        return el.tagName.toLowerCase();
                    };
                    const inputNodes = [...document.querySelectorAll(
                        'input:not([type=hidden]),textarea,select,[contenteditable],[role="textbox"],.ProseMirror,[data-placeholder]'
                    )].filter((el, index, list) => list.indexOf(el) === index && (visible(el) || label(el) || el.getAttribute('data-placeholder')));
                    const inputs = inputNodes.slice(0,60).map(el => ({
                        selector: sel(el),
                        type: el.type || el.getAttribute('role') || (el.isContentEditable ? 'contenteditable' : el.tagName.toLowerCase()),
                        placeholder: trim(el.placeholder || el.getAttribute('data-placeholder')),
                        value: trim(el.value || el.innerText),
                        label: trim(el.getAttribute('aria-label') || el.getAttribute('data-agent-tooltip'))
                    }));
                    const buttonNodes = [...document.querySelectorAll(
                        'button,[role=button],input[type=submit],input[type=button],a[href],[aria-label],[data-agent-tooltip],[data-agent-id]'
                    )].filter(el => {
                        const tag = el.tagName.toLowerCase();
                        return tag !== 'svg' && (visible(el) || label(el));
                    });
                    const buttons = buttonNodes
                        .sort((a, b) => Number(visible(b)) - Number(visible(a)))
                        .slice(0,100)
                        .map(el => ({
                            selector: sel(el),
                            text: label(el),
                            visible: visible(el)
                        }));
                    const links = [...document.querySelectorAll('a[href]')].slice(0,15).map(el => ({
                        selector: sel(el), text: trim(el.innerText), href: el.href
                    }));
                    return {inputs, buttons, links};
                }""")
                content = f"Page: {title}\nURL: {url}\n"
                content += f"\nINPUTS ({len(elements['inputs'])}):\n"
                for el in elements["inputs"]:
                    content += f"  {el['selector']} | type={el['type']} | placeholder={el['placeholder']} | label={el['label']}\n"
                content += f"\nBUTTONS/CLICKABLE ({len(elements['buttons'])}):\n"
                for el in elements["buttons"]:
                    content += f"  {el['selector']} | text={el['text']}\n"
                content += f"\nLINKS ({len(elements['links'])}):\n"
                for el in elements["links"]:
                    content += f"  {el['text']} -> {el['href']}\n"
                return {"success": True, "result": content}

            else:
                return {"success": False, "error": f"Unknown action: {action}"}

        except Exception as e:
            log.error(f"Action '{action}' failed: {e}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------

    def _on_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
            log.debug("Received: %s", msg)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "connected":
            log.info(f"Connected to backend — session: {msg.get('session_id')}")

        elif msg_type == "command":
            command_id = msg.get("command_id")
            action = msg.get("action")
            params = msg.get("params", {})
            log.info(f"Received command '{action}' (id={command_id})")

            if action == "batch":
                # Execute a list of actions sequentially and return combined results
                steps = params.get("actions", [])
                results = []
                for step in steps:
                    step_action = step.get("action")
                    step_params = {k: v for k, v in step.items() if k != "action"}
                    log.info(f"Batch step: {step_action}")
                    r = self._execute(step_action, step_params)
                    results.append({"action": step_action, "success": r.get("success"), "result": r.get("result", r.get("error", ""))})
                    if not r.get("success"):
                        break  # stop on first failure
                result = {
                    "type": "result",
                    "command_id": command_id,
                    "success": all(r["success"] for r in results),
                    "result": "\n".join(f"[{r['action']}] {r['result']}" for r in results)
                }
            else:
                result = self._execute(action, params)
                result["type"] = "result"
                result["command_id"] = command_id

            ws.send(json.dumps(result))
            log.info(f"Sent result for '{action}': success={result['success']}")

        elif msg_type == "ping":
            ws.send(json.dumps({"type": "pong"}))

    def _on_error(self, ws, error):
        log.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        log.info(f"WebSocket closed: {close_status_code} {close_msg}")

    def _on_open(self, ws):
        log.info(f"WebSocket opened: {self.ws_url}")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        with sync_playwright() as pw:
            self.playwright = pw
            context = pw.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    # NOTE: --disable-blink-features=AutomationControlled is intentionally
                    # omitted — the flag itself is a bot signal; stealth patches handle this.
                ],
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
                color_scheme="light",
                device_scale_factor=1,
                has_touch=False,
                java_script_enabled=True,
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                },
            )
            context.add_init_script(STEALTH_INIT_SCRIPT)
            self.page = context.pages[0] if context.pages else context.new_page()
            _apply_stealth(self.page)
            log.info(f"Browser launched (headless={self.headless}, profile={self.user_data_dir})")

            # Keep reconnecting until stopped
            while not self._stop.is_set():
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self.ws.run_forever(ping_interval=20, ping_timeout=10)

                if not self._stop.is_set():
                    log.info("Reconnecting in 3 seconds...")
                    time.sleep(3)

            context.close()
            log.info("Browser closed")


def main():
    parser = argparse.ArgumentParser(description="Toingg browser automation client")
    parser.add_argument(
        "--url",
        default="wss://prepodapi.toingg.com/api/v3/media/browser/default",
        help="Backend WebSocket URL (default: ws://localhost:8002/api/v3/media/browser/default)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (no visible window)",
    )
    parser.add_argument(
        "--user-data-dir",
        default=".browser-profile",
        help="Persistent browser profile directory for cookies and login sessions",
    )
    args = parser.parse_args()

    client = BrowserClient(ws_url=args.url, headless=args.headless, user_data_dir=args.user_data_dir)
    try:
        client.run()
    except KeyboardInterrupt:
        log.info("Stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
