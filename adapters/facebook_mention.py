"""Facebook Page mention adapter isolated from posting core.

The adapter owns volatile Facebook autocomplete DOM. Posting code only consumes
MentionResult and never knows selectors/ranking details.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List
import re
import time

from composer_guard import page_entity


@dataclass
class MentionResult:
    requested: bool = False
    committed: bool = False
    verified: bool = False
    mode: str = "plain_text"
    reason: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)


def _visible(locator, timeout=200):
    try:
        return locator.is_visible(timeout=timeout)
    except Exception:
        return False


def _is_inside_editor(row, editor):
    try:
        handle = editor.element_handle()
        if not handle:
            return False
        return bool(row.evaluate("(row, editor) => editor.contains(row) || row === editor", handle))
    except Exception:
        return False


def _candidate_rows(page):
    """Autocomplete-owned surfaces only; never scan arbitrary dialogs/tabindex nodes."""
    selectors = (
        "[role='listbox'] [role='option'], "
        "[role='menu'] [role='menuitem'], "
        "[role='listbox'] [role='button'], "
        "[aria-label*='mention' i] [role='option']"
    )
    return page.locator(selectors)


def _rank_candidate(row, entity, editor):
    if not _visible(row) or _is_inside_editor(row, editor):
        return None
    try:
        text = (row.inner_text(timeout=500) or "").strip()
    except Exception:
        text = ""
    if not text or entity["name"].casefold() not in text.casefold():
        return None
    try:
        hrefs = [row.locator("a[href]").nth(i).get_attribute("href") or "" for i in range(min(row.locator("a[href]").count(), 8))]
    except Exception:
        hrefs = []
    href = " ".join(hrefs)
    folded = text.casefold()
    score = 0
    evidence = []
    if entity["handle"].casefold() in href.casefold():
        score += 200; evidence.append("canonical_href")
    # Facebook localized Page type is useful semantic evidence. It must be paired
    # with the exact Page name; plain editor echo '@Name' never receives this score.
    if re.search(r"(?:^|\s)(?:trang|page)(?:\s|$)", folded, re.I):
        score += 90; evidence.append("page_type")
    if re.search(r"(?:người theo dõi|followers?)", folded, re.I):
        score += 35; evidence.append("followers")
    first_line = text.splitlines()[0].strip().lstrip("@").strip().casefold()
    if first_line == entity["name"].casefold():
        score += 40; evidence.append("exact_name")
    # Require semantic Page evidence, not text equality alone.
    if not ({"canonical_href", "page_type"} & set(evidence)):
        return None
    return {"score": score, "text": text, "href": href, "evidence": evidence}


def _semantic_commit_evidence(editor, entity):
    """Verify a Lexical mention without assuming Facebook must expose one tag shape."""
    try:
        anchors = editor.locator("a[href]")
        for i in range(min(anchors.count(), 20)):
            a = anchors.nth(i)
            href = a.get_attribute("href") or ""
            text = (a.inner_text(timeout=300) or "").strip()
            if entity["name"].casefold() in text.casefold() and entity["handle"].casefold() in href.casefold():
                return {"kind": "canonical_anchor", "href": href}
    except Exception:
        pass
    # Lexical/Meta can encode mentions as atomic non-editable spans.
    try:
        atoms = editor.locator("[contenteditable='false'], [data-lexical-text='false'], [data-lexical-decorator='true']")
        matches = []
        for i in range(min(atoms.count(), 30)):
            atom = atoms.nth(i)
            text = (atom.inner_text(timeout=250) or atom.text_content(timeout=250) or "").strip()
            if entity["name"].casefold() in text.casefold():
                matches.append(text)
        if len(matches) == 1:
            return {"kind": "atomic_mention", "text": matches[0]}
    except Exception:
        pass
    return {}


def type_with_page_mention(page, editor, text, brand_key=None, plain_type=None):
    entity = page_entity(brand_key)
    value = str(text or "")
    if not entity:
        plain_type(page, editor, value) if plain_type else editor.fill(value)
        return MentionResult(reason="brand_not_requested")
    match = re.search(re.escape(entity["name"]), value, re.I)
    if not match:
        plain_type(page, editor, value) if plain_type else editor.fill(value)
        return MentionResult(reason="brand_name_not_in_content")
    result = MentionResult(requested=True)
    try:
        editor.fill(""); editor.focus(timeout=2000)
        prefix, suffix = value[:match.start()], value[match.end():]
        page.keyboard.insert_text(prefix)
        page.keyboard.insert_text("@")
        page.keyboard.type(entity["name"], delay=65)
        time.sleep(1.8)
        rows = _candidate_rows(page); ranked: List[Any] = []
        for idx in range(min(rows.count(), 80)):
            info = _rank_candidate(rows.nth(idx), entity, editor)
            if info:
                ranked.append((info["score"], idx, info))
        ranked.sort(key=lambda x: x[0], reverse=True)
        result.evidence["candidates"] = [x[2] for x in ranked[:8]]
        print(f"[MentionAdapter] brand={brand_key} semantic_candidates={len(ranked)}")
        if not ranked:
            raise RuntimeError("NO_SEMANTIC_PAGE_CANDIDATE")
        if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            raise RuntimeError("AMBIGUOUS_PAGE_CANDIDATE")
        rows.nth(ranked[0][1]).click(force=True, timeout=2500)
        time.sleep(0.6)
        commit = _semantic_commit_evidence(editor, entity)
        if not commit:
            raise RuntimeError("PAGE_ENTITY_NOT_COMMITTED")
        result.committed = True
        result.evidence["commit"] = commit
        page.keyboard.insert_text(suffix)
        time.sleep(0.4)
        retained = _semantic_commit_evidence(editor, entity)
        if not retained:
            raise RuntimeError("PAGE_ENTITY_LOST_AFTER_SUFFIX")
        result.verified = True; result.mode = "verified_entity"; result.reason = "VERIFIED_ENTITY"
        print(f"[MentionAdapter] VERIFIED_ENTITY {entity['name']} (@{entity['handle']}) evidence={retained.get('kind')}")
        return result
    except Exception as exc:
        result.reason = f"{type(exc).__name__}:{exc}"
        print(f"[MentionAdapter] PLAIN_TEXT_FALLBACK {entity['name']} reason={result.reason}")
        try: editor.fill("")
        except Exception: pass
        plain_type(page, editor, value) if plain_type else editor.fill(value)
        return result
